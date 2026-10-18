BEGIN;
CREATE OR REPLACE FUNCTION reporting.enqueue_ready_requests(p_run uuid DEFAULT NULL,p_limit integer DEFAULT 100)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE job record; app bigint; total integer:=0;
BEGIN
 IF p_limit NOT BETWEEN 1 AND 500 THEN RAISE EXCEPTION 'Enqueue chunk must contain 1..500 jobs' USING ERRCODE='23514'; END IF;
 IF NOT pg_try_advisory_xact_lock(hashtextextended('conduit-report-enqueue',0)) THEN RETURN 0; END IF;
 SELECT app_id INTO STRICT app FROM application WHERE app_name='reporting-service';
 FOR job IN SELECT q.request_id FROM reporting.report_request q JOIN reporting.report_run r USING(run_id)
   WHERE NOT q.enqueued AND r.status='ready' AND (p_run IS NULL OR q.run_id=p_run)
   ORDER BY q.request_id LIMIT p_limit FOR UPDATE OF q SKIP LOCKED
 LOOP
   PERFORM produce('report-render',job.request_id::text,jsonb_build_object('request_id',job.request_id),app,nextval('reporting.message_sequence'));
   UPDATE reporting.report_request SET enqueued=true WHERE request_id=job.request_id;
   total:=total+1;
 END LOOP;
 RETURN total;
END $$;
COMMIT;
