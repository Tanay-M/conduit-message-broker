-- Section 7: read-only query examples, then disposable CRUD rolled back.
-- Generated from the exact commands exercised on 18 October 2026.
\set ON_ERROR_STOP on
\pset pager off
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;

\echo 'Q1 Customer statement: selection, filtering, sorting and a window total'
SELECT customer_ref, order_ref, product_name,
       quantity, unit_price, line_total,
       sum(line_total) OVER () AS statement_total
FROM reporting.v_sales_lines
WHERE customer_id = 1
  AND ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01'
ORDER BY ordered_at, order_id, line_number
LIMIT 3;

\echo 'Q2 The explicit four-table JOIN behind the reporting view'
SELECT c.customer_ref, o.order_ref, i.line_number,
       p.product_name, i.quantity, i.unit_price,
       (i.quantity * i.unit_price)::numeric(20,2) AS line_total
FROM reporting.customer c
JOIN reporting.sales_order o ON o.customer_id = c.customer_id
JOIN reporting.order_item i ON i.order_id = o.order_id
JOIN reporting.product p ON p.product_id = i.product_id
WHERE c.customer_id = 1 AND o.status = 'completed'
  AND o.ordered_at >= DATE '2026-01-01'
  AND o.ordered_at < DATE '2027-01-01'
ORDER BY o.ordered_at, o.order_id, i.line_number
LIMIT 3;

\echo 'Q3 GROUP BY and aggregate totals by category'
SELECT category, sum(quantity) AS units,
       sum(line_total) AS sales
FROM reporting.v_sales_lines
WHERE ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01'
GROUP BY category
ORDER BY sales DESC;

\echo 'Q4 HAVING filters groups after aggregation'
SELECT category, sum(line_total) AS sales
FROM reporting.v_sales_lines
WHERE ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01'
GROUP BY category
HAVING sum(line_total) > 100000000
ORDER BY sales DESC;

\echo 'Q5 Correlated NOT EXISTS subquery'
SELECT c.customer_ref
FROM reporting.customer c
WHERE NOT EXISTS (
    SELECT 1
    FROM reporting.sales_order o
    WHERE o.customer_id = c.customer_id
      AND o.status = 'completed'
      AND o.ordered_at >= DATE '2026-02-01'
      AND o.ordered_at < DATE '2026-03-01'
)
ORDER BY c.customer_ref
LIMIT 3;

\echo 'Q6 Product sales ranking: the product_sales template'
SELECT sku, product_name, category,
       sum(quantity) AS units, sum(line_total) AS sales,
       dense_rank() OVER (ORDER BY sum(line_total) DESC) AS sales_rank
FROM reporting.v_sales_lines
WHERE ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01'
GROUP BY sku, product_name, category
ORDER BY sales DESC, sku
LIMIT 3;

\echo 'Q7 Monthly summary: a CTE and running-total window'
WITH totals AS (
    SELECT date_trunc('month', ordered_at)::date AS month,
           sum(line_total) AS sales,
           count(DISTINCT order_id) AS orders
    FROM reporting.v_sales_lines
    WHERE ordered_at >= DATE '2026-01-01'
      AND ordered_at < DATE '2027-01-01'
    GROUP BY 1
)
SELECT month, orders, sales,
       sum(sales) OVER (ORDER BY month) AS running_sales
FROM totals
ORDER BY month;

\echo 'Q8 Operational query used for reporting progress'
SELECT run_id, code, preparation_status,
       expected, queued, processing, completed, failed
FROM reporting.v_run_progress
ORDER BY created_at DESC
LIMIT 3;

COMMIT;

-- Modify only the uniquely named demonstration fixture below.
BEGIN;

\echo 'INSERT'
INSERT INTO reporting.customer(customer_ref, full_name, email, region)
VALUES ('VIVA-OPS-a02a1b83', 'Operations demo customer', 'viva-ops-a02a1b83@example.test', 'North')
RETURNING customer_ref, full_name, region;

\echo 'UPDATE'
UPDATE reporting.customer
SET region = 'South'
WHERE customer_ref = 'VIVA-OPS-a02a1b83'
RETURNING customer_ref, region;

\echo 'SELECT'
SELECT customer_ref, region
FROM reporting.customer
WHERE customer_ref = 'VIVA-OPS-a02a1b83';

\echo 'DELETE'
DELETE FROM reporting.customer
WHERE customer_ref = 'VIVA-OPS-a02a1b83'
RETURNING customer_ref;

\echo 'CHECK'
SELECT count(*) AS remaining_rows
FROM reporting.customer
WHERE customer_ref = 'VIVA-OPS-a02a1b83';

ROLLBACK;
