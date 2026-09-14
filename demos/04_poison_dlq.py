from _common import banner, check, done, fixtures, info, new_admin, new_client, step

banner("DEMO 04 - POISON MESSAGE: 3 failed deliveries -> dead letter queue -> requeue -> delivered")

admin = new_admin()
fx = fixtures(admin, "d4", schema={"required": ["event"]})
client = new_client(fx)
step(f"provisioned topic={fx['topic']} group={fx['group']} (max_delivery_attempts=3)")

step("producing one poison message")
loc = client.produce(fx["topic"], {"event": "poison", "payload": "worker always throws"}, 1, key="poison")
info(f"stored at partition={loc['partition_id']} offset={loc['msg_offset']}")

for attempt in range(1, 4):
    step(f"delivery attempt {attempt}: claim -> handler fails -> nack")
    msgs = client.consume(fx["group"], fx["topic"], 1, 30)
    check(len(msgs) == 1, f"attempt {attempt} claimed the message (attempts now {msgs[0]['attempts']})")
    outcome = client.nack(fx["group"], [msgs[0]["location"]], "handler threw ValueError")
    info(f"nack result: retried={outcome['retried']} dead={outcome['dead']}")
    if attempt < 3:
        check(outcome["retried"] == 1 and outcome["dead"] == 0, "below threshold: back to pending for retry")
    else:
        check(outcome["dead"] == 1 and outcome["retried"] == 0, "attempts hit 3: routed to the dead letter queue")

step("inspecting the dead letter queue")
dlq = admin.run(
    "SELECT d.dlq_id, d.original_offset, d.failure_reason, d.attempts, d.status "
    "FROM dead_letter_message d WHERE d.original_topic_id = %s::bigint",
    (fx["topic_id"],),
)
for row in dlq:
    info(f"dlq_id={row['dlq_id']} offset={row['original_offset']} attempts={row['attempts']} reason='{row['failure_reason']}' status={row['status']}")
check(len(dlq) == 1, "exactly one DLQ entry")
check(dlq[0]["attempts"] == 3, "DLQ records all 3 delivery attempts")

stats = admin.topic_stats(fx["topic"])
check(stats["dead"] == 1 and stats["dlq_pending"] == 1, "topic stats: 1 dead, 1 pending DLQ entry")

step("requeueing the poison message as a fresh produce (fix the handler, try again)")
requeued = admin.requeue_dlq(dlq[0]["dlq_id"], fx["app_name"])
info(f"requeued as partition={requeued['partition_id']} offset={requeued['msg_offset']}")

msgs = client.consume(fx["group"], fx["topic"], 1, 30)
check(len(msgs) == 1, "requeued message is consumable again")
acked = client.ack(fx["group"], [msgs[0]["location"]])
check(acked == 1, "this time the handler succeeds -> ack -> delivered")

stats = admin.topic_stats(fx["topic"])
info(f"final stats: delivered={stats['delivered']} dead={stats['dead']} dlq_pending={stats['dlq_pending']}")
check(stats["delivered"] == 1 and stats["dlq_pending"] == 0, "message ultimately delivered, DLQ empty")

client.close()
admin.close()
done()
