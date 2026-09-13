\set ON_ERROR_STOP on

\echo '================================================='
\echo ' M4 SMOKE TEST - seed dataset + data management'
\echo ' (run against a SEEDED volume: CONDUIT_SEED=true)'
\echo '================================================='

CREATE FUNCTION fn_assert(p_condition BOOLEAN, p_message TEXT DEFAULT 'assertion failed') RETURNS VOID
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT COALESCE(p_condition, FALSE) THEN
        RAISE EXCEPTION 'FAIL: %', p_message;
    END IF;
END;
$$;

\echo '[1] dataset shape: 2,000 messages with realistic status mix'
SELECT count(*) AS total_messages FROM message;
SELECT fn_assert((SELECT count(*) FROM message) = 2000, 'expected 2000 seeded messages');
SELECT status, count(*) FROM message GROUP BY status ORDER BY status;
SELECT fn_assert((SELECT count(*) FROM message WHERE status = 'delivered') BETWEEN 1560 AND 1600, 'delivered count out of range');
SELECT fn_assert((SELECT count(*) FROM message WHERE status = 'claimed') BETWEEN 25 AND 35, 'in-flight claimed count out of range');
SELECT fn_assert((SELECT count(*) FROM message WHERE status = 'pending') BETWEEN 380 AND 400, 'pending backlog out of range');
SELECT fn_assert((SELECT count(*) FROM message WHERE status = 'dead') = 1, 'expected exactly 1 poison message');
SELECT fn_assert((SELECT count(*) FROM topic) = 4, 'expected 4 topics');
SELECT fn_assert((SELECT count(*) FROM app_user) = 6, 'expected 6 users');
SELECT fn_assert((SELECT count(*) FROM application) = 6, 'expected 6 apps');
SELECT fn_assert((SELECT count(*) FROM consumer_group) = 5, 'expected 5 groups');
SELECT fn_assert((SELECT count(*) FROM group_subscription) = 6, 'expected 6 subscriptions');
SELECT fn_assert((SELECT count(*) FROM access) = 16, 'expected 16 grants');
SELECT * FROM v_topic_stats ORDER BY topic_name;

\echo '[2] audit coverage of the seeded lifecycle'
SELECT event_type, count(*) FROM audit_log GROUP BY event_type ORDER BY event_type;
SELECT fn_assert((SELECT count(*) FROM audit_log WHERE event_type = 'PRODUCE') = 2000, 'expected 2000 PRODUCE rows');
SELECT fn_assert((SELECT count(*) FROM audit_log WHERE event_type = 'DELIVERED') BETWEEN 1560 AND 1600, 'DELIVERED audit out of range');
SELECT fn_assert((SELECT count(*) FROM audit_log WHERE event_type = 'DLQ') = 1, 'expected 1 DLQ row');
SELECT fn_assert((SELECT count(*) FROM audit_log WHERE event_type = 'ACL_GRANT') = 16, 'expected 16 ACL_GRANT rows');
SELECT fn_assert((SELECT count(*) FROM audit_log WHERE event_type = 'CONFIG_CHANGE') = 3, 'expected 3 CONFIG_CHANGE rows');
SELECT fn_assert((SELECT count(*) FROM audit_log WHERE event_type = 'TOPIC_CREATE') = 4, 'expected 4 TOPIC_CREATE rows');
SELECT fn_assert((SELECT count(*) FROM audit_log WHERE event_type = 'SCHEMA_PUBLISH') = 3, 'expected 3 SCHEMA_PUBLISH rows');
SELECT fn_assert((SELECT count(*) FROM audit_log WHERE event_type = 'AUTH_FAIL') = 0, 'seed should have no auth failures');

\echo '[3] monitoring views populated: lag + throughput timeline'
SELECT count(*) AS lag_rows FROM v_consumer_lag;
SELECT fn_assert((SELECT count(*) FROM v_consumer_lag) > 0, 'consumer lag view empty');
SELECT fn_assert((SELECT max(lag_messages) FROM v_consumer_lag) > 0, 'expected nonzero lag somewhere');
SELECT count(*) AS throughput_minutes FROM v_throughput_by_minute;
SELECT fn_assert((SELECT count(*) FROM v_throughput_by_minute) >= 100, 'throughput timeline should cover >= 100 minutes');
SELECT count(*) AS dead_letter_entries FROM dead_letter_message WHERE status = 'pending';
SELECT fn_assert((SELECT count(*) FROM dead_letter_message WHERE status = 'pending') = 1, 'expected 1 pending DLQ entry');

\echo '[4] retention purge: exactly the 30 aged notifications expire'
SELECT purge_retention('notifications') AS purged;
SELECT fn_assert((SELECT purge_retention('notifications')) = 0, 'second purge must find nothing');
SELECT fn_assert((SELECT count(*) FROM message) = 1970, 'expected 1970 messages after purging 30');

\echo '[5] schema evolution: payments v2 published, v1 deprecated, old shape rejected'
SELECT publish_schema_version('payments', '{"required":["event","payment_id","order_id","currency"]}') AS new_version;
SELECT fn_assert((SELECT count(*) FROM schema_version sv JOIN topic t ON t.topic_id = sv.topic_id
                  WHERE t.topic_name = 'payments' AND sv.status = 'active') = 1, 'exactly one active schema version');
SELECT sv.version, sv.status FROM schema_version sv JOIN topic t ON t.topic_id = sv.topic_id WHERE t.topic_name = 'payments' ORDER BY sv.version;
DO $$
DECLARE v_app_id BIGINT;
BEGIN
    SELECT a.app_id INTO v_app_id FROM application a WHERE a.app_name = 'payment-service';
    BEGIN
        PERFORM produce('payments', 'pay-old', jsonb_build_object('event','captured','payment_id',9001,'order_id',1), v_app_id, 501);
        RAISE EXCEPTION 'old payload shape was accepted';
    EXCEPTION
        WHEN SQLSTATE 'CDT04' THEN NULL;
    END;
    PERFORM produce('payments', 'pay-new', jsonb_build_object('event','captured','payment_id',9001,'order_id',1,'currency','INR'), v_app_id, 501);
END $$;
SELECT fn_assert((SELECT count(*) FROM audit_log WHERE event_type = 'SCHEMA_PUBLISH') = 4, 'expected 4 SCHEMA_PUBLISH rows after v2');

\echo '[6] suspend semantics: suspended user loses produce access at trigger AND RLS layers'
SELECT suspend_user('priya.payments');
SELECT fn_assert(NOT fn_user_can_produce((SELECT u.user_id FROM app_user u WHERE u.username = 'priya.payments'),
                                         (SELECT t.topic_id FROM topic t WHERE t.topic_name = 'payments')),
                'suspended user must fail RLS produce policy');
DO $$
DECLARE v_app_id BIGINT;
BEGIN
    SELECT a.app_id INTO v_app_id FROM application a WHERE a.app_name = 'payment-service';
    BEGIN
        PERFORM produce('payments', 'pay-blocked', jsonb_build_object('event','captured','payment_id',9002,'order_id',2,'currency','INR'), v_app_id, 502);
        RAISE EXCEPTION 'suspended user produce was allowed';
    EXCEPTION
        WHEN SQLSTATE 'CDT17' THEN NULL;
        WHEN SQLSTATE '42501' THEN NULL;
    END;
END $$;
SELECT activate_user('priya.payments');
DO $$
DECLARE v_app_id BIGINT;
BEGIN
    SELECT a.app_id INTO v_app_id FROM application a WHERE a.app_name = 'payment-service';
    PERFORM produce('payments', 'pay-restored', jsonb_build_object('event','captured','payment_id',9002,'order_id',2,'currency','INR'), v_app_id, 502);
END $$;

\echo '[7] application revocation: revoked app cannot produce (CDT03), restored app can'
SELECT set_application_status('fraud-detector', 'revoked');
DO $$
DECLARE v_app_id BIGINT;
BEGIN
    SELECT a.app_id INTO v_app_id FROM application a WHERE a.app_name = 'fraud-detector';
    BEGIN
        PERFORM produce('notifications', 'note-blocked', jsonb_build_object('event','email','channel','email','recipient','user-9'), v_app_id, 301);
        RAISE EXCEPTION 'revoked app produce was allowed';
    EXCEPTION
        WHEN SQLSTATE 'CDT03' THEN NULL;
    END;
END $$;
SELECT set_application_status('fraud-detector', 'active');
DO $$
DECLARE v_app_id BIGINT;
BEGIN
    SELECT a.app_id INTO v_app_id FROM application a WHERE a.app_name = 'fraud-detector';
    PERFORM produce('notifications', 'note-restored', jsonb_build_object('event','email','channel','email','recipient','user-9'), v_app_id, 301);
END $$;

\echo '[8] group lifecycle: paused group cannot consume (CDT06), reactivated group can'
SELECT pause_group('email-workers');
DO $$
BEGIN
    BEGIN
        PERFORM consume('email-workers', 'notifications', 5, 60);
        RAISE EXCEPTION 'paused group consume was allowed';
    EXCEPTION
        WHEN SQLSTATE 'CDT06' THEN NULL;
    END;
END $$;
SELECT activate_group('email-workers');
SELECT jsonb_agg(jsonb_build_object('partition_id', partition_id, 'msg_offset', msg_offset)) AS email_loc
FROM consume('email-workers', 'notifications', 1, 60) \gset
SELECT ack('email-workers', :'email_loc'::JSONB) AS email_acked;

\echo '[9] topic lifecycle: archived topic rejects produce (CDT02), reactivated topic accepts'
SELECT archive_topic('user-activity');
DO $$
DECLARE v_app_id BIGINT;
BEGIN
    SELECT a.app_id INTO v_app_id FROM application a WHERE a.app_name = 'checkout-service';
    BEGIN
        PERFORM produce('user-activity', NULL, jsonb_build_object('event','click','user','user-1','page','/p1'), v_app_id, 1100);
        RAISE EXCEPTION 'archived topic produce was allowed';
    EXCEPTION
        WHEN SQLSTATE 'CDT02' THEN NULL;
    END;
END $$;
SELECT update_topic_config('user-activity', NULL, NULL, 'active');
DO $$
DECLARE v_app_id BIGINT;
BEGIN
    SELECT a.app_id INTO v_app_id FROM application a WHERE a.app_name = 'checkout-service';
    PERFORM produce('user-activity', NULL, jsonb_build_object('event','click','user','user-1','page','/p1'), v_app_id, 1100);
END $$;

\echo '[10] final state: matview refreshed and consistent, message ledger balances'
SELECT refresh_dashboard();
SELECT fn_assert((SELECT count(*) FROM message) = 1974, 'expected 1974 messages after purge + 4 new produces');
SELECT fn_assert((SELECT mv.pending FROM mv_topic_stats mv WHERE mv.topic_name = 'orders')
              = (SELECT vs.pending FROM v_topic_stats vs WHERE vs.topic_name = 'orders'), 'matview inconsistent after refresh');
SELECT * FROM mv_topic_stats ORDER BY topic_name;

\echo '================================================='
\echo ' M4 SMOKE TEST COMPLETE'
\echo '================================================='
