# Conduit DBMS first execution plan

Accepted direction: asynchronous business reporting over relational sales data. Date: 17 October 2026. Database design, SQL, constraints, transactions, testing and viva evidence take priority. UI redesign and presentation/report authoring follow verified implementation.

## Execution order

| Order | Work | Completion gate |
|---|---|---|
| 1 | Native local PostgreSQL and Python bootstrap; Git-safe configuration; remove Docker run dependency | Fresh local cluster, schema and API start without Docker; documented repeatable commands |
| 2 | Correct broker defects affecting reporting, permissions and evidence | Focused regressions plus existing integration tests |
| 3 | Relational sales and reporting schema in versioned SQL migrations | PK/FK/UNIQUE/NOT NULL/CHECK constraints exercised; relationships and normalization documented |
| 4 | Three approved SQL reports, views, submission procedure, audit and transactional enqueue | Real joins/filtering/aggregation/subqueries; COMMIT/ROLLBACK verified |
| 5 | Persistent report datasets, worker, CSV/HTML artifacts and minimal reporting API/CLI | A request produces real downloadable outputs; no UI redesign required |
| 6 | Historical replay, duplicate-safe completion, failure/recovery and authorization | Source change preserves old run; new run changes; retry does not duplicate business results |
| 7 | Deterministic small and bulk fixtures; measured experiments | Incremental workloads up to 10,000 reports; distinct results/files reconciled; actual timings retained |
| 8 | DBMS evidence pack, portability rehearsal and full tests | SQL plus observed outputs, normalization notes, clean setup rehearsal and test results |
| 9 | UI redesign | Implemented after backend verification; real reporting workflows, SQL/data inspection and desktop/mobile browser checks |
| 10 | Final PPT/report/viva materials and optional AI | Follow new 20-mark allocation; optional AI cannot delay core correctness |

## Local execution and portability

Primary portable target is Windows x64, matching this machine. Provide PowerShell setup/start/stop/doctor commands that resolve all paths relative to the checkout. Use an isolated PostgreSQL cluster owned by this project on a dedicated loopback port, without changing an existing system PostgreSQL service. Keep database files, downloaded runtimes, virtual environments, local secrets and generated outputs out of Git. Pin Python dependencies and PostgreSQL major/runtime version. First-time setup needs internet to obtain dependencies; a prepared checkout should run offline.

Use PostgreSQL binaries directly, not containers, and a project Python environment. Bootstrap should use existing compatible binaries when explicitly provided or obtain pinned vendor binaries. A friend clones the repo, runs setup, then starts the project. Database contents are recreated from SQL migrations plus deterministic seed scripts; copying a live data directory or a machine-specific virtual environment is not the transfer mechanism. Startup checks ports, database version, migrations and connectivity. Existing Docker volumes/data are preserved; no Docker command is required for normal use.

If the friend's laptop is not Windows x64, document the native PostgreSQL/Python route and validate it separately; do not claim an untested platform works. Installation failures should produce actionable errors, not silently connect to another local database.

## Database implementation boundary

Base sales entities: customer, product, sales_order, order_item. Reporting entities: immutable template versions, runs, requests, frozen datasets, results and state audit as necessary. Reuse existing Conduit identities and queue functions. Report types: customer statement, product/category sales, monthly summary. Use NUMERIC for money, typed relational keys and explicit date ranges. SQL calculates authoritative values; Python renders them.

Create requests and their broker messages on the same database transaction/connection. Prepare a persistent consistent run dataset before rendering. A meaningful stored procedure orchestrates submission. Results are unique per immutable report request. Files are written outside long database transactions using stable identities and atomic publication, with database result publication and acknowledgement coordinated. Test failure boundaries; do not claim exactly-once filesystem execution.

Core novelty is historical replay with visible template/parameters/dataset lineage. Optional AI selects approved parameterized reports after core delivery; it cannot supply arbitrary executable SQL or authoritative totals.

## Verification and evidence

Keep isolated test databases and deterministic fixtures. Verify exact fixture totals, invalid FK/check/unique/date cases, CRUD and subqueries, rollback of request plus enqueue, two-worker distinct work, retries after interruption, historical replay, failed-job redrive and real file content. Benchmark ingestion, SQL preparation, queue wait, rendering and total completion separately. Run existing suites and targeted new integration tests. Record observations, not predicted marks or speedups.

## Status

- Steps 1-8 implemented and exercised on native PostgreSQL; see IMPLEMENTATION_STATUS.md and artifacts for observed results and portability limits.
- The 10,000-report experiment completed with verified CSV/HTML outputs; final verification is captured by scripts/verify.ps1.
- Step 9 is implemented: reporting workspace, report creation and progress, saved data/SQL/audit inspector, downloads/replay, relational data explorer and read-only SQL workspace. Full regression suite: 43 passing tests; screenshots in artifacts/ui.
- Username/password login and reporting-only demo navigation are implemented; broker processing remains internal.
- Step 10 remains deferred: final PPT/report authoring and optional AI.
- For later PPT authoring, follow [PPT_REFERENCE.md](PPT_REFERENCE.md), including worked normalization examples and the complete table/column/key dictionary in [DATABASE_TABLE_REFERENCE.md](DATABASE_TABLE_REFERENCE.md).
- Later user request: inventory management, to be designed after the current review walkthrough is finished; see [FUTURE_WORK.md](FUTURE_WORK.md). It is outside the current implementation and review claims.
- Existing broker audit/runtime findings are recorded in RUNTIME_VERIFICATION.md; the new blueprint and assessment mapping are in REPORTING_PROJECT_BLUEPRINT.md.
