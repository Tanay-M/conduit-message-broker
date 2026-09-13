\set ON_ERROR_STOP on

\echo '================================================='
\echo ' M2 SMOKE TEST - full broker loop against a FRESH'
\echo ' volume (docker compose down -v && up -d db first)'
\echo '================================================='

\echo '[1] setup: user, app, topic(3 partitions), group, subscription, grants'
SELECT register_user('admin', 'admin@conduit.io', 'admin') AS admin_id \gset
SELECT app_id, api_key FROM register_application('orders-producer', 'admin', 'producer') \gset
SELECT create_topic('orders', 'order lifecycle events', 3, '{"required":["event","order_id"]}', 'admin') AS topic_id \gset
SELECT create_group('billing-workers', 'admin', 3) AS group_id \gset
SELECT subscribe_group('billing-workers', 'orders') AS partitions_wired;
SELECT grant_access('admin', 'orders', 'produce', 'admin') AS produce_grant;
SELECT grant_access('admin', 'orders', 'consume', 'admin') AS consume_grant;

\echo '[2] produce: 6 keyed (hash-routed) + 4 unkeyed (least-loaded) via produce_batch'
SELECT * FROM produce_batch('orders', '[
  {"seq":1,  "key":"order-1", "payload":{"event":"created","order_id":1}},
  {"seq":2,  "key":"order-2", "payload":{"event":"created","order_id":2}},
  {"seq":3,  "key":"order-3", "payload":{"event":"created","order_id":3}},
  {"seq":4,  "key":"order-1", "payload":{"event":"paid","order_id":1}},
  {"seq":5,  "key":"order-2", "payload":{"event":"paid","order_id":2}},
  {"seq":6,  "key":"order-3", "payload":{"event":"paid","order_id":3}},
  {"seq":7,  "payload":{"event":"audit","order_id":0}},
  {"seq":8,  "payload":{"event":"audit","order_id":0}},
  {"seq":9,  "payload":{"event":"audit","order_id":0}},
  {"seq":10, "payload":{"event":"audit","order_id":0}}
]', :app_id);

\echo '[3] idempotency: same (app, seq) produce again -> is_duplicate = true, same location'
SELECT * FROM produce('orders', 'order-1', '{"event":"created","order_id":1}', :app_id, 1);

\echo '[4] error handling: expect CDT04 schema violation + CDT01 unknown topic'
DO $$
DECLARE
    v_app_id BIGINT;
BEGIN
    SELECT a.app_id INTO v_app_id FROM application a WHERE a.app_name = 'orders-producer';
    BEGIN
        PERFORM produce('orders', 'bad-key', '{"event":"created"}', v_app_id, 100);
        RAISE EXCEPTION 'FAIL: schema violation did not raise';
    EXCEPTION WHEN OTHERS THEN
        IF SQLSTATE <> 'CDT04' THEN RAISE EXCEPTION 'FAIL: wrong sqlstate % (%)', SQLSTATE, SQLERRM; END IF;
        RAISE NOTICE 'OK: caught % %', SQLSTATE, SQLERRM;
    END;
    BEGIN
        PERFORM produce('no-such-topic', NULL, '{"x":1}', v_app_id, 101);
        RAISE EXCEPTION 'FAIL: unknown topic did not raise';
    EXCEPTION WHEN OTHERS THEN
        IF SQLSTATE <> 'CDT01' THEN RAISE EXCEPTION 'FAIL: wrong sqlstate % (%)', SQLSTATE, SQLERRM; END IF;
        RAISE NOTICE 'OK: caught % %', SQLSTATE, SQLERRM;
    END;
END $$;

\echo '[5] consume: batch of 5 (SKIP LOCKED claim), capture locations'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS locs5,
       count(*) AS claimed_count
FROM consume('billing-workers', 'orders', 5, 60) \gset

\echo '[6] ack: those 5 -> delivered, committed_offset advances atomically'
SELECT ack('billing-workers', :'locs5'::JSONB) AS acked_now_delivered;
SELECT pt.partition_number AS part_no, go.committed_offset, pt.next_offset
FROM group_offset go
JOIN partition pt ON pt.partition_id = go.partition_id
JOIN topic t ON t.topic_id = pt.topic_id
WHERE t.topic_name = 'orders' ORDER BY pt.partition_number;

\echo '[7] nack: consume 1 and reject it -> back to pending (attempts 2 < max 3)'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS locs_nack
FROM consume('billing-workers', 'orders', 1, 60) \gset
SELECT * FROM nack('billing-workers', :'locs_nack'::JSONB, 'handler threw exception');
SELECT msg_offset, status, attempts, visible_at FROM message WHERE topic_id = :topic_id ORDER BY msg_offset;

\echo '[8] poison message: nack the same message 2 more times -> attempts hits 3 -> DLQ'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS locs_poison
FROM consume('billing-workers', 'orders', 1, 60) \gset
SELECT * FROM nack('billing-workers', :'locs_poison'::JSONB, 'handler threw exception');
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS locs_poison2
FROM consume('billing-workers', 'orders', 1, 60) \gset
SELECT * FROM nack('billing-workers', :'locs_poison2'::JSONB, 'handler threw exception');
SELECT dlq_id, original_offset, failure_reason, attempts, status FROM dead_letter_message WHERE original_topic_id = :topic_id \gset
SELECT * FROM topic_stats('orders');

\echo '[9] requeue: DLQ entry -> fresh message on the topic'
SELECT * FROM requeue_dlq(:dlq_id, :app_id, NULL);
SELECT * FROM topic_stats('orders');

\echo '[10] visibility timeout + reaper: claim with 2s timeout, sleep 3s, reap'
SELECT count(*) AS claimed_for_crash_sim
FROM consume('billing-workers', 'orders', 3, 2) \gset
SELECT pg_sleep(3);
SELECT * FROM reap_expired_claims();
SELECT * FROM topic_stats('orders');

\echo '[11] broker config upsert + maintenance no-ops'
SELECT update_broker_config('default_visibility_timeout_s', '45', 'visibility timeout for claims', 'admin');
SELECT config_key, config_value, updated_at FROM broker_config WHERE config_key = 'default_visibility_timeout_s';
SELECT create_monthly_partition('2027-04-15'::DATE) AS new_partition;
SELECT purge_retention('orders') AS purged_old_messages;
SELECT drop_old_partitions(90) AS dropped_partitions;

\echo '[12] final state: group offsets vs partition heads'
SELECT t.topic_name, pt.partition_number, go.committed_offset, pt.next_offset
FROM group_offset go
JOIN partition pt ON pt.partition_id = go.partition_id
JOIN topic t ON t.topic_id = pt.topic_id
WHERE t.topic_name = 'orders'
ORDER BY pt.partition_number;

\echo '================================================='
\echo ' M2 SMOKE TEST COMPLETE - inspect outputs above'
\echo '================================================='
