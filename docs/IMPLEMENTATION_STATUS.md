# Native reporting implementation status

## Final-review expansion — verified 19 October 2026

Implemented sales CSV staging/whole-order validation/manual or optional Gemini mapping/duplicate-safe commit; basic inventory receipts, atomic sales posting, immutable movements, reorder thresholds and reconciliation; five-kind natural-language to approved SQL with preview/execution/queued sales reports; SQL-backed analysis and optional Gemini explanations. Added six workflow tables and one inventory view through migration 150. Current logical table count is 34 (including schema_migration). Full regression: **57 passed in 26.88s**; new code passes Ruff. Real HTTP tests cover forms/auth/error/preview/commit and report integration. A database stock/rollback experiment is captured in artifacts/retail-operations-evidence.json. Live Gemini inference awaits the user's key and was not claimed as verified. The newer scope supersedes the earlier notes below about UI navigation, table count and deferred AI/inventory. No cache or query optimizer advisor was added. See FINAL_REVIEW_DEMO.md and FINAL_REVIEW_SCHEMA.md.

Verified on 17 October 2026. The accepted implementation plan is in IMPLEMENTATION_PLAN.md. The application now runs natively on Windows without Docker. Existing Docker installations and volumes were not removed; Docker packaging and the old Docker crash script were removed from this repository's active run path.

## Implemented

- Project-local PostgreSQL 16.15 cluster, Python 3.12.12 environment and pinned dependencies; setup/start/stop/doctor/verify PowerShell entry points.
- Checksum-tracked atomic SQL migrations, an example environment file, Git exclusions for local credentials/runtime/data/generated files, and a native Windows ASGI launcher compatible with psycopg async.
- Four normalized sales fact relations and six reporting/audit relations, real constraints, four-table reporting view, approved versioned SQL templates, ranking and running totals, a monthly materialized view, and explicit refresh.
- Transactional stored procedure submission with duplicate-identity checks, typed date/parameter validation, persistent consistent datasets, bounded coordinated enqueueing, and actual CSV/HTML generation.
- Request status/audit, unique successful results, checksum-checked downloads, SQL evidence endpoints, historical content replay, failed-job redrive, and expired-worker state reconciliation.
- Database evidence runner covering CRUD, filtering, joins, aggregation, HAVING, correlated subquery, procedure, transaction COMMIT/ROLLBACK, audit triggers, indexes/query plans and materialized-view refresh.
- Corrections for timestamp producer-sequence overflow, app dashboard identity/counts, private DLQ/audit web access, seeded administrator grant attribution, and contiguous acknowledgement position/counting.
- Reporting UI with a consistent navigation shell, report form and customer search, real run progress, saved-data/SQL/history inspection, downloads, replay, source-data exploration and a read-only SQL workspace. Username/password sign-in replaces browser token/key login; broker navigation and Administration integration controls are removed from the demo. Styles, icons and scripts are bundled locally; compiled CSS replaces the runtime Tailwind compiler.

The reporting API is currently administrator-only. It is a trusted local demonstration service. The direct-DB broker SDK is not presented as hostile tenant isolation. Files are published outside long database transactions; the database cannot roll back filesystem operations. Recovery tests cover publication-before-database-commit and duplicate deliveries, without claiming exactly-once external side effects.

Username/password accounts and eight-hour, revocable sessions are persisted in two additional authentication relations. Passwords use salted PBKDF2-SHA256 hashes; session identifiers are random and only their hashes are stored. First startup provisions the configured demo account without resetting existing passwords.

## Actual bulk results

The successful large run used 10,000 fictional customers, 100,000 orders and 300,000 order items. Four native workers completed 10,000 distinct report requests and produced 20,000 files: one CSV and one HTML per request. The benchmark verified every result row and output checksum. No permanently failed request remained.

| Measurement | Observed |
|---|---:|
| Synthetic source loading | 6.862 seconds |
| Report submission | 0.088 seconds |
| Consistent dataset preparation | 6.030 seconds |
| Submission through observed generation completion, including startup/polling | 101.249 seconds |
| Median completion latency from request creation | 49.418 seconds |
| p95 completion latency from request creation | 91.958 seconds |
| Completed requests | 10,000 |
| Verified files | 20,000 |
| Output bytes | 88,773,656 |

Raw machine/configuration/results are in [report-benchmark-10000.json](../artifacts/report-benchmark-10000.json). The 101.249 seconds exclude source seeding and the subsequent sequential output-verification pass. This is one measured CSV/HTML run on this shared Windows machine, not a repeated-trial capacity estimate, PDF measurement, or pure PostgreSQL throughput result. File hashes prove agreement with recorded output bytes, not SQL semantic correctness; known-fixture totals and report-content tests provide separate correctness evidence.

Earlier successful 100- and 1,000-report runs are retained in artifacts. The first four-worker 1,000 run exposed partition-lock deadlocks during batch enqueue. A later migration coordinates bounded enqueue chunks; the repeated 1,000 run and 10,000 run then succeeded. Performance claims should use the retained successful results and these limitations.

## Tests and portability

The final full-suite result is recorded in [test-results.txt](../artifacts/test-results.txt). It covers the existing HTTP/SDK/UI contracts and new SQL/worker/reporting API cases: known exact totals, FK/CHECK/UNIQUE/date contracts, rollback without orphan jobs, submission identity, historical replay, summaries/bulk counts, interrupted result publication, repeated delivery, retry/DLQ recovery, final claim expiry, malformed UUID jobs, large sequences, out-of-order acknowledgement, dashboard counts and private DLQ access. Static lint checks also pass for the new reporting modules and tests.

A separate source checkout under a path containing spaces was bootstrapped with its own Python environment and a fresh native cluster on port 55433. Its API ran on 8001, generated a report and returned the CSV download, then its processes/cluster were stopped. The rehearsal reused downloaded PostgreSQL/uv archives; Python and dependencies were provisioned through the setup. It did not copy a database or virtual environment. [Portability evidence](../artifacts/portability-rehearsal.json).

This verifies a fresh checkout on this Windows computer, not a second physical laptop or another OS. The main local system uses database port 55432 and API port 8000. First-time bootstrap needs internet; Windows C++ runtime prerequisites still apply. Prepare the friend's Windows x64 laptop before the review and run doctor/verify there. The root README contains the exact clone/setup/seed/start commands.

## UI verification

The updated full suite contains 43 passing tests, including real HTML-form submission, duplicate submission identity, worker completion, inspector pages/downloads, validation and access boundaries. Login regressions verify generic credential errors, password/session hashing, session rotation, expiry, disabled accounts and logout revocation. SQL-result regression coverage includes decimal totals, dates, timestamps, UUIDs, NULL and escaped text. Browser checks exercised customer selection and report generation through inspection, SQL aggregation and error feedback, customer-reference search, and mobile navigation/layout at 390px. Screenshots are retained under artifacts/ui. These checks used the native local PostgreSQL/API/workers and actual data.

## Remaining deliverables

A replacement presentation, the final Word report and optional AI remain deferred. The implemented UI exposes the verified database/reporting operations. The demonstration navigation contains only Reports, Data explorer and SQL workspace. The existing queue continues handling asynchronous report generation internally.
