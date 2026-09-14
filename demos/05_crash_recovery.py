import time

from _common import banner, check, done, fixtures, info, new_admin, new_client, step

banner("DEMO 05 - CRASHED CONSUMER RECOVERY: visibility timeout + reaper = at-least-once delivery")

admin = new_admin()
fx = fixtures(admin, "d5")
client = new_client(fx)
step(f"provisioned topic={fx['topic']} group={fx['group']}")

step("producing 3 messages")
client.produce_batch(fx["topic"], [{"payload": {"event": "work", "n": i}} for i in range(3)], seq_start=1)
info("3 messages pending")

step("worker A claims all 3 with a 2-second visibility timeout...")
claimed = client.consume(fx["group"], fx["topic"], 3, 2)
for m in claimed:
    info(f"claimed offset={m['msg_offset']} visible_until={m['visible_until']} attempts={m['attempts']}")
check(len(claimed) == 3, "worker A holds 3 claims")

step("worker A CRASHES - it never acks, it just disappears")
info("(in a real crash the process dies holding these claims; the rows stay status='claimed')")
info("(no other consumer can take them while the visibility window is open)")
time.sleep(3)
info("... 3 seconds later: the visibility timeout has expired")

step("running the reaper: expired claims are re-queued or dead-lettered")
outcome = admin.reap_expired()
info(f"reap_expired_claims: requeued={outcome['requeued']} dead={outcome['dead']}")
check(outcome["requeued"] == 3 and outcome["dead"] == 0, "all 3 expired claims returned to pending")

rows = admin.run(
    "SELECT m.msg_offset, m.status, m.attempts FROM message m WHERE m.topic_id = %s::bigint ORDER BY m.msg_offset",
    (fx["topic_id"],),
)
for row in rows:
    info(f"offset={row['msg_offset']} status={row['status']} attempts={row['attempts']}")
check(all(r["status"] == "pending" for r in rows), "messages are pending again")
check(all(r["attempts"] == 1 for r in rows), "attempt counter records the crashed claim (attempts=1)")

step("worker B (a new process) picks them up and completes the work")
msgs = client.consume(fx["group"], fx["topic"], 3, 30)
check(len(msgs) == 3, "worker B claimed all 3 recovered messages")
check(all(m["attempts"] == 2 for m in msgs), "worker B's claim bumps attempts to 2 (crash counted as a receive)")
acked = client.ack(fx["group"], [m["location"] for m in msgs])
check(acked == 3, "worker B acknowledged all 3 - nothing was lost")

stats = admin.topic_stats(fx["topic"])
check(stats["delivered"] == 3, "final state: 3 delivered - at-least-once delivery held")

client.close()
admin.close()
done()
