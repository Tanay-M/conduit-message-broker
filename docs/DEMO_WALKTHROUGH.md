# Conduit: live presentation walkthrough

For the expanded final-review script with current PPT slide references, exact inputs, expected results, ACID explanations and optional history demonstration, use [FINAL_WEBSITE_DEMO_SCRIPT.md](FINAL_WEBSITE_DEMO_SCRIPT.md). Copy-ready read-only SQL is in [final_website_demo_queries.sql](../demos/final_website_demo_queries.sql). The script uses an optional 10-unit receipt before a 7-unit sale; this older short walkthrough uses a sale directly from opening stock, so its stock totals differ by that receipt.

Use this as your rehearsal script. The main example is a retailer importing sales, managing physical stock, analysing revenue and generating a customer statement. Keep the explanation centred on PostgreSQL.

## Start with a double-click

1. Open the project folder and double-click **START_CONDUIT.bat**.
2. On a fresh Windows x64 laptop, it runs the existing setup automatically. That first run needs internet to obtain Python, PostgreSQL and dependencies. Prepare the laptop before the review.
3. On an already configured laptop, it starts the local database, API and two workers, prepares missing small demo fixtures, and opens the workspace in your default browser.
4. The preferred address is **http://127.0.0.1:8001/**. A running API belonging to this project is reused. If the preferred port belongs to another application, the launcher selects a nearby free port and prints/opens its actual address.
5. Sign in with **admin / Conduit@123**, unless you previously changed these credentials. Starting again does not reset the password, existing stock, orders or reports.

You may close the launcher window. The background services continue running. After the presentation, double-click **STOP_CONDUIT.bat**. Stop after reports finish if you want to avoid interrupting the demo mid-job.

Each launch writes a fresh, matching CSV pair into **.local/demo-inputs/**:

- `01-sales-with-error.csv`
- `02-sales-corrected.csv`

The pair uses new order references, so a rehearsal can demonstrate first-time insertion without deleting old data. The second file repeats the good order and repairs the bad one. Do not restart the launcher between uploading the two files: another launch replaces the pair with new references.

The launcher prepares 20 sample customers only when the required generic demo references are missing. This is a small working dataset, not a recreation of the recorded 10,000-report experiment. A clone does not contain this laptop's database or generated reports.

## Before the professor arrives

- Rehearse this sequence once on the actual laptop. Check downloads open and two workers start.
- Keep the project folder open in File Explorer so the CSV pair is easy to select.
- Open Reports, Inventory and SQL workspace. Check the current **DEMO-KEYBOARD** quantity. A fresh fixture starts at 50, but rehearsals can change it.
- Choose a new movement reference for each intentional new sale, such as `VIVA-SALE-01`. Use another reference for the rejection, such as `VIVA-OVERSELL-01`.
- Keep the period **2026-01-01 to 2027-01-01** throughout. The end date is exclusive. Named opening stock uses 1 October 2026. Use **2026-10-19** for the demonstrated sale.
- If demonstrating Gemini, configure the key in `.env.local`, then stop and start the app and verify the feature before the review. Without a key, the local question parser and SQL analysis still work. Call them the local parser and deterministic analysis, not AI.
- Keep the PPT's hidden schema and SQL slides available for questions. Do not run a large benchmark for the first time in front of the evaluator.

## Opening explanation: about 30 seconds

**Say:**

“Conduit is a PostgreSQL-based retail operations and reporting system. A retailer can import sales, reject invalid orders, manage stock and query business results. Large report requests run in the background. The database preserves the data behind each generated report so we can explain it later.”

“I will demonstrate a bad sales record, its correction, a stock sale, an overselling rejection, the SQL calculations, and a downloadable customer statement.”

## 1. Import sales and show database validation: about 90 seconds

**Click:** Sales import in the sidebar.

1. Choose `.local/demo-inputs/01-sales-with-error.csv` and click **Preview import**.
2. Show the header mapping. `OrderNo` maps to `order_ref`, `ClientCode` to `customer_ref`, `OrderDate` to `ordered_at`, `LineNo` to `line_number`, `ItemCode` to `sku`, `Qty` to `quantity`, and `Rate` to `unit_price`.
3. Scroll to Validation results. The good order has two lines: 2 × 25.00 and 1 × 50.00, totalling **100.00**. The bad order has price **-10.00**, so it is rejected.
4. Click **Confirm mapping & commit valid orders**. The two valid lines enter the sales tables. The rejected order remains staged with its error.
5. Return to Sales import. Upload `.local/demo-inputs/02-sales-corrected.csv` and preview it.
6. The unchanged good order appears as a duplicate. The repaired bad order has price **10.00** and can be accepted. Commit the valid order.

**Say:**

“We retain the original input and validation errors in import_batch and import_row. We publish complete valid orders into sales_order and order_item. Customer and product references must already exist. Database foreign keys and checks protect the accepted facts.”

“Retrying an identical order creates no duplicate. A conflicting existing reference is rejected rather than silently overwritten. Historical CSV imports do not deduct physical stock. New physical sales use the inventory transaction.”

**Show the DBMS concept:** INSERT, PK, FK, CHECK, UNIQUE, staging, whole-order validation and transaction atomicity.

If a file unexpectedly shows only duplicates, you have already committed those references. That is the retry protection working. Finish the correction pair, then relaunch for a new pair if you want another complete rehearsal.

## 2. Sell stock and reject an impossible sale: about 90 seconds

**Click:** Inventory.

1. Show **Stock on hand** and **Ledger check**. DEMO-MOUSE begins below its reorder threshold to give an immediate low-stock example.
2. Read DEMO-KEYBOARD's current quantity, call it **Q**. On a fresh fixture, Q = 50.
3. In Post a movement, select **DEMO-KEYBOARD**, operation **Complete a sale**, quantity **7**, customer **REVIEW-001**, unit price **2499.00**, date **2026-10-19**, a new reference such as **VIVA-SALE-01**, and a short note.
4. Click **Post movement**. On a fresh fixture, quantity becomes **43**. In general it becomes **Q − 7**. The sales order value is **17,493.00**.
5. Show the new movement and its linked sales order. The balance and signed movement sum should still match.
6. Submit another **Complete a sale** with a **different reference** and a quantity greater than the displayed remaining stock. If 43 remain, try **45**. Keep the same customer, price and date.
7. Show the insufficient-stock error, then show that neither stock nor the order history gained a successful second sale.

**Say:**

“The post_stock stored function locks the product balance with SELECT FOR UPDATE. It checks available stock and records the order, line, movement and balance change in one transaction. An insufficient-stock exception prevents a partial sale.”

“The stock ledger is append-only. The inventory view compares its sum with the maintained balance. A concurrent-sale test also verifies that two users cannot both spend the same stock.”

**Show the DBMS concept:** stored function, row locking, JOIN/aggregation view, trigger, CHECK and atomic transaction.

If fewer than seven units remain before the demo, record a Receipt with a fresh reference for enough units, then explain that explicit receipt. Do not delete movements or reset the database. Reusing the original opening-receipt reference does not add stock a second time.

## 3. Ask a question and inspect its SQL: about 60 seconds

**Click:** Ask your data.

1. Enter **Statement for REVIEW-001 in 2026**.
2. Interpretation is automatic: local rules first, with Gemini as a fallback for unresolved phrasing. No checkbox is needed.
3. Click **Translate & preview SQL**.
4. Point to the interpreted customer/period, SQL text and bound parameters.
5. Click **Run approved query**. Show the sale from step 2. After one fresh sale, it contains seven units at 2499.00 and line total 17,493.00. Earlier rehearsals may add more statement lines.

**Say:**

“The question selects a supported reporting intent. We preview the approved SQL and bind values separately. PostgreSQL executes the query in a read-only transaction. We support five query kinds rather than arbitrary generated SQL.”

Explain that Gemini is an automatic fallback for unresolved interpretation, while recognized questions use local rules. SQL executes the approved plan in both cases.

Alternative question: **Top 5 products by revenue in February 2026**. Point out GROUP BY, SUM and DENSE_RANK in its SQL.

## 4. Queue a statement and inspect the output: about 60 seconds

From the statement query, click **Generate saved report**. Alternatively, use Reports → New report → Customer statement, select the customer REVIEW-001, and the same period.

1. Open the resulting run. Explain the queued/processing/completed states. For a small report, the worker may finish before you see the intermediate states.
2. Open the completed individual report.
3. Show **Data preview**, **SQL & parameters**, and **Processing history**.
4. Download/open **HTML** to show the readable report. Also show the CSV download.
5. Show **Replay saved report** and explain that it uses the saved dataset and retained template version.

**Say:**

“The browser submits a request and receives a run identity. A separate worker prepares the data and generates files. Once the request is committed, closing the browser does not cancel it. Asynchronous execution keeps the browser request short and lets workers manage batches. It does not inherently make an individual SQL calculation faster.”

“The saved dataset contains the original report figures. The audit records contain its processing transitions. If source data changes later, a new report can show the correction while replaying the old report still shows its original values.”

You do not need to edit source data live to explain history. Use the PPT's 47.50/49.50 scenario and the existing replay test if asked.

## 5. Show SQL analysis: about 45 seconds

**Click:** Analysis.

1. Set **Start date = 2026-01-01**, **End date = 2027-01-01**.
2. Click **Analyse**.
3. Show revenue, completed order count, distinct customers, units, category totals and monthly comparison.
4. Show current low-stock alerts and expand **SQL evidence**.

**Say:**

“SQL calculates the facts in one REPEATABLE READ snapshot. The monthly comparison uses a complete month series and window calculations. A visible rule flags a fall of at least 25% against the previous completed calendar month. A current partial month or future month is not a completed-month alert.”

“The stock alerts describe current stock. The sales figures describe the chosen period. The explanation describes SQL facts and does not prove why revenue changed.”

Do not promise a revenue-decline alert in the seeded dataset. No alert is a valid result. The automated fixture verifies that 1000 falling to 600 produces a 40% decline.

## 6. Show the relational SQL directly: about 60 seconds

**Click:** SQL workspace. Paste this SELECT and click **Run query**:

```sql
SELECT c.customer_ref, o.order_ref, i.line_number,
       p.product_name, i.quantity, i.unit_price,
       (i.quantity * i.unit_price)::numeric(20,2) AS line_total
FROM reporting.customer c
JOIN reporting.sales_order o ON o.customer_id = c.customer_id
JOIN reporting.order_item i ON i.order_id = o.order_id
JOIN reporting.product p ON p.product_id = i.product_id
WHERE c.customer_ref = 'REVIEW-001'
  AND o.status = 'completed'
ORDER BY o.ordered_at, o.order_id, i.line_number;
```

**Say:** “Each row represents an order line. These joins follow foreign keys. We keep customer and product descriptions in their own relations, and preserve the actual selling price in order_item.”

Then run the reconciliation query:

```sql
SELECT sku, quantity, ledger_quantity, reconciled, low_stock
FROM reporting.v_inventory
ORDER BY sku;
```

**Say:** “This view joins products and balances to an aggregate of stock movements. Reconciled should be true.”

For aggregation, run:

```sql
SELECT category, sum(line_total) AS sales
FROM reporting.v_sales_lines
WHERE ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01'
GROUP BY category
HAVING sum(line_total) > 0
ORDER BY sales DESC;
```

**Say:** “WHERE filters sales rows, GROUP BY collects categories, SUM calculates revenue, and HAVING filters the resulting groups.”

The SQL workspace permits read-only queries. Show stock posting through its form and stored-function source, not by trying to run writes or transaction commands in this read-only screen.

## Closing: about 20 seconds

“The main database contribution is the connected workflow: validated relational facts, atomic stock updates, inspectable SQL and retained report results. Our additional features make correction and retries visible, and let users ask supported business questions while PostgreSQL remains responsible for validation and calculation.”

If asked about scale, show the **recorded 17 October benchmark**: 10,000 statements, four workers, 20,000 CSV/HTML files and approximately 101.249 seconds. That includes application/queue/rendering work and is one local run. It is not a pure PostgreSQL benchmark or a newly repeated result on your friend's laptop.

## Recovery and repeat-demo notes

| Situation | What to do |
|---|---|
| A report remains queued | Check workers started. Run START_CONDUIT.bat again, then refresh. This also replaces the sample CSV pair, so finish any current import correction first. |
| The usual API port is busy | Use the URL the launcher prints and opens. It does not stop unrelated applications. |
| PostgreSQL port 55432 is busy | Check the message. Another database may own it. Change both database DSNs consistently or use the prepared laptop. The launcher does not kill another PostgreSQL service. |
| AI service unavailable | Local parsing/manual mapping and standard SQL analysis remain available automatically. |
| A sale reference is a duplicate | Identical details return the original movement. Use a new reference only for an intentional new sale. |
| Stock differs from the PPT | Rehearsals change it. State the current quantity and demonstrate subtraction/rejection using that value. |
| You closed the browser | Open the Ready URL again. Committed report jobs continue. |
| You changed the Gemini key | Double-click STOP_CONDUIT.bat, then START_CONDUIT.bat so the API reads the new configuration. |
| First run fails on a missing runtime DLL | Install Microsoft's supported x64 Visual C++ Redistributable, then rerun. Rehearse first-time setup before presentation day. |

For an optional port override from a terminal: `START_CONDUIT.bat -Port 8100`. Normal use requires only the double-click.

Source references: `docs/FINAL_REVIEW_DEMO.md`, current UI templates, `db/migrations/150_retail_operations.sql`, `reporting/launcher.py`, `artifacts/report-benchmark-10000.json` and recorded test results.

