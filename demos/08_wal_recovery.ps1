$ErrorActionPreference = 'Stop'

Write-Host ''
Write-Host '=================================================' -ForegroundColor Cyan
Write-Host ' WAL CRASH RECOVERY DEMO - kill -9 mid-flight' -ForegroundColor Cyan
Write-Host '=================================================' -ForegroundColor Cyan

Write-Host '-> producing 5 messages and acknowledging them (committed, durable state)...'
$baseline = @'
import sys
sys.path.insert(0, "/app/demos")
from _common import fixtures, new_admin, new_client
admin = new_admin()
fx = fixtures(admin, "d8", schema={"required": ["event"]})
c = new_client(fx)
c.produce_batch(fx["topic"], [{"payload": {"event": "wal", "n": i}} for i in range(5)], seq_start=1)
msgs = c.consume(fx["group"], fx["topic"], 5, 60)
c.ack(fx["group"], [m["location"] for m in msgs])
print(f"TOPIC={fx['topic']}")
print(f"APPKEY={fx['app']['api_key']}")
c.close()
admin.close()
'@ | docker compose exec -T api python -

$topic = ($baseline | Select-String '^TOPIC=').ToString().Substring(6).Trim()
$appkey = ($baseline | Select-String '^APPKEY=').ToString().Substring(7).Trim()
Write-Host "   topic under test: $topic"
Write-Host '   state on disk: 5 delivered messages + committed group offsets (in the WAL)'

Write-Host '-> SIMULATING POWER LOSS: docker kill conduit-db (SIGKILL, no checkpoint)' -ForegroundColor Yellow
docker kill conduit-db | Out-Null
Write-Host '   the database is dead. everything acknowledged exists only in the WAL on disk.'

Write-Host '-> restarting the database container (same volume)...'
docker compose up -d db | Out-Null
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep 2
    $h = docker inspect --format '{{.State.Health.Status}}' conduit-db 2>$null
    if ($h -eq 'healthy') { $healthy = $true; break }
}
if (-not $healthy) { throw 'FAIL: database did not come back healthy' }
Write-Host '   postgres restarted and replayed the WAL on startup'

Write-Host '-> verifying the acknowledged state survived the crash:'
$delivered = [int](docker exec conduit-db psql -U conduit -d conduit -t -A -c "SELECT count(*) FROM message m JOIN topic t ON t.topic_id = m.topic_id WHERE t.topic_name = '$topic' AND m.status = 'delivered'")
$offsets = [int](docker exec conduit-db psql -U conduit -d conduit -t -A -c "SELECT count(*) FROM group_offset go JOIN partition p ON p.partition_id = go.partition_id JOIN topic t ON t.topic_id = p.topic_id WHERE t.topic_name = '$topic' AND go.committed_offset > 0")

if ($delivered -eq 5) { Write-Host "   [PASS] all 5 acknowledged messages present after WAL replay ($delivered/5)" -ForegroundColor Green }
else { throw "FAIL: expected 5 delivered messages after recovery, got $delivered" }

if ($offsets -ge 1) { Write-Host "   [PASS] committed group offsets intact ($offsets partitions advanced)" -ForegroundColor Green }
else { throw 'FAIL: committed group offsets were lost' }

Write-Host '-> proving the recovered broker is fully operational: producing one more message...'
$post = @'
import os
import sys
sys.path.insert(0, "/app/demos")
from conduit import Conduit
from _common import DSN
c = Conduit(os.environ["DEMO_APPKEY"], dsn=DSN)
loc = c.produce(os.environ["DEMO_TOPIC"], {"event": "post-crash"}, 900001, key="recovered")
print(f"PRODUCED offset={loc['msg_offset']} partition={loc['partition_id']}")
c.close()
'@ | docker compose exec -e DEMO_TOPIC=$topic -e DEMO_APPKEY=$appkey -T api python -
Write-Host "   $post"

$total = [int](docker exec conduit-db psql -U conduit -d conduit -t -A -c "SELECT count(*) FROM message m JOIN topic t ON t.topic_id = m.topic_id WHERE t.topic_name = '$topic'")
if ($total -eq 6) { Write-Host "   [PASS] 5 old messages + 1 new message on the recovered broker ($total total)" -ForegroundColor Green }
else { throw "FAIL: expected 6 messages after post-crash produce, got $total" }

Write-Host '-> restarting the api container (its connection pools pointed at the dead database)...'
docker compose restart api | Out-Null
Write-Host '   stack fully recovered'

Write-Host ''
Write-Host ' DEMO COMPLETE - the DBMS WAL is the durability layer' -ForegroundColor Green
Write-Host ''
