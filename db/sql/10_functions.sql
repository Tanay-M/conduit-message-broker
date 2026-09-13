BEGIN;

CREATE SEQUENCE dlq_requeue_seq START 1000000;

CREATE FUNCTION validate_schema(p_payload JSONB, p_definition JSONB) RETURNS BOOLEAN
LANGUAGE sql
AS $$
    SELECT p_payload IS NOT NULL
       AND jsonb_typeof(p_payload) = 'object'
       AND (
           NOT p_definition ? 'required'
           OR NOT EXISTS (
               SELECT 1
               FROM jsonb_array_elements_text(p_definition->'required') AS r(required_key)
               WHERE NOT p_payload ? r.required_key
           )
       )
$$;

CREATE FUNCTION register_user(p_username TEXT, p_email TEXT, p_role_name TEXT) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id BIGINT;
BEGIN
    INSERT INTO app_user (username, email, role_id)
    SELECT p_username, p_email, r.role_id
    FROM role r
    WHERE r.role_name = p_role_name
    RETURNING app_user.user_id INTO v_user_id;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'unknown role %', p_role_name USING ERRCODE = 'CDT11';
    END IF;
    RETURN v_user_id;
END;
$$;

CREATE FUNCTION register_application(p_app_name TEXT, p_owner_username TEXT, p_app_type TEXT)
RETURNS TABLE(app_id BIGINT, api_key UUID)
LANGUAGE plpgsql
AS $$
DECLARE
    v_app_id BIGINT;
    v_api_key UUID;
BEGIN
    IF p_app_type NOT IN ('producer', 'consumer', 'both') THEN
        RAISE EXCEPTION 'app_type must be producer, consumer or both' USING ERRCODE = 'CDT15';
    END IF;

    INSERT INTO application (app_name, owner_user_id, app_type)
    SELECT p_app_name, u.user_id, p_app_type
    FROM app_user u
    WHERE u.username = p_owner_username
    RETURNING application.app_id, application.api_key INTO v_app_id, v_api_key;

    IF v_app_id IS NULL THEN
        RAISE EXCEPTION 'unknown user %', p_owner_username USING ERRCODE = 'CDT12';
    END IF;
    RETURN QUERY VALUES (v_app_id, v_api_key);
END;
$$;

CREATE FUNCTION create_topic(p_topic_name TEXT, p_description TEXT, p_partition_count INT, p_schema JSONB, p_owner_username TEXT) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_topic_id BIGINT;
    v_owner_id BIGINT;
    v_i INT;
BEGIN
    IF p_partition_count IS NULL OR p_partition_count < 1 OR p_partition_count > 64 THEN
        RAISE EXCEPTION 'partition count must be between 1 and 64' USING ERRCODE = 'CDT13';
    END IF;

    SELECT u.user_id INTO v_owner_id FROM app_user u WHERE u.username = p_owner_username;
    IF v_owner_id IS NULL THEN
        RAISE EXCEPTION 'unknown user %', p_owner_username USING ERRCODE = 'CDT12';
    END IF;

    INSERT INTO topic (topic_name, description, created_by)
    VALUES (p_topic_name, p_description, v_owner_id)
    RETURNING topic.topic_id INTO v_topic_id;

    FOR v_i IN 0 .. p_partition_count - 1 LOOP
        INSERT INTO partition (topic_id, partition_number) VALUES (v_topic_id, v_i);
    END LOOP;

    IF p_schema IS NOT NULL THEN
        INSERT INTO schema_version (topic_id, version, definition, created_by)
        VALUES (v_topic_id, 1, p_schema, v_owner_id);
    END IF;
    RETURN v_topic_id;
END;
$$;

CREATE FUNCTION create_group(p_group_name TEXT, p_created_by_username TEXT, p_max_delivery_attempts INT DEFAULT 3) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_group_id BIGINT;
    v_user_id BIGINT;
BEGIN
    SELECT u.user_id INTO v_user_id FROM app_user u WHERE u.username = p_created_by_username;
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'unknown user %', p_created_by_username USING ERRCODE = 'CDT12';
    END IF;

    INSERT INTO consumer_group (group_name, created_by, max_delivery_attempts)
    VALUES (p_group_name, v_user_id, p_max_delivery_attempts)
    RETURNING consumer_group.group_id INTO v_group_id;
    RETURN v_group_id;
END;
$$;

CREATE FUNCTION subscribe_group(p_group_name TEXT, p_topic_name TEXT) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_group_id BIGINT;
    v_topic_id BIGINT;
    v_partitions INT;
BEGIN
    SELECT cg.group_id INTO v_group_id FROM consumer_group cg WHERE cg.group_name = p_group_name;
    IF v_group_id IS NULL THEN
        RAISE EXCEPTION 'unknown group %', p_group_name USING ERRCODE = 'CDT06';
    END IF;

    SELECT t.topic_id INTO v_topic_id FROM topic t WHERE t.topic_name = p_topic_name;
    IF v_topic_id IS NULL THEN
        RAISE EXCEPTION 'unknown topic %', p_topic_name USING ERRCODE = 'CDT01';
    END IF;

    INSERT INTO group_subscription (group_id, topic_id)
    VALUES (v_group_id, v_topic_id)
    ON CONFLICT DO NOTHING;

    INSERT INTO group_offset (group_id, partition_id, committed_offset)
    SELECT v_group_id, pt.partition_id, 0
    FROM partition pt
    WHERE pt.topic_id = v_topic_id
    ON CONFLICT DO NOTHING;

    SELECT count(*) INTO v_partitions FROM group_offset go WHERE go.group_id = v_group_id AND go.partition_id IN (SELECT pt.partition_id FROM partition pt WHERE pt.topic_id = v_topic_id);
    RETURN v_partitions;
END;
$$;

CREATE FUNCTION grant_access(p_username TEXT, p_topic_name TEXT, p_access_type TEXT, p_granted_by_username TEXT) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id BIGINT;
    v_topic_id BIGINT;
    v_grantor_id BIGINT;
    v_access_id BIGINT;
BEGIN
    SELECT u.user_id INTO v_user_id FROM app_user u WHERE u.username = p_username;
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'unknown user %', p_username USING ERRCODE = 'CDT12';
    END IF;

    SELECT t.topic_id INTO v_topic_id FROM topic t WHERE t.topic_name = p_topic_name;
    IF v_topic_id IS NULL THEN
        RAISE EXCEPTION 'unknown topic %', p_topic_name USING ERRCODE = 'CDT01';
    END IF;

    SELECT u.user_id INTO v_grantor_id FROM app_user u WHERE u.username = p_granted_by_username;
    IF v_grantor_id IS NULL THEN
        RAISE EXCEPTION 'unknown user %', p_granted_by_username USING ERRCODE = 'CDT12';
    END IF;

    INSERT INTO access (user_id, topic_id, access_type, granted_by)
    VALUES (v_user_id, v_topic_id, p_access_type, v_grantor_id)
    ON CONFLICT (user_id, topic_id, access_type) DO NOTHING;

    SELECT a.access_id INTO v_access_id FROM access a
    WHERE a.user_id = v_user_id AND a.topic_id = v_topic_id AND a.access_type = p_access_type;
    RETURN v_access_id;
END;
$$;

CREATE FUNCTION revoke_access(p_username TEXT, p_topic_name TEXT, p_access_type TEXT) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted INT;
BEGIN
    DELETE FROM access a
    USING app_user u, topic t
    WHERE a.user_id = u.user_id
      AND a.topic_id = t.topic_id
      AND u.username = p_username
      AND t.topic_name = p_topic_name
      AND a.access_type = p_access_type;
    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$;

CREATE FUNCTION update_broker_config(p_config_key TEXT, p_config_value TEXT, p_description TEXT DEFAULT NULL, p_updated_by_username TEXT DEFAULT NULL) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id BIGINT;
BEGIN
    SELECT u.user_id INTO v_user_id FROM app_user u WHERE u.username = p_updated_by_username;
    INSERT INTO broker_config (config_key, config_value, description, updated_by)
    VALUES (p_config_key, p_config_value, p_description, v_user_id)
    ON CONFLICT (config_key)
    DO UPDATE SET config_value = EXCLUDED.config_value,
                  description = COALESCE(EXCLUDED.description, broker_config.description),
                  updated_by = EXCLUDED.updated_by,
                  updated_at = now();
END;
$$;

CREATE FUNCTION produce(p_topic_name TEXT, p_msg_key TEXT, p_payload JSONB, p_producer_app_id BIGINT, p_producer_seq BIGINT)
RETURNS TABLE(loc_topic_id BIGINT, loc_partition_id BIGINT, loc_msg_offset BIGINT, is_duplicate BOOLEAN)
LANGUAGE plpgsql
AS $$
DECLARE
    v_topic_id BIGINT;
    v_max_bytes INT;
    v_schema JSONB;
    v_partition_id BIGINT;
    v_partition_count INT;
    v_msg_offset BIGINT;
    v_size INT;
    v_ledger_topic_id BIGINT;
    v_ledger_partition_id BIGINT;
    v_ledger_msg_offset BIGINT;
BEGIN
    SELECT t.topic_id, t.max_message_bytes INTO v_topic_id, v_max_bytes
    FROM topic t
    WHERE t.topic_name = p_topic_name AND t.status = 'active';

    IF v_topic_id IS NULL THEN
        IF EXISTS (SELECT 1 FROM topic t WHERE t.topic_name = p_topic_name) THEN
            RAISE EXCEPTION 'topic % is not active', p_topic_name USING ERRCODE = 'CDT02';
        END IF;
        RAISE EXCEPTION 'unknown topic %', p_topic_name USING ERRCODE = 'CDT01';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM application a WHERE a.app_id = p_producer_app_id AND a.status = 'active') THEN
        RAISE EXCEPTION 'unknown or revoked application %', p_producer_app_id USING ERRCODE = 'CDT03';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM application a WHERE a.app_id = p_producer_app_id AND a.app_type IN ('producer', 'both')) THEN
        RAISE EXCEPTION 'application % is registered as consumer-only and cannot produce', p_producer_app_id USING ERRCODE = 'CDT20';
    END IF;

    PERFORM pg_advisory_xact_lock(p_producer_app_id::int, p_producer_seq::int);

    SELECT ps.topic_id, ps.partition_id, ps.msg_offset
    INTO v_ledger_topic_id, v_ledger_partition_id, v_ledger_msg_offset
    FROM producer_sequence ps
    WHERE ps.producer_app_id = p_producer_app_id AND ps.producer_seq = p_producer_seq;

    IF FOUND THEN
        RETURN QUERY VALUES (v_ledger_topic_id, v_ledger_partition_id, v_ledger_msg_offset, TRUE);
        RETURN;
    END IF;

    SELECT sv.definition INTO v_schema
    FROM schema_version sv
    WHERE sv.topic_id = v_topic_id AND sv.status = 'active'
    ORDER BY sv.version DESC
    LIMIT 1;

    IF v_schema IS NOT NULL AND NOT validate_schema(p_payload, v_schema) THEN
        RAISE EXCEPTION 'payload violates active schema of topic %', p_topic_name USING ERRCODE = 'CDT04';
    END IF;

    v_size := octet_length(p_payload::text);
    IF v_size > v_max_bytes THEN
        RAISE EXCEPTION 'payload size % exceeds limit % of topic %', v_size, v_max_bytes, p_topic_name USING ERRCODE = 'CDT05';
    END IF;

    SELECT count(*) INTO v_partition_count FROM partition pt WHERE pt.topic_id = v_topic_id;
    IF v_partition_count = 0 THEN
        RAISE EXCEPTION 'topic % has no partitions', p_topic_name USING ERRCODE = 'CDT09';
    END IF;

    IF p_msg_key IS NULL THEN
        SELECT pt.partition_id INTO v_partition_id
        FROM partition pt
        WHERE pt.topic_id = v_topic_id
        ORDER BY pt.next_offset, pt.partition_number
        LIMIT 1;
    ELSE
        SELECT pt.partition_id INTO v_partition_id
        FROM partition pt
        WHERE pt.topic_id = v_topic_id
          AND pt.partition_number = abs(hashtext(p_msg_key)) % v_partition_count;
    END IF;

    SELECT pt.next_offset INTO v_msg_offset
    FROM partition pt
    WHERE pt.partition_id = v_partition_id
    FOR UPDATE;

    UPDATE partition SET next_offset = v_msg_offset + 1 WHERE partition.partition_id = v_partition_id;

    INSERT INTO message (topic_id, partition_id, msg_offset, msg_key, payload, size_bytes, producer_app_id, producer_seq, status)
    VALUES (v_topic_id, v_partition_id, v_msg_offset, p_msg_key, p_payload, v_size, p_producer_app_id, p_producer_seq, 'pending');

    INSERT INTO producer_sequence (producer_app_id, producer_seq, topic_id, partition_id, msg_offset)
    VALUES (p_producer_app_id, p_producer_seq, v_topic_id, v_partition_id, v_msg_offset);

    RETURN QUERY VALUES (v_topic_id, v_partition_id, v_msg_offset, FALSE);
END;
$$;

CREATE FUNCTION produce_batch(p_topic_name TEXT, p_messages JSONB, p_producer_app_id BIGINT)
RETURNS TABLE(producer_seq BIGINT, loc_topic_id BIGINT, loc_partition_id BIGINT, loc_msg_offset BIGINT, is_duplicate BOOLEAN)
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT t.seq, t.key, t.payload
             FROM jsonb_to_recordset(p_messages) AS t(seq BIGINT, key TEXT, payload JSONB)
    LOOP
        RETURN QUERY SELECT r.seq, p.loc_topic_id, p.loc_partition_id, p.loc_msg_offset, p.is_duplicate
                     FROM produce(p_topic_name, r.key, r.payload, p_producer_app_id, r.seq) p;
    END LOOP;
END;
$$;

CREATE FUNCTION consume(p_group_name TEXT, p_topic_name TEXT, p_batch_size INT, p_visibility_timeout_s INT DEFAULT 30)
RETURNS TABLE(partition_id BIGINT, msg_offset BIGINT, msg_key TEXT, payload JSONB, attempts INT, visible_until TIMESTAMPTZ)
LANGUAGE plpgsql
AS $$
DECLARE
    v_group_id BIGINT;
    v_topic_id BIGINT;
    v_batch INT;
    v_timeout INT;
BEGIN
    SELECT cg.group_id INTO v_group_id FROM consumer_group cg WHERE cg.group_name = p_group_name AND cg.status = 'active';
    IF v_group_id IS NULL THEN
        RAISE EXCEPTION 'unknown or inactive group %', p_group_name USING ERRCODE = 'CDT06';
    END IF;

    SELECT t.topic_id INTO v_topic_id FROM topic t WHERE t.topic_name = p_topic_name AND t.status = 'active';
    IF v_topic_id IS NULL THEN
        RAISE EXCEPTION 'unknown or inactive topic %', p_topic_name USING ERRCODE = 'CDT02';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM group_subscription gs WHERE gs.group_id = v_group_id AND gs.topic_id = v_topic_id) THEN
        RAISE EXCEPTION 'group % is not subscribed to topic %', p_group_name, p_topic_name USING ERRCODE = 'CDT07';
    END IF;

    INSERT INTO group_offset (group_id, partition_id, committed_offset)
    SELECT v_group_id, pt.partition_id, 0
    FROM partition pt
    WHERE pt.topic_id = v_topic_id
    ON CONFLICT DO NOTHING;

    v_batch := GREATEST(LEAST(COALESCE(p_batch_size, 1), 1000), 1);
    v_timeout := GREATEST(LEAST(COALESCE(p_visibility_timeout_s, 30), 3600), 1);

    RETURN QUERY
    WITH candidates AS (
        SELECT m.created_at, m.partition_id, m.msg_offset
        FROM message m
        WHERE m.topic_id = v_topic_id
          AND m.status = 'pending'
          AND (m.visible_at IS NULL OR m.visible_at <= now())
        ORDER BY m.msg_offset
        LIMIT v_batch
        FOR UPDATE SKIP LOCKED
    )
    UPDATE message m
    SET status = 'claimed',
        claimed_by = v_group_id,
        visible_at = now() + make_interval(secs => v_timeout),
        attempts = m.attempts + 1
    FROM candidates c
    WHERE m.created_at = c.created_at
      AND m.topic_id = v_topic_id
      AND m.partition_id = c.partition_id
      AND m.msg_offset = c.msg_offset
    RETURNING m.partition_id, m.msg_offset, m.msg_key::TEXT, m.payload, m.attempts, m.visible_at;
END;
$$;

CREATE FUNCTION ack(p_group_name TEXT, p_locations JSONB) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_group_id BIGINT;
    v_acked INT;
BEGIN
    SELECT cg.group_id INTO v_group_id FROM consumer_group cg WHERE cg.group_name = p_group_name;
    IF v_group_id IS NULL THEN
        RAISE EXCEPTION 'unknown group %', p_group_name USING ERRCODE = 'CDT06';
    END IF;

    WITH loc AS (
        SELECT (e.partition_id)::BIGINT AS partition_id, (e.msg_offset)::BIGINT AS msg_offset
        FROM jsonb_to_recordset(COALESCE(p_locations, '[]'::JSONB)) AS e(partition_id BIGINT, msg_offset BIGINT)
    ),
    upd AS (
        UPDATE message m
        SET status = 'delivered'
        FROM loc
        WHERE m.claimed_by = v_group_id
          AND m.status = 'claimed'
          AND m.partition_id = loc.partition_id
          AND m.msg_offset = loc.msg_offset
        RETURNING m.partition_id AS acked_partition_id, m.msg_offset AS acked_msg_offset
    )
    INSERT INTO group_offset (group_id, partition_id, committed_offset)
    SELECT v_group_id, upd.acked_partition_id, max(upd.acked_msg_offset) + 1
    FROM upd
    GROUP BY upd.acked_partition_id
    ON CONFLICT (group_id, partition_id)
    DO UPDATE SET committed_offset = GREATEST(group_offset.committed_offset, EXCLUDED.committed_offset),
                  updated_at = now();

    SELECT count(*) INTO v_acked
    FROM jsonb_to_recordset(COALESCE(p_locations, '[]'::JSONB)) AS e(partition_id BIGINT, msg_offset BIGINT)
    JOIN message m ON m.partition_id = e.partition_id AND m.msg_offset = e.msg_offset
    WHERE m.status = 'delivered';

    RETURN v_acked;
END;
$$;

CREATE FUNCTION nack(p_group_name TEXT, p_locations JSONB, p_reason TEXT DEFAULT 'consumer rejected')
RETURNS TABLE(retried INT, dead INT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_group_id BIGINT;
    v_max_attempts INT;
    v_retried INT;
    v_dead INT;
BEGIN
    SELECT cg.group_id, cg.max_delivery_attempts INTO v_group_id, v_max_attempts
    FROM consumer_group cg
    WHERE cg.group_name = p_group_name;
    IF v_group_id IS NULL THEN
        RAISE EXCEPTION 'unknown group %', p_group_name USING ERRCODE = 'CDT06';
    END IF;

    UPDATE message m
    SET status = 'pending', visible_at = NULL, claimed_by = NULL
    FROM jsonb_to_recordset(COALESCE(p_locations, '[]'::JSONB)) AS e(partition_id BIGINT, msg_offset BIGINT)
    WHERE m.claimed_by = v_group_id
      AND m.status = 'claimed'
      AND m.partition_id = e.partition_id
      AND m.msg_offset = e.msg_offset
      AND m.attempts < v_max_attempts;
    GET DIAGNOSTICS v_retried = ROW_COUNT;

    WITH doomed AS (
        SELECT m.topic_id, m.partition_id, m.msg_offset, m.msg_key, m.payload, m.attempts
        FROM message m
        JOIN jsonb_to_recordset(COALESCE(p_locations, '[]'::JSONB)) AS e(partition_id BIGINT, msg_offset BIGINT)
          ON m.partition_id = e.partition_id AND m.msg_offset = e.msg_offset
        WHERE m.claimed_by = v_group_id
          AND m.status = 'claimed'
          AND m.attempts >= v_max_attempts
        FOR UPDATE SKIP LOCKED
    )
    INSERT INTO dead_letter_message (original_topic_id, original_offset, msg_key, payload, failed_group_id, failure_reason, attempts)
    SELECT doomed.topic_id, doomed.msg_offset, doomed.msg_key, doomed.payload, v_group_id, p_reason, doomed.attempts
    FROM doomed;
    GET DIAGNOSTICS v_dead = ROW_COUNT;

    UPDATE message m
    SET status = 'dead', claimed_by = NULL
    FROM jsonb_to_recordset(COALESCE(p_locations, '[]'::JSONB)) AS e(partition_id BIGINT, msg_offset BIGINT)
    WHERE m.claimed_by = v_group_id
      AND m.status = 'claimed'
      AND m.partition_id = e.partition_id
      AND m.msg_offset = e.msg_offset;

    RETURN QUERY VALUES (v_retried, v_dead);
END;
$$;

CREATE FUNCTION reap_expired_claims()
RETURNS TABLE(requeued INT, dead INT)
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_requeued INT := 0;
    v_dead INT := 0;
BEGIN
    FOR r IN
        SELECT m.created_at, m.topic_id, m.partition_id, m.msg_offset, m.msg_key, m.payload,
               m.attempts, m.claimed_by, cg.max_delivery_attempts
        FROM message m
        JOIN consumer_group cg ON cg.group_id = m.claimed_by
        WHERE m.status = 'claimed' AND m.visible_at < now()
        FOR UPDATE OF m SKIP LOCKED
    LOOP
        IF r.attempts >= r.max_delivery_attempts THEN
            INSERT INTO dead_letter_message (original_topic_id, original_offset, msg_key, payload, failed_group_id, failure_reason, attempts)
            VALUES (r.topic_id, r.msg_offset, r.msg_key, r.payload, r.claimed_by, 'visibility timeout', r.attempts);

            UPDATE message m
            SET status = 'dead', claimed_by = NULL
            WHERE m.created_at = r.created_at AND m.topic_id = r.topic_id
              AND m.partition_id = r.partition_id AND m.msg_offset = r.msg_offset;
            v_dead := v_dead + 1;
        ELSE
            UPDATE message m
            SET status = 'pending', visible_at = NULL, claimed_by = NULL
            WHERE m.created_at = r.created_at AND m.topic_id = r.topic_id
              AND m.partition_id = r.partition_id AND m.msg_offset = r.msg_offset;
            v_requeued := v_requeued + 1;
        END IF;
    END LOOP;
    RETURN QUERY VALUES (v_requeued, v_dead);
END;
$$;

CREATE FUNCTION requeue_dlq(p_dlq_id BIGINT, p_producer_app_id BIGINT, p_target_topic_name TEXT DEFAULT NULL)
RETURNS TABLE(dlq_id BIGINT, requeued BOOLEAN, loc_topic_id BIGINT, loc_partition_id BIGINT, loc_msg_offset BIGINT)
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_target TEXT;
    v_loc RECORD;
BEGIN
    SELECT * INTO r FROM dead_letter_message d WHERE d.dlq_id = p_dlq_id AND d.status = 'pending';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'dlq entry % not found or not pending', p_dlq_id USING ERRCODE = 'CDT14';
    END IF;

    IF p_target_topic_name IS NOT NULL THEN
        v_target := p_target_topic_name;
    ELSE
        SELECT t.topic_name INTO v_target FROM topic t WHERE t.topic_id = r.original_topic_id;
    END IF;
    IF v_target IS NULL THEN
        RAISE EXCEPTION 'cannot resolve target topic for dlq entry %', p_dlq_id USING ERRCODE = 'CDT01';
    END IF;

    SELECT * INTO v_loc FROM produce(v_target, r.msg_key, r.payload, p_producer_app_id, nextval('dlq_requeue_seq'));

    UPDATE dead_letter_message d SET status = 'requeued' WHERE d.dlq_id = p_dlq_id;

    RETURN QUERY VALUES (p_dlq_id, TRUE, v_loc.loc_topic_id, v_loc.loc_partition_id, v_loc.loc_msg_offset);
END;
$$;

CREATE FUNCTION purge_retention(p_topic_name TEXT DEFAULT NULL) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_deleted BIGINT := 0;
    v_batch_deleted INT;
BEGIN
    FOR r IN SELECT t.topic_id, t.retention_days
             FROM topic t
             WHERE (p_topic_name IS NULL OR t.topic_name = p_topic_name)
    LOOP
        DELETE FROM message m
        WHERE m.topic_id = r.topic_id
          AND m.created_at < now() - make_interval(days => r.retention_days);
        GET DIAGNOSTICS v_batch_deleted = ROW_COUNT;
        v_deleted := v_deleted + v_batch_deleted;
    END LOOP;
    RETURN v_deleted;
END;
$$;

CREATE FUNCTION drop_old_partitions(p_keep_days INT DEFAULT 90) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_dropped INT := 0;
BEGIN
    FOR r IN
        SELECT c.relname AS part_name,
               substring(pg_get_expr(c.relpartbound, c.oid) FROM 'TO \(''([^'']+)''\)')::TIMESTAMPTZ AS upper_bound
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        WHERE i.inhparent = 'message'::regclass
          AND c.relname <> 'message_default'
    LOOP
        IF r.upper_bound < now() - make_interval(days => GREATEST(COALESCE(p_keep_days, 90), 1)) THEN
            EXECUTE format('ALTER TABLE message DETACH PARTITION %I', r.part_name);
            EXECUTE format('DROP TABLE %I', r.part_name);
            v_dropped := v_dropped + 1;
        END IF;
    END LOOP;
    RETURN v_dropped;
END;
$$;

CREATE FUNCTION create_monthly_partition(p_any_day_in_month DATE) RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_from TIMESTAMPTZ := date_trunc('month', p_any_day_in_month::TIMESTAMP);
    v_to TIMESTAMPTZ := date_trunc('month', p_any_day_in_month::TIMESTAMP) + interval '1 month';
    v_name TEXT := 'message_' || to_char(v_from, 'YYYY_MM');
BEGIN
    IF to_regclass(v_name) IS NOT NULL THEN
        RETURN v_name;
    END IF;

    IF EXISTS (SELECT 1 FROM message_default d WHERE d.created_at >= v_from AND d.created_at < v_to LIMIT 1) THEN
        RAISE EXCEPTION 'rows for % already live in message_default; move them before creating %', v_from, v_name USING ERRCODE = 'CDT16';
    END IF;

    EXECUTE format('CREATE TABLE %I PARTITION OF message FOR VALUES FROM (%L) TO (%L)', v_name, v_from, v_to);
    RETURN v_name;
END;
$$;

CREATE FUNCTION topic_stats(p_topic_name TEXT)
RETURNS TABLE(pending BIGINT, claimed BIGINT, delivered BIGINT, dead BIGINT, dlq_pending BIGINT, oldest_pending TIMESTAMPTZ, produced_last_hour BIGINT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_topic_id BIGINT;
BEGIN
    SELECT t.topic_id INTO v_topic_id FROM topic t WHERE t.topic_name = p_topic_name;
    IF v_topic_id IS NULL THEN
        RAISE EXCEPTION 'unknown topic %', p_topic_name USING ERRCODE = 'CDT01';
    END IF;

    RETURN QUERY
    SELECT count(*) FILTER (WHERE m.status = 'pending'),
           count(*) FILTER (WHERE m.status = 'claimed'),
           count(*) FILTER (WHERE m.status = 'delivered'),
           count(*) FILTER (WHERE m.status = 'dead'),
           (SELECT count(*) FROM dead_letter_message d WHERE d.original_topic_id = v_topic_id AND d.status = 'pending'),
           min(m.created_at) FILTER (WHERE m.status = 'pending'),
           count(*) FILTER (WHERE m.created_at >= now() - interval '1 hour')
    FROM message m
    WHERE m.topic_id = v_topic_id;
END;
$$;

CREATE FUNCTION suspend_user(p_username TEXT) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id BIGINT;
BEGIN
    SELECT u.user_id INTO v_user_id FROM app_user u WHERE u.username = p_username;
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'unknown user %', p_username USING ERRCODE = 'CDT12';
    END IF;
    UPDATE app_user SET status = 'suspended' WHERE app_user.user_id = v_user_id;
END;
$$;

CREATE FUNCTION activate_user(p_username TEXT) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id BIGINT;
BEGIN
    SELECT u.user_id INTO v_user_id FROM app_user u WHERE u.username = p_username;
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'unknown user %', p_username USING ERRCODE = 'CDT12';
    END IF;
    UPDATE app_user SET status = 'active' WHERE app_user.user_id = v_user_id;
END;
$$;

CREATE FUNCTION set_application_status(p_app_name TEXT, p_status TEXT) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_app_id BIGINT;
BEGIN
    IF p_status NOT IN ('active', 'revoked') THEN
        RAISE EXCEPTION 'application status must be active or revoked' USING ERRCODE = 'CDT15';
    END IF;
    SELECT a.app_id INTO v_app_id FROM application a WHERE a.app_name = p_app_name;
    IF v_app_id IS NULL THEN
        RAISE EXCEPTION 'unknown application %', p_app_name USING ERRCODE = 'CDT03';
    END IF;
    UPDATE application SET status = p_status WHERE application.app_id = v_app_id;
END;
$$;

CREATE FUNCTION update_topic_config(p_topic_name TEXT, p_retention_days INT DEFAULT NULL, p_max_message_bytes INT DEFAULT NULL, p_status TEXT DEFAULT NULL) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_topic_id BIGINT;
BEGIN
    IF p_retention_days IS NOT NULL AND (p_retention_days < 1 OR p_retention_days > 3650) THEN
        RAISE EXCEPTION 'retention_days must be between 1 and 3650' USING ERRCODE = 'CDT13';
    END IF;
    IF p_status IS NOT NULL AND p_status NOT IN ('active', 'archived') THEN
        RAISE EXCEPTION 'topic status must be active or archived' USING ERRCODE = 'CDT15';
    END IF;

    SELECT t.topic_id INTO v_topic_id FROM topic t WHERE t.topic_name = p_topic_name;
    IF v_topic_id IS NULL THEN
        RAISE EXCEPTION 'unknown topic %', p_topic_name USING ERRCODE = 'CDT01';
    END IF;

    UPDATE topic
    SET retention_days = COALESCE(p_retention_days, retention_days),
        max_message_bytes = COALESCE(p_max_message_bytes, max_message_bytes),
        status = COALESCE(p_status, status)
    WHERE topic.topic_id = v_topic_id;
END;
$$;

CREATE FUNCTION archive_topic(p_topic_name TEXT) RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM update_topic_config(p_topic_name, NULL, NULL, 'archived');
END;
$$;

CREATE FUNCTION pause_group(p_group_name TEXT) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_group_id BIGINT;
BEGIN
    SELECT cg.group_id INTO v_group_id FROM consumer_group cg WHERE cg.group_name = p_group_name;
    IF v_group_id IS NULL THEN
        RAISE EXCEPTION 'unknown group %', p_group_name USING ERRCODE = 'CDT06';
    END IF;
    UPDATE consumer_group SET status = 'paused' WHERE consumer_group.group_id = v_group_id;
END;
$$;

CREATE FUNCTION activate_group(p_group_name TEXT) RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_group_id BIGINT;
BEGIN
    SELECT cg.group_id INTO v_group_id FROM consumer_group cg WHERE cg.group_name = p_group_name;
    IF v_group_id IS NULL THEN
        RAISE EXCEPTION 'unknown group %', p_group_name USING ERRCODE = 'CDT06';
    END IF;
    UPDATE consumer_group SET status = 'active' WHERE consumer_group.group_id = v_group_id;
END;
$$;

CREATE FUNCTION publish_schema_version(p_topic_name TEXT, p_definition JSONB) RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_topic_id BIGINT;
    v_version INT;
BEGIN
    SELECT t.topic_id INTO v_topic_id FROM topic t WHERE t.topic_name = p_topic_name;
    IF v_topic_id IS NULL THEN
        RAISE EXCEPTION 'unknown topic %', p_topic_name USING ERRCODE = 'CDT01';
    END IF;

    SELECT COALESCE(max(sv.version), 0) + 1 INTO v_version
    FROM schema_version sv
    WHERE sv.topic_id = v_topic_id;

    UPDATE schema_version sv SET status = 'deprecated'
    WHERE sv.topic_id = v_topic_id AND sv.status = 'active';

    INSERT INTO schema_version (topic_id, version, definition, created_by)
    VALUES (v_topic_id, v_version, p_definition, NULL);

    RETURN v_version;
END;
$$;

COMMIT;
