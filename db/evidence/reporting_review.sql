\set ON_ERROR_STOP on
\pset pager off
\echo '1. Tables and actual constraints'
SELECT table_name FROM information_schema.tables WHERE table_schema='reporting' ORDER BY table_name;
SELECT conrelid::regclass AS relation,conname,pg_get_constraintdef(oid) AS definition
FROM pg_constraint WHERE connamespace='reporting'::regnamespace ORDER BY conrelid::regclass::text,conname;

\echo '2. Four-table JOIN, filtering, calculated values'
SELECT customer_ref,full_name,order_ref,ordered_at,sku,quantity,unit_price,line_total
FROM reporting.v_sales_lines WHERE customer_id=1 AND ordered_at >= '2026-01-01' AND ordered_at < '2027-01-01'
ORDER BY ordered_at,order_id,line_number LIMIT 12;

\echo '3. GROUP BY, aggregate, HAVING'
SELECT category,sum(quantity) AS units,sum(line_total) AS sales
FROM reporting.v_sales_lines WHERE ordered_at >= '2026-01-01' AND ordered_at < '2027-01-01'
GROUP BY category HAVING sum(line_total)>100 ORDER BY sales DESC;

\echo '4. Correlated NOT EXISTS subquery'
SELECT c.customer_ref FROM reporting.customer c WHERE NOT EXISTS
(SELECT 1 FROM reporting.sales_order o WHERE o.customer_id=c.customer_id AND o.ordered_at >= '2026-10-01' AND o.ordered_at < '2026-11-01')
ORDER BY c.customer_ref LIMIT 10;

\echo '5. Window function in approved monthly report'
SELECT reporting.calculate((SELECT template_id FROM reporting.template_version WHERE code='monthly_sales' AND version=1),NULL,'2026-01-01','2027-01-01',10);

\echo '6. INSERT, UPDATE, DELETE with COMMIT on a dedicated disposable fixture'
SELECT gen_random_uuid()::text AS demo_key \gset
BEGIN;
INSERT INTO reporting.customer(customer_ref,full_name,email,region)
VALUES('EVIDENCE-'||:'demo_key','Disposable fixture',:'demo_key'||'@example.test','North');
UPDATE reporting.customer SET region='South' WHERE customer_ref='EVIDENCE-'||:'demo_key';
SELECT customer_ref,region FROM reporting.customer WHERE customer_ref='EVIDENCE-'||:'demo_key';
COMMIT;
BEGIN;
DELETE FROM reporting.customer WHERE customer_ref='EVIDENCE-'||:'demo_key';
COMMIT;
SELECT count(*) AS fixture_rows_after_delete FROM reporting.customer WHERE customer_ref='EVIDENCE-'||:'demo_key';

\echo '7. Stored procedure plus transactional enqueue, then ROLLBACK'
SELECT user_id AS owner_id FROM app_user WHERE username='sysadmin' \gset
SELECT gen_random_uuid()::text AS submission \gset
BEGIN;
CALL reporting.submit_run(:'submission','monthly_sales',NULL,'2026-01-01','2027-01-01',10,false,:owner_id,NULL);
SELECT r.run_id,r.status,m.status AS queue_status
FROM reporting.report_run r JOIN message m ON m.msg_key=r.run_id::text WHERE r.submission_key=:'submission';
ROLLBACK;
SELECT count(*) AS requests_after_rollback FROM reporting.report_run WHERE submission_key=:'submission';

\echo '8. A controlled CHECK rejection'
DO $$ BEGIN
 BEGIN
  INSERT INTO reporting.product(sku,product_name,category,catalogue_price) VALUES('INVALID-CHECK-EVIDENCE','Invalid','Test',-1);
  RAISE EXCEPTION 'Expected CHECK to reject the row';
 EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: negative catalogue price rejected';
 END;
END $$;
SELECT count(*) AS invalid_rows FROM reporting.product WHERE sku='INVALID-CHECK-EVIDENCE';

\echo '9. Trigger-written state history and view of actual outcomes'
SELECT * FROM reporting.v_run_progress ORDER BY created_at DESC LIMIT 5;
SELECT request_id,old_state,new_state,event_at FROM reporting.report_audit ORDER BY audit_id DESC LIMIT 12;

\echo '10. Indexes and a real SELECT execution plan'
SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='reporting' ORDER BY indexname;
EXPLAIN (ANALYZE,BUFFERS)
SELECT * FROM reporting.sales_order WHERE customer_id=1 AND ordered_at >= '2026-01-01' AND ordered_at < '2027-01-01';

\echo '11. Materialized view refresh is explicit'
REFRESH MATERIALIZED VIEW reporting.mv_monthly_sales;
SELECT * FROM reporting.mv_monthly_sales ORDER BY month,category LIMIT 12;
