# Final-review implementation — 19 October 2026

Accepted scope: simple sales CSV import, natural-language requests translated to approved parameterized SQL, SQL-backed sales analysis, and basic inventory. No caching or SQL tuning advisor. The final review is tomorrow; keep one cohesive retailer workflow and existing reporting/queue behavior.

Completion status: core implementation and UI are complete; 57 regression tests pass (26.88 seconds), stock/rollback evidence and the updated 34-table catalogue were captured. Native API is running on port 8001. Gemini live inference remains pending user key configuration, as explicitly deferred by the user. See FINAL_REVIEW_DEMO.md for rehearsal and actual limitations.

1. Add versioned database migration for stock balances/append-only movements, atomic stock/sale posting, staged import/error records, and assistant/analysis evidence.
2. Implement bounded CSV validation, whole-order acceptance, duplicate-safe retry and correction. Preview mapping/errors before committing. AI mapping optional; manual mapping works offline.
3. Add free-tier Gemini adapter using backend-only configuration, approved SQL intent selection and facts-only analysis. Without a provider key use explicitly labelled local parsing/manual workflows. Never execute arbitrary generated SQL.
4. Add inventory receipt/sale/reorder operations and SQL sales analysis, integrated with the professional reporting workspace.
5. Add meaningful integrity/concurrency/import/AI-boundary tests, run existing regressions, inspect UI, and prepare a concise demo/evidence guide and sample CSVs.

Presentation story: **Validate → Commit → Analyse → Report**. Additional feature is an inspectable data-quality workflow: invalid orders are quarantined, accepted orders commit atomically, retries do not duplicate them, and a stock sale updates sales and stock together. AI assists mapping/intent/explanation; PostgreSQL enforces correctness. These are coursework additions built with established techniques, not claims of a new database algorithm.

Inventory cutover: old seeded sales remain historical; new inventory starts from explicit receipts/opening stock, with stock posting applied to new sales. No deduction of all historical orders from an empty ledger.

Provider key: CONDUIT_GEMINI_API_KEY in ignored .env.local; configurable model. Live AI verification depends on user configuration. Manual features and deterministic analysis must work independently. Update demo/report/PPT references with actual test evidence when complete. Authoring the final PPT/Word report is separate from this implementation request.
