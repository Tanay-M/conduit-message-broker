-- Website SQL workspace: paste ONE complete SELECT or EXPLAIN at a time.
-- These queries only read data. No INSERT, CALL, COMMIT or ROLLBACK here.
-- Use web forms to post movements/imports and request reports.

-- 1. Sales for the named demonstration customer: four-table JOIN.
SELECT c.customer_ref, o.order_ref, i.line_number,
       p.product_name, i.quantity, i.unit_price,
       (i.quantity*i.unit_price)::numeric(20,2) AS line_total
FROM reporting.customer c
JOIN reporting.sales_order o ON o.customer_id=c.customer_id
JOIN reporting.order_item i ON i.order_id=o.order_id
JOIN reporting.product p ON p.product_id=i.product_id
WHERE c.customer_ref='REVIEW-001' AND o.status='completed'
  AND o.ordered_at>=DATE '2026-01-01'
  AND o.ordered_at<DATE '2027-01-01'
ORDER BY o.ordered_at,o.order_id,i.line_number;

-- 2. GROUP BY, SUM, WHERE and HAVING.
-- Threshold >0 works on the small laptop fixture as well as the larger seed.
SELECT category, sum(line_total) AS sales
FROM reporting.v_sales_lines
WHERE ordered_at>=DATE '2026-01-01'
  AND ordered_at<DATE '2027-01-01'
GROUP BY category
HAVING sum(line_total)>0
ORDER BY sales DESC;

-- 3. Window total retains line-level detail.
SELECT customer_ref,order_ref,product_name,quantity,unit_price,line_total,
       sum(line_total) OVER () AS statement_total
FROM reporting.v_sales_lines
WHERE customer_ref='REVIEW-001'
  AND ordered_at>=DATE '2026-01-01'
  AND ordered_at<DATE '2027-01-01'
ORDER BY ordered_at,order_id,line_number
LIMIT 20;

-- 4. Ordinary view: inventory balance vs movement-ledger aggregate.
SELECT sku,quantity,reorder_level,ledger_quantity,reconciled,low_stock
FROM reporting.v_inventory
WHERE sku IN ('DEMO-KEYBOARD','DEMO-MOUSE','DEMO-HUB')
ORDER BY sku;

-- 5. Verify intentional/failed sale references. Change VIVA-01 if rehearsing.
SELECT reference,kind,quantity_delta,order_id,posted_on
FROM reporting.stock_movement
WHERE reference IN ('VIVA-01-RECEIPT','VIVA-01-SALE',
                    'VIVA-01-OVERSELL','VIVA-01-HISTORY')
ORDER BY movement_id;

-- 6. Inventory mutation links to the relational sale.
SELECT m.reference,m.quantity_delta,o.order_ref,
       c.customer_ref,p.product_name,i.quantity,i.unit_price,
       (i.quantity*i.unit_price)::numeric(20,2) AS line_total
FROM reporting.stock_movement m
JOIN reporting.sales_order o ON o.order_id=m.order_id
JOIN reporting.customer c ON c.customer_id=o.customer_id
JOIN reporting.order_item i ON i.order_id=o.order_id
JOIN reporting.product p ON p.product_id=i.product_id
WHERE m.reference='VIVA-01-SALE';

-- 7. Database-trigger audit evidence for this customer's latest requests.
SELECT a.request_id,a.old_state,a.new_state,a.event_at
FROM reporting.report_audit a
JOIN reporting.report_request q USING(request_id)
JOIN reporting.report_run r USING(run_id)
JOIN reporting.customer c ON c.customer_id=q.customer_id
WHERE c.customer_ref='REVIEW-001'
ORDER BY a.audit_id DESC
LIMIT 12;

-- 8. Saved datasets exist separately from source facts.
SELECT q.request_id,r.created_at,d.captured_at,
       jsonb_array_length(d.rows) AS saved_rows,q.state
FROM reporting.report_request q
JOIN reporting.report_run r USING(run_id)
JOIN reporting.report_dataset d USING(request_id)
JOIN reporting.customer c ON c.customer_id=q.customer_id
WHERE c.customer_ref='REVIEW-001'
ORDER BY r.created_at DESC
LIMIT 5;

-- 9. All report-run progress counts (view); newest first.
SELECT code,preparation_status,expected,queued,processing,completed,failed
FROM reporting.v_run_progress
ORDER BY created_at DESC
LIMIT 5;

-- 10. PostgreSQL version: DBMS choice evidence.
SELECT version();

-- 11. Index access path. The optimizer may select another valid plan.
EXPLAIN SELECT order_id FROM reporting.sales_order
WHERE customer_id=1 AND ordered_at>=DATE '2026-01-01'
  AND ordered_at<DATE '2027-01-01';

-- 12. Constraints on the actual order_item table, not Python rules.
SELECT conname AS constraint_name,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid='reporting.order_item'::regclass
ORDER BY conname;
