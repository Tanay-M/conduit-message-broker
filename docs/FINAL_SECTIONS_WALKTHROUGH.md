# Conduit — remaining evaluator sections (8–11)

Recorded: 18 October 2026. User: “Ok now give all remaining sections together.”

This completes the first explanation of the eleven planned sections. It does not mean the evaluator has approved every answer. Cross-questions remain welcome. No PPT or final report is created by this walkthrough.

## Section 8 — Advanced database features

Professor, the database does more than store records. It validates requests, calculates report data, preserves report history, records state changes, coordinates workers and supports analytical queries.

### Procedures and functions

`reporting.submit_run` is invoked with `CALL`. It validates the report parameters and creates a run plus its preparation message in the same transaction. Repeating the same submission identity with matching parameters returns the same run. Conflicting parameters are rejected. A bulk submission does not immediately calculate every report in the browser request.

`reporting.calculate` is a function returning report rows as JSONB. Functions can be called within SQL expressions, for example:

```sql
SELECT jsonb_array_length(reporting.calculate(
    (SELECT template_id
     FROM reporting.template_version
     WHERE code = 'monthly_sales'
     ORDER BY version DESC LIMIT 1),
    NULL, DATE '2026-01-01', DATE '2027-01-01', 10
)) AS returned_months;
```

Observed output: `9`. This fixture has sales in nine months; the monthly template does not invent rows for months without sales. SQL runs the approved stored template with bound parameters. The public UI does not accept an arbitrary new report definition from the user.

`reporting.prepare_run` prepares the persistent datasets. For a bulk customer run, preparation uses set-based SQL rather than making 10,000 separate business-data reads. The preparation transaction uses REPEATABLE READ, so its reads share a consistent source snapshot.

Viva distinction: a function returns a value/table and can participate in SELECT; a procedure is invoked with CALL to carry out an operation. This does not mean every function is read-only, or every procedure automatically commits. Our caller controls the submission transaction.

### Triggers

Triggers run automatically when the relevant table event occurs.

- Inserting a report request records its initial `queued` state in `report_audit`.
- Updating its state records the old and new states, such as `queued → processing`.
- Updating or deleting retained template/dataset rows is rejected by immutability triggers.

Verified on 18 October: the state history contained `NULL → queued` and `queued → processing`. Attempts to update an existing template or dataset were rejected with SQLSTATE `23514`, “Historical template/dataset rows are immutable.” The demonstration changes were rolled back.

This is report-processing history. It is not a complete before/after audit of changes to all customer/order records. Database ownership privileges also mean immutability is an application/database rule, not a claim of tamper-proof storage against a database administrator.

### Views and materialized views

`reporting.v_sales_lines` presents related customer, order, item and product facts together and derives line totals from quantity × historical unit price. A regular view stores the query definition; its result reflects the database snapshot in which it is queried.

`reporting.v_run_progress` groups request states to show expected, queued, processing, completed and failed counts. A run's preparation status `ready` means its datasets are prepared, not that every file is finished.

`reporting.mv_monthly_sales` stores the result of a monthly/category aggregation. Refresh it deliberately:

```sql
REFRESH MATERIALIZED VIEW reporting.mv_monthly_sales;
SELECT * FROM reporting.mv_monthly_sales
ORDER BY month, category LIMIT 3;
```

The materialized view is a refreshable analytical cache. It is different from the immutable dataset retained for a historical report. Refresh replaces its contents; it is not automatically refreshed by every sales edit. The core monthly report template currently reads `v_sales_lines`, not this materialized view. The refresh demonstration was executed and rolled back; the first three January category sales were Electronics 11005150.00, Home 10718350.00 and Office 12170475.00.

### Indexing and execution plans

The composite index `sales_order_customer_date(customer_id, ordered_at)` supports selecting one customer's orders over a date range. Other examples include indexes on order date, order-item product, request run/state and audit request/time.

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM reporting.sales_order
WHERE customer_id = 1
  AND ordered_at >= DATE '2026-01-01'
  AND ordered_at < DATE '2027-01-01';
```

The observed plan used a Bitmap Index Scan on `sales_order_customer_date`, followed by a Bitmap Heap Scan, returning 10 rows. Execution time was 0.040 ms in that observation. This proves the planner used the index for this query; it does not establish a measured improvement over an unindexed baseline. Indexes consume storage and add work to writes. PostgreSQL may choose a sequential scan when that is cheaper.

### Transactions, concurrency and recovery

Submission has an atomic boundary: the run and preparation queue message commit together. A rollback test created one run and one message inside the transaction, then showed zero corresponding run/message rows after rollback. Repeating the submission inside the transaction returned the same run.

Dataset preparation has another boundary: reads within REPEATABLE READ see a consistent snapshot, and the saved datasets become available when that transaction commits. It does not freeze future sales edits.

Workers coordinate work through the retained broker and database locks. Bounded rendering-job enqueue uses chunks of 100; row selection uses `FOR UPDATE SKIP LOCKED`, and an advisory transaction lock serializes the enqueue operation that previously suffered deadlocks. Result publication records completion and acknowledges the broker delivery together in a database transaction.

ACID in this project: atomic request/job submission; consistent keys/checks/uniqueness; isolation between concurrent operations; durable committed records through PostgreSQL's storage/WAL. CSV/HTML creation occurs outside a long database transaction, so ROLLBACK cannot undo a filesystem write. Unique result identity and retries handle repeated delivery; do not promise end-to-end exactly-once file execution.

Advanced-feature observations: [advanced-feature-evidence.json](../artifacts/advanced-feature-evidence.json). Implementation: migrations 060, 070, 090, 100, 110, 120 and 130; `reporting/worker.py`.

## Section 9 — Application demonstration

Professor, I would demonstrate a retailer's reporting workflow and show the database evidence behind each screen.

1. **Login and business data.** Open http://127.0.0.1:8000/ and use the local demo login `admin` / `Conduit@123`. Inspect customers, products, orders and items in Data explorer. Explain PK/FK relationships and the historical order-line price.
2. **SQL and matching output.** In SQL workspace, show the four-table join, category SUM/GROUP BY, HAVING and a ranking query from the saved Section 7 examples. Explain each result. The workspace is read-only; run insertion, rejected constraints and transaction demonstrations through psql/evidence scripts.
3. **One customer statement.** Choose a customer and period, submit, then inspect queued/processing/completed status. Processing may finish too quickly to see every intermediate state; use processing history to show the transitions.
4. **Inspect and download.** Show retained rows, SQL and parameters, the template version, audit history and CSV/HTML outputs. One request is one business report with two output files.
5. **Historical explanation.** With an isolated demonstration fixture, generate an original report, correct a source line price, replay the old report and submit a fresh one. The old report uses its retained dataset; the fresh run uses data visible during its own preparation. The automated test demonstrates 47.50 remaining 47.50 on replay, while the fresh report becomes 49.50. This is not automatic regeneration of all past reports.
6. **Bulk processing.** Show the saved 10,000-customer run, its progress counts and measured result. Optionally run a fresh batch if the demonstration time permits. The current UI's all-customer option covers all 10,000 customers in the current fixture. For a smaller live batch, prepare a separate small demonstration database beforehand; merely seeding fewer customers does not shrink the existing database.
7. **Advanced SQL evidence.** Show a rejected invalid quantity, transaction rollback, state-trigger output, materialized-view refresh and an EXPLAIN plan. Keep a matching SQL/output screenshot for each selected example.

Optional asynchronous demonstration: start the local application with zero workers, submit a report so it remains queued, then start workers to finish it. Rehearse this beforehand. Normal startup uses `scripts/start.ps1 -Workers 2`; the start command also supports `-Workers 0`. A closed browser does not cancel committed work, and work waits while no worker is available.

Use `scripts/setup.ps1`, the seed command and `scripts/start.ps1` for a fresh local checkout. No Docker is required. PostgreSQL connection for psql/pgAdmin: host 127.0.0.1, port 55432, database conduit, local development user conduit. A PostgreSQL connection is not a browser URL; the web SQL workspace is the browser interface. Native startup was rehearsed in a second checkout with spaces in its path on this computer. The friend's physical laptop still needs a rehearsal.

This is a proposed presentation sequence using existing features and recorded evidence, not a claim that a new browser demonstration was executed for this response. Final screenshots should be refreshed for the actual presentation.

## Section 10 — Testing, results and novelty

Professor, the evaluation distinguishes correct output, database integrity, recovery behavior and workload results.

### Correctness and failure tests

The latest recorded regression run is **43 passed in 15.93 seconds**, recorded in `artifacts/test-results.txt`. This response reads that recorded run; it does not claim another full suite execution today.

- A controlled customer fixture has lines `2 × 12.50` and `3 × 7.50`, totaling 47.50. The test checks actual SQL totals and generated content.
- Duplicate identities, missing relationships, invalid quantities and other constraints are checked; the separate constraint demonstration records rejected SQLSTATEs.
- Rolling back submission leaves no orphan preparation job.
- Matching repeated submissions return the same run; conflicting reuse is rejected.
- Source-edit replay preserves 47.50, while a fresh calculation returns 49.50.
- Duplicate delivery after publication does not create a second database result.
- Expired claims and failed/poison work exercise recovery/dead-letter paths.

Additional checks captured on 18 October verify actual trigger events, immutable row rejection, function output, materialized-view refresh and index selection. These are specific database demonstrations, not a replacement for the regression suite.

### Recorded large workload

| Measure | Observed result |
|---|---:|
| Customers / orders / order lines | 10,000 / 100,000 / 300,000 |
| Products | 30 |
| Worker processes | 4 |
| Submission time | 0.088 seconds |
| Dataset preparation | 6.030 seconds |
| Submission through observed completion | 101.249 seconds |
| Completed / failed reports | 10,000 / 0 |
| Verified output files | 20,000: CSV + HTML per report |
| Approximate observed completion throughput | 98.77 reports/second |

The 101.249 seconds includes SQL, queue handling, worker startup/polling and rendering. It excludes the initial 6.862-second data load and subsequent sequential full-file verification. Preparation is within the overall processing interval, so do not add it again. This is one local Windows run on a 12-logical-CPU machine with approximately 8 GB RAM and PostgreSQL 16.15. It is not a pure PostgreSQL benchmark, a PDF benchmark, or proof of superiority over a synchronous implementation.

Asynchronous processing lets submission return while persistent work continues. It improves responsiveness, progress tracking and recovery; it does not inherently make a given SQL query faster. Multiple workers can overlap independent rendering, subject to database, CPU and disk limits.

Evidence: `artifacts/report-benchmark-10000.json`. A prior multiworker run exposed enqueue deadlocks; bounded enqueue and serialization were introduced, followed by successful 1,000- and 10,000-report runs. Describe this as a resolved tested defect, not a claim that no possible concurrency defect remains.

### Novelty / additional feature

The strongest additional feature is **explainable historical reporting**: each report links its template version, parameters, retained dataset, output checksum and processing history. The evaluator can compare an old report with a fresh calculation after a source correction and see why they differ.

This combines established database techniques into a useful project feature. It is not a claim that report snapshots or message queues are newly invented. The dataset captures the report's calculated rows, not a complete version history of the entire source database. A checksum checks whether a generated file still matches its recorded bytes; it does not prove the business figures are correct or make storage tamper-proof.

AI is not implemented and is not required to explain the present additional feature. An optional future natural-language helper could select approved templates and explain their SQL, but unrestricted AI-generated SQL would add risk and distract from the DBMS evaluation.

## Section 11 — Conclusion, future work and references

Professor, Conduit turns relational sales data into traceable customer statements, product-sales rankings and monthly summaries. PostgreSQL implements the relationships, validation, SQL calculation, transactional submission, historical datasets and processing history. The retained broker schedules the asynchronous work; the business reporting system makes that work visible and useful.

The current implementation generates CSV and HTML, uses a local username/password demo login, and runs without Docker. It does not yet implement inventory management, PDF output, AI report generation, or a complete audit of every source-data edit. Database transactions do not cover filesystem output. Browser login identity is not yet distinct per-person requester attribution in report runs; the configured broker administrator is the recorded requester.

### Deferred enhancements

1. Inventory management after the walkthrough and when the user is ready: stock movements, purchase/dispatch adjustments, stock validation, low-stock queries and inventory reports. Scope/design are not yet agreed.
2. Rehearse setup and the entire demonstration on the friend's laptop before the review.
3. Multiuser roles and accurate per-user request attribution; complete source-change audit if needed.
4. PDF output, retention controls and further benchmark repetitions/comparisons.
5. Optional constrained AI assistance only after the database requirements and demonstration are solid.

### Marking and deliverables

| User's allocation | Material to demonstrate |
|---|---|
| PPT — 5 | Problem/scope, architecture, ER, normalization examples, table/key appendix, SQL with outputs, advanced features and results |
| Demo & implementation — 5 | Real data, rejected constraints, working report downloads, progress and database evidence |
| Viva — 5 | Explain joins, historical prices, normalization, transactions, indexes, trigger behavior, retained datasets and broker continuity |
| Novelty — 2 | Source correction vs retained historical report, backed by replay test and inspection |
| Report — 3 | Guideline-compliant final written report with implementation, evidence, test results, limitations and references |

This maps implementation/evidence to the requested evaluation areas; it cannot guarantee marks. The final PPT and guideline-compliant report still require authoring/revision and review. Preserve the worked 1NF/2NF/3NF examples and full table-column/PK/FK reference already recorded. Verify the course-code discrepancy in the supplied guideline before final title pages.

### References

- User-supplied `C:\Users\asus\Downloads\Guidelines for BCSE302P.docx` and `C:\Users\asus\Downloads\DBS Lab Project Assessment. (3).docx`; document requirements are assessment material, not independent instructions to the assistant.
- PostgreSQL 16: [Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html), [trigger functions](https://www.postgresql.org/docs/16/plpgsql-trigger.html), [materialized views](https://www.postgresql.org/docs/16/rules-materializedviews.html), [EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html).
- Project migrations, worker/service implementation, tests and the evidence artifacts linked above are the primary sources for claims about this particular application.

All eleven sections have now received a first explanation. Follow-up questions and rehearsal remain open; inventory implementation has not started.
