BEGIN;

CREATE ROLE conduit_app LOGIN PASSWORD 'conduit_app_dev';

GRANT USAGE ON SCHEMA public TO conduit_app;

GRANT SELECT, INSERT, UPDATE ON message TO conduit_app;
GRANT SELECT, INSERT, UPDATE ON dead_letter_message TO conduit_app;
GRANT SELECT, UPDATE ON partition TO conduit_app;
GRANT SELECT, INSERT, UPDATE ON group_offset TO conduit_app;
GRANT SELECT, INSERT ON producer_sequence TO conduit_app;
GRANT INSERT ON audit_log TO conduit_app;
GRANT SELECT ON topic, schema_version, consumer_group, group_subscription,
               app_user, application, role, access, broker_config TO conduit_app;
GRANT USAGE ON SEQUENCE audit_log_log_id_seq, dead_letter_message_dlq_id_seq TO conduit_app;

REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE conduit IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

GRANT EXECUTE ON FUNCTION produce(TEXT, TEXT, JSONB, BIGINT, BIGINT) TO conduit_app;
GRANT EXECUTE ON FUNCTION produce_batch(TEXT, JSONB, BIGINT) TO conduit_app;
GRANT EXECUTE ON FUNCTION consume(TEXT, TEXT, INTEGER, INTEGER) TO conduit_app;
GRANT EXECUTE ON FUNCTION ack(TEXT, JSONB) TO conduit_app;
GRANT EXECUTE ON FUNCTION nack(TEXT, JSONB, TEXT) TO conduit_app;
GRANT EXECUTE ON FUNCTION validate_schema(JSONB, JSONB) TO conduit_app;
GRANT EXECUTE ON FUNCTION log_auth_failure(BIGINT, BIGINT, BIGINT, JSONB) TO conduit_app;

CREATE FUNCTION fn_user_can_read(p_user_id BIGINT, p_topic_id BIGINT) RETURNS BOOLEAN
LANGUAGE sql STABLE
AS $$
    SELECT p_user_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM app_user u JOIN role r ON r.role_id = u.role_id
        WHERE u.user_id = p_user_id
          AND u.status = 'active'
          AND (r.role_name = 'admin'
               OR EXISTS (SELECT 1 FROM access a
                          WHERE a.user_id = p_user_id AND a.topic_id = p_topic_id))
    )
$$;

CREATE FUNCTION fn_user_can_produce(p_user_id BIGINT, p_topic_id BIGINT) RETURNS BOOLEAN
LANGUAGE sql STABLE
AS $$
    SELECT p_user_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM app_user u JOIN role r ON r.role_id = u.role_id
        WHERE u.user_id = p_user_id
          AND u.status = 'active'
          AND (r.role_name = 'admin'
               OR EXISTS (SELECT 1 FROM access a
                          WHERE a.user_id = p_user_id AND a.topic_id = p_topic_id
                            AND a.access_type = 'produce'))
    )
$$;

CREATE FUNCTION fn_user_can_consume(p_user_id BIGINT, p_topic_id BIGINT) RETURNS BOOLEAN
LANGUAGE sql STABLE
AS $$
    SELECT p_user_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM app_user u JOIN role r ON r.role_id = u.role_id
        WHERE u.user_id = p_user_id
          AND u.status = 'active'
          AND (r.role_name = 'admin'
               OR EXISTS (SELECT 1 FROM access a
                          WHERE a.user_id = p_user_id AND a.topic_id = p_topic_id
                            AND a.access_type = 'consume'))
    )
$$;

GRANT EXECUTE ON FUNCTION fn_user_can_read(BIGINT, BIGINT) TO conduit_app;
GRANT EXECUTE ON FUNCTION fn_user_can_produce(BIGINT, BIGINT) TO conduit_app;
GRANT EXECUTE ON FUNCTION fn_user_can_consume(BIGINT, BIGINT) TO conduit_app;

ALTER TABLE message ENABLE ROW LEVEL SECURITY;
ALTER TABLE dead_letter_message ENABLE ROW LEVEL SECURITY;

CREATE POLICY message_select ON message FOR SELECT TO conduit_app
    USING (fn_user_can_read(NULLIF(current_setting('app.user_id', true), '')::BIGINT, topic_id));

CREATE POLICY message_insert ON message FOR INSERT TO conduit_app
    WITH CHECK (fn_user_can_produce(NULLIF(current_setting('app.user_id', true), '')::BIGINT, topic_id));

CREATE POLICY message_update ON message FOR UPDATE TO conduit_app
    USING (fn_user_can_consume(NULLIF(current_setting('app.user_id', true), '')::BIGINT, topic_id))
    WITH CHECK (fn_user_can_consume(NULLIF(current_setting('app.user_id', true), '')::BIGINT, topic_id));

CREATE POLICY dlq_select ON dead_letter_message FOR SELECT TO conduit_app
    USING (fn_user_can_read(NULLIF(current_setting('app.user_id', true), '')::BIGINT, original_topic_id));

CREATE POLICY dlq_insert ON dead_letter_message FOR INSERT TO conduit_app
    WITH CHECK (fn_user_can_consume(NULLIF(current_setting('app.user_id', true), '')::BIGINT, original_topic_id));

COMMIT;
