BEGIN;
ALTER TABLE reporting.report_request ADD COLUMN enqueued boolean NOT NULL DEFAULT false;
UPDATE reporting.report_request SET enqueued=true;
CREATE INDEX request_not_enqueued ON reporting.report_request(run_id) WHERE NOT enqueued;
CREATE OR REPLACE FUNCTION reporting.prepare_run(p_run uuid) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE r reporting.report_run; code text; v_app bigint; v_job record; v_count integer:=0;
BEGIN
 SELECT * INTO STRICT r FROM reporting.report_run WHERE run_id=p_run FOR UPDATE;
 IF r.status='ready' THEN RETURN 0; END IF;
 SELECT t.code INTO code FROM reporting.template_version t WHERE t.template_id=r.template_id;
 SELECT app_id INTO STRICT v_app FROM application WHERE app_name='reporting-service';
 IF r.bulk THEN
   INSERT INTO reporting.report_request(run_id,subject_key,customer_id)
   SELECT r.run_id,'customer:'||customer_id,customer_id FROM reporting.customer ORDER BY customer_id;
   -- One set-based business-data read for all recipients. Customer rows and line details are frozen together.
   WITH selected_lines AS MATERIALIZED (
     SELECT l.*,sum(line_total) OVER(PARTITION BY customer_id) AS statement_total
     FROM reporting.v_sales_lines l WHERE ordered_at >= r.start_date AND ordered_at < r.end_date
   ), grouped AS (
     SELECT customer_id,jsonb_agg(jsonb_build_object(
       'customer_ref',customer_ref,'full_name',full_name,'order_ref',order_ref,'ordered_at',ordered_at,
       'sku',sku,'product_name',product_name,'quantity',quantity,'unit_price',unit_price,
       'line_total',line_total,'statement_total',statement_total) ORDER BY ordered_at,order_id,line_number) AS rows
     FROM selected_lines GROUP BY customer_id
   )
   INSERT INTO reporting.report_dataset(request_id,rows)
   SELECT q.request_id,COALESCE(g.rows,'[]') FROM reporting.report_request q
   LEFT JOIN grouped g USING(customer_id) WHERE q.run_id=r.run_id;
 ELSE
   INSERT INTO reporting.report_request(run_id,subject_key,customer_id)
   VALUES(r.run_id,COALESCE('customer:'||r.customer_id,'summary'),r.customer_id);
   INSERT INTO reporting.report_dataset(request_id,rows)
   SELECT request_id,reporting.calculate(r.template_id,r.customer_id,r.start_date,r.end_date,r.top_n)
   FROM reporting.report_request WHERE run_id=r.run_id;
 END IF;
 SELECT count(*) INTO v_count FROM reporting.report_request WHERE run_id=r.run_id;
 UPDATE reporting.report_run SET status='ready',prepared_at=clock_timestamp(),error=NULL WHERE run_id=r.run_id;
 RETURN v_count;
END $$;
CREATE FUNCTION reporting.enqueue_ready_requests(p_run uuid DEFAULT NULL,p_limit integer DEFAULT 100)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE job record; app bigint; total integer:=0;
BEGIN
 IF p_limit NOT BETWEEN 1 AND 500 THEN RAISE EXCEPTION 'Enqueue chunk must contain 1..500 jobs' USING ERRCODE='23514'; END IF;
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
REVOKE EXECUTE ON FUNCTION reporting.enqueue_ready_requests(uuid,integer) FROM PUBLIC;
COMMIT;
