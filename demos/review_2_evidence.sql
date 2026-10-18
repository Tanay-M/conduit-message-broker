-- Review 2 read-only evidence collection.
-- Executed successfully on 2026-10-13 against an isolated database initialized from current SQL.
-- Run with psql on the database whose deployed definitions you intend to demonstrate:
-- Use the project-local psql on 127.0.0.1:55432; reporting evidence: python -m reporting.evidence
-- For the web SQL console, paste individual SELECT/EXPLAIN statements, not the full file.
-- No fixture creation, writes, retention purge, or partition drops occur here.
\set ON_ERROR_STOP on
\pset pager off
BEGIN READ ONLY;

\echo 'Environment and deployed object counts'
SELECT version(), current_database(), current_user;
SELECT
    count(*) FILTER (WHERE c.relkind IN ('r', 'p') AND NOT c.relispartition) AS logical_tables,
    count(*) FILTER (WHERE c.relkind IN ('r', 'p') AND c.relispartition) AS child_tables,
    count(*) FILTER (WHERE c.relkind = 'v') AS normal_views,
    count(*) FILTER (WHERE c.relkind = 'm') AS materialized_views
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public';

-- Extra fixtures/benchmark relations can change deployed counts.
SELECT c.relname AS table_name, c.relispartition AS is_physical_partition
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
ORDER BY c.relispartition, c.relname;

\echo 'Criterion 1: actual constraints, without double-counting child tables'
SELECT c.relname AS table_name, con.conname AS constraint_name,
       con.contype AS constraint_type, pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND NOT c.relispartition
ORDER BY c.relname, con.contype, con.conname;

-- PostgreSQL 16 represents NOT NULL separately from pg_constraint.
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name IN ('message', 'producer_sequence', 'group_subscription')
ORDER BY table_name, ordinal_position;

SELECT child.relname AS physical_partition,
       pg_get_expr(child.relpartbound, child.oid) AS time_boundary
FROM pg_inherits i JOIN pg_class child ON child.oid = i.inhrelid
WHERE i.inhparent = 'message'::regclass
ORDER BY child.relname;

\echo 'Criterion 2: current data, stored messages, and deduplication ledger'
SELECT status, count(*) AS message_count FROM message GROUP BY status ORDER BY status;
SELECT topic_name, pending, claimed, delivered, dead, dlq_pending
FROM v_topic_stats ORDER BY topic_name;
SELECT m.created_at, t.topic_name, p.partition_number, m.msg_offset,
       a.app_name, m.producer_seq, m.payload, m.status
FROM message m
JOIN topic t ON t.topic_id = m.topic_id
JOIN partition p ON p.partition_id = m.partition_id
JOIN application a ON a.app_id = m.producer_app_id
ORDER BY m.created_at DESC, m.partition_id, m.msg_offset DESC LIMIT 10;
SELECT a.app_name, ps.producer_seq, ps.partition_id, ps.msg_offset
FROM producer_sequence ps JOIN application a ON a.app_id = ps.producer_app_id
ORDER BY ps.created_at DESC, ps.producer_app_id, ps.producer_seq LIMIT 10;

\echo 'Criterion 3: filtering, joins, aggregation, and window totals'
SELECT t.topic_name, p.partition_number, m.msg_offset, m.payload
FROM message m
JOIN topic t ON t.topic_id = m.topic_id
JOIN partition p ON p.partition_id = m.partition_id
WHERE m.status = 'pending' AND (m.visible_at IS NULL OR m.visible_at <= now())
ORDER BY t.topic_name, p.partition_number, m.msg_offset LIMIT 10;

SELECT t.topic_name,
       count(m.msg_offset) AS total,
       count(m.msg_offset) FILTER (WHERE m.status = 'pending') AS pending,
       count(m.msg_offset) FILTER (WHERE m.status = 'claimed') AS claimed,
       count(m.msg_offset) FILTER (WHERE m.status = 'delivered') AS delivered
FROM topic t LEFT JOIN message m ON m.topic_id = t.topic_id
GROUP BY t.topic_id, t.topic_name ORDER BY t.topic_name;

-- Position difference is the current implemented metric, not a guaranteed unfinished-work count.
SELECT * FROM v_consumer_lag;
SELECT * FROM v_throughput_by_minute ORDER BY topic_name, minute_ts DESC LIMIT 20;
SELECT log_id, username, app_name, topic_name, event_type, status
FROM v_audit_recent ORDER BY log_id DESC LIMIT 10;

\echo 'Criterion 4: deployed functions, triggers, policies, and indexes'
SELECT p.proname, pg_get_function_identity_arguments(p.oid) AS arguments,
       CASE p.prokind WHEN 'f' THEN 'function' WHEN 'p' THEN 'procedure' ELSE p.prokind::text END AS routine_kind
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public' AND p.proname IN
      ('validate_schema', 'produce', 'produce_batch', 'consume', 'ack', 'nack', 'reap_expired_claims', 'refresh_dashboard')
ORDER BY p.proname;

-- tgparentid=0 excludes partition trigger clones; internal FK triggers are also excluded.
SELECT c.relname AS table_name, t.tgname AS trigger_name, pg_get_triggerdef(t.oid) AS definition
FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND NOT t.tgisinternal AND t.tgparentid = 0
ORDER BY c.relname, t.tgname;
SELECT schemaname, tablename, policyname, roles, cmd, qual, with_check
FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename, policyname;
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public' AND tablename IN ('message', 'producer_sequence', 'audit_log', 'mv_topic_stats')
ORDER BY tablename, indexname;

SELECT viewname, definition FROM pg_views WHERE schemaname = 'public' ORDER BY viewname;
SELECT matviewname, ispopulated, definition FROM pg_matviews WHERE schemaname = 'public';

-- Read-only, nonlocking plan. This differs from the row-locking consume plan in the saved benchmark.
-- A sequential scan on a small dataset is a legitimate planner choice.
EXPLAIN (COSTS ON)
SELECT created_at, partition_id, msg_offset
FROM message
WHERE topic_id = (SELECT min(topic_id) FROM topic)
  AND status = 'pending' AND (visible_at IS NULL OR visible_at <= now())
ORDER BY msg_offset LIMIT 10;

COMMIT;
