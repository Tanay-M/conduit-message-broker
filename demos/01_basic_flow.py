from _common import banner, check, done, fixtures, info, new_admin, new_client, step, timed

banner("DEMO 01 - BASIC FLOW: send a message, see it stored, read it, ack it")

admin = new_admin()
fx = fixtures(admin, "d1", schema={"required": ["event", "n"]})
step(f"provisioned user={fx['user']} app={fx['app_name']} topic={fx['topic']} (2 partitions) group={fx['group']}")

client = new_client(fx)

step("producing 5 messages (3 keyed, 2 unkeyed)")
messages = [
    {"key": "alpha", "payload": {"event": "created", "n": 1}},
    {"key": "beta", "payload": {"event": "created", "n": 2}},
    {"key": "alpha", "payload": {"event": "paid", "n": 3}},
    {"payload": {"event": "audit", "n": 4}},
    {"payload": {"event": "audit", "n": 5}},
]
results, ms = timed(client.produce_batch, fx["topic"], messages, seq_start=1)
info(f"produce_batch of 5 took {ms:.1f} ms")
for r in results:
    info(f"stored at topic={r['topic_id']} partition={r['partition_id']} offset={r['msg_offset']}")
check(len(results) == 5, "all 5 produces returned a location")
keys = {(r["partition_id"]) for r in results[:2]}
check(results[0]["partition_id"] == results[2]["partition_id"], "same key routes to the same partition every time")

step("opening the database and reading the stored rows back")
rows = admin.run(
    "SELECT pt.partition_number, m.msg_offset, m.status, m.msg_key, m.payload, m.created_at "
    "FROM message m JOIN partition pt ON pt.partition_id = m.partition_id "
    "WHERE m.topic_id = %s::bigint ORDER BY pt.partition_number, m.msg_offset",
    (fx["topic_id"],),
)
for row in rows:
    info(f"partition {row['partition_number']} offset {row['msg_offset']} status={row['status']} key={row['msg_key']} payload={row['payload']}")
check(len(rows) == 5, "5 rows found on disk in the message table")
check(all(r["status"] == "pending" for r in rows), "all rows start as pending")

step("consuming a batch of 5 (SKIP LOCKED claim with 60s visibility)")
consumed, ms = timed(client.consume, fx["group"], fx["topic"], 5, 60)
info(f"consume took {ms:.1f} ms")
for m in consumed:
    info(f"claimed partition={m['partition_id']} offset={m['msg_offset']} visible_until={m['visible_until']} attempts={m['attempts']}")
check(len(consumed) == 5, "consumer claimed 5 messages")
check(all(m["attempts"] == 1 for m in consumed), "claim increments the attempt counter (SQS ReceiveCount style)")

offsets_before = admin.run(
    "SELECT go.committed_offset FROM group_offset go "
    "JOIN partition p ON p.partition_id = go.partition_id WHERE p.topic_id = %s::bigint",
    (fx["topic_id"],),
)
check(all(r["committed_offset"] == 0 for r in offsets_before), "group offsets still 0 before ack")

step("acknowledging all 5 (atomic claim->delivered + offset advance in one transaction)")
locations = [m["location"] for m in consumed]
acked, ms = timed(client.ack, fx["group"], locations)
info(f"ack took {ms:.1f} ms, acknowledged {acked}")
check(acked == 5, "5 messages acknowledged")

offsets_after = admin.run(
    "SELECT pt.partition_number, go.committed_offset, pt.next_offset FROM group_offset go "
    "JOIN partition pt ON pt.partition_id = go.partition_id WHERE pt.topic_id = %s::bigint "
    "ORDER BY pt.partition_number",
    (fx["topic_id"],),
)
for row in offsets_after:
    info(f"partition {row['partition_number']}: committed_offset={row['committed_offset']} head={row['next_offset']}")
check(all(r["committed_offset"] == r["next_offset"] for r in offsets_after), "committed offset caught up to the partition head")

stats = admin.topic_stats(fx["topic"])
check(stats["delivered"] == 5 and stats["pending"] == 0, "topic stats show 5 delivered, 0 pending")

client.close()
admin.close()
done()
