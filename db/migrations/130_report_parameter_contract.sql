BEGIN;
CREATE OR REPLACE PROCEDURE reporting.submit_run(
    IN p_submission uuid, IN p_template text, IN p_customer bigint,
    IN p_start date, IN p_end date, IN p_top integer, IN p_bulk boolean,
    IN p_requester bigint, INOUT p_run uuid DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE v_template bigint; existing reporting.report_run; v_app bigint;
BEGIN
 SELECT template_id INTO STRICT v_template FROM reporting.template_version
 WHERE code=p_template ORDER BY version DESC LIMIT 1;
 IF p_template<>'customer_statement' AND p_customer IS NOT NULL THEN
   RAISE EXCEPTION 'This report does not accept a customer filter' USING ERRCODE='23514';
 END IF;
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
COMMIT;
