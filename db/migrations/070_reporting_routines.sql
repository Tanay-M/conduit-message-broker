BEGIN;
INSERT INTO reporting.template_version(code,version,title,sql_text) VALUES
('customer_statement',1,'Customer purchase statement', $query$
SELECT customer_ref,full_name,order_ref,ordered_at,sku,product_name,quantity,unit_price,line_total,
       sum(line_total) OVER () AS statement_total
FROM reporting.v_sales_lines
WHERE customer_id=$1 AND ordered_at >= $2 AND ordered_at < $3
ORDER BY ordered_at,order_id,line_number
$query$),
('product_sales',1,'Product sales ranking', $query$
SELECT sku,product_name,category,sum(quantity) AS units,sum(line_total) AS sales,
       dense_rank() OVER(ORDER BY sum(line_total) DESC) AS sales_rank
FROM reporting.v_sales_lines WHERE ordered_at >= $2 AND ordered_at < $3
GROUP BY sku,product_name,category
ORDER BY sales DESC,sku LIMIT $4
$query$),
('monthly_sales',1,'Monthly sales summary', $query$
WITH totals AS (
 SELECT date_trunc('month',ordered_at)::date AS month,sum(line_total) AS sales,
        count(DISTINCT order_id) AS orders
 FROM reporting.v_sales_lines WHERE ordered_at >= $2 AND ordered_at < $3 GROUP BY 1
)
SELECT month,orders,sales,sum(sales) OVER(ORDER BY month) AS running_sales
FROM totals ORDER BY month
$query$);

CREATE SEQUENCE reporting.message_sequence;

CREATE FUNCTION reporting.calculate(p_template_id bigint,p_customer bigint,p_start date,p_end date,p_top integer)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE query_text text; result jsonb;
BEGIN
 SELECT sql_text INTO STRICT query_text FROM reporting.template_version WHERE template_id=p_template_id;
 EXECUTE 'SELECT COALESCE(jsonb_agg(to_jsonb(result_rows)), ''[]''::jsonb) FROM (' || query_text || ') result_rows'
 INTO result USING p_customer,p_start,p_end,p_top;
 RETURN result;
END $$;

CREATE PROCEDURE reporting.submit_run(
    IN p_submission uuid, IN p_template text, IN p_customer bigint,
    IN p_start date, IN p_end date, IN p_top integer, IN p_bulk boolean,
    IN p_requester bigint, INOUT p_run uuid DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE v_template bigint; existing reporting.report_run; v_app bigint;
BEGIN
 SELECT template_id INTO STRICT v_template FROM reporting.template_version
 WHERE code=p_template ORDER BY version DESC LIMIT 1;
 IF p_template='customer_statement' AND p_customer IS NULL AND NOT p_bulk THEN
   RAISE EXCEPTION 'Customer statement requires a customer or bulk mode' USING ERRCODE='23514';
 END IF;
 IF p_bulk AND (p_template <> 'customer_statement' OR p_customer IS NOT NULL) THEN
   RAISE EXCEPTION 'Bulk mode generates one statement per customer' USING ERRCODE='23514';
 END IF;
 INSERT INTO reporting.report_run(submission_key,template_id,requested_by,customer_id,start_date,end_date,top_n,bulk)
 VALUES(p_submission,v_template,p_requester,p_customer,p_start,p_end,p_top,p_bulk)
 ON CONFLICT(submission_key) DO NOTHING RETURNING run_id INTO p_run;
 IF p_run IS NULL THEN
   SELECT * INTO STRICT existing FROM reporting.report_run WHERE submission_key=p_submission;
   IF (existing.template_id,existing.requested_by,existing.customer_id,existing.start_date,existing.end_date,existing.top_n,existing.bulk)
      IS DISTINCT FROM (v_template,p_requester,p_customer,p_start,p_end,p_top,p_bulk) THEN
     RAISE EXCEPTION 'Submission key was reused with different parameters' USING ERRCODE='23505';
   END IF;
   p_run:=existing.run_id;
   RETURN;
 END IF;
 SELECT app_id INTO STRICT v_app FROM application WHERE app_name='reporting-service';
 PERFORM produce('report-prepare',p_run::text,jsonb_build_object('run_id',p_run),v_app,nextval('reporting.message_sequence'));
END $$;

CREATE FUNCTION reporting.prepare_run(p_run uuid) RETURNS integer LANGUAGE plpgsql AS $$
DECLARE r reporting.report_run; code text; v_app bigint; q record; v_count integer:=0;
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
 FOR q IN SELECT request_id FROM reporting.report_request WHERE run_id=r.run_id LOOP
   PERFORM produce('report-render',q.request_id::text,jsonb_build_object('request_id',q.request_id),v_app,nextval('reporting.message_sequence'));
   v_count:=v_count+1;
 END LOOP;
 UPDATE reporting.report_run SET status='ready',prepared_at=clock_timestamp(),error=NULL WHERE run_id=r.run_id;
 RETURN v_count;
END $$;

CREATE FUNCTION reporting.replay_request(p_request uuid) RETURNS jsonb LANGUAGE sql STABLE AS $$
 SELECT jsonb_build_object('request_id',q.request_id,'run_id',r.run_id,'template',t.code,
   'version',t.version,'title',t.title,'start_date',r.start_date,'end_date',r.end_date,'rows',d.rows)
 FROM reporting.report_request q JOIN reporting.report_run r USING(run_id)
 JOIN reporting.template_version t USING(template_id) JOIN reporting.report_dataset d USING(request_id)
 WHERE q.request_id=p_request
$$;

-- Explicit local bootstrap identity, no dependency on the old shopping demo seed.
SELECT register_user('sysadmin','sysadmin@conduit.local','admin');
SELECT register_application('reporting-service','sysadmin','both');
SELECT create_topic('report-prepare','Prepare consistent report datasets',1,'{"required":["run_id"]}','sysadmin');
SELECT create_topic('report-render','Render retained report datasets',4,'{"required":["request_id"]}','sysadmin');
SELECT create_group('report-preparers','sysadmin',3);
SELECT create_group('report-workers','sysadmin',3);
SELECT subscribe_group('report-preparers','report-prepare');
SELECT subscribe_group('report-workers','report-render');
REVOKE ALL ON ALL TABLES IN SCHEMA reporting FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA reporting FROM PUBLIC;
REVOKE EXECUTE ON ALL PROCEDURES IN SCHEMA reporting FROM PUBLIC;
COMMIT;
