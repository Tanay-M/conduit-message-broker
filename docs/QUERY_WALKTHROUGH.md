# Section 7 — database operations, SQL and actual outputs

Executed against the local PostgreSQL database on 18 October 2026. The SELECT examples share one REPEATABLE READ, read-only transaction so their sales results come from one consistent read. These values describe the demonstration fixture, not fixed values in application code.

Three approved business-report templates are implemented: customer_statement, product_sales and monthly_sales. Other queries here demonstrate database operations for the review; they are not additional downloadable UI templates. Values are filled in below for direct reading; application parameters are bound separately.

## CRUD: INSERT, UPDATE, SELECT and DELETE

CRUD means Create, Read, Update and Delete. In this context Create means inserting a record, not the separate DDL command CREATE TABLE. Only a new, uniquely named customer fixture was changed. No existing customer/order/product was edited. The whole rehearsal ended in ROLLBACK, and a later check found zero fixture rows. Identity counters can still advance despite rollback.

### INSERT

```sql
INSERT INTO reporting.customer(customer_ref, full_name, email, region)
VALUES ('VIVA-OPS-a02a1b83', 'Operations demo customer', 'viva-ops-a02a1b83@example.test', 'North')
RETURNING customer_ref, full_name, region;
```

| customer_ref | full_name | region |
| --- | --- | --- |
| VIVA-OPS-a02a1b83 | Operations demo customer | North |

### UPDATE

```sql
UPDATE reporting.customer
SET region = 'South'
WHERE customer_ref = 'VIVA-OPS-a02a1b83'
RETURNING customer_ref, region;
```

| customer_ref | region |
| --- | --- |
| VIVA-OPS-a02a1b83 | South |

### SELECT

```sql
SELECT customer_ref, region
FROM reporting.customer
WHERE customer_ref = 'VIVA-OPS-a02a1b83';
```

| customer_ref | region |
| --- | --- |
| VIVA-OPS-a02a1b83 | South |

### DELETE

```sql
DELETE FROM reporting.customer
WHERE customer_ref = 'VIVA-OPS-a02a1b83'
RETURNING customer_ref;
```

| customer_ref |
| --- |
| VIVA-OPS-a02a1b83 |

### CHECK

```sql
SELECT count(*) AS remaining_rows
FROM reporting.customer
WHERE customer_ref = 'VIVA-OPS-a02a1b83';
```

| remaining_rows |
| --- |
| 0 |

The fixture customer has no dependent orders, so DELETE is allowed. Deleting an existing referenced customer would be blocked by the FK restriction. SELECT retrieves rows without modifying them; UPDATE and DELETE use WHERE to target the fixture. RETURNING displays rows changed by INSERT/UPDATE/DELETE.

The commands above ran between BEGIN and ROLLBACK. COMMIT would make the transaction durable; that distinction and the submission-plus-enqueue transaction are covered in the next advanced-features section. The existing review evidence runner separately demonstrates CRUD with COMMIT.

## Q1 — Customer statement: selection, filtering, sorting and a window total

A three-row preview of the real customer_statement template with customer/date values filled in. Its production template has no LIMIT 3.

```sql
SELECT customer_ref, order_ref, product_name,
       quantity, unit_price, line_total,
       sum(line_total) OVER () AS statement_total
FROM reporting.v_sales_lines
WHERE customer_id = 1
  AND ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01'
ORDER BY ordered_at, order_id, line_number
LIMIT 3;
```

| customer_ref | order_ref | product_name | quantity | unit_price | line_total | statement_total |
| --- | --- | --- | --- | --- | --- | --- |
| DEMO-000001 | DEMO-000001-1 | Product 3 | 3 | 75.00 | 225.00 | 25500.00 |
| DEMO-000001 | DEMO-000001-1 | Product 4 | 4 | 100.00 | 400.00 | 25500.00 |
| DEMO-000001 | DEMO-000001-1 | Product 5 | 1 | 125.00 | 125.00 | 25500.00 |

WHERE selects the customer's completed-sale lines in the period; the view already excludes cancelled orders. ORDER BY makes the display deterministic. SUM OVER adds the full matching statement total while retaining detail rows. LIMIT is applied after that window result, so the repeated statement_total is for all 30 matching lines, not only the three displayed rows. The date interval includes 1 January 2026 and excludes 1 January 2027.

## Q2 — The explicit four-table JOIN behind the reporting view

A review query exposing the table relationships already used by reporting.v_sales_lines.

```sql
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
```

| customer_ref | order_ref | line_number | product_name | quantity | unit_price | line_total |
| --- | --- | --- | --- | --- | --- | --- |
| DEMO-000001 | DEMO-000001-1 | 1 | Product 3 | 3 | 75.00 | 225.00 |
| DEMO-000001 | DEMO-000001-1 | 2 | Product 4 | 4 | 100.00 | 400.00 |
| DEMO-000001 | DEMO-000001-1 | 3 | Product 5 | 1 | 125.00 | 125.00 |

The three JOIN predicates follow declared foreign keys: order to customer, item to order, and item to product. One result row represents an order line. The SELECT calculates the line value without updating source tables. Queries against the view still execute its underlying relational logic.

## Q3 — GROUP BY and aggregate totals by category

Category aggregation, as available in the SQL workspace; this is an evidence query rather than a fourth downloadable report template.

```sql
SELECT category, sum(quantity) AS units,
       sum(line_total) AS sales
FROM reporting.v_sales_lines
WHERE ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01'
GROUP BY category
ORDER BY sales DESC;
```

| category | units | sales |
| --- | --- | --- |
| Office | 249992 | 104988900.00 |
| Electronics | 250002 | 94998150.00 |
| Home | 250006 | 92497450.00 |

GROUP BY collects rows for the same category. SUM(quantity) counts units rather than order lines, and SUM(line_total) adds their sales values. The output has one row per category, unlike Q1's detail rows.

## Q4 — HAVING filters groups after aggregation

A threshold-specific variation of the HAVING demonstration in the review evidence script.

```sql
SELECT category, sum(line_total) AS sales
FROM reporting.v_sales_lines
WHERE ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01'
GROUP BY category
HAVING sum(line_total) > 100000000
ORDER BY sales DESC;
```

| category | sales |
| --- | --- |
| Office | 104988900.00 |

WHERE filters individual input rows before grouping. HAVING filters the resulting groups using their aggregate totals. The threshold here is 100 million units of sales value; it is chosen for the demonstration, not hardcoded into report submission.

## Q5 — Correlated NOT EXISTS subquery

Find customers without a completed order in February 2026; a review query, not a separate UI report template.

```sql
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
```

| customer_ref |
| --- |
| DEMO-000032 |
| DEMO-000033 |
| DEMO-000034 |

The inner query refers to the outer customer's c.customer_id, making it correlated. EXISTS asks whether a qualifying order exists; NOT EXISTS keeps customers for whom it does not. SELECT 1 is an existence test, not a returned order count. LIMIT shows only the first three matching customers; it does not imply only three exist.

## Q6 — Product sales ranking: the product_sales template

The real approved template with dates filled in and top_n set to 3.

```sql
SELECT sku, product_name, category,
       sum(quantity) AS units, sum(line_total) AS sales,
       dense_rank() OVER (ORDER BY sum(line_total) DESC) AS sales_rank
FROM reporting.v_sales_lines
WHERE ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01'
GROUP BY sku, product_name, category
ORDER BY sales DESC, sku
LIMIT 3;
```

| sku | product_name | category | units | sales | sales_rank |
| --- | --- | --- | --- | --- | --- |
| SKU-30 | Product 30 | Office | 29988 | 22491000.00 | 1 |
| SKU-28 | Product 28 | Home | 29988 | 20991600.00 | 2 |
| SKU-26 | Product 26 | Electronics | 29988 | 19492200.00 | 3 |

Aggregate each product's units and value first, then rank products by sales value. DENSE_RANK gives equal totals the same rank and leaves no gap in the next rank. LIMIT 3 returns three product rows, not necessarily every product in the first three rank groups if ties occur.

## Q7 — Monthly summary: a CTE and running-total window

The real monthly_sales template with dates filled in. No preview LIMIT is added: all returned months are recorded below.

```sql
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
```

| month | orders | sales | running_sales |
| --- | --- | --- | --- |
| 2026-01-01 | 11603 | 33893975.00 | 33893975.00 |
| 2026-02-01 | 10453 | 30573125.00 | 64467100.00 |
| 2026-03-01 | 11542 | 33773975.00 | 98241075.00 |
| 2026-04-01 | 11101 | 32471375.00 | 130712450.00 |
| 2026-05-01 | 11420 | 33412425.00 | 164124875.00 |
| 2026-06-01 | 10972 | 32067650.00 | 196192525.00 |
| 2026-07-01 | 11359 | 33247525.00 | 229440050.00 |
| 2026-08-01 | 11483 | 33570600.00 | 263010650.00 |
| 2026-09-01 | 10067 | 29473850.00 | 292484500.00 |

The WITH clause defines a named intermediate query for monthly aggregates, not a persistent table. date_trunc maps order dates to the start of their month; GROUP BY 1 groups by that first SELECT expression. COUNT(DISTINCT order_id) avoids counting an order repeatedly because it has multiple item lines. The window then accumulates sales in month order. Months without matching sales are absent; zero-filled calendar months are not implemented.

The web editor currently requires statements to start with SELECT or EXPLAIN. The standalone WITH version above runs in psql and in the approved report routine. This equivalent, verified wrapper runs in the web editor:

```sql
SELECT * FROM (
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
ORDER BY month
) AS monthly_report
ORDER BY month;
```

## Q8 — Operational query used for reporting progress

Inspect the latest three runs through the application's progress view.

```sql
SELECT run_id, code, preparation_status,
       expected, queued, processing, completed, failed
FROM reporting.v_run_progress
ORDER BY created_at DESC
LIMIT 3;
```

| run_id | code | preparation_status | expected | queued | processing | completed | failed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 39e4c54e-1b88-419a-b238-42e217bb50ee | product_sales | ready | 1 | 0 | 0 | 1 | 0 |
| 5d1c679a-df8f-40c2-8b89-0d1de0cce7c3 | monthly_sales | ready | 1 | 0 | 0 | 1 | 0 |
| c9b5ae7c-1ce4-461e-9708-b55f48b1f704 | monthly_sales | ready | 1 | 0 | 0 | 1 | 0 |

This view aggregates individual request states. expected is the number of individual reports, while queued/processing/completed/failed are mutually exclusive request-state counts. preparation_status describes dataset preparation separately from output completion. These are captured observations, not permanently fixed values.

## Concept summary

| Operation | What it demonstrates |
|---|---|
| SELECT / WHERE / ORDER BY / LIMIT | Retrieval, filtering and bounded sorted previews |
| JOIN | Reconstruction of related facts through FK relationships |
| GROUP BY / SUM | One aggregate row per category/product/month |
| HAVING | Filtering groups after aggregation |
| NOT EXISTS | Correlated exclusion/existence logic |
| Window functions | Totals/rankings while retaining query rows |
| CTE | Named intermediate query, not a permanent table |
| INSERT / UPDATE / DELETE | Controlled record creation/modification/removal |

## Demo access and evidence

- Read-only queries: http://127.0.0.1:8000/sql, after logging in. Paste one SELECT query at a time; use the verified SELECT wrapper for Q7. The current editor does not accept a standalone statement starting with WITH.
- Write/transaction rehearsal: use psql or the evidence runner; the web SQL workspace is read-only.
- All exact commands and fixtures: db/evidence/section_7_queries.sql. This is a psql script with meta-commands and transaction control; do not paste the entire file into the web editor.
- Machine-readable matching results: artifacts/section-7-query-results.json.
- Original full review evidence: db/evidence/reporting_review.sql and artifacts/dbms-evidence.txt.
- No PPT was authored or edited; these are sources for later slides.

Additional consistency check: the sum of the three category sales totals equals the final monthly running_sales: 292484500.00. This compares the same selected-period sales through two different groupings.
