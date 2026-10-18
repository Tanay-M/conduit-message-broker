# Novelty options after caching was declined

Date: 19 October 2026. Status: research/proposals only. The user explicitly declined caching and prefers a free hosted AI API if AI is added. Historical replay remains an existing feature, not the new addition proposed here.

## Clarification: application additions versus DBMS novelty

The user asked whether these proposals are novel specifically in the DBMS part. Mostly they are application-level additions using established database techniques: AI header mapping is AI/usability, staging/validation and SQL alerts are standard database engineering, and inventory what-if is business analysis. They should not be presented as new database algorithms or automatic evidence of DBMS innovation. The course's innovation/additional-feature criterion may allow such integration, but the evaluator decides.

A more directly database-focused candidate is an **AI-assisted SQL performance advisor**: capture a report query, existing indexes/schema and an EXPLAIN JSON plan; ask a hosted model for explained suggestions; evaluate reviewed index candidates in a disposable benchmark database; record baseline/candidate plans, repeated timings, buffer observations and index storage/write costs. Execute only controlled SELECT experiments, never arbitrary model-generated changes against the demo database. Keep PostgreSQL as the optimizer; the AI advises rather than replacing it. Index experiments retain the same query/results; any proposed query rewrite needs separate semantic validation beyond one fixture. This is an AI/database-engineering integration, not an original optimizer algorithm. PostgreSQL provides machine-readable EXPLAIN and documents index-usage experiments: [EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html), [examining index usage](https://www.postgresql.org/docs/16/indexes-examine.html). This candidate is unimplemented and has not been accepted as scope.

## Recommended addition: AI-assisted sales-data onboarding

Current Conduit mostly reports on seeded source data. Add a bounded CSV-import workflow so users can bring actual fictional sales records into the normalized database, inspect validation results and generate reports from the imported data.

### Proposed demonstration

Prepare two CSV exports representing the same supported sales-line structure but with different header names. For example ClientCode corresponds to customer_ref, OrderNo to order_ref, ItemCode to sku, Qty to quantity and Rate to unit_price. Require a stable line number/identifier and an explicit date format. AI proposes the mapping; the user confirms it against a preview. Do not infer prices, invent missing customers/products or silently reinterpret ambiguous dates.

Load a synthetic batch of 100 orders. Quarantine three entire orders containing deliberately invalid data: an unknown product/customer reference, a negative unit price, and a repeated/conflicting order-line identity. Commit the 97 valid orders only after validation. Correct a rejected order and retry without duplicating the previously accepted orders. Generate a customer statement/product ranking to show that the imported records affect actual SQL results.

These counts are a planned fixture, not an observed implementation result. Validate by order, not isolated line: importing the good lines of a partly invalid order would create an incomplete business document. A different valid batch policy is all-or-nothing, but it must be explicit in the UI and tests.

### Responsibilities

- AI: propose field mappings and optionally explain a supplied validation error. One/few calls per mapping session rather than a call per row or per report. Call count is a design goal, not a guarantee of provider behavior.
- Application: parse the supported CSV safely, enforce upload limits, preview the proposal, validate model output and require confirmation.
- PostgreSQL: retain batch/staging/error state, resolve existing business keys, validate typed data, enforce keys/checks/FKs, atomically publish valid orders, track rejected orders and duplicate-safe retries.
- Existing broker: can schedule the bounded validation/import work asynchronously once the database workflow is designed; report preparation/rendering continues as today.

Provisional database roles: import_batch, import_mapping, staging_sales_line, import_error. Store original row text/raw fields in staging and error records; final facts belong in existing normalized sales tables. Use explicit typed business keys/status/counts for metadata rather than hiding every relationship inside JSON.

PostgreSQL COPY supports CSV ingestion. Use COPY FROM STDIN via the application into staging, not a server-side arbitrary user filesystem path. COPY alone does not provide the proposed quarantine/correction workflow. [PostgreSQL 16 COPY](https://www.postgresql.org/docs/16/sql-copy.html). Final database constraints remain the authoritative last check even when application validation has passed. [PostgreSQL constraints](https://www.postgresql.org/docs/16/ddl-constraints.html).

### Retry and integrity requirements

Use stable order_ref plus line_number and a documented import identity. Exact repeats must not insert twice; conflicting reuse must be reported, not silently skipped with ON CONFLICT DO NOTHING. Existing order corrections should be a separate explicit workflow, not an accidental overwrite on import. Catch validation errors without aborting every subsequent statement; use controlled savepoints/transactions. Publish each accepted order, its lines and its import bookkeeping atomically. If inventory is later introduced, sales posting must use its stock procedure rather than bypassing it through direct imports.

Keep manual mapping as a normal fallback if the provider is unavailable. This is a distinct, honest manual workflow, not a cached/canned AI response. Configure the provider key only on the backend; the simple username/password demo login is unchanged.

This proposal strengthens insertion/management, relations/constraints, joins for validation, transactions, procedures and error evidence. Mapping CSV headers with an LLM is an established application pattern, not a claim of a new AI algorithm or guaranteed novelty marks.

## Option 2: explainable business exceptions

Compute business exceptions with SQL, retain their measured figures/rule version/supporting records, then optionally ask AI to describe those facts.

Planned fixture: two complete months with revenue 100000 and 60000. SQL calculates a 40% decrease, which exceeds a configured 25% threshold. Display the SQL, category contributions and source records. The AI can summarize the observed decline but cannot infer an unsupported cause such as supplier disruption.

Additional rule after inventory: stock below threshold. A high-order-value rule needs a defined baseline/minimum sample and must not label every unusual order as fraud. Allow reviewed/resolved states if a finding workflow is selected.

Database concepts: GROUP BY, LAG, aggregate/window baselines, rule versioning, finding/evidence relationships, indexes and transactional state changes. Build a complete calendar when zero-sale months matter; guard zero baselines and incomplete periods. These are SQL/statistical rules, not trained ML. [Window functions](https://www.postgresql.org/docs/16/functions-window.html), [aggregate functions](https://www.postgresql.org/docs/16/functions-aggregate.html).

This is the most contained enhancement if the user wants to extend the current reporting path with fewer ingestion changes.

## Option 3: inventory what-if/reorder scenarios

After inventory is implemented, let users change explicit assumptions without changing real stock: demand +20%, supplier lead time seven days, safety stock ten units. A simple assumed reorder rule of daily demand × lead time + safety stock yields 45 units at five/day, and 52 units at six/day. Store the scenario assumptions separately from authoritative transactions.

Join stock, recent sales and supplier configuration to compare baseline/scenario recommendations. Save scenario/version/results for inspection. AI can translate a scenario request or explain calculated differences, while SQL owns arithmetic and recommendations under the selected rule.

This is sensitivity analysis under assumptions, not an independently validated demand forecast. It depends on inventory/lead-time data that the current system does not yet have, so do not offer it as an immediately working feature.

## Free API recommendation and limits

Gemini Developer API lists free input/output for selected models; exact quotas are model/project dependent. Groq offers a free plan with model-specific limits. Both need a provider account/key. See the primary-source comparison in [FREE_AI_API_OPTIONS.md](FREE_AI_API_OPTIONS.md). Never promise unlimited free requests or guaranteed demo capacity.

Prefer one selected provider/model first; verify a live call and structured-response behavior after the user configures their backend key. Do not ask them to paste a secret into the chat or commit it to Git. Provider-side AI credentials do not restore the removed broker API-key login UI. Use synthetic/minimal payloads; Gemini's free-tier pricing page states content may be used to improve products. [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Groq free-plan limits](https://console.groq.com/docs/rate-limits).

## Selection recommendation

For a substantial new workflow: choose AI-assisted sales CSV onboarding with visible staging/validation/error repair. For the smallest useful reporting extension: choose SQL-backed business alerts with optional AI explanation. Natural-language selection of approved reports can be a companion convenience, but is a weaker standalone scope expansion with only three templates. Inventory what-if is a later option after inventory is real.

The current request is a choice/research discussion, not authorization to implement every option. No cache feature, application/schema changes, dependency installation, provider calls or GitHub push was performed for this note.
