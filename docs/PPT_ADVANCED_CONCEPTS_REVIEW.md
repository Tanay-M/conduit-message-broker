# Advanced database concepts and ACID evidence

20 October 2026. Authoritative presentation: Updated_Conduit_Final_Presentation.pptx. Preserve the user's ER diagrams; architecture simplification is still pending review.

## Scope and complete reporting-object inventory

The running `reporting` schema contains one procedure (`submit_run`), six callable functions (`calculate`, `post_stock`, `prepare_run`, `enqueue_ready_requests`, `reconcile_failed_requests`, `replay_request`), three trigger functions (`audit_state`, `prevent_history_change`, `protect_stock_history`), five non-internal triggers, three ordinary views and one materialized view. These counts describe current reporting/demo objects, not every legacy broker routine.

The five triggers are reporting_request_insert, reporting_request_state, immutable_template, immutable_dataset and stock_history_immutable. Ordinary views are v_sales_lines, v_inventory and v_run_progress. The materialized view is mv_monthly_sales. It is refreshed during seeding; the normal dashboard is not presented as using a new cache.

## What to show as an output

- Procedure CALL: returned INOUT run UUID, plus the created run's preparing status.
- post_stock function: returned movement ID, stock before/after, reconciled ledger quantity and generated sale line.
- prepare_run/enqueue_ready_requests: integer counts, with repeated enqueue returning zero for the same already-enqueued request; v_run_progress shows its status counts.
- Views: SELECT result grids with actual values.
- Audit triggers: UPDATE RETURNING plus automatically inserted audit rows.
- Protection triggers: actual PostgreSQL errors and SQLSTATE, demonstrating the rejected change.
- COMMIT/ROLLBACK: a separate connection reads the committed product at 75.00; a later update returns 80.00, but rollback restores 75.00.
- calculate/replay_request: explicit projected JSONB results (array length 32 and saved template/row count), rather than dumping a large JSON document on a slide.
- reconcile_failed_requests: actual return zero in this capture. This is a no-eligible-failures case, not fabricated evidence of a successful recovery.
- Materialized view: REFRESH command acknowledgement followed by SELECT rows.
- Index: actual EXPLAIN Bitmap Index Scan excerpt, not an invented speedup figure.

Full current function/procedure bodies were read with pg_get_functiondef and embedded in relevant slide notes. Longer supporting demonstrations belong in hidden viva appendix slides. Named UUID parameters refer to captured controlled records. Existing CREATE definitions explain implementation; the existing objects were not recreated merely for presentation evidence.

## ACID in the project

**Atomicity:** post_stock changes inventory balance, movement ledger, sales order and order item in one transaction. A test receipt of 10 units followed by a sale of 3 at 75.00 produced a 225.00 sale and balance/ledger 7. Rolling back the fixture transaction removed its changes. PostgreSQL sequences can have gaps after rollbacks; sequence values were not reset.

**Consistency:** PK/FK/UNIQUE/NOT NULL/CHECK constraints, plus stock function rules, preserve declared integrity. Attempting an 8-unit sale when 7 were available raised SQLSTATE 23514 with “Insufficient stock: 7 available, 8 requested”. Balance remained 7. Expected failures used savepoints so the test could continue safely.

**Isolation:** actual two-connection test: session A held FOR UPDATE on inventory_balance product 1; B used FOR UPDATE NOWAIT and received SQLSTATE 55P03. After A rolled back, B acquired the row. NOWAIT was the nonblocking test option; post_stock uses FOR UPDATE. Reporting worker preparation and analysis use REPEATABLE READ. Do not claim every transaction is serializable.

**Durability:** a dedicated product was committed and read from a fresh connection. fsync, synchronous_commit and full_page_writes were verified on. PostgreSQL WAL provides the underlying persistence/recovery mechanism, subject to storage guarantees. No power-loss or crash recovery test was performed. CSV/HTML filesystem writes are outside the database transaction.

## Evidence safety and status

Report/stock fixtures and queued messages were rolled back before becoming visible to workers. A separate product used to prove COMMIT was deliberately deleted and committed after capture. Cleanup verified that neither proof product remains. No real customer/product business facts were changed.

Private source backup, captured SQL/results, authored slides and validation are in `.local/ppt_advanced_20261020/`. The authoritative file is saved and its hash matches the validated revision. Source backups include the user's final PowerPoint save; the user confirmed no new changes. Package, font and first-party import validation passed, with no layout findings or warnings. All new/changed slides were visually reviewed. Retained slide content and media are preserved.

Main advanced-concepts section is slides 29–39. Procedure 30; stock function 31; sales/inventory views 32–33; preparation/enqueue/progress 34; audit 35; history protection 36; COMMIT/ROLLBACK 37; ACID 38–39. Hidden supporting viva slides 54–58 contain calculate/replay, failed-request reconciliation, materialized view, index/EXPLAIN and the complete trigger list. Full routine definitions are in speaker notes. The main deck has 53 visible slides; 34 appendix slides remain hidden.

## Primary references

- https://www.postgresql.org/docs/16/tutorial-transactions.html
- https://www.postgresql.org/docs/16/transaction-iso.html
- https://www.postgresql.org/docs/16/explicit-locking.html
- https://www.postgresql.org/docs/16/wal-intro.html
- Current migrations 060, 070, 090, 100, 110, 120, 130 and 150; reporting/worker.py; reporting/analysis.py; reporting/seed.py.
