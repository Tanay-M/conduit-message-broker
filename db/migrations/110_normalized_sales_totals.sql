BEGIN;
-- Keep authoritative business facts normalized; derive line totals in a view.
DROP MATERIALIZED VIEW reporting.mv_monthly_sales;
DROP VIEW reporting.v_sales_lines;
ALTER TABLE reporting.order_item DROP COLUMN line_total;
CREATE VIEW reporting.v_sales_lines AS
SELECT c.customer_id,c.customer_ref,c.full_name,c.region,
       o.order_id,o.order_ref,o.ordered_at,
       i.line_number,p.sku,p.product_name,p.category,i.quantity,i.unit_price,
       (i.quantity::numeric * i.unit_price)::numeric(20,2) AS line_total
FROM reporting.customer c
JOIN reporting.sales_order o ON o.customer_id=c.customer_id
JOIN reporting.order_item i ON i.order_id=o.order_id
JOIN reporting.product p ON p.product_id=i.product_id
WHERE o.status='completed';
CREATE MATERIALIZED VIEW reporting.mv_monthly_sales AS
SELECT date_trunc('month',ordered_at)::date AS month,category,
       sum(quantity) AS units,sum(line_total) AS sales
FROM reporting.v_sales_lines GROUP BY 1,2;
CREATE UNIQUE INDEX monthly_sales_key ON reporting.mv_monthly_sales(month,category);
COMMIT;
