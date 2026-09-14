import threading

from _common import banner, check, done, fixtures, info, new_admin, new_client, step, timed

banner("DEMO 03 - IDEMPOTENCY: the same (app, seq) produced 6 times lands on disk exactly once")

admin = new_admin()
fx = fixtures(admin, "d3", schema={"required": ["event"]})
client = new_client(fx)
step(f"provisioned app={fx['app_name']} topic={fx['topic']}")

step("first produce of seq=1 (the original)")
original, ms = timed(client.produce, fx["topic"], {"event": "created"}, 1, key="idem-1")
info(f"original location: partition={original['partition_id']} offset={original['msg_offset']} duplicate={original['duplicate']} ({ms:.1f} ms)")
check(original["duplicate"] is False, "original produce is not a duplicate")

step("5 concurrent retries of the exact same (app, seq=1) - a retry storm")
results = []
errors = []
barrier = threading.Barrier(5)

def retry():
    try:
        barrier.wait()
        results.append(client.produce(fx["topic"], {"event": "created"}, 1, key="idem-1"))
    except Exception as e:
        errors.append(str(e))

threads = [threading.Thread(target=retry) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()

for e in errors:
    info(e)
check(not errors, "all retries completed without error")

for r in results:
    info(f"retry returned: partition={r['partition_id']} offset={r['msg_offset']} duplicate={r['duplicate']}")
check(all(r["duplicate"] is True for r in results), "every retry was flagged as a duplicate")
check(all(r["msg_offset"] == original["msg_offset"] and r["partition_id"] == original["partition_id"] for r in results),
      "every retry got the ORIGINAL location back")

rows = admin.run("SELECT count(*) AS n FROM message WHERE topic_id = %s::bigint", (fx["topic_id"],))
info(f"rows on disk for this topic: {rows[0]['n']}")
check(rows[0]["n"] == 1, "exactly one row exists on disk despite 6 produce calls")

ledger = admin.run(
    "SELECT ps.producer_seq, ps.partition_id, ps.msg_offset FROM producer_sequence ps "
    "JOIN application a ON a.app_id = ps.producer_app_id WHERE a.app_name = %s::text",
    (fx["app_name"],),
)
info(f"producer_sequence ledger rows: {[(r['producer_seq'], r['msg_offset']) for r in ledger]}")
check(len(ledger) == 1, "the idempotency ledger holds exactly one row for (app, seq=1)")

step("and a fresh seq=2 behaves normally")
fresh = client.produce(fx["topic"], {"event": "created"}, 2, key="idem-2")
check(fresh["duplicate"] is False, "a new seq produces a new message")

stats = admin.topic_stats(fx["topic"])
check(stats["pending"] == 2, "2 pending messages total (seq 1 and seq 2)")

client.close()
admin.close()
done()
