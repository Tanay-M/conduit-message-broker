# Conduit grading and engineering audit

Assessment date: 13 October 2026. Scope: attached assessment DOCX, submitted Review 1 PDF, current SQL, API, SDK, web interface, tests, demos, recorded benchmarks, Review 2 PPTX, and presentation script.

**Assessment update 17 October 2026:** The user supplied new final PPT/report guidelines and a new 20-mark allocation (PPT 5, demo 5, viva 5, novelty 2, report 3), and selected report generation as the demonstration direction. Use [REPORTING_PROJECT_BLUEPRINT.md](REPORTING_PROJECT_BLUEPRINT.md) for current deliverable planning. The 10-mark Review 2 discussion below records the earlier assessment; its source and runtime findings remain useful.

**Runtime update:** Subsequent execution on 13 October resolved Docker startup, passed all three SQL smoke suites, 20 integration tests and seven Python demos, and reproduced all five principal defects below. See [the fresh runtime verification](RUNTIME_VERIFICATION.md). The historical verification-limit section describes the earlier static pass; the execution report is now authoritative for fresh runtime results.

**Verdict: all four technical Review 2 categories have substantial implementation evidence, but the current project is not ready for an unconditional readiness claim.** Demo-path bugs, security inconsistencies, misleading offset semantics, and unsupported presentation claims need attention. The assessment does not provide enough detail to predict an exact mark.

No implementation or existing presentation files were changed in this review. The deliverables are analysis documents and a read-only SQL evidence script. The user requested a replacement deck later.

## 1. What the assessment actually requires

The attached `DBS Lab Project Assessment. (3).docx` assigns 30 marks overall, divided into three reviews of 10 marks each. It does not specify per-item weights, mandatory table counts, mandatory row counts, or a requirement to use every example advanced feature.

The online shopping system and its ER image are design examples. They are not requirements to turn Conduit into a shopping system.

### Review 2 implementation review — 10 marks total

| Assessment criterion | Evidence in this repository | Current assessment | What to show |
|---|---|---|---|
| Database implementation: tables/collections and constraints/validation | `00_schema.sql`; 15 logical tables; PK, FK, UNIQUE, CHECK, NOT NULL; required-field validator | Covered in source; integrity limitations remain | Current ER model, actual DDL, constraint rejection and rollback |
| Data insertion and management | `produce`, `produce_batch`, seed, ack/nack, DLQ, retention and admin functions | Covered in source; web Send and seeded ACL-management paths have risks | Insert one message, query stored row, update through claim/ack, demonstrate a controlled management operation |
| Database operations: queries, filtering, aggregation, joins | Four reporting views, browser queries, FILTER aggregates, window totals | Covered in source; chart identity and lag correctness need correction | Concrete SQL plus interpretable result rows, not just a feature list |
| Advanced features as applicable | 48 SQL function definitions across initialization files, 14 declared triggers, five RLS policies, indexes, transactions, four views, one materialized view | Strong breadth; several deck descriptions are incorrect | A function call, trigger effect, transaction rollback, RLS comparison, and an explained index plan |
| Presentation | Existing 17-slide deck, narrated demos, dashboard | Needs revision and rehearsal | Readable slides, faithful claims, visible SQL outputs, clear explanation of revised architecture |

“Covered in source” means relevant implementation exists. It does not mean the evaluator must award full marks, or that every behavior has been freshly tested.

### Review 3 final demonstration — 10 marks total

| Assessment criterion | Existing foundation | Remaining preparation |
|---|---|---|
| Execution and demonstration | Docker Compose, dashboard, SDK, eight demo scripts | Working runtime, rehearsed happy path and failure path, fallback screenshots/output |
| Correctness of operations and results | SQL smoke suites, 20 Python integration test functions, saved demo outputs | Fresh results, edge-case tests, corrections to offsets, identity propagation, and concurrent requeue |
| Report/documentation | README, plan, eight milestone reports | A coherent final report matching the actual stack/model, updated ER diagram, results and limitations |
| Viva voce | Existing presentation script and the companion project guide | Explain mechanisms without memorizing inflated claims; each teammate should rehearse |

The final report's exact institutional format is not specified in the attachment. The repository has useful documentation but no clearly identified consolidated final report matching the current implementation.

## 2. Verification performed and limitations

Performed in this pass:

- Extracted and read the assessment body and inspected its embedded ER example.
- Read the submitted Review 1 text, all six initialization SQL files, backend/SDK modules, custom frontend code and templates, tests and demos, benchmark implementations/results, and project documentation.
- Extracted the text of all 17 presentation slides and inspected representative rendered slides 2, 3, 8, 9, and 17 using the artifact renderer. This was not a PowerPoint application check.
- Parsed all 34 Python files under server, client, demos, benchmarks, and tests with Python's AST parser. All passed syntax parsing. This does not establish dependency availability or behavioral correctness.
- Counted source declarations: 15 logical tables plus eight physical children, 48 functions, zero CREATE PROCEDURE statements, 14 CREATE TRIGGER statements, five policies, four normal views, one materialized view.
- Cross-checked quoted performance numbers against the retained JSON and execution plan.
- Tried to start Docker Desktop and inspect the engine, without resetting or deleting a data volume. The engine remained unavailable through its named pipe. `docker desktop start` also reported a missing installation registry key.

**No fresh SQL integration, HTTP, browser-interaction, concurrency, or WAL crash tests completed in this pass.** Previous milestone documents report passing smoke suites and 20/20 integration tests. Those are historical claims supported by retained files, not new verification. New source findings explain why earlier tests alone do not certify current demo readiness.

The read-only evidence script is `demos/review_2_evidence.sql`. It has been reviewed statically but has not been run against PostgreSQL in this pass.

## 3. Highest-priority findings

These findings are grounded in current source. Except where described as measured from saved files, the runtime outcomes are predictions that need reproduction once PostgreSQL is available.

### A. Playground Send uses sequences the database cannot accept

**Location:** `server/app/static/app.js:122`, `db/sql/10_functions.sql:253`.

The UI submits `seq: Date.now()`, roughly a 13-digit millisecond timestamp. `produce()` casts both BIGINT identifiers to `int` for `pg_advisory_xact_lock`. Current timestamps exceed the signed 32-bit maximum 2,147,483,647. A valid Playground Send request therefore reaches a predicted integer-out-of-range error before insertion.

**Grading impact:** Direct threat to the main end-to-end demonstration and Review 2 presentation.

**Correction:** Support the promised BIGINT deduplication identity in lock-key generation, preserving serialization for the same `(app, seq)` pair. A collision-resistant 64-bit lock key is a possible implementation, with hash collisions causing extra serialization rather than duplicate ingestion. Do not merely truncate sequences or reset them, because ledger uniqueness is application-wide.

**Acceptance check:** Actual browser Send succeeds with its timestamp sequence; repeating that request returns the same location and leaves one message and one ledger row. Include a sequence above 2^31 in integration coverage.

### B. App chart endpoints omit the RLS user identity

**Location:** `server/app/api/monitor.py:38–53`.

`_pools(ctx)` returns both pool and user ID. `/api/dashboard`, `/api/lag`, and `/api/throughput` discard the ID and call `db.run()` without `user_id`. The RLS policy helpers therefore receive no app identity when the transaction context is clean. App message counts become zero and throughput becomes empty. The server-rendered cards use `_q()` correctly, creating a visible inconsistency between cards and charts.

The lag view reads metadata tables without RLS, so omitting context there does not necessarily empty its results. It instead exposes group/partition metadata without a topic visibility filter.

**Grading impact:** Incorrect reporting and query results in the app dashboard.

**Correction:** Propagate the identity consistently and explicitly scope metadata reports where required. The accepted `minutes` parameter is currently unused by the throughput endpoint; implement it or remove the misleading parameter.

**Acceptance check:** A granted app sees counts matching SQL for its topics and a nonempty recent timeline. An ungranted app cannot see restricted topics or group metadata. Check values, not just HTTP 200.

### C. App-facing pages bypass DLQ row security

**Location:** `server/app/webui/router.py:138–145`, `211–226`, `290–304`.

The web audit and DLQ pages/fragments use `db.admin_pool` for every authenticated session. The DLQ template displays payloads. An application with no permission for another topic can therefore receive that topic's DLQ payload through the web route, even though direct message reads obey RLS.

The overview also fetches recent audit data as admin. Topic/group pages expose all metadata. The project must decide which metadata is intentionally public; the current deck's blanket isolation claim is broader than the behavior.

**Grading impact:** Security demonstration can contradict the claimed engine-enforced isolation. RLS is an optional advanced feature in the rubric, but correctness of a feature being claimed still matters.

**Correction:** Use authenticated app context for protected reads or make those pages and fragments admin-only. If audit should be visible to apps, introduce an explicit permission-scoped audit query/policy and required grants.

**Acceptance check:** An ungranted app receives zero protected DLQ payloads across page and fragment routes. Admin sees all. A granted app sees only its permitted topic data.

### D. Recorded offsets can skip unfinished messages

**Location:** `db/sql/10_functions.sql:389–429`, `db/sql/40_views.sql:3–16`, `demos/07_exactly_once.py`.

The offset update uses `max(acked_offset) + 1`. In a one-partition topic, produce offsets 0 and 1, claim both, and acknowledge only 1. The recorded offset becomes 2 while message 0 is still claimed. The lag view reports `2 - 2 = 0` despite unfinished work.

The pending row is not currently discarded: consumption selects by state, not committed offset. The bug concerns reporting and claims that the offset is a contiguous completed prefix. The existing partial-batch demo assumes an ordered RETURNING result and checks a convenient prefix, rather than the arbitrary completion order permitted by concurrent workers.

**Grading impact:** Threat to Review 3 result correctness and Review 2 transaction/lag explanations.

**Correction:** Choose and document the intended metric. For queue semantics, report pending/claimed work counts and label the maximum acknowledged position honestly. If claiming contiguous commits, advance only over settled prefixes and define how dead or expired rows affect the prefix.

**Acceptance check:** Out-of-order acknowledgements must not falsely report zero outstanding work. Add the two-message case and a multiple-worker completion case.

### E. Seeded web permission grants name a nonexistent administrator

**Location:** `server/app/webui/router.py:454–468`, `db/sql/50_seed.sql:8`, `db/sql/10_functions.sql:165–173`.

The web grant handler hardcodes the grantor username `admin`. The seeded administrator is `sysadmin`; the admin-token context is not itself an `app_user` row. On a fresh seeded database, the grant function predicts CDT12 (unknown user admin).

**Grading impact:** The Admin access-management form can fail during data-management demonstration even when the JSON API path works.

**Correction:** Resolve an actual grantor identity or make grantor selection explicit. Avoid silently inventing audit attribution for a token-only admin.

**Acceptance check:** Grant and revoke work through the actual web form on a fresh seeded database, and the audit attribution matches the chosen database user.

## 4. Scope and guarantee corrections

### Consumer groups share delivery state

`message.status`, `claimed_by`, and `attempts` are global. `consume()` never uses a per-group delivery ledger or the group's committed offset to find its own copy of a message. Two groups subscribed to a topic compete for the same rows.

Keep the shared queue model and update the explanation if that scope is sufficient. Implement independent per-group delivery only if it is a genuine requirement. The rubric itself does not demand Kafka fan-out.

### Atomic acknowledgement does not imply exactly-once processing

The SQL transaction keeps delivered status and an offset update together. It does not include external email/payment operations. Timeout recovery can cause a worker to process again. The current claim identity also has no worker receipt or generation token: a stale worker in the same group can settle a message reclaimed by another worker using the same location.

Use “idempotent producer ingestion, atomic acknowledgement, and retryable delivery.” Retire the “exactly-once effects” and “Kafka/SQS-grade correctness” wording unless a precisely scoped guarantee and test support it.

### Security requires a trusted database caller

`conduit_app` can SELECT the entire `application` and `app_user` tables, including API keys, and the SDK exposes arbitrary SQL through `query()`. The caller can set the custom identity GUC. This is a trusted-caller RLS demonstration, not strong isolation against an adversary holding the shared database login.

Topic ACLs are checked on user owners. The consume trigger checks the creator of the supplied group, while app RLS checks the request owner. The API does not enforce that the requesting app owns the group, and `require_app` does not reject producer-only apps for consume operations. Thus app-type and group-ownership claims need narrower wording or stronger enforcement.

### Validation is a subset of JSON Schema

`validate_schema()` checks object shape and the presence of required keys. It does not enforce property types, nested contracts, value ranges, or non-null required values. It is invoked by produce rather than by a message validation trigger, so direct INSERTs can bypass contract and size validation when their privileges and ACL checks allow them.

The declarative constraints are real, but not every business invariant is enforced against arbitrary direct writes. Present a representative constraint and validator accurately instead of claiming universal bad-data prevention.

## 5. Additional correctness and maintenance concerns

| Finding | Evidence | Priority and practical implication |
|---|---|---|
| Concurrent DLQ requeue can duplicate replacements | `requeue_dlq` reads pending row without `FOR UPDATE`; different generated sequences defeat dedupe | High if requeue concurrency is demonstrated; lock/recheck the DLQ row |
| Retention drop ignores topic retention policy | `drop_old_partitions(keep_days)` drops by a global supplied cutoff | Avoid demonstrating destructive drops on valuable data; validate cutoff against topic retention policies and define active-work treatment |
| Retention deletion also removes pending/claimed messages | `purge_retention` filters only topic and age | May be intentional expiry; document it as expiry, not delivered-only cleanup |
| Ledger survives message retention | `purge_retention` deletes messages but not producer sequences | An old retry can return the location of an expired message; document dedupe/retention semantics |
| No maintenance scheduler | No recurring task in app lifespan or Compose | Reaper/purge/refresh/partition creation are callable, not autonomous scheduled operations |
| Config values do not control several operations | Consume uses hardcoded 1000/30 bounds rather than reading broker config | Changing config rows does not necessarily change broker behavior |
| Acknowledgement response is not number newly changed | Final ack count checks delivered locations, not UPDATE RETURNING rows and group ownership | Duplicate acknowledgements can return the original count; a wrong group's call can report delivered rows it did not change |
| Audit is not immutable | No UPDATE/DELETE audit guard; admin can mutate audit; app can INSERT audit rows | Say trigger-generated audit for selected successful events, not tamper-proof audit |
| Failed authorization logging is manual | API handlers do not call `log_auth_failure`; demo explicitly does | Demo demonstrates caller-assisted logging, not universal automatic failure persistence |
| Notification scope is global | `/api/events` forwards all `conduit_events` notifications to any authenticated session | Cross-topic IDs leak; filter events and account for long-lived authentication changes |
| SSE generator timeout may close notification iterator | `wait_for(anext(notifies), timeout=15)` cancels pending iteration | Fresh test should produce after more than 15 seconds idle; current SSE test produces after 1.5 seconds |
| Charts initialize once | `app.js` builds charts on DOMContentLoaded, without periodic dataset updates | Do not claim continuously updated charts; message table has a separate 15-second polling fallback |
| UI clears claims after failed settlement | `ackOne`, `nackOne`, `ackAll` remove local items even when `_settle` records an error | Preserve the claim list after a failed request so a worker can retry |
| Monthly partitions are initially finite | September 2026 through March 2027 plus DEFAULT | DEFAULT preserves routing outside the range; future partition creation is manual and rejects conflicting default rows |
| Schema publishing has a max-plus-one race | `publish_schema_version` calculates the next version without topic serialization | Concurrent publication can fail a unique constraint; define serialized version publication |
| Hash routing has an integer minimum edge case | `abs(hashtext(key))` on int32 | Widen before abs to avoid the minimum signed integer overflow |
| Dependency versions are open-ended | Requirements use lower bounds with no lockfile | Build reproduction depends on future package resolution; record tested versions for final submission |

These are not all requirements in the assessment. The first five findings directly affect the advertised demo and results. The remaining items define honest scope and priorities; they should not cause unnecessary feature expansion before Review 2.

## 6. Claims to correct in the presentation

- Review 2 is 10 marks overall. Do not put “10 marks” against each criterion or predict “10/10.” Presentation is its own fifth criterion.
- There are 14 source-declared triggers, not 15. There are 15 function definitions in the triggers file because it includes `log_auth_failure`. Deployed trigger counts can also include clones on physical partitions.
- The original 157 constraint count is historical and includes physical catalog effects. It is not a normalization score or proof of 157 independent business rules. Show actual constraint examples and fresh catalog definitions.
- The function is `validate_schema`, not `fn_validate_schema`. The slide's `fn_can_access_topic` and `fn_is_admin` policy helpers are absent; actual helpers are `fn_user_can_read`, `fn_user_can_produce`, and `fn_user_can_consume`.
- All broker routines are CREATE FUNCTION objects called with SELECT, not CREATE PROCEDURE objects called with CALL.
- `v_consumer_lag` joins four tables: group_offset, partition, topic, consumer_group. The slide's five-table SQL including group_subscription is not the implemented definition.
- SKIP LOCKED takes row locks; it is not lock-free and does not eliminate all contention. The saved plan has Limit above LockRows, not the reversed order stated on slide 8.
- Unkeyed produce chooses the least-used lane by `next_offset`, not strict round-robin under concurrency.
- The schema does not establish blanket 3NF/BCNF. In particular MESSAGE contains the dependency partition_id → topic_id while partition_id alone is not its superkey. Explain normalization of role and junction tables and deliberate redundant location fields instead.
- Deduplication uses a B-tree primary key, not an O(1) hash lookup. BRIN storage savings depend on data and configuration; no retained index-size benchmark proves “99% smaller.”
- Plain partition DETACH inside the function is not a zero-downtime guarantee. Concurrent materialized refresh permits reads of the existing snapshot but still uses locks. Dashboard queries currently read normal views rather than the materialized view.
- The WAL demo produces and acknowledges **five** messages, not 100. It checks their survival and subsequent broker operation. It does not create and verify an in-flight uncommitted transaction or empirically prove zero corruption in all cases.
- Retained produce JSON supports 494.6 → 1520.5 → 2562.4 messages/sec. That is about 3.07× and 5.18× over batch 1, not 5× and 15×.
- Retained consume JSON records 1856.1 messages/sec for batch 1000 and 267.9 messages/sec for five-worker drain. The deck incorrectly attributes 3379 to the five workers. The historical report mentions another run, but that run's figure is not in the retained JSON.
- The retained EXPLAIN execution time is **1.665 ms**, not 1.9 ms. Explain the observed index plan and data conditions; do not generalize one plan into a universal speed guarantee.
- The three-tier overhead benchmark changes more than RLS alone: raw storage lacks constraints/indexes/triggers; admin and SDK calls also differ in client work and occur sequentially. The result is a useful illustrative comparison, not isolated causal measurement of every guarantee.

See the companion presentation plan for slide-by-slide actions.

## 7. Concrete Review 2 evidence sequence

Keep the main demonstration focused. Once the runtime and the first five findings are resolved or explicitly excluded from the chosen demo:

1. Explain the asynchronous work-queue problem and current architecture in under a minute.
2. Show the current ER model, one composite key, two foreign keys, and a CHECK constraint.
3. Produce one known message, show its stored row and ledger row, then repeat the same sequence to show deduplication.
4. Submit a missing-required-field payload and show failure with no message or counter change from that operation.
5. Claim and acknowledge the known message. Show status change, affected offset row, and audit record.
6. Run a readable filtered SELECT, join query, and aggregate query. Explain every result column.
7. Demonstrate a trigger rejection or effect, and compare RLS visibility for permitted and unpermitted users on the same topic.
8. Show an index definition and the saved EXPLAIN tree with its actual data size. Use the materialized-view example if time permits.
9. Finish with a five-row rubric coverage checklist and honest current limitations.

`demos/review_2_evidence.sql` collects read-only catalog, filtering, joins, aggregation, reporting, and index evidence. Because the SQL console requires a single read-only SELECT/EXPLAIN, paste one SELECT at a time there. Run the whole file with psql.

The UI Send issue can be bypassed for an initial rehearsal using the SDK with a small sequence, but a bypass is not a fix or justification for claiming the full Playground works.

## 8. Safe runtime verification plan

First make Docker Desktop operational and inspect existing containers. `docker compose up -d --build` preserves an existing named data volume; it does not reapply initialization SQL to that volume. Inspect deployed definitions before assuming they match source.

Use an isolated test database/stack for clean and seeded checks. The README's `docker compose down -v` deletes the database volume and should not be part of an ordinary rehearsal against data you want to keep.

- Run smoke M2/M3 against an appropriate fresh unseeded fixture. Both create named objects; do not rerun blindly on a populated database.
- Run smoke M4 against a separate fresh seeded fixture. It purges messages and changes schema/state. It also creates `fn_assert`, which conflicts with M3 if both suites share the same database without cleanup.
- Run the existing Python tests against a freshly built API and correct DB connection path. They provision unique fixtures, but their 200-status monitoring assertions do not check report correctness, and their Playground flow uses direct HTTP rather than the browser's JS sequence.
- Add targeted checks for the five principal findings, out-of-order acknowledgements, competing groups, stale claims, and concurrent requeue if those guarantees remain in scope.
- Rehearse browser actions rather than treating rendered HTML as proof that buttons work.
- Reserve the hard database crash demo for an isolated stack and restore API connections afterward. It is optional evidence for Review 2, not a reason to risk the main demonstration environment.

Store fresh results with timestamp, source revision, dataset, and environment. Existing benchmark artifacts do not record enough environment metadata to make general throughput claims.

## 9. Recommended order of work

**Before Review 2:** resolve the Send sequence bug, monitoring identity bug, protected-page access, misleading offset output, and seeded grantor failure; correct the deck claims; document the shared queue scope and Review 1 change; rehearse the evidence sequence.

**Before Review 3:** make result correctness reproducible, decide receipt/claim identity and requeue concurrency semantics, consolidate the report, and prepare the team for viva questions.

**Only if required by scope:** independent group fan-out, stronger direct-database tenant isolation, a maintenance scheduler, or a transactional business-processing API. These expand the project and are not explicitly mandated by the supplied grading document.

## 10. Primary technical references

PostgreSQL's [SELECT locking documentation](https://www.postgresql.org/docs/16/sql-select.html) confirms that FOR UPDATE locks rows and SKIP LOCKED skips conflicting row locks. Its [row security documentation](https://www.postgresql.org/docs/16/ddl-rowsecurity.html) explains owner/superuser bypass and policy-based access. Its [partitioning documentation](https://www.postgresql.org/docs/16/ddl-partitioning.html) explains the partition-key requirement for uniqueness and partition maintenance. Its [CREATE FUNCTION documentation](https://www.postgresql.org/docs/16/sql-createfunction.html) distinguishes the function objects used here.

The findings about this project derive primarily from the local source and retained artifacts, rather than assumptions about a generic broker.
