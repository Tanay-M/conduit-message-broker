# Final-review demo and viva — 20 October 2026

Implemented on 19 October. Main story: **Conduit — Retail Operations and Explainable Reporting**. The PostgreSQL broker from Review 1 still prepares/renders reports asynchronously. New operations add a data-quality gate, inspectable question-to-SQL translation, SQL-backed analysis and atomic inventory posting.

## Start and prepare

For an existing configured checkout:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -Workers 2 -Port 8001
.\.venv\Scripts\python.exe -m reporting.demo_operations
```

Current verified workspace: http://127.0.0.1:8001/ (port 8000 was occupied by another process). On a clean laptop use the README's setup/seed first, then these commands. No Docker/local LLM is required. Demo fixtures are additive and repeat-safe; they do not reset stock or old reports. Sign in: admin / Conduit@123.

## Five-to-eight-minute presentation sequence

1. **Problem and idea.** A retailer needs to bring sales data into a relational database, reject bad records, manage stock, analyse sales and generate traceable reports without keeping the browser waiting.
2. **Import.** Open Sales import. Upload demos/data/sales_import_demo.csv (also downloadable in the UI). Inspect column mapping and preview: the good order has two lines totaling 100.00, while the negative-price order is rejected. Confirm to publish only complete valid orders. Show that rejected data stays in staging with an explanation. Upload sales_import_corrected.csv: unchanged good lines are duplicates, and the repaired order is accepted. On repeated rehearsals these stable order references already exist; that is idempotency, not a failure. To repeat first-time acceptance, use new order references in a copied CSV rather than deleting historical records.
3. **Inventory.** Show DEMO-KEYBOARD's explicit opening receipt of 50 units. Sell 7 at 2499.00 to REVIEW-001 with a new reference and date 2026-10-19; balance becomes 43 on a fresh fixture. Show the generated sales order and ledger match. Attempt 45 when only 43 remain: rejection leaves the order and stock unchanged. A repeated identical reference returns the original movement. Do not sell repeatedly with new references expecting the opening balance to reset. DEMO-MOUSE starts at 8 with threshold 10 for an immediate low-stock example.
4. **Ask your data.** Enter “Statement for REVIEW-001 in 2026” or “Top 5 products by revenue in February 2026.” Preview the chosen query and bound parameters; click Run approved query. The local rule parser works without AI and is explicitly labelled. Click Generate saved report to use the existing async worker pipeline and download CSV/HTML. Stock questions execute the inventory view; they are not new downloadable templates.
5. **Analysis.** Choose 2026-01-01 to 2027-01-01 and Analyse. Show revenue, distinct-order counts, category totals, monthly percentage changes and current low-stock alerts. Expand SQL evidence. A decline alert uses a visible 25% rule and only fully included completed calendar months; it does not establish a cause. Automated fixtures verify 1000→600 gives -40%. AI explanation is optional; deterministic text is not presented as AI.
6. **Database depth.** Show normalized sales relations, six new workflow tables, their keys/checks, the inventory view, append-only movement trigger, post_stock function, and the rollback/concurrency evidence. Show exact SQL/output rather than listing feature names alone.
7. **Existing scale result.** Present the retained 10,000-customer benchmark as a prior measured run (four workers, 10,000 reports, 20,000 CSV/HTML files, ~101.249 seconds). New fixtures change today's source row totals; do not represent the old benchmark as a rerun of these new workflows.

## Defensible additional-feature wording

“Our additional feature is an inspectable data-quality and reporting workflow. It quarantines invalid orders, lets users correct and retry without duplicates, translates supported business questions into visible SQL, and posts stock sales atomically. AI assists interpretation and explanation; PostgreSQL owns validation, calculations and transactions.”

These combine established techniques into coursework functionality. Do not claim a new optimizer/database algorithm, arbitrary natural-language SQL generation, fraud detection, AI correctness guarantees or guaranteed novelty marks.

## AI setup later

Add to the ignored .env.local:

```dotenv
CONDUIT_GEMINI_API_KEY=your_private_key
CONDUIT_GEMINI_MODEL=gemini-3.5-flash-lite
```

Restart the API (stop/start scripts can restart all owned local services). Select the Gemini checkbox in import, Ask your data or analysis. One mapping call sends headers only; query interpretation sends the question/reference date; analysis sends compact aggregate facts. No call is made per imported row or per generated statement. Configurable model IDs allow provider availability changes. Verify the account's free quota before the presentation. Keys never belong in Git or screenshots. Live provider inference has not been tested without the user's key; mocked integration tests do not establish live access or answer quality.

## Important boundaries for viva

- Natural language supports five approved query kinds, not arbitrary SQL: customer statements, product revenue rankings, monthly sales, stock on hand and low stock. Unknown/unsupported questions need clarification or a different input. Local parsing is not an LLM.
- Mapping must be confirmed before commit. It does not invent products/customers or repair ambiguous values automatically. CSV limits: UTF-8, 2 MB, 2,000 lines; explicit dates/decimal prices/stable order-line identities.
- Duplicate import means identical business content; conflicting order references are rejected, not overwritten. Acceptance is whole-order and all import publication/bookkeeping is transactional.
- CSV import represents historical sales; it does not change physical stock. New physical stock sales go through Inventory. No supplier purchasing, reservations, transfers, returns/reversals or accounting valuation is implemented.
- Stock starts from explicit opening receipts. Old seeded sales are not retroactively deducted. Balance must reconcile to net movement sum. Sale posting serializes access to a product balance; a concurrency test verifies two simultaneous sales of seven against ten units yield one success and three remaining.
- Analysis figures come from SQL in one REPEATABLE READ snapshot; current stock facts are distinguished from period sales. Stored AI summaries may be inaccurate and are labelled; raw numeric evidence remains visible.
- Existing report generation is asynchronous; the new small import/analysis/translation operations are bounded request/response operations. Do not describe import as a queued worker feature.
- No new cache subsystem, unrestricted model SQL, automatic index changes or local model installation was added.

## Grade evidence

| Criterion | Demonstration |
|---|---|
| Tables/constraints | Six new relations plus existing normalized facts; stock bounds, FKs, unique references and typed checks |
| Insert/manage | CSV staging/commit/correction and receipt/sale/reorder forms |
| Queries/joins/aggregates | Import reference resolution, ledger reconciliation, category/month analysis, approved NL SQL |
| Advanced features | Stock posting function and row locks, immutable movement trigger, transaction rollback, inventory view; existing report procedures/indexes remain |
| Presentation/viva/novelty | Connected Validate→Commit→Analyse→Report story with actual error/retry/oversell evidence |
| Report document | Update current schema, screenshots, new SQL, tests and limitations; this guide is not the final Word report |

Source: db/migrations/150_retail_operations.sql; reporting/{imports,inventory,assistant,analysis,ai}.py; tests/test_operations.py; tests/py/test_operations_ui.py. Executable database evidence is db/evidence/retail_operations.sql. Current schema additions and verified counts are in FINAL_REVIEW_SCHEMA.md.
