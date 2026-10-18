# Conduit asynchronous business reporting

A DBMS project built around PostgreSQL relational sales data, inspectable SQL reports, constraints, transactions, audit triggers, views and historical replay. Conduit's existing PostgreSQL queue schedules dataset preparation and CSV/HTML rendering.

Team 17: G Anirudh, Tanay Mohta, Dhyey Dhumasia.

## Native setup on Windows x64

Docker is not required. From a cloned repository in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
.\.venv\Scripts\python.exe -m reporting.seed --customers 20 --orders 5
powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -Workers 2
```

Setup obtains pinned uv 0.13.1, managed Python 3.12.12 and PostgreSQL 16.15 binaries into project-local directories, installs requirements.lock, creates an isolated native cluster and applies checksum-tracked migrations. It does not change an existing PostgreSQL service. First setup needs internet and disk space; prepared operation works offline. If Windows reports a missing Visual C++ runtime DLL, install Microsoft's supported x64 Visual C++ Redistributable and rerun setup.

- API and interactive documentation: http://127.0.0.1:8000/docs
- Reporting workspace: http://127.0.0.1:8000
- PostgreSQL: 127.0.0.1:55432, database conduit
- Demo login: username `admin`, password `Conduit@123`
- Demo database owner: conduit / conduit_dev; broker role: conduit_app / conduit_app_dev
- Local configuration: .env.local, copied from .env.example if absent. Services bind to loopback.

Open the reporting workspace and sign in with the demo username and password. Navigation contains Reports, Data explorer and SQL workspace. Broker integration controls and API-key sign-in are removed from the demonstration interface; the queue still processes reports internally.

First API startup creates a database account using `CONDUIT_LOGIN_USERNAME` and `CONDUIT_LOGIN_PASSWORD` from .env.local (defaults shown above). Passwords are stored as salted PBKDF2-SHA256 hashes. Database-backed sessions expire after eight hours and are revoked on sign-out or replacement login. Restarting never resets an existing account's password. The API token remains available for developer scripts and backend regression tests; it is not a browser login credential. For direct API use, enter `Bearer conduit-admin-token` in /docs or use the CLI below.

## Reporting workspace

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

docs/IMPLEMENTATION_PLAN.md records the accepted order; docs/REPORTING_PROJECT_BLUEPRINT.md maps the updated assessment. DBMS/backend work and the reporting UI are implemented. A replacement PPT, final Word report and optional AI remain later phases. Older milestone/research notes retain historical Docker commands; use this README and current status for execution.

AI is not implemented. Authoritative figures come from approved SQL templates.

## Latest publication verification

On 18 October 2026, the full regression suite passed: **43 tests in 31.00 seconds**. The API was tested on port 8001 using `CONDUIT_API_URL=http://127.0.0.1:8001` because another process occupied port 8000. The documented `start.ps1 -Port` option supports this configuration. See `artifacts/test-results.txt` for the captured results.
