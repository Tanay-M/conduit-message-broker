from pathlib import Path

from _bench_common import banner, check, fixtures, new_admin, new_client

TOTAL = 30000
KEEP_PENDING = 100
BATCH = 1000

banner(f"EXPLAIN AT SCALE: {TOTAL} messages via the real API, then prove the partial pending index wins")

admin = new_admin()
fx = fixtures(admin, "ex", partitions=4, schema={"required": ["event", "n"]})
client = new_client(fx)
print(f"  topic={fx['topic']} partitions=4")

print(f"  producing {TOTAL} messages through produce_batch...")
seq = 1
for i in range(0, TOTAL, BATCH):
    msgs = [{"payload": {"event": "explain", "n": i + j}} for j in range(BATCH)]
    client.produce_batch(fx["topic"], msgs, seq_start=seq)
    seq += BATCH

produced = admin.run(
    "SELECT count(*) AS n FROM message WHERE topic_id = %s::bigint", (fx["topic_id"],)
)[0]["n"]
check(produced == TOTAL, f"{produced}/{TOTAL} messages on disk")

target = TOTAL - KEEP_PENDING
print(f"  consuming + acking {target} (leaving the highest {KEEP_PENDING} pending)...")
consumed = 0
while consumed < target:
    want = min(BATCH, target - consumed)
    msgs = client.consume(fx["group"], fx["topic"], want, 300)
    if not msgs:
        break
    client.ack(fx["group"], [m["location"] for m in msgs])
    consumed += len(msgs)
check(consumed == target, f"consumed exactly {target}")

stats = admin.topic_stats(fx["topic"])
check(stats["pending"] == KEEP_PENDING, f"{KEEP_PENDING} pending remain, {stats['delivered']} delivered")

sql = (
    f"EXPLAIN (ANALYZE, BUFFERS) SELECT m.created_at, m.partition_id, m.msg_offset "
    f"FROM message m WHERE m.topic_id = {fx['topic_id']} "
    f"AND m.status = 'pending' AND (m.visible_at IS NULL OR m.visible_at <= now()) "
    f"ORDER BY m.msg_offset LIMIT 10 FOR UPDATE SKIP LOCKED"
)
plan_rows = admin.run(sql)
plan_text = "\n".join(r["QUERY PLAN"] for r in plan_rows)
print()
print(plan_text)
print()

out = Path("/app/benchmarks/explain_at_scale.txt")
out.write_text(
    f"EXPLAIN (ANALYZE, BUFFERS) consume candidates query\n"
    f"topic: {fx['topic']} ({TOTAL} messages, {KEEP_PENDING} pending)\n\n{plan_text}\n"
)
print(f"  plan saved -> {out}")

partial_names = [
    r["indexname"]
    for r in admin.run(
        "SELECT c.relname AS indexname FROM pg_inherits inh "
        "JOIN pg_class c ON c.oid = inh.inhrelid "
        "WHERE inh.inhparent = 'idx_message_pending'::regclass"
    )
]
print(f"  partial pending index children: {partial_names}")
check(
    any(name in plan_text for name in partial_names),
    "the partial pending index is used at scale",
)
check("Seq Scan" not in plan_text, "no sequential scan on the populated partition")

client.close()
admin.close()
print()
print("  EXPLAIN AT SCALE COMPLETE - partial index proof captured")
print()
