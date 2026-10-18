# DBMS-focused expansion and novelty research

Research date: 18 October 2026. Status: recommendations only, not accepted scope or implemented features. No schema, UI, runtime configuration or GitHub publication is changed by this research.

**User decision, 19 October 2026:** caching was declined. Its discussion below is retained as historical research, not the current recommended implementation scope. The user prefers investigating a free hosted AI API and useful additions beyond historical report replay. See [NOVELTY_OPTIONS_NO_CACHE.md](NOVELTY_OPTIONS_NO_CACHE.md) and [FREE_AI_API_OPTIONS.md](FREE_AI_API_OPTIONS.md).

## Recommendation

Expand Conduit from sales-report generation into a **retail operations and reporting system**. Keep the retained PostgreSQL message broker as the mechanism for report preparation, refresh and rendering.

The strongest combination is:

1. Inventory/purchase/sales posting: a real transactional business workflow.
2. A change-aware report calculation cache: repeat expensive calculations only when necessary, with visible freshness and correct invalidation.
3. Report comparison and/or SQL-based operational alerts: demonstrate what changed and which records support an observation.
4. Optional AI report assistant: translate language into approved report parameters and explain SQL-derived facts. Keep the normal form interface fully functional without AI.

These are proposed applications of established techniques, not claims of globally original inventions. The faculty's additional-feature criterion rewards a useful demonstrable extension; adding dependency names alone does not establish novelty.

## Existing project baseline

Inspected current migrations, settings, design/status documents and native extension files. The current project already has four sales relations, three report templates, immutable template/dataset history, replay, report-state audit, a monthly materialized view, SQL evidence, native PostgreSQL 16.15 and asynchronous CSV/HTML generation. The last recorded full suite has 43 passing tests. Full logical schema count is 28, including broker/auth/migration infrastructure; the business scenario itself is four sales tables.

The scope can feel narrow because the UI mainly reads seeded sales data and generates reports. Creating an additional source-data workflow is more meaningful than increasing internal table count or generating a larger synthetic batch. Current history replay and the materialized view must not be presented as newly added features.

## Candidate comparison

Complexity is relative implementation/rehearsal effort, not a promised duration or measured result.

| Candidate | User-visible addition | DBMS relevance | Relative effort | Offline/native suitability | Recommendation |
|---|---|---|---|---|---|
| Inventory, receipts and sales posting | Receive goods, sell goods, reject insufficient stock, generate stock reports | Very high: relationships, constraints, procedures, locking, transactions, aggregates | Medium–high | Strong with existing PostgreSQL | Main scope expansion |
| Change-aware report cache | Visible cache miss/hit/invalidation; reuse calculated data without stale answers | Very high: dependency/version metadata, triggers, isolation, uniqueness, indexes | Medium–high for correct concurrency | Strong; no separate cache service required | Main technical additional feature |
| Report comparison | Compare two saved reports; show added/removed/changed rows and totals | High: JSONB/table conversion, joins, aggregates, history | Medium | Strong | Best short extension to current replay |
| SQL-based anomaly and stock-risk alerts | Flag unusual sales or low stock with evidence | High: windows, statistical aggregates, rules, versioned observations | Medium | Strong; AI explanation optional | Add after inventory if useful |
| AI report assistant | Natural-language request resolves to an approved report, filters and SQL preview | Moderate alone; stronger when interpretation/audit is persisted | Medium, plus model integration/rehearsal | Conditional; local model is another runtime | Optional interface layer |
| Incremental summary maintenance | Update affected aggregate buckets instead of refreshing all history | Very high | High for joins/updates/deletes | Custom SQL possible; extension adds packaging work | Stretch alternative to cache, not another mandatory subsystem |
| Vector/semantic report search | Search a large report/document catalogue by meaning | Real database feature but weak need for only three templates | Medium–high with embeddings/native packaging | Additional model/extension provisioning | Defer |
| Query performance laboratory | Compare plans and repeated timings for equivalent queries/indexes | Very high academically; limited business scope | Low–medium | Strong | Useful demo panel, not primary novelty |

## 1. Inventory and purchasing: expand the business workflow

### Business purpose

Show where products come from, how stock changes, and how transactions produce reports. Commercial inventory systems use posted ledger entries for quantity increases/decreases and link them to purchases and sales. This is an established real application pattern. [Microsoft Business Central: Manage inventory](https://learn.microsoft.com/en-us/dynamics365/business-central/inventory-manage-inventory).

For a bounded first version use one stock location and one unit of measure per product. Suggested new relation roles: supplier, purchase_order, purchase_order_item, stock_movement, inventory_balance and reorder_rule. Reuse the existing customer/product/sales_order/order_item. These names and six-table sketch are provisional, not a finalized schema. Multiple warehouses, reservations, payments, tax, FIFO valuation and a full accounting ledger are separate scope.

### Demo

1. Receive 50 units of a product against a purchase receipt.
2. Complete a sale for 7: balance becomes 43.
3. Attempt a sale for 45: reject it; no partial sale/stock movement persists.
4. Set a reorder threshold of 45: the product appears in the low-stock report.
5. Inspect the movement ledger and generate stock/sales reports asynchronously.

Add a second-session exercise with stock 10: two transactions each try to sell 7. Exactly one may succeed; final stock must be 3. This is more convincing concurrency evidence than explaining worker processes alone.

### Database design principles

Use a stored posting operation to write the business document, its lines, stock movements and balance update in one transaction. Protect each balance row with a conditional decrement or row lock; acquire multiple product locks in a stable order. A ledger SUM checked without serialization is vulnerable to concurrent overselling. PostgreSQL documents row locking and deadlock behavior. [Explicit locking](https://www.postgresql.org/docs/16/explicit-locking.html).

Positive line quantities, valid FKs, unique posting identities and appropriate balance checks belong in the database. A CHECK constraint cannot safely express an arbitrary aggregate rule across all movement rows; use a protected balance/posting transaction and reconcile it against the ledger. [PostgreSQL constraints](https://www.postgresql.org/docs/16/ddl-constraints.html).

Retain movement history: reverse a posted movement rather than deleting it to conceal a cancellation. The inventory balance is a maintained projection, not an unrelated second truth. Add a reconciliation query asserting balance equals opening stock plus net movements. Restrict direct writes that bypass posting operations for application accounts.

Existing benchmark data requires a cutover plan. Do not subtract all 100,000 historical completed orders from an empty new inventory table. Introduce explicit opening balances at a documented cutover, retain earlier sales as historical data, and apply stock posting to the new workflow. Corrections to posted quantities require a reversal/reposting policy; price-only corrections do not change physical quantity.

### New reports

- Stock on hand and movement history.
- Products below reorder threshold.
- Receipts by supplier/product/period.
- Sales velocity and explicitly assumption-based days of cover.
- Optional stock-versus-sales reconciliation.

Avoid adding a profit/margin report before defining purchase cost and costing policy; catalogue price is not cost. More report codes require updating the current template-code constraint, parameter contracts, procedures, API/form, rendering and tests. Region filtering is also a proposed extension, not currently supported by every template.

## 2. Change-aware report cache: strongest cache feature

### User story

The same manager asks for the same sales ranking twice with no source changes. The second request reuses calculated rows. Correct a source order, ask again, and show a cache miss/invalidation followed by the new figures. Previously generated historical reports remain unchanged.

Caching saves repeated computation; it is not the same as submission idempotency (same submission identity) or historical replay (open a specific old report). A new logical request can reuse a valid calculation while retaining its own request/history identity.

Cache consistency is a real design problem; a basic cache-aside approach does not guarantee freshness under concurrent/external updates. Expiration alone does not prove current data. [Microsoft Cache-Aside pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside).

### Proposed PostgreSQL design

Start with a conservative transactional source revision and a report_cache table. The conceptual key includes:

`template/version + canonical typed parameters + relevant source revision + access scope`

Reuse calculated rows, then preserve the immutable per-request dataset as today. If output bytes are also reused later, renderer version/output format and metadata semantics need their own identity; sharing file paths is not part of this initial proposal.

Source-table triggers advance a revision in the same transaction as relevant INSERT/UPDATE/DELETE operations. Cover customer/product label changes as well as quantities/prices/order dates/status. Include a TRUNCATE policy or prohibit it through the application role. Rollback must roll back the source change and its revision update together.

Read the revision and calculate/read the source rows under a coherent snapshot. REPEATABLE READ gives the relevant stable snapshot, with retries where necessary. Never calculate old rows and label them with a newer revision fetched afterward. [PostgreSQL transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html).

A cache result belongs to the source snapshot observed during preparation; it does not promise to include a source transaction committed after that snapshot. Changes make older revisions ineligible for later current-data requests, not retroactively invalid historical reports. Start with broad invalidation. A single global revision row can serialize writes; measure that cost and keep the first version bounded. Period/customer dependency tracking is a later optimization, not a correctness claim for the initial version.

Concurrent identical misses need a unique calculation identity and coordinated builder/publication to avoid duplicate heavy work. Transaction-scoped advisory locks are one possible coordination mechanism; they only work when the participating code follows the protocol. [PostgreSQL advisory locks](https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS).

Use statement-level triggers to avoid updating revision metadata once per affected row during a large statement. PostgreSQL also supports transition tables containing the statement's affected rows, useful for future affected-period tracking. This still needs event-specific handling for updates, deletes and relationship/label changes. [CREATE TRIGGER](https://www.postgresql.org/docs/16/sql-createtrigger.html).

### Presentation evidence

Expose calculation source (computed/cache), source revision, prepared-at time, hit/miss counts and the query used. Measure actual SQL/preparation time separately from file rendering and queue delay. Compare identical workloads with/without result reuse over repeated trials. A faster second query can partly reflect PostgreSQL/OS buffer warming; do not attribute every millisecond to the new cache or invent a speedup.

A clear correctness demonstration is: MISS → identical request HIT → committed source correction → MISS → original historical report unchanged. Add rollback and concurrent-change tests.

### Materialized view alternative

The project already has mv_monthly_sales. PostgreSQL 16 REFRESH replaces the view's contents. CONCURRENTLY permits continued reads under documented unique-index/population requirements; it is not automatic incremental maintenance. [REFRESH MATERIALIZED VIEW](https://www.postgresql.org/docs/16/sql-refreshmaterializedview.html).

For an initial dashboard, an explicitly refreshed materialized view with a visible refresh time is simpler. It is a useful improvement if wired into actual dashboard reads, but merely renaming the existing view “smart cache” adds no new behavior. Choose the cache/refresh strategy based on the selected use case rather than building every variant.

Redis would add a separate service and freshness coordination; it is not needed for this bounded PostgreSQL-centered demonstration. PostgreSQL's page buffers and prepared execution plans must not be confused with the proposed application-level reusable result cache.

## 3. Report comparison: extend existing historical replay

The current system can show old rows and fresh rows separately. Add a comparison operation that aligns compatible report rows and shows added, removed and changed values, plus reconciled total deltas.

For example, a report total changes from 47.50 to 49.50. Display the affected order line, old/new quantity and unit price, and its +2.00 contribution. SQL can expand saved JSONB rows into records and FULL OUTER JOIN old/new data to include unmatched rows. [JSON functions](https://www.postgresql.org/docs/16/functions-json.html), [joined tables](https://www.postgresql.org/docs/16/queries-table-expressions.html#QUERIES-JOIN).

Current customer-statement snapshots contain order_ref and SKU but omit line_number/order_id in the output. The same SKU can legitimately appear on two lines. For reliable future line comparison, add stable row identity through a NEW template version and corresponding bulk preparation update; do not overwrite old snapshots or match by JSON array position. Existing ambiguous snapshots must get a compatibility warning or aggregate-only comparison. Product rankings have SKU identity, but top-N truncation means a product leaving the displayed set does not necessarily mean it had no sales.

Comparisons need the same report meaning, period, filters and compatible versions. A changed period should be explicitly labeled a period comparison, not a correction. Dataset differences establish changed values, not the actor/reason behind the original database edit. To answer who/why, add a separate source_change_log with old/new values, actor and reason recorded by an authenticated change workflow. The existing report-state audit does not provide that information.

This is a compact, useful feature with low deployment dependency and strong join/history demonstrations. It is an application of established techniques, not a claim of formal provenance or arbitrary-query causal analysis.

## 4. SQL-based alerts, with optional AI explanations

Examples: unusually high order value, product sales falling sharply versus a prior comparable period, or stock below its threshold. Use SQL to compute the observation first. LAG, windowed AVG and statistical aggregates support comparisons and baselines. [Window functions](https://www.postgresql.org/docs/16/functions-window.html), [aggregate functions](https://www.postgresql.org/docs/16/functions-aggregate.html).

Proposed metadata roles: insight_rule (version, threshold/window, minimum sample), insight_run (data cutoff/version), insight (measured value, baseline, severity, supporting record IDs) and optional explanation record (exact input facts/model/version/text).

Demo: create a controlled unusually large order, run the rule, display the measured value, baseline and matching SQL rows. Optionally explain the finding in ordinary language. Detection by SQL thresholds is rule/statistics-based analysis, not a trained AI model. Do not claim fraud or a causal reason for a sales fall from an alert alone.

Daily windows require a complete date series, zero-sale days and deliberate handling of partial days. Exclude the current observation from its historical baseline, require sufficient samples, and compare suitable weekdays/periods if needed. The present regular synthetic benchmark is not sufficient evidence of real anomaly-detection accuracy; create separate controlled fixtures and document false positives/limitations.

AI can verbalize approved facts; it must not invent supplier delays, customer motives or other unsupported causes. Preserve the deterministic alert/table view if AI is unavailable. See the companion AI research note for model/structured-output sources.

## 5. AI report assistant

Recommended request: “Show the five highest-selling products in February 2026.” The model proposes product_sales, dates and top_n=5; application validation resolves exact meaning; the user previews filters/SQL; the existing reporting path executes approved SQL. Store the original question, interpreted parameters, validation/confirmation, optional model version and resulting run link.

Ambiguous “last month” must resolve against a displayed reference date/timezone; “best products” must distinguish revenue from quantity. Unsupported requests should say what is unsupported, rather than silently generating a different report. Authorization and database parameter validation remain mandatory even for JSON-schema-conforming model output.

This makes the project easier to use, but natural-language routing over only three templates adds less DBMS depth than inventory transactions or cache correctness. Add it after expanding the useful report catalogue. Do not market deterministic keyword parsing or template text as a live LLM. Local AI adds a model download/runtime and must be benchmarked on the actual laptop; a hosted option adds network/key/cost dependence. Keep manual report forms as the authoritative offline fallback.

Companion primary-source investigation: [AI_DBMS_FEATURE_RESEARCH.md](AI_DBMS_FEATURE_RESEARCH.md).

## Stretch candidates and deployment checks

### Incremental aggregation

For a monthly/category summary, a changed order line could update affected buckets rather than scan all history. Updates moving an order between dates/categories, cancellation/deletion and empty-bucket cleanup require both old and new contributions; arbitrary joins and window/top-N queries are harder. A narrow transactional summary table can be an educational implementation, but do not claim to have implemented a general incremental-query engine.

pg_ivm is an actual PostgreSQL extension providing incremental view maintenance through immediate triggers; it is separate from native REFRESH and supports a constrained query set. [pg_ivm official repository](https://github.com/sraoss/pg_ivm). It is not part of the current native bundle; integrating an external extension adds provisioning/rehearsal work. Treat it as research/stretch scope, not a silent install or mandatory dependency.

### Query performance laboratory

Capture equivalent query plans before/after justified indexes in a disposable benchmark database and report repeated timing/buffer observations. pg_stat_statements tracks normalized query statistics but requires shared_preload_libraries configuration and a server restart. Its control file exists in the current native bundle; that is not proof that it is enabled. [pg_stat_statements](https://www.postgresql.org/docs/16/pgstatstatements.html). Do not make disruptive shared-cluster configuration changes for this research.

The current extension directory includes pg_trgm, pg_stat_statements, pgcrypto and btree_gist control files; vector and pg_ivm control files were absent when inspected. Presence/absence is a local packaging observation, not a universal claim about PostgreSQL installations.

## Proposed coherent project demonstration

Receive stock → post a sale transaction → inspect sales/stock SQL → request a report → repeat it and observe a valid cache hit → correct source data through an audited workflow → observe invalidation/new calculation → compare historical and current reports → optionally request another report in natural language.

The broker naturally processes report/refresh work in the background. Do not introduce Kafka, Redis, microservices or an AI framework solely to increase apparent size. Core database correctness and manual workflows should remain demonstrable offline.

## Mapping to the assessment

| Review requirement | Proposed evidence |
|---|---|
| Tables and constraints | Supplier/purchase/movement relationships; positive quantities; valid posting states; unique posting identities |
| Data insertion and management | Receive goods, complete/reverse sales, maintain reorder rules; source changes through visible workflows |
| Queries, filtering, joins, aggregation | Supplier receipts, movement ledger, low-stock and velocity reports; report comparison; alert evidence |
| Advanced database features | Atomic posting procedure, locking/conditional updates, invalidation triggers, snapshot-consistent cache, views/indexes |
| Presentation | One connected retailer scenario, matching SQL/output, explicit cache state and historical comparison |
| Novelty/additional feature | Observable freshness-aware reuse and/or explainable report differences; optional real AI intent layer |

Marks remain PPT5/demo5/viva5/novelty2/report3 as supplied by the user. This research maps features to evidence; it does not guarantee marks or replace the final PPT/report.

## Recommended execution order if the user accepts scope

1. Agree the bounded inventory/posting workflow and report catalogue; preserve existing evidence/tests as baseline.
2. Implement database schema, posting procedures and known-fixture/concurrent-stock tests, then minimal operational forms.
3. Add the new stock reports to the existing asynchronous reporting path.
4. Implement cache identity/invalidation/snapshot consistency and visible metrics, with stale-data/rollback/concurrency tests.
5. Add compatible report comparison with stable row identities; source-change audit if who/why is required.
6. Select either SQL alerts or a genuine AI intent assistant as the optional final addition; avoid making both mandatory prematurely.
7. Refine UI and rehearse native/offline behavior on the actual demo laptop; rerun evidence and update schema/normalization/PPT/report.

No implementation is authorized by this note alone. The user requested research; previously deferred inventory remains a proposal until they choose to proceed.
