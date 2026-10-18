# DBMS-focused novelty for asynchronous reporting

Research date: 17 October 2026. This is a proposed design, not an implementation or a claim that these features already exist. The latest mark allocation provided by the user is PPT 5, demo/implementation 5, viva 5, novelty/additional feature 2, report document 3, total 20. The parent review separately verifies the uploaded guidelines.

## Recommendation

Use a business reporting portal, backed by Conduit's existing PostgreSQL work queue. Offer a small set of real SQL reports over one coherent business dataset: customer statements, sales by category/month, and outstanding invoices. The visible result is a downloadable CSV or PDF with query evidence. Keep the message broker as the processing mechanism.

Make the primary additional feature **auditable, explainable report runs**: each generated report records its parameters, query/template version, frozen data or structured result, and processing history. A user can open a report and answer: “Which query produced this number, which inputs did it use, and why is last week's saved report different from a report run today?” This is a proposed coursework feature, not a claim of globally original database research or a guarantee of the novelty marks.

Add natural-language report requests only after that core works. Treat AI as an optional convenience for selecting approved report templates. The database remains responsible for authorization, calculations, constraints, result persistence, and the audit trail.

## Feature 1: historical report evidence and reproducible results

Suggested demonstration:

1. Generate a customer's October statement. Show its SQL joins, parameter values, total, and saved run identifier.
2. Correct an invoice amount through the normal application workflow.
3. Reopen the historical report: its saved data and displayed total remain the same.
4. Generate a new statement: its total reflects the correction.
5. Compare the two runs and show which saved values changed.

Design recommendation: persist a compact, application-protected dataset or structured query result for each run, along with the report template version and the parameters. Copy all values needed for the output, including names and labels; retaining only foreign keys does not preserve those values if the referenced rows later change. Preserve the original output file too. Rerendering identical data can still produce different file bytes if the rendering version, fonts, timestamps, or metadata change; promise stable report content unless the renderer is also controlled.

PostgreSQL's default Read Committed mode takes a new snapshot for each statement. Repeatable Read gives successive reads in a transaction a stable view from its first non-control statement. This is useful when assembling several sections of a report, but it does not create a permanent historical archive. [PostgreSQL 16 transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html).

PostgreSQL permits snapshot export/import across transactions, but the snapshot remains available for import only until the exporting transaction ends. Saving a snapshot identifier in a row does not make it a reusable “time machine” for future jobs. [PostgreSQL 16 snapshot synchronization](https://www.postgresql.org/docs/16/functions-admin.html#FUNCTIONS-SNAPSHOT-SYNCHRONIZATION).

Consequently, a saved timestamp alone cannot reconstruct overwritten or deleted source values. That conclusion follows from the snapshot behavior above. For this project, a short transaction that persists the chosen report data is easier to explain and test than maintaining historical versions of every source table. Define the freeze point explicitly: request submission, batch preparation, or worker execution. Do not label a worker-execution snapshot as submission-time data.

For a batch, prepare the dataset and run/batch metadata in a transaction, commit, then let asynchronous workers render from that saved dataset. If preparation uses multiple source reads, use a suitable consistent transaction. Workers should not keep an MVCC transaction open during PDF rendering. PostgreSQL must retain row versions that may still be visible to transactions, which is one reason to avoid a long-running snapshot for the entire rendering batch. [PostgreSQL 16 routine vacuuming](https://www.postgresql.org/docs/16/routine-vacuuming.html).

## Feature 2: duplicate-safe completion and verifiable batch totals

Proposed behavior: one logical report request has one committed result, even if its queue message is retried. A unique result key can enforce this in PostgreSQL; `INSERT ... ON CONFLICT` provides a database-supported conflict-handling mechanism. [PostgreSQL 16 INSERT](https://www.postgresql.org/docs/16/sql-insert.html).

Persist the result and acknowledge the queue job in one database transaction when both operations are in the same database and the existing broker API permits it. A duplicate/recovery attempt checks for the completed result before doing work again. This does not by itself guarantee exactly-once filesystem writes, email delivery, or every possible side effect. A safe local artifact design uses a stable output identity and only exposes committed results; orphaned temporary files can be cleaned up.

Show a worker interruption after a result is committed and demonstrate recovery without a second logical result. Distinguish this from producer-message deduplication, which Conduit already has: preventing a duplicate queue row and preventing a duplicate business result are separate properties.

For 10,000 requests, show a batch view with expected, queued, processing, completed, and permanently failed counts. These states must be mutually exclusive at the report-request level; retry attempts belong in an attempt history and must not inflate the expected count. Verify that the terminal totals reconcile with the batch size.

Conduit's use of `FOR UPDATE SKIP LOCKED` fits competing workers claiming queue jobs. PostgreSQL explicitly describes this use case, while warning that skipping locked rows gives an inconsistent view for general-purpose reads. Use it to claim work; ordinary report joins and totals should use normal reads over a defined dataset. [PostgreSQL 16 SELECT locking](https://www.postgresql.org/docs/16/sql-select.html#SQL-FOR-UPDATE-SHARE).

## Feature 3: explainable SQL and query optimization

An “SQL evidence” panel should display the developer-authored SQL template, validated bound parameters, involved tables, result row count, and saved run ID. Give faculty one concrete join, one filter, one aggregate, one view, one constraint rejection, and one transaction rollback that they can reproduce.

An optional materialized view can accelerate a monthly sales dashboard. Show its refresh time and the change before/after refresh. PostgreSQL stores materialized-view results and allows refresh; the contents may be stale. A refreshable shared view is a useful cache, not a substitute for a versioned report archive. [PostgreSQL 16 materialized views](https://www.postgresql.org/docs/16/rules-materializedviews.html).

For an indexing experiment, compare the same query and dataset before and after a justified index using `EXPLAIN (ANALYZE, BUFFERS)`. PostgreSQL documents that `ANALYZE` actually runs the statement, and that instrumentation adds overhead. Measure read-only queries in an isolated benchmark database, repeat comparable trials, and retain plans. Do not promise a speedup or force index usage merely for presentation. [PostgreSQL 16 EXPLAIN](https://www.postgresql.org/docs/16/sql-explain.html).

## Optional AI: natural-language intent to approved SQL

Example input: “Create the October unpaid invoice report for the North region.”

Proposed path: model proposes an allowlisted template identifier and typed parameters; the application validates and authorizes them; the user sees the resolved filters; Conduit queues the approved request; the worker runs a developer-authored parameterized query. AI does not supply executable SQL, table names, credentials, or authorization decisions.

This follows OWASP's recommended foundations of parameterized queries, allowlist validation for query elements that cannot be bound, and least privilege. These controls address SQL injection and access exposure; they do not guarantee that a model interpreted the user's business intent correctly. The preview and strict template scope address that separate usability problem. [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).

If adding a written summary, let SQL produce the totals and comparisons. Prefer deterministic wording or let AI choose among approved observations identified by fact IDs. Do not claim arbitrary free-text AI summaries are fully verified merely because their numeric tokens match known totals: wording can still invent causation or misstate a category. Save the exact generated summary alongside its fact inputs. A normal form-based request path should work without an AI API or internet access; label a deterministic fallback honestly rather than pretending it is a live model.

## A credible 10,000-report experiment

Make the workload meaningful: 10,000 customer statements, each drawing from its own invoices/line items, is better than rendering one identical report 10,000 times. Use deterministic synthetic business data and label it as such. Keep a small live demonstration and a separately reproducible large run.

Measure enqueue time, SQL/data preparation time, queue wait, rendering time, end-to-end completion time, success/failure totals, duplicates prevented, and output count. Compare a fixed workload with one worker and a small worker pool, stating machine resources, dataset size, PDF/CSV format, batch sizes, and repeated-trial results. A PDF run includes renderer CPU and disk I/O; it is not a pure PostgreSQL throughput benchmark. Do not infer “PostgreSQL handled 10,000 reports” from 10,000 inserted queue rows alone.

No target runtime, throughput, speedup, successful large-run count, or novelty score is claimed by this research note. These require implementation and measurement.

## Suggested priority

1. Core portal, coherent relational dataset, three approved reports, real downloadable output, and existing broker defect fixes.
2. Historical report evidence and duplicate-safe saved results as the primary additional feature.
3. Measured batch demonstration and SQL evidence panel.
4. Optional bounded natural-language request interface if time remains.

This order supports implementation, viva, and report-document marks directly, while keeping the project centered on DBMS design rather than adding distributed infrastructure.
