\set ON_ERROR_STOP on

\getenv seed_switch CONDUIT_SEED

\if :seed_switch

\echo '[seed] users (6, across all roles)'
SELECT register_user('sysadmin', 'sysadmin@conduit.io', 'admin');
SELECT register_user('maya.ops', 'maya@conduit.io', 'operator');
SELECT register_user('arjun.checkout', 'arjun@conduit.io', 'producer');
SELECT register_user('priya.payments', 'priya@conduit.io', 'producer');
SELECT register_user('dev.analytics', 'dev@conduit.io', 'consumer');
SELECT register_user('guest.viewer', 'guest@conduit.io', 'viewer');

\echo '[seed] client applications (6 service apps)'
SELECT app_id AS app_checkout FROM register_application('checkout-service', 'arjun.checkout', 'producer') \gset
SELECT app_id AS app_inventory FROM register_application('inventory-service', 'arjun.checkout', 'producer') \gset
SELECT app_id AS app_payments FROM register_application('payment-service', 'priya.payments', 'both') \gset
SELECT app_id AS app_fraud FROM register_application('fraud-detector', 'maya.ops', 'both') \gset
SELECT app_id AS app_email FROM register_application('email-service', 'dev.analytics', 'consumer') \gset
SELECT app_id AS app_analytics FROM register_application('analytics-worker', 'dev.analytics', 'consumer') \gset

\echo '[seed] topics (4: three schema-validated, one schemaless)'
SELECT create_topic('orders', 'order lifecycle events', 4, '{"required":["event","order_id"]}', 'sysadmin');
SELECT create_topic('payments', 'payment events', 2, '{"required":["event","payment_id","order_id"]}', 'sysadmin');
SELECT create_topic('notifications', 'outbound notifications', 2, '{"required":["event","channel","recipient"]}', 'maya.ops');
SELECT create_topic('user-activity', 'clickstream events (schemaless)', 3, NULL, 'maya.ops');

\echo '[seed] access grants (16) - guest.viewer deliberately ungranted'
SELECT grant_access('arjun.checkout', 'orders', 'produce', 'sysadmin');
SELECT grant_access('arjun.checkout', 'user-activity', 'produce', 'sysadmin');
SELECT grant_access('priya.payments', 'orders', 'consume', 'sysadmin');
SELECT grant_access('priya.payments', 'payments', 'produce', 'sysadmin');
SELECT grant_access('priya.payments', 'payments', 'consume', 'sysadmin');
SELECT grant_access('maya.ops', 'orders', 'produce', 'sysadmin');
SELECT grant_access('maya.ops', 'orders', 'consume', 'sysadmin');
SELECT grant_access('maya.ops', 'payments', 'produce', 'sysadmin');
SELECT grant_access('maya.ops', 'payments', 'consume', 'sysadmin');
SELECT grant_access('maya.ops', 'notifications', 'produce', 'sysadmin');
SELECT grant_access('maya.ops', 'notifications', 'consume', 'sysadmin');
SELECT grant_access('maya.ops', 'user-activity', 'produce', 'sysadmin');
SELECT grant_access('maya.ops', 'user-activity', 'consume', 'sysadmin');
SELECT grant_access('dev.analytics', 'orders', 'consume', 'sysadmin');
SELECT grant_access('dev.analytics', 'notifications', 'consume', 'sysadmin');
SELECT grant_access('dev.analytics', 'user-activity', 'consume', 'sysadmin');

\echo '[seed] consumer groups (5) and subscriptions (6, incl. a two-topic group)'
SELECT create_group('billing-workers', 'maya.ops', 3);
SELECT create_group('payment-processors', 'priya.payments', 3);
SELECT create_group('email-workers', 'dev.analytics', 3);
SELECT create_group('analytics-team', 'dev.analytics', 5);
SELECT create_group('fraud-team', 'maya.ops', 3);
SELECT subscribe_group('billing-workers', 'orders');
SELECT subscribe_group('payment-processors', 'payments');
SELECT subscribe_group('email-workers', 'notifications');
SELECT subscribe_group('analytics-team', 'orders');
SELECT subscribe_group('analytics-team', 'user-activity');
SELECT subscribe_group('fraud-team', 'payments');

\echo '[seed] broker configuration defaults'
SELECT update_broker_config('default_visibility_timeout_s', '30', 'consumer claim visibility (seconds)', 'sysadmin');
SELECT update_broker_config('max_consume_batch', '1000', 'upper bound on consume batch size', 'sysadmin');
SELECT update_broker_config('maintenance_purge_interval_hours', '24', 'how often purge_retention is expected to run', 'sysadmin');

\echo '[seed] producing 2,000 messages through the real broker API'
SELECT count(*) AS orders_from_checkout FROM produce_batch('orders', (
    SELECT jsonb_agg(jsonb_build_object(
        'seq', g,
        'key', 'order-' || (g % 50),
        'payload', jsonb_build_object('event', (ARRAY['created','paid','shipped','cancelled'])[1 + (g % 4)],
                                      'order_id', g, 'amount', (g % 200 + 1) * 10)
    )) FROM generate_series(1, 600) g
), :app_checkout);
SELECT count(*) AS orders_from_inventory FROM produce_batch('orders', (
    SELECT jsonb_agg(jsonb_build_object(
        'seq', g,
        'key', 'order-' || (g % 50),
        'payload', jsonb_build_object('event', 'restocked', 'order_id', g + 1000)
    )) FROM generate_series(1, 200) g
), :app_inventory);
SELECT count(*) AS payments_produced FROM produce_batch('payments', (
    SELECT jsonb_agg(jsonb_build_object(
        'seq', g,
        'key', 'pay-' || (g % 40),
        'payload', jsonb_build_object('event', (ARRAY['authorized','captured','refunded'])[1 + (g % 3)],
                                      'payment_id', g, 'order_id', g % 600 + 1)
    )) FROM generate_series(1, 500) g
), :app_payments);
SELECT count(*) AS notifications_produced FROM produce_batch('notifications', (
    SELECT jsonb_agg(jsonb_build_object(
        'seq', g,
        'key', 'note-' || (g % 25),
        'payload', jsonb_build_object('event', (ARRAY['email','sms','push'])[1 + (g % 3)],
                                      'channel', (ARRAY['email','sms','push'])[1 + (g % 3)],
                                      'recipient', 'user-' || (g % 120))
    )) FROM generate_series(1, 300) g
), :app_fraud);
SELECT count(*) AS activity_produced FROM produce_batch('user-activity', (
    SELECT jsonb_agg(jsonb_build_object(
        'seq', 600 + g,
        'payload', jsonb_build_object('event', 'click', 'user', 'user-' || (g % 120), 'page', '/p' || (g % 30))
    )) FROM generate_series(1, 400) g
), :app_checkout);

\echo '[seed] poison message on payments: 3 claim+nack cycles -> dead + DLQ'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS poison_loc
FROM consume('payment-processors', 'payments', 1, 60) \gset
SELECT * FROM nack('payment-processors', :'poison_loc'::JSONB, 'invalid payment webhook');
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS poison_loc
FROM consume('payment-processors', 'payments', 1, 60) \gset
SELECT * FROM nack('payment-processors', :'poison_loc'::JSONB, 'invalid payment webhook');
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS poison_loc
FROM consume('payment-processors', 'payments', 1, 60) \gset
SELECT * FROM nack('payment-processors', :'poison_loc'::JSONB, 'invalid payment webhook');

\echo '[seed] billing-workers on orders: 600 consumed, 580 acked, 10 in-flight, 10 nacked'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS locs1
FROM consume('billing-workers', 'orders', 200, 300) \gset
SELECT ack('billing-workers', :'locs1'::JSONB) AS batch1_acked;
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS locs2
FROM consume('billing-workers', 'orders', 200, 300) \gset
SELECT ack('billing-workers', :'locs2'::JSONB) AS batch2_acked;
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS locs3
FROM consume('billing-workers', 'orders', 200, 300) \gset
SELECT ack('billing-workers', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'locs3'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord <= 180)) AS batch3_acked;
SELECT * FROM nack('billing-workers', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'locs3'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord > 190), 'handler timeout');

\echo '[seed] payment-processors on payments: 390 acked, 5 in-flight, 5 nacked'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS plocs1
FROM consume('payment-processors', 'payments', 200, 300) \gset
SELECT ack('payment-processors', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'plocs1'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord <= 190)) AS pbatch1_acked;
SELECT * FROM nack('payment-processors', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'plocs1'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord > 195), 'gateway 502');
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS plocs2
FROM consume('payment-processors', 'payments', 200, 300) \gset
SELECT ack('payment-processors', :'plocs2'::JSONB) AS pbatch2_acked;

\echo '[seed] fraud-team on payments leftovers: 35 acked, 3 in-flight, 2 nacked'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS flocs
FROM consume('fraud-team', 'payments', 40, 300) \gset
SELECT ack('fraud-team', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'flocs'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord <= 35)) AS fraud_acked;
SELECT * FROM nack('fraud-team', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'flocs'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord > 38), 'score threshold retry');

\echo '[seed] email-workers on notifications: 285 acked, 7 in-flight, 8 nacked'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS nlocs1
FROM consume('email-workers', 'notifications', 150, 300) \gset
SELECT ack('email-workers', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'nlocs1'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord <= 140)) AS nbatch1_acked;
SELECT * FROM nack('email-workers', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'nlocs1'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord > 145), 'smtp throttled');
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS nlocs2
FROM consume('email-workers', 'notifications', 150, 300) \gset
SELECT ack('email-workers', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'nlocs2'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord <= 145)) AS nbatch2_acked;
SELECT * FROM nack('email-workers', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'nlocs2'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord > 147), 'provider retry');

\echo '[seed] analytics-team on user-activity: 290 acked, 4 in-flight, 6 nacked'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS alocs
FROM consume('analytics-team', 'user-activity', 300, 300) \gset
SELECT ack('analytics-team', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'alocs'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord <= 290)) AS analytics_acked;
SELECT * FROM nack('analytics-team', (SELECT jsonb_agg(e.value) FROM jsonb_array_elements(:'alocs'::JSONB) WITH ORDINALITY AS e(value, ord) WHERE e.ord > 294), 'sink backpressure');

\echo '[seed] backdating: spread all messages over the last 2 hours, age 30 notifications past retention'
UPDATE message SET created_at = now() - (random() * 120 * interval '1 minute');
UPDATE message m SET created_at = now() - interval '8 days'
WHERE (m.partition_id, m.msg_offset) IN (
    SELECT p2.partition_id, p2.msg_offset
    FROM message p2
    WHERE p2.topic_id = (SELECT t.topic_id FROM topic t WHERE t.topic_name = 'notifications')
    ORDER BY p2.partition_id, p2.msg_offset
    LIMIT 30
);
SELECT refresh_dashboard();

\echo '[seed] dataset summary'
SELECT * FROM v_topic_stats ORDER BY topic_name;
SELECT * FROM v_consumer_lag;

\else

\echo '[seed] CONDUIT_SEED is not true - skipping demo dataset'

\endif
