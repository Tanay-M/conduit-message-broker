from conduit.errors import ConduitError

from _common import banner, check, done, fixtures, info, new_admin, new_client, step

banner("DEMO 07 - EXACTLY-ONCE EFFECT: atomic ack + offset commit, no regressions")

admin = new_admin()
fx = fixtures(admin, "d7")
client = new_client(fx)
step(f"provisioned topic={fx['topic']} group={fx['group']}")

TOTAL = 10
ACK_FIRST = 7

step(f"producing {TOTAL} messages and claiming all of them")
client.produce_batch(fx["topic"], [{"payload": {"event": "txn", "n": i}} for i in range(TOTAL)], seq_start=1)
claimed = client.consume(fx["group"], fx["topic"], TOTAL, 60)
check(len(claimed) == TOTAL, f"claimed all {TOTAL}")
locations = [m["location"] for m in claimed]

step(f"processing completes for only the first {ACK_FIRST} - acking a PARTIAL batch")
acked = client.ack(fx["group"], locations[:ACK_FIRST])
info(f"ack returned {acked}")
check(acked == ACK_FIRST, f"{ACK_FIRST} of {TOTAL} acknowledged")

offsets = admin.run(
    "SELECT pt.partition_number, go.committed_offset, "
    "(SELECT count(*) FROM message m WHERE m.partition_id = pt.partition_id) AS produced "
    "FROM group_offset go JOIN partition pt ON pt.partition_id = go.partition_id "
    "WHERE pt.topic_id = %s::bigint ORDER BY pt.partition_number",
    (fx["topic_id"],),
)
total_committed = 0
for row in offsets:
    info(f"partition {row['partition_number']}: committed={row['committed_offset']}/{row['produced']} produced")
    total_committed += row["committed_offset"]
check(total_committed == ACK_FIRST,
      f"committed offsets advance to EXACTLY the acked prefix ({total_committed}/{ACK_FIRST})")

step("the remaining 3 claims are still in-flight (claimed, not lost)")
rows = admin.run(
    "SELECT m.status, count(*) AS n FROM message m WHERE m.topic_id = %s::bigint GROUP BY m.status",
    (fx["topic_id"],),
)
by_status = {r["status"]: r["n"] for r in rows}
info(f"status mix: {by_status}")
check(by_status.get("delivered") == ACK_FIRST and by_status.get("claimed") == TOTAL - ACK_FIRST,
      f"{ACK_FIRST} delivered + {TOTAL - ACK_FIRST} still claimed - the acked prefix is durable")

step("duplicate ack of the same locations - offsets must not move (idempotent)")
before = total_committed
acked_again = client.ack(fx["group"], locations[:ACK_FIRST])
offsets_again = admin.run(
    "SELECT sum(go.committed_offset) AS total FROM group_offset go "
    "JOIN partition pt ON pt.partition_id = go.partition_id WHERE pt.topic_id = %s::bigint",
    (fx["topic_id"],),
)
info(f"second ack returned {acked_again}, total committed now {offsets_again[0]['total']}")
check(offsets_again[0]["total"] == before, "offsets unchanged after a duplicate ack")

step("attempting to REGRESS committed offsets - the trigger refuses (CDT19)")
try:
    admin.run(
        "UPDATE group_offset go SET committed_offset = 0 "
        "WHERE go.partition_id IN (SELECT pt.partition_id FROM partition pt WHERE pt.topic_id = %s::bigint)",
        (fx["topic_id"],),
    )
    check(False, "offset regression should have been rejected")
except ConduitError as e:
    info(f"caught typed exception: [{e.code}] {e.message}")
    check(e.code == "CDT19", "monotonic offset guard rejected the regression")

step("nacking the 3 in-flight, then draining the rest")
client.nack(fx["group"], locations[ACK_FIRST:], "batch finished")
msgs = client.consume(fx["group"], fx["topic"], TOTAL, 60)
client.ack(fx["group"], [m["location"] for m in msgs])
stats = admin.topic_stats(fx["topic"])
info(f"final stats: delivered={stats['delivered']} pending={stats['pending']}")
check(stats["delivered"] == TOTAL, f"all {TOTAL} delivered after the full cycle")

client.close()
admin.close()
done()
