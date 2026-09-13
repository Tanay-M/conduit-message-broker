BEGIN;

CREATE FUNCTION trg_audit_message_insert() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner_id BIGINT;
BEGIN
    SELECT a.owner_user_id INTO v_owner_id FROM application a WHERE a.app_id = NEW.producer_app_id;
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (v_owner_id, NEW.producer_app_id, NEW.topic_id, 'PRODUCE', 'success',
            jsonb_build_object('partition_id', NEW.partition_id, 'msg_offset', NEW.msg_offset,
                               'key', NEW.msg_key, 'size_bytes', NEW.size_bytes, 'producer_seq', NEW.producer_seq));
    RETURN NEW;
END;
$$;
CREATE TRIGGER message_insert_audit AFTER INSERT ON message FOR EACH ROW EXECUTE FUNCTION trg_audit_message_insert();

CREATE FUNCTION trg_audit_message_delivered() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (NULL, NULL, NEW.topic_id, 'DELIVERED', 'success',
            jsonb_build_object('partition_id', NEW.partition_id, 'msg_offset', NEW.msg_offset,
                               'group_id', NEW.claimed_by));
    RETURN NEW;
END;
$$;
CREATE TRIGGER message_delivered_audit AFTER UPDATE ON message FOR EACH ROW
    WHEN (OLD.status = 'claimed' AND NEW.status = 'delivered')
    EXECUTE FUNCTION trg_audit_message_delivered();

CREATE FUNCTION trg_audit_dlq() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (NULL, NULL, NEW.original_topic_id, 'DLQ', 'success',
            jsonb_build_object('dlq_id', NEW.dlq_id, 'original_offset', NEW.original_offset,
                               'failed_group_id', NEW.failed_group_id, 'reason', NEW.failure_reason,
                               'attempts', NEW.attempts));
    RETURN NEW;
END;
$$;
CREATE TRIGGER dead_letter_insert_audit AFTER INSERT ON dead_letter_message FOR EACH ROW EXECUTE FUNCTION trg_audit_dlq();

CREATE FUNCTION trg_audit_access_grant() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (NEW.granted_by, NULL, NEW.topic_id, 'ACL_GRANT', 'success',
            jsonb_build_object('grantee_user_id', NEW.user_id, 'access_type', NEW.access_type));
    RETURN NEW;
END;
$$;
CREATE TRIGGER access_grant_audit AFTER INSERT ON access FOR EACH ROW EXECUTE FUNCTION trg_audit_access_grant();

CREATE FUNCTION trg_audit_access_revoke() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (NULL, NULL, OLD.topic_id, 'ACL_REVOKE', 'success',
            jsonb_build_object('revoked_user_id', OLD.user_id, 'access_type', OLD.access_type));
    RETURN OLD;
END;
$$;
CREATE TRIGGER access_revoke_audit AFTER DELETE ON access FOR EACH ROW EXECUTE FUNCTION trg_audit_access_revoke();

CREATE FUNCTION trg_audit_topic_create() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (NEW.created_by, NULL, NEW.topic_id, 'TOPIC_CREATE', 'success',
            jsonb_build_object('topic_name', NEW.topic_name));
    RETURN NEW;
END;
$$;
CREATE TRIGGER topic_insert_audit AFTER INSERT ON topic FOR EACH ROW EXECUTE FUNCTION trg_audit_topic_create();

CREATE FUNCTION trg_audit_schema_publish() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (NEW.created_by, NULL, NEW.topic_id, 'SCHEMA_PUBLISH', 'success',
            jsonb_build_object('version', NEW.version, 'status', NEW.status));
    RETURN NEW;
END;
$$;
CREATE TRIGGER schema_version_insert_audit AFTER INSERT ON schema_version FOR EACH ROW EXECUTE FUNCTION trg_audit_schema_publish();

CREATE FUNCTION trg_audit_config_change() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (NEW.updated_by, NULL, NULL, 'CONFIG_CHANGE', 'success',
            jsonb_build_object('config_key', NEW.config_key, 'old_value', OLD.config_value, 'new_value', NEW.config_value));
    RETURN NEW;
END;
$$;
CREATE TRIGGER broker_config_update_audit AFTER UPDATE ON broker_config FOR EACH ROW EXECUTE FUNCTION trg_audit_config_change();

CREATE FUNCTION trg_audit_config_create() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (NEW.updated_by, NULL, NULL, 'CONFIG_CHANGE', 'success',
            jsonb_build_object('config_key', NEW.config_key, 'old_value', NULL, 'new_value', NEW.config_value));
    RETURN NEW;
END;
$$;
CREATE TRIGGER broker_config_insert_audit AFTER INSERT ON broker_config FOR EACH ROW EXECUTE FUNCTION trg_audit_config_create();

CREATE FUNCTION trg_bump_updated_at() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER broker_config_bump_updated_at BEFORE UPDATE ON broker_config FOR EACH ROW EXECUTE FUNCTION trg_bump_updated_at();

CREATE FUNCTION trg_group_offset_monotonic() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.committed_offset < OLD.committed_offset THEN
        RAISE EXCEPTION 'committed_offset cannot regress from % to %', OLD.committed_offset, NEW.committed_offset
            USING ERRCODE = 'CDT19';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER group_offset_monotonic BEFORE UPDATE ON group_offset FOR EACH ROW EXECUTE FUNCTION trg_group_offset_monotonic();

CREATE FUNCTION trg_acl_produce() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner_id BIGINT;
    v_allowed BOOLEAN;
BEGIN
    SELECT a.owner_user_id INTO v_owner_id FROM application a WHERE a.app_id = NEW.producer_app_id;

    SELECT EXISTS (
        SELECT 1 FROM app_user u JOIN role r ON r.role_id = u.role_id
        WHERE u.user_id = v_owner_id
          AND u.status = 'active'
          AND (r.role_name = 'admin'
               OR EXISTS (SELECT 1 FROM access acc
                          WHERE acc.user_id = v_owner_id AND acc.topic_id = NEW.topic_id
                            AND acc.access_type = 'produce'))
    ) INTO v_allowed;

    IF NOT v_allowed THEN
        RAISE EXCEPTION 'produce access denied for application % on topic %', NEW.producer_app_id, NEW.topic_id
            USING ERRCODE = 'CDT17';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER message_produce_acl BEFORE INSERT ON message FOR EACH ROW EXECUTE FUNCTION trg_acl_produce();

CREATE FUNCTION trg_acl_consume() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_creator_id BIGINT;
    v_allowed BOOLEAN;
BEGIN
    SELECT cg.created_by INTO v_creator_id FROM consumer_group cg WHERE cg.group_id = NEW.claimed_by;
    IF v_creator_id IS NULL THEN
        RAISE EXCEPTION 'claim by unknown consumer group %', NEW.claimed_by USING ERRCODE = 'CDT06';
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM app_user u JOIN role r ON r.role_id = u.role_id
        WHERE u.user_id = v_creator_id
          AND u.status = 'active'
          AND (r.role_name = 'admin'
               OR EXISTS (SELECT 1 FROM access acc
                          WHERE acc.user_id = v_creator_id AND acc.topic_id = NEW.topic_id
                            AND acc.access_type = 'consume'))
    ) INTO v_allowed;

    IF NOT v_allowed THEN
        RAISE EXCEPTION 'consume access denied for group % on topic %', NEW.claimed_by, NEW.topic_id
            USING ERRCODE = 'CDT18';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER message_consume_acl BEFORE UPDATE ON message FOR EACH ROW
    WHEN (OLD.status = 'pending' AND NEW.status = 'claimed')
    EXECUTE FUNCTION trg_acl_consume();

CREATE FUNCTION trg_notify_message() RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM pg_notify('conduit_events',
        jsonb_build_object('event', 'PRODUCE', 'topic_id', NEW.topic_id,
                           'partition_id', NEW.partition_id, 'msg_offset', NEW.msg_offset)::text);
    RETURN NEW;
END;
$$;
CREATE TRIGGER message_notify AFTER INSERT ON message FOR EACH ROW EXECUTE FUNCTION trg_notify_message();

CREATE FUNCTION log_auth_failure(p_user_id BIGINT, p_app_id BIGINT, p_topic_id BIGINT, p_details JSONB) RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO audit_log (user_id, app_id, topic_id, event_type, status, details)
    VALUES (p_user_id, p_app_id, p_topic_id, 'AUTH_FAIL', 'failure', p_details);
END;
$$;

COMMIT;
