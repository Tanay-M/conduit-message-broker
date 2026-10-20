# Conduit — presentation reference and explicit user requirements

## Active editing instructions — 20 October 2026

The authoritative working deck is **Updated_Conduit_Final_Presentation.pptx** in the repository root. Use [PPT_EDITING_REQUIREMENTS.md](PPT_EDITING_REQUIREMENTS.md) for the user's required order and current authorisations. Preserve their ER image slides. Architecture/workflow simplification remains pending chat review. Show only demo-related tables, not the total table count. These instructions supersede the older scope/count and ER-generation instructions below.

# Final-review additions — 19 October 2026 (supersedes older scope counts)
The current implementation includes Sales import, Inventory, Analysis and Ask your data. Current schema is **34 logical tables**, 33 excluding schema_migration; six new relations are inventory_balance, stock_movement, import_batch, import_row, assistant_request and analysis_run. Add their column/key appendix from [FINAL_REVIEW_SCHEMA.md](FINAL_REVIEW_SCHEMA.md); keep the pre-expansion table dictionary for the original 28 relations. One new view v_inventory reconciles balances to net movement sums. The new post_stock routine is a function; existing submit_run remains a procedure.

Full regression on 19 October: **57 passed in 26.88s**. Existing 10,000-report results remain a prior measured run, not a rerun after these new business fixtures. Live Gemini needs the user's key; mocked tests establish adapter/validation behavior only. Manual import, deterministic analysis and a labelled local rule parser already work offline.

Updated story and demonstrations: [FINAL_REVIEW_DEMO.md](FINAL_REVIEW_DEMO.md). Additional-feature wording: an inspectable Validate→Commit→Analyse→Report workflow, whole-order quarantine/correction without duplicates, visible question-to-SQL translation and atomic stock sales. AI assists interpretation; PostgreSQL enforces correctness. Do not claim a new DBMS algorithm. Caching and the optimizer advisor were declined. No new final PPT or Word report was authored in this implementation step.

Created 18 October 2026. This is the reference for preparing the replacement PPT later; no new deck is being generated in this step.

## Explicit requirements from the user

1. Explain **how normalization was performed**, including the starting problem, dependencies, decomposition, normal forms and the worked examples used during the evaluator discussion. Do not merely write “normalized database.”
2. Include the **exact database table count**, the tables, every column's short meaning, primary keys, foreign keys and relevant constraints.
3. Show actual SQL and matching outputs, with evidence for the database implementation, insertion/management, joins/filtering/aggregation and advanced features required by the uploaded guidelines.
4. Preserve continuity with Review 1. Show retained broker entities and how the reporting application uses them internally, while keeping the main demo interface focused on reporting.
5. Keep the presentation professional, readable and DBMS-focused. Use grouped schema slides plus readable appendix slides for the complete dictionary, rather than squeezing every column description into one slide.
6. Inventory was initially deferred; the user approved basic inventory on 19 October and it is now implemented. Present only the receipt/sale/reorder/reconciliation scope described in FINAL_REVIEW_DEMO.md.

Authoritative sources for the future deck:

- [Complete table/column/key dictionary](DATABASE_TABLE_REFERENCE.md): all 28 logical tables and 177 column descriptions, generated from live PostgreSQL catalog metadata with specific human explanations.
- [Evaluator discussion](EVALUATOR_DISCUSSION.md): the exact questions, answers, examples and progression.
- [Updated guidelines](<C:/Users/asus/Downloads/Guidelines for BCSE302P.docx>): required PPT/report contents.
- [Implementation status](IMPLEMENTATION_STATUS.md): implemented scope, measurements and limitations.
- [Future work](FUTURE_WORK.md): deferred inventory management.

## Assessment structure to cover

User-supplied allocation: PPT 5, demonstration/implementation 5, viva 5, novelty/additional feature 2, report 3; total 20. The guidelines document supplies required contents, not this numerical allocation.

Include title; abstract/problem; objectives/scope; architecture/workflow; ER diagram; relational schema and normalization; DBMS/table creation/constraints/sample insertion/SQL outputs; procedures/functions/triggers/views/COMMIT/ROLLBACK; application screenshots/demo; testing/results; conclusion/future enhancement; references. Do not invent a mandatory slide count.

The report-title example and guideline heading use different course-code suffixes. Verify the official course code and student/faculty details before authoring final title material.

## Exact table count and counting convention

Verified against database conduit, PostgreSQL 16.15, on 18 October 2026:

| Area | Logical tables |
|---|---:|
| Original broker foundation in public | 15 |
| Sales business facts in reporting | 4 |
| Reporting/history in reporting | 6 |
| Browser login/session in reporting | 2 |
| Migration history in public | 1 |
| **Total logical tables** | **28** |

- 27 domain/application/support tables if the infrastructure-only schema_migration relation is excluded. Always state the counting convention.
- public has 16 logical tables; reporting has 12.
- public.message has **8 child monthly/default storage partitions**. Including those child relations produces **36 table/partition relations** in the catalog. The partitioned parent is included in the logical count; these children are not eight separate business entities.
- **6 ordinary views** and **2 materialized views** are separate objects, excluded from the 28-table count.
- The 28 logical definitions contain **177 columns**, excluding repeated inherited child-partition columns.
- public.partition is a queue-partition metadata table. It is not the same concept as the monthly PostgreSQL message storage partitions.
- Refresh these numbers from the actual schema if implementation changes before deck creation, especially if inventory is added later. Do not carry forward stale numbers automatically.

### All logical tables to include in schema overview/appendix

Sales (4): customer, product, sales_order, order_item.

Reporting/history (6): template_version, report_run, report_request, report_dataset, report_result, report_audit.

Login/session (2): web_account, web_session.

Retained broker (15): role, app_user, application, topic, partition, schema_version, message, producer_sequence, consumer_group, group_subscription, group_offset, access, dead_letter_message, audit_log, broker_config.

Migration infrastructure (1): schema_migration.

The full appendix must take column names, types, short meanings, PK/FK/UNIQUE and NULL behavior from DATABASE_TABLE_REFERENCE.md. Include composite keys in full, not just the first column. Do not export passwords, hashes, API-key values or live session values onto slides.

## Normalization — mandatory worked explanation

The claim applies to the four authoritative sales-fact relations under the documented business dependencies. Frozen JSON datasets and materialized aggregates are derived historical/reporting artifacts; do not claim every table in the entire application is automatically 3NF or BCNF.

### Start with the problem

An unnormalized order could contain an item list such as “Keyboard × 2, Mouse × 1.” A flat sales-line spreadsheet can still repeat customer names/emails, order dates and product descriptions. Repetition creates update inconsistency and insertion/deletion anomalies.

Illustrative teaching records (not a claim that these values are current seeded data):

| Order | Line | Customer | Product | Quantity | Sale-time unit price |
|---|---|---|---|---:|---:|
| 101 | 1 | Customer C1 | Keyboard P1 | 2 | 500.00 |
| 101 | 2 | Customer C1 | Mouse P2 | 1 | 200.00 |
| 102 | 1 | Customer C1 | Keyboard P1 | 1 | 550.00 |

The combined labels here are explanatory display labels; actual IDs, names and other attributes are separate columns. Show an initial flat row layout including order_id, line_number, ordered_at, customer_id, full_name, email, product_id, product_name, quantity and unit_price when explaining dependencies.

### 1NF — atomic values and identifiable item rows

- Replace the repeating product list with one row per order item.
- Identify a line by (order_id,line_number).
- Explain that an atomic flat table can be in 1NF and still have repeated metadata.

### 2NF — remove partial-key dependencies

- Composite line identity: (order_id,line_number).
- Order date and customer identity depend on order_id alone, not on line_number.
- Move order-level facts into sales_order, leaving line-level facts in order_item.
- Example: an order's date should not be repeated and independently maintained on each of its lines.

### 3NF — remove transitive non-key dependencies

- order_id → customer_id → customer name/email: store customer descriptions in customer.
- (order_id,line_number) → product_id → product name/category/catalogue price: store product descriptions in product.
- Keep only the appropriate reference keys in orders/lines.

Show these final dependencies explicitly:

```text
customer_id           → customer_ref, full_name, email, region
product_id            → sku, product_name, category, catalogue_price
order_id              → order_ref, customer_id, ordered_at, status
(order_id,line_number) → product_id, quantity, unit_price
```

Declared unique customer references/email, SKU and order references also provide alternate keys. Do not claim a single-column PK by itself proves 3NF.

### Price and derived-value examples

- Catalogue price and sale-time price are different facts. The same Keyboard P1 can sell at 500 on order 101 and 550 on order 102. Both order-line prices must be retained.
- Use line_total = quantity × unit_price as the derived value. The final schema calculates it in v_sales_lines; it is not stored on order_item.
- A stored historical report deliberately freezes its detail values and totals. It does not become a second editable source of current sales truth. This explains the tradeoff between normalized source facts and retained report content.

### Other normal forms — backup/viva notes

The normal forms explained and applied in the main example are 1NF, 2NF and 3NF. Higher forms include BCNF (every determinant of a nontrivial functional dependency is a superkey), 4NF (addresses nontrivial multivalued dependencies) and 5NF (addresses join dependencies). Do not claim a full BCNF/4NF/5NF analysis of the complete project; none has been established. Keep the main slides focused on the actual decomposition.

## Database implementation — show actual creation and insertion

Use the current final order_item definition, not the original migration's now-removed generated line_total column:

```sql
CREATE TABLE reporting.order_item (
    order_id bigint NOT NULL
        REFERENCES reporting.sales_order(order_id) ON DELETE RESTRICT,
    line_number integer NOT NULL CHECK (line_number > 0),
    product_id bigint NOT NULL
        REFERENCES reporting.product(product_id) ON DELETE RESTRICT,
    quantity integer NOT NULL CHECK (quantity BETWEEN 1 AND 1000000),
    unit_price numeric(12,2) NOT NULL CHECK (unit_price >= 0),
    PRIMARY KEY (order_id, line_number)
);
```

The application already has this table. The above is for explanation or a fresh schema, not an instruction to recreate an existing table. Actual migrations are applied with their checksums in transactions by reporting.local.migrate.

Simple insertion example for a direct database client:

```sql
BEGIN;
INSERT INTO reporting.customer(customer_ref,full_name,email,region)
VALUES ('VIVA-CUSTOMER-001','Viva sample customer',
        'viva-customer-001@example.test','South')
RETURNING customer_id,customer_ref,full_name,region;
ROLLBACK;
```

Explain that RETURNING displays the inserted row; ROLLBACK removes the sample transaction's changes. Identity sequence values may still have gaps after rollback, so do not claim that every database object returns to exactly the same numeric state.

The UI SQL workspace is read-only. CREATE/INSERT/UPDATE/DELETE and transaction demonstrations belong in psql/the evidence runner, not in the read-only web editor.

### Constraint demonstrations actually executed on 18 October 2026

Valid related rows were inserted into customer, product, sales_order and order_item inside a transaction and then rolled back. Within savepoints, the following invalid attempts were rejected:

| Attempt | Database protection | Observed SQLSTATE |
|---|---|---|
| Duplicate customer reference | UNIQUE | 23505 |
| NULL customer name | NOT NULL | 23502 |
| Order with nonexistent customer | FOREIGN KEY | 23503 |
| Negative catalogue price | CHECK | 23514 |
| Zero order-line quantity | CHECK | 23514 |
| Duplicate (order_id,line_number) | PRIMARY KEY | 23505 |

Zero sample customer rows remained after rollback. Evidence: artifacts/schema-constraint-demonstration.json. Use an exact matching SQL/output pair in the final deck; screenshot final execution if the fixtures differ.

## Review 1 continuity — mandatory clarification

- The full ER explanation must include the retained broker layer, not only the sales/reporting slice.
- USER is implemented as app_user plus role. Producer/consumer applications are represented in application; Python workers consume jobs through the existing queue functions.
- Topic/group subscriptions are M:N through group_subscription. Progress is per group/partition in group_offset, refining the simplified Review 1 diagram.
- audit_log remains the broker/admin event audit. reporting.report_audit adds report-state history. Neither is a full before/after audit of source sales edits.
- The old PDF describes a separate append-only/WAL data plane. The current implementation uses message rows in PostgreSQL and PostgreSQL's own WAL. State the implementation difference honestly.
- Hiding broker integration from the main demo removed navigation/API-key login choices; it did not remove the internal queue implementation.
- Show the actual reporting-to-broker connection: submit_run → produce(report-prepare) → consume/prepare → bounded produce(report-render) → consume/render → ack, with nack/recovery for failures. artifacts/report-broker-trace.json matches a completed report to its real delivered queue messages. Do not describe retained tables alone as proof that every broker feature runs for every report.

## Verified scope, novelty and results to preserve

- Three reports: customer_statement, product_sales, monthly_sales. Outputs: CSV + HTML. PDF and AI are not implemented.
- Core novelty: retained, versioned report content with inspection/replay. Source correction does not silently rewrite an old report. A fresh report uses current data during preparation.
- Run vs request: 1 bulk run → 10,000 report requests → 20,000 CSV/HTML files, not 20,000 business reports.
- Observed large workload: 10,000 customers, 100,000 orders, 300,000 items, four workers, about 101.249 seconds from submission through observed completion. Excludes seeding and later sequential file verification. One measured local run; not a pure PostgreSQL or PDF benchmark or a synchronous comparison.
- Most recent full regression result: 43 passing tests; reference artifacts/test-results.txt. Refresh if code changes before presenting.
- File publication is outside database rollback. Do not claim end-to-end exactly-once external side effects.
- Prepared operation is local/offline without Docker. Portability rehearsal was on another checkout on this computer, not another physical laptop.

## Evidence and source map for slide authoring

Section 7 now has a complete [query walkthrough](QUERY_WALKTHROUGH.md), [executable psql script](../db/evidence/section_7_queries.sql) and [matching observed outputs](../artifacts/section-7-query-results.json), captured on 18 October 2026. It includes CRUD, customer selection/window totals, explicit four-table joins, category grouping, HAVING, a correlated NOT EXISTS subquery, product rankings, monthly CTE/running totals and progress queries. Use exact SQL/output pairs; retain the distinction between the three runtime report templates and additional review-only evidence queries.

Explain these viva points on the relevant slides: WHERE filters input rows while HAVING filters groups; COUNT(DISTINCT order_id) avoids counting each line as a separate order; window sums retain detail rows while grouped sums collapse them; LIMIT on the customer preview does not reduce the full statement_total computed by its window; and top-N product rows are not necessarily all tied rank groups. The monthly template omits months without sales. The current web SQL editor rejects a statement beginning with WITH; the walkthrough supplies an equivalent verified SELECT wrapper. Writes run through psql/evidence scripts, not the read-only web editor.

| Required topic | Source/evidence |
|---|---|
| Table/column/key appendix | docs/DATABASE_TABLE_REFERENCE.md and artifacts/database-schema-catalog.json |
| Sales facts and historical prices | db/migrations/060_reporting_schema.sql plus 110_normalized_sales_totals.sql |
| Report queries | db/migrations/070_reporting_routines.sql |
| Current submission procedure | db/migrations/130_report_parameter_contract.sql |
| Bounded enqueue/concurrency | db/migrations/090_bounded_enqueue.sql and 100_serialized_enqueue.sql |
| Login/session tables | db/migrations/140_web_login.sql |
| CRUD, joins, HAVING, subquery, rollback, indexes, materialized view | db/evidence/reporting_review.sql and artifacts/dbms-evidence.txt |
| Section 7 query-by-query teaching examples | docs/QUERY_WALKTHROUGH.md, db/evidence/section_7_queries.sql and artifacts/section-7-query-results.json |
| Valid insertion and rejected constraints | artifacts/schema-constraint-demonstration.json |
| Actual four-table join and output | artifacts/er-model-query.json |
| Retained Review 1 implementation | artifacts/review1-retained-components.json; db/sql; original Review 1 PDF |
| Replay/failure correctness | tests/test_reporting.py and artifacts/test-results.txt |
| Bulk generation | artifacts/report-benchmark-10000.json |
| UI screenshots | artifacts/ui; refresh after final UI changes |

Final authoring checklist: verify current facts, show SQL plus corresponding output, include normalization examples and full key/column appendix, reconcile Review 1 differences, keep future work separate, and validate slide readability at presentation size.

## Sections 8–11 — completed first explanation, 18 October 2026

Full teaching/demo notes: [FINAL_SECTIONS_WALKTHROUGH.md](FINAL_SECTIONS_WALKTHROUGH.md). These sections have been explained together at the user's request; this does not imply evaluator approval or that slides/report have been produced.

- Advanced-feature evidence: artifacts/advanced-feature-evidence.json. Verified submission identity returned the same run; rollback left zero corresponding run rows and preparation jobs; triggers recorded NULL→queued and queued→processing; immutable template/dataset update attempts failed with 23514; calculate returned nine monthly rows; the selected predicate used sales_order_customer_date; materialized-view refresh returned actual grouped data. The demonstration transactions were rolled back.
- Show CALL vs SELECT, automatic triggers, v_sales_lines/v_run_progress, manual materialized-view refresh, EXPLAIN output, and transaction boundaries. A materialized view is refreshable and distinct from the immutable historical report dataset. The core monthly template queries v_sales_lines, not mv_monthly_sales.
- Index observation: Bitmap Index Scan + Bitmap Heap Scan, ten rows, observed 0.040 ms execution. No unindexed comparison was measured; do not claim a quantified speedup.
- Demo sequence: login → source data → SQL/output → single report → retained rows/query/history/download → isolated source-correction/replay comparison → bulk results → selected advanced SQL demonstrations.
- Bulk scope warning for demo author: current all-customer UI selection means all 10,000 seeded customers. A smaller live batch needs a separately prepared smaller database; additive seeding does not shrink the current database.
- Replay test example: original 2×12.50 + 3×7.50 = 47.50; correcting the first line's unit price by +1 makes a fresh report 49.50, while old replay remains 47.50. Do not alter the shared benchmark fixture to stage this without an isolated rehearsal fixture.
- Benchmark table: four workers, 10,000 reports, 20,000 CSV/HTML files, zero failures, 0.088438 s submission, 6.029593 s preparation, 101.249024 s submission through observed completion. Preparation is inside that interval. Initial seeding and later sequential verification are excluded. Single recorded run; not proof that asynchronous SQL is inherently faster.
- Novelty is traceable historical reporting: approved versioned SQL, bound parameters, retained calculated rows, history and output hashes. Hashes verify bytes, not business truth. No AI/PDF/current inventory claim.
- Latest full regression rerun before GitHub publication on 18 October 2026: 43 passed in 31.00 s, API port 8001 because port 8000 was occupied. Earlier walkthrough notes cite the preceding 15.93 s run. Use the latest artifacts/test-results.txt when authoring slides; rerun before presenting if implementation changes.
- Show implementation limits honestly: filesystem outside database rollback; current configured requester identity is not separate web-user attribution; full source-record change audit is not implemented; second checkout rehearsal was on this computer, not the friend's physical laptop.
- Marking allocation supplied by user: PPT5/demo5/viva5/novelty2/report3. Final report remains a separate required artifact. Future inventory work waits for the user to be ready after the review walkthrough.
