\set ON_ERROR_STOP on

\echo '================================================='
\echo ' M3 SMOKE TEST - triggers, RLS, views'
\echo ' (run against a FRESH volume)'
\echo '================================================='

CREATE FUNCTION fn_assert(p_condition BOOLEAN, p_message TEXT DEFAULT 'assertion failed') RETURNS VOID
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT COALESCE(p_condition, FALSE) THEN
        RAISE EXCEPTION 'FAIL: %', p_message;
    END IF;
END;
$$;
GRANT EXECUTE ON FUNCTION fn_assert(BOOLEAN, TEXT) TO conduit_app;

\echo '[1] fixtures: secadmin (admin), alice (producer, granted), bob (consumer, NO grants)'
SELECT register_user('secadmin', 'secadmin@conduit.io', 'admin') AS secadmin_id \gset
SELECT register_user('alice', 'alice@conduit.io', 'producer') AS alice_id \gset
SELECT register_user('bob', 'bob@conduit.io', 'consumer') AS bob_id \gset
SELECT app_id AS alice_app, api_key AS alice_key FROM register_application('alice-producer', 'alice', 'both') \gset
SELECT app_id AS bob_app, api_key AS bob_key FROM register_application('bob-producer', 'bob', 'both') \gset
SELECT create_topic('secure-orders', 'rls demo topic', 2, '{"required":["event"]}', 'secadmin') AS sec_topic_id \gset
SELECT grant_access('alice', 'secure-orders', 'produce', 'secadmin') AS alice_produce_grant;
SELECT grant_access('alice', 'secure-orders', 'consume', 'secadmin') AS alice_consume_grant;
SELECT create_group('alice-workers', 'alice', 3) AS alice_group_id \gset
SELECT subscribe_group('alice-workers', 'secure-orders') AS partitions_wired;

\echo '[2] audit: PRODUCE rows written by trigger on message insert'
SELECT * FROM produce('secure-orders', 'k1', '{"event":"tick"}', :alice_app, 1);
SELECT * FROM produce('secure-orders', NULL, '{"event":"tock"}', :alice_app, 2);
SELECT fn_assert((SELECT count(*) FROM audit_log al WHERE al.topic_id = :sec_topic_id AND al.event_type = 'PRODUCE') = 2, 'expected 2 PRODUCE audit rows');
SELECT fn_assert((SELECT count(*) FROM audit_log al WHERE al.topic_id = :sec_topic_id AND al.event_type = 'PRODUCE' AND al.user_id = :alice_id) = 2, 'PRODUCE audit rows attributed to alice');
SELECT log_id, event_type, status, details FROM audit_log al WHERE al.topic_id = :sec_topic_id ORDER BY log_id;

\echo '[3] audit: DELIVERED rows on claim+ack'
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS locs
FROM consume('alice-workers', 'secure-orders', 2, 60) \gset
SELECT ack('alice-workers', :'locs'::JSONB) AS acked;
SELECT fn_assert((SELECT count(*) FROM audit_log al WHERE al.topic_id = :sec_topic_id AND al.event_type = 'DELIVERED') = 2, 'expected 2 DELIVERED audit rows');

\echo '[4] audit: DLQ row after poison message exhausts attempts'
SELECT * FROM produce('secure-orders', 'poison', '{"event":"poison"}', :alice_app, 3);
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS poison_loc
FROM consume('alice-workers', 'secure-orders', 1, 60) \gset
SELECT * FROM nack('alice-workers', :'poison_loc'::JSONB, 'handler failed 1');
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS poison_loc
FROM consume('alice-workers', 'secure-orders', 1, 60) \gset
SELECT * FROM nack('alice-workers', :'poison_loc'::JSONB, 'handler failed 2');
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS poison_loc
FROM consume('alice-workers', 'secure-orders', 1, 60) \gset
SELECT * FROM nack('alice-workers', :'poison_loc'::JSONB, 'handler failed 3');
SELECT fn_assert((SELECT count(*) FROM audit_log al WHERE al.topic_id = :sec_topic_id AND al.event_type = 'DLQ') = 1, 'expected 1 DLQ audit row');

\echo '[5] audit: admin events (ACL_GRANT, TOPIC_CREATE, SCHEMA_PUBLISH, CONFIG_CHANGE) + updated_at bump'
SELECT fn_assert((SELECT count(*) FROM audit_log al WHERE al.topic_id = :sec_topic_id AND al.event_type = 'ACL_GRANT') = 2, 'expected 2 ACL_GRANT rows');
SELECT fn_assert((SELECT count(*) FROM audit_log al WHERE al.topic_id = :sec_topic_id AND al.event_type = 'TOPIC_CREATE') = 1, 'expected 1 TOPIC_CREATE row');
SELECT fn_assert((SELECT count(*) FROM audit_log al WHERE al.topic_id = :sec_topic_id AND al.event_type = 'SCHEMA_PUBLISH') = 1, 'expected 1 SCHEMA_PUBLISH row');
SELECT update_broker_config('m3_test', '42', 'test key', 'secadmin');
SELECT fn_assert((SELECT count(*) FROM audit_log al WHERE al.event_type = 'CONFIG_CHANGE' AND al.details->>'config_key' = 'm3_test') = 1, 'expected 1 CONFIG_CHANGE row');
UPDATE broker_config SET updated_at = '2000-01-01'::TIMESTAMPTZ WHERE config_key = 'm3_test';
SELECT fn_assert((SELECT bc.updated_at FROM broker_config bc WHERE bc.config_key = 'm3_test') > '2000-01-01'::TIMESTAMPTZ, 'updated_at auto-bumped despite manual override');

\echo '[6] monotonic offset guard: regression must raise CDT19'
DO $$
BEGIN
    BEGIN
        UPDATE group_offset go SET committed_offset = go.committed_offset - 1
        WHERE go.group_id = (SELECT cg.group_id FROM consumer_group cg WHERE cg.group_name = 'alice-workers');
        RAISE EXCEPTION 'regression was allowed';
    EXCEPTION
        WHEN SQLSTATE 'CDT19' THEN NULL;
    END;
END $$;
\echo 'OK: offset regression rejected'

\echo '[7] RLS as conduit_app - alice allowed, bob denied, anonymous sees nothing'
\c conduit conduit_app
SET app.user_id = :'alice_id';
SELECT count(*) AS alice_message_visibility FROM message;
SELECT fn_assert((SELECT count(*) FROM message) > 0, 'alice should see secure-orders messages');
SELECT * FROM produce('secure-orders', 'k9', '{"event":"via-rls"}', :alice_app, 9);
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS rls_loc
FROM consume('alice-workers', 'secure-orders', 1, 60) \gset
SELECT ack('alice-workers', :'rls_loc'::JSONB) AS acked_via_rls;
SELECT fn_assert((SELECT count(*) FROM message m WHERE m.status = 'delivered') >= 3, 'RLS-path produce+consume+ack worked for alice');

SET app.user_id = :'bob_id';
SELECT count(*) AS bob_message_visibility FROM message;
SELECT fn_assert((SELECT count(*) FROM message) = 0, 'bob must see zero messages');

DO $$
DECLARE
    v_bob_app BIGINT;
    v_bob_id BIGINT;
    v_topic_id BIGINT;
BEGIN
    SELECT a.app_id INTO v_bob_app FROM application a WHERE a.app_name = 'bob-producer';
    SELECT u.user_id INTO v_bob_id FROM app_user u WHERE u.username = 'bob';
    SELECT t.topic_id INTO v_topic_id FROM topic t WHERE t.topic_name = 'secure-orders';
    BEGIN
        PERFORM produce('secure-orders', 'bob-key', '{"event":"bob-tries"}'::JSONB, v_bob_app, 99);
        RAISE EXCEPTION 'bob produce was allowed';
    EXCEPTION
        WHEN SQLSTATE 'CDT17' THEN NULL;
        WHEN SQLSTATE '42501' THEN NULL;
    END;
    PERFORM log_auth_failure(v_bob_id, v_bob_app, v_topic_id,
                             jsonb_build_object('reason', 'produce denied by ACL/RLS'));
END $$;
\echo 'OK: bob blocked (CDT17/42501) and AUTH_FAIL logged'

RESET app.user_id;
SELECT count(*) AS anonymous_visibility FROM message;
SELECT fn_assert((SELECT count(*) FROM message) = 0, 'anonymous (no GUC) must see zero messages');

\c conduit conduit
SELECT fn_assert((SELECT count(*) FROM audit_log al WHERE al.event_type = 'AUTH_FAIL') = 1, 'expected 1 AUTH_FAIL row');

\echo '[8] views: lag, stats (vs function), throughput, audit trail, matview refresh'
SELECT * FROM v_consumer_lag;
SELECT * FROM v_topic_stats;
SELECT fn_assert((SELECT vs.pending FROM v_topic_stats vs WHERE vs.topic_name = 'secure-orders')
              = (SELECT ts.pending FROM topic_stats('secure-orders') ts), 'v_topic_stats disagrees with topic_stats()');
SELECT fn_assert((SELECT vs.delivered FROM v_topic_stats vs WHERE vs.topic_name = 'secure-orders')
              = (SELECT ts.delivered FROM topic_stats('secure-orders') ts), 'delivered count mismatch');
SELECT * FROM v_throughput_by_minute ORDER BY topic_name, minute_ts;
SELECT log_id, username, app_name, topic_name, event_type, status FROM v_audit_recent ORDER BY log_id DESC LIMIT 12;
SELECT refresh_dashboard();
SELECT * FROM mv_topic_stats ORDER BY topic_name;
SELECT fn_assert((SELECT mv.pending FROM mv_topic_stats mv WHERE mv.topic_name = 'secure-orders')
              = (SELECT vs.pending FROM v_topic_stats vs WHERE vs.topic_name = 'secure-orders'), 'matview disagrees with view after refresh');

\echo '================================================='
\echo ' M3 SMOKE TEST COMPLETE'
\echo '================================================='
