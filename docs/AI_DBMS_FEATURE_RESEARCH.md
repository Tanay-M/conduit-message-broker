# AI additions for Conduit: DBMS-focused research

Research date: 18 October 2026. Status: researched proposals only; no feature implementation, dependency installation, migration, commit or push was performed for this note.

**19 October steering:** The user declines caching as a new feature and is interested in free cloud AI APIs rather than requiring a local model. See `docs/FREE_AI_API_OPTIONS.md` for current Gemini/Groq research. Historical replay already exists; the new novelty candidates are inspectable natural-language report intent and SQL exception investigations with optional grounded AI explanation. Neither is implemented by these notes.

## Recommendation

Expand the business workflow first, then add one modest AI capability. The strongest combination is **SQL-generated business exception reports with inspectable evidence, plus an optional natural-language interface that selects approved reports**. PostgreSQL must remain responsible for figures, constraints and historical evidence. An LLM can interpret a request or explain already-calculated facts.

This is an engineering recommendation for the current project and grading priorities, not a claim that these techniques are new inventions or that a particular feature guarantees novelty marks.

## Existing code that constrains the proposals

- `README.md` explicitly says AI is not implemented.
- `db/migrations/070_reporting_routines.sql` seeds exactly three report codes: `customer_statement`, `product_sales`, and `monthly_sales`. Templates are approved SQL, and `reporting.calculate` binds customer/date/top-N parameters through `EXECUTE ... USING`.
- `db/migrations/130_report_parameter_contract.sql` validates the latest report-submission parameter contract. `reporting/service.py:submit` calls that procedure inside a transaction.
- `reporting/service.py:evidence` joins a report request to its selected immutable template version, retained rows, parameters and result metadata. An AI feature should attach to this evidence rather than bypass it.
- `docs/FUTURE_WORK.md` records inventory as deferred until the user is ready; this research does not implement or approve that expansion.

## 1. Natural-language requests mapped to approved report intents

### Faculty-visible demonstration

Type: “Show the top five products by revenue in January 2026.” Show the proposed interpretation before submission:

```json
{
  "template_code": "product_sales",
  "customer_ref": null,
  "start_date": "2026-01-01",
  "end_date_exclusive": "2026-02-01",
  "top_n": 5,
  "bulk": false,
  "needs_clarification": false
}
```

The application validates the fields, displays the interpretation and template SQL with bound parameters, and submits through the existing reporting procedure after the user confirms the preview. PostgreSQL still calculates all totals.

For “Generate Raj's statement for last month,” an ambiguous customer name must produce candidate customers or a clarification. Relative dates should be resolved against an explicit application date/timezone and shown as absolute dates. Do not silently turn a missing customer into all-customer bulk mode. A fabricated model confidence percentage is not a reliable decision rule.

### Evidence and database scope

Proposed `assistant_request` rows can store request ID, authenticated actor, original prompt, provider/model version, schema/prompt version, structured proposal, validation outcome, selected template version, confirmed parameters, confirmation time and eventual run ID. Use typed columns for keys/status/dates where those are queried or constrained; JSONB can preserve the raw structured proposal. Apply foreign keys, allowed-state checks, indexes and access rules.

A viva can show the complete chain: prompt → proposal → validation/confirmation → approved SQL → retained dataset → output. Demonstrate malformed intent, ambiguous customer and unavailable AI provider as well as a successful request. This is more educational than showing an uninspectable chatbot reply.

### Provider support and boundaries

Ollama supports a JSON Schema in its local API's `format` field, and its documentation demonstrates validating responses with Pydantic. This constrains output shape; it does not establish that the customer's meaning, date range or chosen template is correct. The current documentation says its cloud service does not support structured outputs, so verify provider-specific capability rather than assuming cloud/local parity. [Official Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

Do not ask the model to write executable SQL. It receives only the approved report catalogue and necessary entity-resolution context. Unsupported requests stay unsupported until a developer adds a reviewed template. Schema-valid JSON can still contain invalid IDs, inappropriate bulk scope or nonexistent dates; application and database validation remain mandatory.

### Portability and cost

Ollama has a native Windows application and a standalone Windows distribution, so Docker is unnecessary. [Official Windows documentation](https://docs.ollama.com/windows).

Its FAQ documents local-only mode, configurable model retention and the increased memory required by concurrent requests/context. These are useful controls for an 8 GB laptop, but do not prove that any chosen model will run quickly alongside PostgreSQL and the browser. [Official Ollama FAQ](https://docs.ollama.com/faq).

Proposed trial: benchmark one small, quantized model with one request at a time and bounded context on both demo laptops. Record cold/warm latency, peak memory, exact intent accuracy on a fixed prompt set and clarification failures. Download the runtime/model before the demo. Keep the existing form usable if the AI service is absent; never label a canned fallback response as live AI. Cloud inference adds credentials, network availability and data-sharing considerations; local inference adds memory and installation cost. Select only after measurement.

Assessment: **medium DBMS relevance, strong visible extra feature, moderate implementation/deployment effort**. It complements a complete data workflow but does not by itself expand that workflow.

## 2. SQL business exception detection, with optional grounded AI explanation

### Recommended scope

Add an “Exceptions and insights” report with two initially explicit rules:

1. Revenue for a completed calendar month falls more than a configured percentage below the preceding completed month, with a minimum prior revenue to avoid tiny-baseline noise.
2. An order exceeds a documented historical order-value threshold calculated from an appropriate baseline, such as a chosen percentile with a minimum sample size.

These are SQL rules/statistical checks, not a trained machine-learning model. PostgreSQL supports aggregates and statistical functions, and window functions such as `LAG` support prior-period comparisons. [Aggregate functions](https://www.postgresql.org/docs/16/functions-aggregate.html), [window functions](https://www.postgresql.org/docs/16/functions-window.html).

The exact thresholds, minimum sample sizes and evaluation periods are proposed policy decisions, not facts established by these sources. Calling a flagged order “fraud” or claiming the database proved a cause would be wrong.

### Database design and teaching value

Proposed entities: `rule_version`, `analysis_run`, `finding`, `finding_evidence`, and optional `finding_explanation`. Keep rule SQL/version/thresholds, baseline period, observed metric, expected comparison, source dimensions and retained evidence. Connect findings to customer/product/order keys when relevant; do not squeeze all relationships into opaque text.

This provides useful joins, grouped subqueries, window functions, numeric calculations, constraints, unique identities to prevent duplicate findings, indexes and transactions. Findings should have reviewed/resolved states with state-history audit if that workflow is in scope. Original detection evidence remains historical even after a business correction; reevaluation creates a fresh run.

### Demo

Seed an isolated scenario with two complete months: previous revenue 100,000 and current revenue 60,000. SQL calculates a 40% decline and flags it under a 25% threshold. Show category breakdowns, which may establish that a particular category contributes most of the observed fall.

The optional LLM receives a compact evidence object with rule ID/version, dates, figures, percentage and category contributions. It may explain: “Revenue decreased 40% against the preceding month and crossed the configured 25% threshold.” It cannot assert unsupported causes such as a supplier disruption. Display calculated facts alongside the prose and mark the text as AI generated. Store the evidence hash, model/prompt version and explanation. A fixed SQL-generated explanation works offline without AI.

### Correctness conditions

- Build a calendar series if missing months must count as zero; `LAG` over existing rows alone can compare nonadjacent calendar months.
- Exclude or explicitly label incomplete months. Use a consistent timezone and half-open date boundaries.
- Handle zero baselines without division errors. Percentage decline is undefined when the prior amount is zero, so use a separate rule.
- Avoid counting an order once per order item; aggregate line totals to orders before order-value statistics.
- Threshold exceedance is a business exception, not proof of misconduct or causality. Seasonality and insufficient history can make a simplistic statistical rule noisy.
- Current catalogue price versus historical sale price is not automatically an anomaly: historical discounts and price changes can be legitimate.

Assessment: **high DBMS relevance, easy seeded demo, works entirely offline without AI, and creates a useful workflow beyond downloading reports**. This is the best first option of the AI-related proposals because the valuable core remains SQL.

## 3. pgvector semantic retrieval: valid technology, poor first priority here

pgvector is a PostgreSQL extension for vector similarity search. It supports PostgreSQL 13+, exact nearest-neighbour search, and optional HNSW/IVFFlat approximate indexes that trade recall for speed. Its official Windows source-build instructions require Visual Studio C++ tooling, an x64 tools prompt and `nmake`. [Official pgvector repository](https://github.com/pgvector/pgvector).

Potential use: find a relevant approved report or documented historical insight from a paraphrase such as “Which products bring in the most money?” Store an embedding with catalogue text and retrieve candidate template IDs, then validate intent and parameters as in option 1. Vector proximity neither verifies SQL nor supplies missing dates/customer IDs.

Ollama exposes embeddings for semantic-search applications and advises consistent embedding generation for indexing and queries. The embedding model is an additional model dependency. [Official Ollama embeddings documentation](https://docs.ollama.com/capabilities/embeddings).

With only three templates, direct selection, keyword aliases or a small structured classifier are simpler. Repeating three templates thousands of times to create a vector-search workload would be artificial. If the project later contains a useful catalogue of report definitions, descriptions, saved investigations or a real text corpus, reevaluate semantic retrieval against keyword search using labelled relevance examples.

PostgreSQL already has native full-text search and GIN indexes, providing a deployment-friendly lexical baseline without an embedding service. Lexical search does not promise semantic equivalence for paraphrases. [Text-search introduction](https://www.postgresql.org/docs/16/textsearch-intro.html), [text-search indexes](https://www.postgresql.org/docs/16/textsearch-indexes.html).

If vector retrieval is later selected, prototype exact search first. Do not add HNSW simply to list another advanced feature. Benchmark relevance, latency and memory with realistic corpus size. Version embedding model/dimensions and rebuild on model changes. Verify matching PostgreSQL 16 Windows extension binaries and setup on the friend's machine; extension files and model weights do not arrive merely by pushing Python/SQL source to Git.

Assessment: **real DBMS technology, high extra deployment effort, currently weak justification**. Defer for the present three-template catalogue.

## Proposed order, pending the user's choice

1. Expand the relational business workflow with an agreed module, such as the previously requested inventory/purchases/stock-movement lifecycle.
2. Implement SQL exception rules and historical evidence linked to that business workflow.
3. Add optional, inspectable natural-language report selection or explanations. Choose one first and keep all authoritative calculations in SQL.
4. Reconsider semantic search only if a realistic text/catalogue use case emerges.

No arbitrary text-to-SQL, model training, production AI reliability or novel database-engine research is required to make this a stronger college DBMS project. Evaluate the chosen expansion by visible business actions and inspectable database behavior rather than by increasing table or technology counts.
