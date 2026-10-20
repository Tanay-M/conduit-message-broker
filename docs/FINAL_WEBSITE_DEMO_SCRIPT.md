# Conduit: end-to-end website demonstration and spoken script

Presentation save status: Inventory Management additions are saved in the authoritative PPT. Slide references below reflect that revision.

Verified against current UI templates, implementation and live database on 20 October 2026. This guide does not modify the presentation. PPT references are for the current Updated_Conduit_Final_Presentation deck. Inventory Management slides32–36 were added after the stock-function example; references below reflect that insertion. If you later reorder slides, follow the slide titles.

Use the story **“A retailer receives sales records, manages physical stock and produces explainable customer statements.”** Focus on what PostgreSQL stores, checks, calculates and preserves. The message queue supports report generation in the background.

## 1. Prepare before the evaluator arrives

1. Use the actual laptop on which you will present. A Git clone contains code, not this laptop's local PostgreSQL database or saved reports.
2. Open the project folder, then double-click `START_CONDUIT.bat`. First-time setup needs internet to obtain the runtimes/dependencies. Complete that setup before entering the examination room.
3. Wait for the **Ready** URL. Normally it is `http://127.0.0.1:8001/`. Use the printed URL if the launcher picks another port. This runs the website, native PostgreSQL and two workers locally.
4. Log in with `admin` / `Conduit@123`, unless you changed these credentials. You should land on Reports. Do not display `.env.local` or your private API key.
5. Keep File Explorer open at `.local/demo-inputs/`. The launcher writes a fresh matching pair: `01-sales-with-error.csv` and `02-sales-corrected.csv`.
6. **Do not relaunch between those two imports:** relaunch creates a different pair of references. Do not substitute the UI's static sample downloads mid-demo; those are useful examples but may already have been imported in rehearsals.
7. Have this guide, the PPT and `demos/final_website_demo_queries.sql` open. You will paste one SELECT at a time; do not execute the whole SQL file in the website.
8. Use a new prefix for each rehearsal. This script uses `VIVA-01`; next time use `VIVA-02`. Intentional new sales need new posting references. Identical retries intentionally do not create new movements.
9. Standard dates: reporting period **2026-01-01 to 2027-01-01**, with an exclusive end date. For today's receipt/sale use **2026-10-20**. Select the dates explicitly; a browser may show them in a local date format.
10. Check Inventory. On this laptop at guide creation: DEMO-KEYBOARD=50, DEMO-MOUSE=8 and DEMO-HUB=20; ledger checks match. REVIEW-001 is **Northstar Office Supplies**, with no completed sales yet. These are observations, not values the launcher resets to every time.
11. Check one existing report can open and download. Run one small report during rehearsal to verify workers. Do not create a 10,000-report batch during the actual viva unless requested and already rehearsed.
12. AI controls are automatic. Recognized headers/questions use local rules; unresolved interpretation falls back to Gemini when configured. Analysis tries an AI summary after SQL calculation and retains the standard summary if unavailable. Live provider fallback was verified on20October2026; rehearse before presenting.

**Suggested tabs:** Reports, Sales import, Inventory, SQL workspace. Use sidebar links or open those pages in separate browser tabs. A direct page path below uses the launcher URL as its base.

## 2. Choose your running order

The full demonstration below is approximately 12–15 minutes. Do not jump to a PPT slide for every click: present the concepts first, then say “I will now demonstrate those features.” Keep the slide references as your bridge when questioned.

| Website action | PPT connection | Main DBMS evidence |
|---|---|---|
| Explain the retail problem | 2–7 | Problem, objectives, scope, workflow |
| Browse customer/product/order/item records | 8–19 | ER relationships, schema, 1NF/2NF/3NF |
| Import, reject, correct, retry | 21–25; screenshot 49 | Tables, INSERT, FK/CHECK/UNIQUE, staging, transaction |
| Receive/sell stock; reject overselling | 31, 38, 41, 43–44; screenshot 50 | Function, ledger view, trigger, ACID |
| Run raw SQL | 26–28, 37–38 | JOIN, filtering, aggregation, HAVING, window |
| Ask a business question | 47; screenshot 51 | Approved parameterized SQL; optional AI interpretation |
| Generate and inspect a report | 30, 39–40, 45; screenshots 48/53 | Procedure, functions, progress view, audit triggers |
| Replay old result after a new sale | 41, 46 | Saved dataset, versioned template, history protection |
| Analysis and SQL evidence | 47; screenshot 52 | SUM, COUNT DISTINCT, GROUP BY, window, consistent snapshot |
| Summarize tests and scale | 54–56 | Correctness tests and a recorded performance run |

## 3. Opening: explain what you will prove

**Screen:** Reports landing page. **PPT:** Problem Statement, Objectives, Workflow.

**Say:**

> “Our project is Conduit, a PostgreSQL-based retail operations and reporting system. The retailer needs consistent sales records, accurate stock and reports whose figures can be explained later. I will demonstrate invalid-data rejection, correction without duplicates, an atomic stock sale, SQL calculations and a downloadable customer statement.”
>
> “The website is the interface. PostgreSQL stores the related facts, enforces constraints and executes the calculations. Background workers handle report files after the request is saved.”

Do not call it an e-commerce shopping website: there is no customer checkout/cart workflow. It is a retail operations/reporting application. Do not explain API keys or the old broker administration screens; they are outside this demo.

## 4. Show the database structure first: 45–60 seconds

**Click:** sidebar **Data explorer** (`/data`).

1. Open **Customers**, search `REVIEW-001` and press Enter. Show Northstar Office Supplies and its customer ID.
2. Open **Products**, search `DEMO-KEYBOARD`. Show the SKU, name and current catalogue price 2499.00.
3. Point to **Orders** and **Order items**. Explain that an order is a header and its items are separate rows. You will create an example in Inventory shortly.

**Say:**

> “We keep customer details in customer and product details in product. sales_order records who placed an order and when. order_item records each product, quantity and historical selling price. Foreign keys connect them.”
>
> “This avoids repeating names and emails in every sale. The item key is the combination of order_id and line_number. The normalization slides show why order-level facts move out of the composite-key line relation in 2NF, and customer/product descriptions move to their own relations in 3NF.”

**PPT:** ER slides 8–10, schema 12–14, normalization 15–19. Show the actual attributes briefly rather than reading every column.

## 5. Import a sales file with an error: 90 seconds

**Click:** **Sales import** (`/imports`).

1. Under **Sales CSV**, select `.local/demo-inputs/01-sales-with-error.csv`.
2. Column mapping is automatic: aliases first, Gemini for unresolved headers when configured. There is no AI checkbox. Review the mapping and validation outcome before committing.
3. Click **Preview import**.
4. Under **Review column mapping**, point to the mapping:

| CSV header | Database field |
|---|---|
| OrderNo | order_ref |
| ClientCode | customer_ref |
| OrderDate | ordered_at |
| LineNo | line_number |
| ItemCode | sku |
| Qty | quantity |
| Rate | unit_price |

5. If a mapping is missing, select the correct header and click **Apply mapping & revalidate**. Otherwise no remapping is needed.
6. In **Validation results**, show the two valid lines of the GOOD order and the BAD order's negative price.
7. Expected fresh preview: **2 ready lines and 1 quarantined line**. Two lines belong to one valid order: 2×25.00 + 1×50.00 = **100.00**.
8. Click **Confirm mapping & commit valid orders**.
9. Expected committed result: **2 imported lines**, **1 rejected/quarantined line**. The invalid order remains in staging; it did not enter authoritative sales facts.

**Say:**

> “We stage the file before publishing sales. The preview checks mapped fields, dates, numeric bounds, existing customer/SKU references and order consistency. Here the negative price fails. We accept whole orders, so one bad line prevents a partial version of that order.”
>
> “Python provides readable preview errors. PostgreSQL independently enforces its PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL and CHECK constraints when accepted facts are written.”

**DBMS link:** import_batch/import_row retain raw values, cleaned values, errors and states; sales_order/order_item hold accepted normalized data. **PPT:** 21–25 and 49.

**Do not say:** “PostgreSQL knows the true price.” A valid positive price can still be wrong in the supplier's file; constraints enforce the declared rules.

## 6. Correct the file and prove duplicate protection: 45–60 seconds

1. Return to **Sales import**.
2. Select the matching `.local/demo-inputs/02-sales-corrected.csv`.
3. Click **Preview import**.
4. Show that the previous GOOD order's two lines are unchanged duplicates. The BAD order now has price **10.00** and is valid.
5. Click **Confirm mapping & commit valid orders**.
6. Expected result: **1 imported line, 2 unchanged duplicates**. This retry adds one repaired order worth **10.00**, not another copy of the 100.00 order. Across this fresh CSV pair the accepted sales value is **110.00**.

**Say:**

> “We corrected a rejected record and retried the file. The system compares the existing order's business content, so unchanged orders are skipped. A conflicting existing order reference is rejected rather than silently overwritten. This makes correction and retry safe.”

For extra proof, run the import-value query from the quick check below using your LIVE token, or open **Data explorer → Orders** and search the LIVE reference displayed in the import preview.

**Important:** historical CSV imports do **not** deduct stock. Say: “These represent sales imported from an earlier system. New physical stock sales go through the Inventory transaction.”

## 7. Receive stock: 30 seconds

**Click:** **Inventory** (`/inventory`). Read DEMO-KEYBOARD's current **On hand** value and call it **Q**. At guide creation Q=50.

Fill **Post a movement**:

| Field | Enter/select |
|---|---|
| Operation | Receive stock |
| Product | DEMO-KEYBOARD · Wireless Keyboard |
| Quantity | 10 |
| Business date | 2026-10-20 |
| Unique posting reference | VIVA-01-RECEIPT |
| Note | Demo replenishment |

Customer and sale-price fields are for sales only; the receipt handler does not pass them to the stored function.

Click **Post movement**. Expected keyboard stock is **Q+10**, currently **60** on a fresh run. Under **Recent movements**, show the +10 receipt and its reference. **Ledger check** must show **Matches**.

**Say:**

> “Stock begins from explicit receipts. We record each quantity change in stock_movement and maintain inventory_balance. The view compares the running ledger total with the balance, so we can inspect whether they agree.”

**PPT:** function 31, inventory view 38, screenshot 50.

## 8. Complete a stock sale and trace its relational records: 60–90 seconds

Fill the same form again:

| Field | Enter/select |
|---|---|
| Operation | Complete a sale |
| Product | DEMO-KEYBOARD |
| Quantity | 7 |
| Business date | 2026-10-20 |
| Unique posting reference | VIVA-01-SALE |
| Customer reference | REVIEW-001 |
| Sale unit price | 2499.00 |
| Note | Northstar office keyboard order |

1. Click **Post movement**.
2. Expected stock: **Q+10−7 = Q+3**. With the observed starting50, stock is **53**.
3. Show the `−7` movement, its Order ID, and **Ledger check: Matches**.
4. Open **Data explorer → Orders**, search `STOCK-VIVA-01-SALE`, and show the generated order. This is the function's order-reference format.
5. The order line is 7×2499.00 = **17,493.00**. You will show the joined line in SQL next.

**Say:**

> “One request calls reporting.post_stock. The function locks the product balance, checks the sale, inserts a sales order and item, updates stock and records a movement. Those related changes commit together. This is our stored-function and atomic-transaction example.”
>
> “The order item stores the actual sale price. A later change to the product's catalogue price should not rewrite what this customer paid.”

**PPT:** 31, 42–44; normalized historical prices 19.

Optional duplicate test: submit **exactly the same reference and every field again**. Expected result is the existing movement ID; stock does not decrease again. A changed note/date/quantity with that reference is a conflicting retry, so keep all fields identical if doing this test. A new reference means an intentional new sale.

## 9. Reject overselling and prove no partial sale: 45 seconds

1. Read remaining stock **R**. With the above first-run steps, R=53.
2. Use **Complete a sale**, same product/customer/price/date, but quantity **R+1** (54 in the example).
3. Use a **new reference**, `VIVA-01-OVERSELL`, so this is a stock test rather than duplicate-reference detection.
4. Click **Post movement**.
5. Show the insufficient-stock error. Expected example: **53 available, 54 requested**.
6. Show the unchanged On hand count and the absence of a successful OVERSELL movement. Optionally search Data explorer Orders for `STOCK-VIVA-01-OVERSELL`; it should not exist.

**Say:**

> “The database function rejects the sale before it can leave a partial order or deduct stock. This demonstrates consistency and atomicity. The transaction rolls back on the exception.”

**PPT:** 43. For isolation, say: “The function also locks the balance. The two-session test on slide 44 shows a competing lock being blocked; that concurrency test is recorded evidence, not what these sequential clicks prove.”

## 10. Show SQL directly: 90 seconds

**Click:** **SQL workspace** (`/sql`). Paste **one query at a time** from `demos/final_website_demo_queries.sql`, then click **Run query** or press **Ctrl+Enter**.

### A. Four-table JOIN — query 1

Expected on the first run for REVIEW-001: a keyboard sale of7 at2499.00, line_total17493.00. Earlier rehearsals can produce additional lines.

**Say:**

> “This query follows the foreign keys from customer to order, item and product. We filter completed sales for the customer and selected year. The database reconstructs a useful statement from normalized relations.”

**PPT:** 26, 37 and normalization19.

### B. Aggregation/HAVING — query 2

Expected: one row per category with positive revenue. Accessories includes the new named-product sale. Totals depend on the laptop's seed and rehearsals.

**Say:**

> “WHERE filters source rows by date. GROUP BY forms categories. SUM calculates sales, and HAVING filters the category totals. The threshold here is zero so this works on the small laptop dataset; the PPT's larger recorded example uses a higher threshold.”

**PPT:** 27. Do not read out a large seeded total as real retail revenue.

### C. Window function — query 3

**Say:**

> “SUM OVER gives a statement total without collapsing the individual item rows. This differs from GROUP BY. If more rows match than the display limit, the window total still covers all matching rows before LIMIT.”

**PPT:** 28. First-run statement total for REVIEW-001 is17493.00; later steps/rehearsals change it.

### D. Inventory reconciliation — query 4

Expected: keyboard quantity equals ledger_quantity, reconciled=true. DEMO-MOUSE normally shows low_stock=true.

**Say:**

> “This ordinary view combines product/balance data with an aggregate of the append-only ledger. We can inspect current stock and the consistency check through SQL.”

**PPT:** 38. Optional query6 traces the movement to the actual sale; query12 shows PostgreSQL's real constraint definitions.

**Do not run writes here.** The SQL workspace accepts one SELECT or EXPLAIN, runs it read-only, limits output to500rows and has a5-second timeout. Use forms for writes. For COMMIT/ROLLBACK, trigger rejections and simultaneous locking, show the recorded PPT evidence rather than trying write commands in this console.

## 11. Natural-language question with visible SQL: 45–60 seconds

**Click:** **Ask your data** (`/assistant`).

1. Enter exactly: **Statement for REVIEW-001 in 2026**.
2. Interpretation is automatic: recognized phrasing uses local rules; unresolved phrasing falls back to Gemini when configured. There is no AI checkbox.
3. Click **Translate & preview SQL**.
4. Point to **Query plan**, interpreted customer/date period, SQL and **Bound parameters**.
5. Confirm the plan matches the question, then click **Run approved query**.
6. Show the keyboard sale and statement total.

**Say:**

> “The question selects a supported business query. The plan and bound parameters are visible before execution. PostgreSQL performs the actual calculation in a read-only transaction.”

If asked about AI, say: “Recognized questions use our local parser. Gemini is an automatic interpretation fallback; it does not get unrestricted SQL execution.” Do not claim a familiar locally parsed question used AI.

The five supported kinds are customer statements, product revenue rankings, monthly sales, stock on hand and low stock. Alternative questions: **Top 5 products by revenue in February 2026**, **Monthly sales in 2026**, **Show stock on hand**, **Show low stock**.

**PPT:** 47 and51. Do not claim arbitrary natural-language-to-SQL support or claim that all modes call AI.

## 12. Generate the report: 60 seconds

Two routes reach the same reporting pipeline:

**Shortest route:** click **Generate saved report** on the statement Query plan.

**Explicit report-form route (better for explaining parameters):**

1. Click **Reports → New report** (`/reports/new`).
2. Template: **Customer purchase statement**.
3. Start date2026-01-01; end date2027-01-01.
4. Scope: **Single customer**.
5. Search `REVIEW-001` and **click Northstar Office Supplies in the search results**. Typing alone does not select the hidden customer ID.
6. Show the **Query preview** and template SQL.
7. Click **Generate report**.

**Expected:** a run page with preparing/in-progress/completed status, then **1 of1 reports completed**. Intermediate states can finish too quickly to observe; that is fine. The page refreshes while work remains.

**Say:**

> “The application calls submit_run. The procedure stores the run and preparation job in one database transaction. A background worker prepares a consistent dataset and then generates the files. The browser does not wait for the entire batch computation.”
>
> “Once the request is committed, closing the browser does not cancel it. Asynchronous processing shortens the submission request and supports controlled batches; it does not inherently make one SQL query faster.”

**PPT:** 30,39,45. The run's preparation_status=ready means datasets are prepared, while individual request.state=completed means its output finished. Do not confuse them.

## 13. Inspect the evidence and download files: 90 seconds

1. Under **Report outputs**, click **Inspect** for Northstar's statement.
2. In **Data preview**, show the saved result rows, capture time and template version. Expected first-run sale value is17493.00.
3. Click **SQL & parameters**. Point to customer ID, inclusive start, exclusive end and versioned SQL.
4. Click **Processing history**. Show New request→queued→processing→completed, with timestamps.
5. Explain that `reporting_request_insert` and `reporting_request_state` triggers generate these audit events.
6. Return to **Data preview**, click **Download HTML**, then open the downloaded `.html` in the browser. This is the readable customer statement.
7. Also click **Download CSV**. It is a real download, not a screenshot or placeholder. Open it in Excel/text editor if desired.
8. Expand **Output integrity** if asked. The SHA-256 values help identify the generated files; they are not encryption and do not by themselves prove business correctness.
9. Click **Replay saved report**. This opens a JSON response containing retained report metadata and rows. It is not another formatted HTML download.

**Say:**

> “There are three kinds of evidence here: the saved dataset contains the report values; the audit history records processing transitions; the template version identifies the query definition. Replay reads the retained dataset rather than querying today's source records again.”

**PPT:** 40–41,45–46 and53. A dataset is not just an audit log: one holds figures, the other holds events.

If no intermediate animation was visible, use Processing history to show the actual transitions. Do not intentionally stop workers in front of the evaluator just to manufacture a queue delay.

## 14. Optional strong history demonstration: 60–90 seconds

This uses a **new legitimate sale**, not an edit to a posted ledger row. It demonstrates how an earlier saved report remains stable when current source facts gain a sale. The PPT's separate price-correction example is a different source-change scenario.

1. Keep the completed first report open in a tab; call its total **T**. On the first run T=17493.00.
2. Open Inventory in another tab. Record **one more keyboard sale** to REVIEW-001 at2499.00, date2026-10-20, new reference **VIVA-01-HISTORY**, note **Additional order after first statement**.
3. Stock drops by1. First-run example:53→52.
4. Run the REVIEW-001 statement query again: current source total is **T+2499.00**, first-run example **19992.00**.
5. Return to the first report and refresh Data preview or Replay saved report: it still contains the original T and original saved rows.
6. Generate a **new** statement for the same customer/period. Its captured dataset includes the additional sale and totalT+2499.00.

**Say:**

> “The original report remains the statement captured at its preparation time. New facts appear in a new report; they do not silently rewrite the older artifact. The stored dataset and template version make the earlier result explainable.”

Do not claim the new report is automatically generated when source data changes: you explicitly requested it. Do not change/delete posted stock movements: a database trigger protects them.

**PPT:** 41 and46. Query8 shows separate dataset capture times/row counts if the professor wants SQL proof.

## 15. Analysis and optional AI explanation: 60 seconds

**Click:** **Analysis** (`/analysis`).

1. Set start2026-01-01, end2027-01-01.
2. AI summary generation is automatic when configured. If unavailable, the SQL facts and standard summary still work; there is no checkbox.
3. Click **Analyse**.
4. Show **Sales revenue**, **Completed orders**, **Customers**, **Units sold**, then **Revenue by category** and **Monthly comparison**.
5. Show **Exceptions to review**: the visible25% completed-month decline rule and current low-stock alerts.
6. Expand **SQL evidence**. Point to SUM, COUNT DISTINCT, joins and calendar/window calculations.

**Say:**

> “SQL computes these facts in one REPEATABLE READ transaction. The explanation uses those facts. Current stock alerts describe stock now; sales totals describe the selected period.”
>
> “Our decline alert is an explicit rule, not a claim that AI discovered the cause. No decline alert is a valid result. Current partial months and future months are not completed-month alerts.”

**PPT:** 44,47 and52. The subtle “With AI insights” note appears only when an AI summary succeeds. Aggregate facts are sent for explanation; do not claim the model calculated the numbers.

## 16. Explain ACID using what the evaluator just saw: 30 seconds

| Property | Say | Evidence boundary |
|---|---|---|
| Atomicity | “The sale's balance, movement, order and item commit together; a failed sale leaves no partial result.” | Sale/overselling forms and recorded rollback test |
| Consistency | “Foreign keys, checks, unique references and stock rules keep declared relationships and values valid.” | Negative price, duplicates, overselling, ledger match |
| Isolation | “Stock row locks coordinate concurrent sales; report preparation uses a stable read snapshot.” | Explain recorded two-session test, not just sequential UI clicks |
| Durability | “Committed records remain available when we reconnect; PostgreSQL uses WAL to persist/recover committed changes.” | Recorded fresh-connection test and durability settings; no crash-test claim |

**PPT:** 43–44. Refreshing a browser is useful continuity evidence; it is not a power-failure durability test.

## 17. Optional batch and scale evidence

For a small demonstration on a clean laptop, Reports→New report→Customer purchase statement→**All customers** generates one report per customer. Count the actual customers first. **All customers does not let you choose an arbitrary batch size**; on this existing database it includes thousands, so do not click it casually.

Use the completed run and recorded benchmark on slide 55 for the large example: 10,000 statements,20,000 CSV/HTML files,four workers,about101.249seconds in the recorded17October run. Those are recorded local end-to-end application measurements, not today's new result, a pure SQL benchmark, or a guarantee for another laptop. The double-click launcher normally starts two workers.

If the evaluator asks for bulk execution on the current large dataset, explain the time/resource impact, then run only if you are prepared to show it. A short, well-understood single-customer transaction is the main DBMS demo.

## 18. Closing script

> “The complete path is validated input, normalized sales facts, atomic stock operations, inspectable SQL and retained report output. The live errors show that the rules affect stored data, not just the presentation. Our additional features are the correction-and-retry workflow, visible question interpretation, stock reconciliation and historical report evidence. PostgreSQL remains responsible for integrity and calculations.”

Then stop and invite questions. Keep the site running until the evaluator finishes. After all reports have completed, double-click **STOP_CONDUIT.bat**. Closing the browser or PowerPoint alone does not stop the database/workers.

## If you have only five minutes

1. Opening and Data explorer overview:30seconds.
2. Import/error/commit/correct/retry:75seconds.
3. Sale and overselling rejection:60seconds. Skip the optional receipt if stock is sufficient, and calculate using the actual starting quantity.
4. One four-table JOIN and reconciliation query:45seconds.
5. Generate one statement, show SQL/history and open HTML:75seconds.
6. Closing ACID/additional-feature summary:15seconds.

Keep AI, extra aggregation queries, history/new-sale comparison and live batch generation for questions.

## Recovery sheet

| Situation | Response |
|---|---|
| Import says duplicate | These references were already committed. Explain the protection; next rehearsal use a fresh matching launcher pair. |
| Preview mapping is wrong | Use Review column mapping→Apply mapping & revalidate before committing. |
| Keyboard stock differs | Use actualQ andR; receipts/sales persist across rehearsals. Do not reset ledger history. |
| Sale reference conflicts | A retry must use every identical field. Use a new prefix for an intentional new event. |
| Report has no rows | Check customer selected from search results, completed sales, date range and exclusive end. Northstar must have the demonstrated sale. |
| Report stays preparing/queued | Wait/refresh, then check worker startup/logs. Relaunch can recover owned services, but creates a fresh CSV pair; finish any active import pair first. |
| Gemini errors or is unavailable | Use unchecked local parser/manual mapping/deterministic analysis. Describe the mode accurately. |
| Replay displays JSON | Expected: replay returns retained data. Download HTML provides the formatted report. |
| SQL workspace rejects a command | Paste one SELECT/EXPLAIN. CALL/INSERT/UPDATE/COMMIT/ROLLBACK do not belong in this read-only screen. |
| Output differs from PPT | PPT results are dated captures. Explain added rehearsal/source facts; use current arithmetic and recorded labels. |

## Quick import-value proof (optional)

Copy the GOOD/BAD order references from the preview. Replace the two quoted values in this single SELECT:

```sql
SELECT order_ref, sum(line_total) AS sales
FROM reporting.v_sales_lines
WHERE order_ref IN ('LIVE-your-token-GOOD','LIVE-your-token-BAD')
GROUP BY order_ref
ORDER BY order_ref;
```

After the first commit, onlyGOOD100.00exists. After correction, GOOD100.00andBAD10.00exist. This avoids confusing the fresh import with all earlier database totals.

## Rehearsal pass criteria

- You can launch/log in without command-line intervention on the actual laptop.
- First import publishes2valid lines and retains1invalid line; correction imports1and skips2duplicates for a fresh pair.
- Receipt/sale arithmetic matches the actual starting stock; the ledger check staysMatches.
- Overselling adds no successful order/movement and stock remains unchanged.
- JOIN output contains your new sale, and the displayed line total is7×2499.00=17493.00.
- The single report completes; CSV and HTML open; SQL, captured data and trigger history are visible.
- Optional history test leaves the old dataset unchanged and includes the new sale in a new report.
- Analysis SQL evidence is visible, and you can identify which steps use a function, procedure, trigger, view and transaction.

Sources checked: START_CONDUIT.bat, reporting/launcher.py, reporting/demo_operations.py, current web templates/routes, reporting/inventory.py, reporting/assistant.py, reporting/analysis.py, reporting/service.py, reporting/worker.py, current migrations and live database read checks. Browser automation was disabled in this session; exact labels were checked against current UI template source rather than claiming a fresh click-through execution.
