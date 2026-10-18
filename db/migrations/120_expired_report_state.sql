BEGIN;
CREATE FUNCTION reporting.reconcile_failed_requests() RETURNS integer LANGUAGE plpgsql AS $$
DECLARE total integer;
BEGIN
 UPDATE reporting.report_request q SET state='failed',last_error='Worker claim expired after maximum attempts'
 WHERE q.state IN ('queued','processing') AND EXISTS (
   SELECT 1 FROM dead_letter_message d WHERE d.msg_key=q.request_id::text AND d.status='pending'
     AND d.failed_group_id=(SELECT group_id FROM consumer_group WHERE group_name='report-workers'))
 AND NOT EXISTS (
   SELECT 1 FROM message m WHERE m.msg_key=q.request_id::text AND m.status IN ('pending','claimed')
     AND m.topic_id=(SELECT topic_id FROM topic WHERE topic_name='report-render'));
 GET DIAGNOSTICS total=ROW_COUNT;
 RETURN total;
END $$;
CREATE INDEX message_key_lookup ON message(msg_key) WHERE msg_key IS NOT NULL;
CREATE INDEX dlq_key_lookup ON dead_letter_message(msg_key) WHERE status='pending';
REVOKE EXECUTE ON FUNCTION reporting.reconcile_failed_requests() FROM PUBLIC;
COMMIT;
