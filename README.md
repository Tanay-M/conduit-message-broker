# Conduit asynchronous business reporting

A DBMS project covering validated sales-data import, basic inventory, inspectable natural-language query translation, SQL sales analysis and asynchronous reports. PostgreSQL enforces relationships, constraints, atomic stock posting, audit history and retained report data. Conduit's existing PostgreSQL queue schedules dataset preparation and CSV/HTML rendering.

Team 17: G Anirudh, Tanay Mohta, Dhyey Dhumasia.

## Native setup on Windows x64

Docker is not required. From a cloned repository in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
.\.venv\Scripts\python.exe -m reporting.seed --customers 20 --orders 5
.\.venv\Scripts\python.exe -m reporting.demo_operations
powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -Workers 2
```

Setup obtains pinned uv 0.13.1, managed Python 3.12.12 and PostgreSQL 16.15 binaries into project-local directories, installs requirements.lock, creates an isolated native cluster and applies checksum-tracked migrations. It does not change an existing PostgreSQL service. First setup needs internet and disk space; prepared operation works offline. If Windows reports a missing Visual C++ runtime DLL, install Microsoft's supported x64 Visual C++ Redistributable and rerun setup.

- API and interactive documentation: http://127.0.0.1:8000/docs
- Reporting workspace: http://127.0.0.1:8000
- PostgreSQL: 127.0.0.1:55432, database conduit
- Demo login: username `admin`, password `Conduit@123`
- Demo database owner: conduit / conduit_dev; broker role: conduit_app / conduit_app_dev
- Local configuration: .env.local, copied from .env.example if absent. Services bind to loopback.

Open the reporting workspace and sign in with the demo username and password. Navigation contains Reports, Sales import, Inventory, Analysis, Ask your data, Data explorer and SQL workspace. Broker integration controls and API-key sign-in are removed from the demonstration interface; the queue still processes reports internally.

First API startup creates a database account using `CONDUIT_LOGIN_USERNAME` and `CONDUIT_LOGIN_PASSWORD` from .env.local (defaults shown above). Passwords are stored as salted PBKDF2-SHA256 hashes. Database-backed sessions expire after eight hours and are revoked on sign-out or replacement login. Restarting never resets an existing account's password. The API token remains available for developer scripts and backend regression tests; it is not a browser login credential. For direct API use, enter `Bearer conduit-admin-token` in /docs or use the CLI below.

## Reporting workspace

- **Sales import:** upload a UTF-8 CSV (up to 2 MB/2,000 lines), review manual/optional AI column mapping and validation, then commit complete valid orders. Rejected orders remain staged with errors; identical retry content is skipped, conflicting references are rejected. Samples are in `demos/data/` and downloadable in the UI. Imports represent historical sales and do not move physical stock.
- **Inventory:** explicit stock receipts, atomic sale/order posting, insufficient-stock rejection, reorder thresholds and a reconciled movement ledger. Run `reporting.demo_operations` for a repeat-safe named customer/product fixture. Existing seeded sales are not retroactively deducted.
- **Ask your data:** supported business questions become approved parameterized SQL with an interpretation preview and read-only execution. Sales questions can generate a saved report using the existing queue. Five query kinds are supported; arbitrary AI-generated SQL is not executed. A labelled local rule parser works without a key.
- **Analysis:** SQL-calculated revenue/customer/order/unit totals, category sales, a complete monthly series and a 25% completed-month decline rule plus current low-stock alerts. SQL and captured evidence are visible; deterministic text or optional AI explains the facts.

- **Reports:** live counts, status filters, search and run history; create a customer statement, product ranking or monthly summary.
- **New report:** select a period, choose one customer or a batch, and inspect the approved SQL before submitting. A run tracks real worker progress and opens each generated output.
- **Report inspector:** saved rows, the template query and its bound parameters, trigger-recorded state changes, CSV/HTML downloads, replay and SHA-256 values.
- **Data explorer:** searchable, paginated customer/product/order tables and their relationships.
- **SQL workspace:** run read-only SELECT/EXPLAIN queries, including sales joins, category aggregation and run-status presets. Queries have a five-second timeout and a 500-row display limit.

The interface uses server-rendered templates, local assets and progressive JavaScript enhancements. It has desktop/mobile layouts and requires no frontend build or internet during a prepared demo. The committed Tailwind stylesheet can be rebuilt by developers with Node/npm using `scripts/build-styles.ps1`; ordinary setup and startup do not require Node.

## Generate a report

```powershell
.\.venv\Scripts\python.exe -m reporting.cli submit customer_statement --customer 1
.\.venv\Scripts\python.exe -m reporting.cli status RUN_UUID
```

The CLI returns a run UUID. Workers complete the report independently. In /docs, GET /api/reports/runs/{run_id}/requests returns request UUIDs; use the download, evidence and replay endpoints for each request.

```powershell
.\.venv\Scripts\python.exe -m reporting.cli evidence REQUEST_UUID
.\.venv\Scripts\python.exe -m reporting.cli replay REQUEST_UUID --output .local/replayed.html
```

Templates: customer_statement, product_sales, monthly_sales. Date defaults cover 2026; --start and --end accept custom dates with an exclusive end. Bulk statements use --bulk instead of --customer. --key accepts a UUID for repeat-safe submission.

Start with -Workers 0 to keep the API/database available while work waits, then start again with -Workers 2. A one-time worker drain is also available:

```powershell
.\.venv\Scripts\python.exe -m reporting.worker --drain
```

## Database evidence and tests

```powershell
.\.venv\Scripts\python.exe -m reporting.evidence
.\.venv\Scripts\python.exe -m pytest tests -v
```

The API must run for tests/py. Reporting SQL/worker tests create and remove a disposable database; HTTP/SDK suites create unique fixtures in the project database. Evidence executes db/evidence/reporting_review.sql and captures code plus actual outputs in artifacts/dbms-evidence.txt: constraints, joins, filtering, aggregation, subqueries, CRUD, procedure submission, rollback, audit, index plans and materialized-view refresh.

See docs/DATABASE_DESIGN.md for functional dependencies, normalization and ER relationships. Original broker schema is in db/sql; reporting migrations are in db/migrations. Add new migrations instead of editing applied files, then run python -m reporting.local migrate. Migration SQL and checksum metadata commit together. No destructive reset is automatic.

## Bulk experiment

Stop normal background workers before timing so the selected worker count is accurate. The benchmark adds deterministic sales records, drains earlier report work, creates distinct customer outputs and verifies result counts and every file checksum.

```powershell
.\.venv\Scripts\python.exe -m reporting.benchmark --customers 100 --orders 10 --workers 2 --output artifacts/report-benchmark-100.json
.\.venv\Scripts\python.exe -m reporting.benchmark --customers 10000 --orders 10 --workers 4 --output artifacts/report-benchmark-10000.json
```

--customers is a seed target; bulk mode includes all customers already present. Seeding is additive and repeat-safe. Ingestion, preparation, queue wait, rendering and completion are different measurements. Results describe this machine and CSV/HTML output, not universal PostgreSQL or PDF throughput. Observed results are in docs/IMPLEMENTATION_STATUS.md.

## Stop and diagnose

```powershell
powershell -ExecutionPolicy Bypass -File scripts/doctor.ps1
powershell -ExecutionPolicy Bypass -File scripts/stop.ps1
```

Logs: .local/postgres.log, api.log and worker-*.log. Startup checks migrations/connectivity. The native Windows API launcher selects a psycopg-compatible event loop. Stop verifies process creation times before terminating recorded project processes, then stops the project-owned database.

If port 55432 is occupied, change both DSNs in .env.local before startup. Select another API port with start.ps1 -Port 8001. An explicit PostgreSQL 16 binary directory can be supplied using setup.ps1 -PostgresBin; data stays project-local.

## Transfer to a friend's laptop

Push source, requirements.lock, scripts, migrations and docs. Keep .env, .env.local, .runtime, .venv, .local, database files and generated reports out of Git. On the other Windows x64 laptop, clone and run setup, seed and start. Recreate data instead of copying a live cluster or virtual environment. After moving folders, use a fresh setup rather than assuming virtual environments relocate.

The bootstrap provides Python/PostgreSQL, subject to Windows runtime prerequisites. macOS/Linux require their native tools and separate validation; the binary bootstrap targets Windows x64. First-time provisioning requires internet; an already-prepared demonstration can run offline. Existing Docker installations and volumes were not uninstalled or deleted.

## Execution plan

docs/IMPLEMENTATION_PLAN.md records the accepted order; docs/REPORTING_PROJECT_BLUEPRINT.md maps the updated assessment. DBMS/backend work and the reporting UI are implemented. A replacement PPT and final Word report remain later phases. Optional AI code is implemented; live provider verification awaits the user key. Older milestone/research notes retain historical Docker commands; use this README and current status for execution.

Optional Gemini interpretation, column mapping and analysis explanations are implemented. Add `CONDUIT_GEMINI_API_KEY` to ignored `.env.local` and restart the API; the example model is configurable with `CONDUIT_GEMINI_MODEL`. Provider credentials remain on the backend, and the normal login stays unchanged. Live inference requires the user's key, internet and available provider quota; integration was tested with mocked responses, not a live account. Local/manual workflows remain usable without AI. Authoritative figures come from SQL. See `docs/FINAL_REVIEW_DEMO.md` for the presentation sequence and boundaries.

## Latest implementation verification

On 19 October 2026, the full regression suite passed: **57 tests in 26.88 seconds**. The API was tested on port 8001 using `CONDUIT_API_URL=http://127.0.0.1:8001` because another process occupied port 8000. The documented `start.ps1 -Port` option supports this configuration. See `artifacts/test-results.txt` for results, `artifacts/retail-operations-evidence.json` for the stock/rollback demonstration and `docs/FINAL_REVIEW_SCHEMA.md` for the current 34-table schema.
