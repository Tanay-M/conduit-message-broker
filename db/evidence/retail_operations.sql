-- psql: final-review stock transaction / rollback demonstration.
BEGIN;
INSERT INTO reporting.customer(customer_ref,full_name,email,region)
VALUES('FINAL-EVIDENCE','Evidence Customer','final-evidence@example.test','South');
INSERT INTO reporting.product(sku,product_name,category,catalogue_price)
VALUES('FINAL-EVIDENCE-P','Evidence Product','Demo',25);
SELECT reporting.post_stock((SELECT product_id FROM reporting.product WHERE sku='FINAL-EVIDENCE-P'),
 'receipt',50,'FINAL-EVIDENCE-OPEN','Opening receipt','evidence',NULL,NULL,DATE '2026-10-01');
SELECT reporting.post_stock((SELECT product_id FROM reporting.product WHERE sku='FINAL-EVIDENCE-P'),
 'sale',7,'FINAL-EVIDENCE-SALE','Sale','evidence',
 (SELECT customer_id FROM reporting.customer WHERE customer_ref='FINAL-EVIDENCE'),25,DATE '2026-10-01');
DO $$ BEGIN
 PERFORM reporting.post_stock((SELECT product_id FROM reporting.product WHERE sku='FINAL-EVIDENCE-P'),
 'sale',45,'FINAL-EVIDENCE-OVERSELL','Reject this sale','evidence',
 (SELECT customer_id FROM reporting.customer WHERE customer_ref='FINAL-EVIDENCE'),25,DATE '2026-10-01');
 RAISE EXCEPTION 'Oversell was incorrectly accepted';
EXCEPTION WHEN check_violation THEN
 RAISE NOTICE 'Expected insufficient-stock rejection: %',SQLERRM;
END $$;
SELECT sku,quantity,ledger_quantity,reconciled FROM reporting.v_inventory WHERE sku='FINAL-EVIDENCE-P';
SELECT o.order_ref,sum(i.quantity*i.unit_price) AS sales_value FROM reporting.sales_order o
 JOIN reporting.order_item i USING(order_id) WHERE o.order_ref LIKE 'STOCK-FINAL-EVIDENCE-%%'
 GROUP BY o.order_ref ORDER BY o.order_ref;
ROLLBACK;
SELECT count(*) AS evidence_products_after_rollback FROM reporting.product WHERE sku='FINAL-EVIDENCE-P';
SELECT count(*) AS oversell_orders_after_rollback FROM reporting.sales_order WHERE order_ref='STOCK-FINAL-EVIDENCE-OVERSELL';
