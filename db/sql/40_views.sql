BEGIN;

CREATE VIEW v_consumer_lag WITH (security_invoker = true) AS
SELECT t.topic_name,
       cg.group_name,
       pt.partition_number,
       go.committed_offset,
       pt.next_offset AS head_offset,
       pt.next_offset - go.committed_offset AS lag_messages,
       go.updated_at AS last_commit_at
FROM group_offset go
JOIN partition pt ON pt.partition_id = go.partition_id
JOIN topic t ON t.topic_id = pt.topic_id
JOIN consumer_group cg ON cg.group_id = go.group_id
ORDER BY t.topic_name, cg.group_name, pt.partition_number;

CREATE VIEW v_topic_stats WITH (security_invoker = true) AS
SELECT t.topic_name,
       t.status AS topic_status,
       t.retention_days,
       count(m.msg_offset) FILTER (WHERE m.status = 'pending') AS pending,
       count(m.msg_offset) FILTER (WHERE m.status = 'claimed') AS claimed,
       count(m.msg_offset) FILTER (WHERE m.status = 'delivered') AS delivered,
       count(m.msg_offset) FILTER (WHERE m.status = 'dead') AS dead,
       (SELECT count(*) FROM dead_letter_message d
        WHERE d.original_topic_id = t.topic_id AND d.status = 'pending') AS dlq_pending,
       min(m.created_at) FILTER (WHERE m.status = 'pending') AS oldest_pending,
       max(m.created_at) AS last_message_at
FROM topic t
LEFT JOIN message m ON m.topic_id = t.topic_id
GROUP BY t.topic_id, t.topic_name, t.status, t.retention_days;

CREATE VIEW v_throughput_by_minute WITH (security_invoker = true) AS
SELECT topic_name,
       minute_ts,
       messages,
       sum(messages) OVER (PARTITION BY topic_name ORDER BY minute_ts) AS cumulative_messages
FROM (
    SELECT t.topic_name,
           date_trunc('minute', m.created_at) AS minute_ts,
           count(*) AS messages
    FROM message m
    JOIN topic t ON t.topic_id = m.topic_id
    WHERE m.created_at >= now() - interval '2 hours'
    GROUP BY t.topic_name, date_trunc('minute', m.created_at)
) per_minute;

CREATE VIEW v_audit_recent WITH (security_invoker = true) AS
SELECT al.log_id,
       COALESCE(u.username, 'system') AS username,
       a.app_name,
       t.topic_name,
       al.event_type,
       al.status,
       al.details,
       al.event_timestamp
FROM audit_log al
LEFT JOIN app_user u ON u.user_id = al.user_id
LEFT JOIN application a ON a.app_id = al.app_id
LEFT JOIN topic t ON t.topic_id = al.topic_id
WHERE al.event_timestamp >= now() - interval '24 hours';

CREATE MATERIALIZED VIEW mv_topic_stats AS
SELECT t.topic_name,
       t.status AS topic_status,
       t.retention_days,
       count(m.msg_offset) FILTER (WHERE m.status = 'pending') AS pending,
       count(m.msg_offset) FILTER (WHERE m.status = 'claimed') AS claimed,
       count(m.msg_offset) FILTER (WHERE m.status = 'delivered') AS delivered,
       count(m.msg_offset) FILTER (WHERE m.status = 'dead') AS dead,
       (SELECT count(*) FROM dead_letter_message d
        WHERE d.original_topic_id = t.topic_id AND d.status = 'pending') AS dlq_pending,
       min(m.created_at) FILTER (WHERE m.status = 'pending') AS oldest_pending,
       max(m.created_at) AS last_message_at
FROM topic t
LEFT JOIN message m ON m.topic_id = t.topic_id
GROUP BY t.topic_id, t.topic_name, t.status, t.retention_days;

CREATE UNIQUE INDEX uq_mv_topic_stats ON mv_topic_stats (topic_name);

CREATE FUNCTION refresh_dashboard() RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_topic_stats';
END;
$$;

GRANT SELECT ON v_consumer_lag, v_topic_stats, v_throughput_by_minute, v_audit_recent, mv_topic_stats TO conduit_app;

COMMIT;
