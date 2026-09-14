# Milestone 3 — Triggers, Row-Level Security, Views (COMPLETE)

**Date:** 2026-09-13 · **Owner:** Team 17 · **Feeds Review-2 deliverables:** D4 (triggers, RLS — advanced features) + D3 (views: joins, aggregation, window functions)

## The Plan (as decided before implementation)

### Triggers (`20_triggers.sql`)
| # | Trigger | Event | Behavior |
|---|---|---|---|
| 1 | Audit: PRODUCE | AFTER INSERT ON message | AUDIT_LOG row attributed to the producing app's owner |
| 2 | Audit: DELIVERED | AFTER UPDATE, `claimed→delivered` | AUDIT_LOG row with group + offset |
| 3 | Audit: DLQ | AFTER INSERT ON dead_letter_message | Reason + attempts snapshot |
| 4 | Audit: admin events | access insert/delete, broker_config update, topic insert, schema_version insert | ACL_GRANT / ACL_REVOKE / CONFIG_CHANGE / TOPIC_CREATE / SCHEMA_PUBLISH |
| 5 | ACL enforcement (produce) | BEFORE INSERT ON message | Raise `CDT17` if producer app's owner lacks `produce` access (admin role bypasses) |
| 6 | ACL enforcement (consume) | BEFORE UPDATE, `pending→claimed` | Raise `CDT18` if claiming group's creator lacks `consume` access |
| 7 | Monotonic offset guard | BEFORE UPDATE ON group_offset | Reject `committed_offset` regression (`CDT19`) |
| 8 | updated_at bump | BEFORE UPDATE ON broker_config | Auto-stamp — manual timestamps can't be faked |
| 9 | NOTIFY | AFTER INSERT ON message | `pg_notify('conduit_events', {event, topic, partition, offset})` — future SSE feed |

Decisions: **terminal events only** (no per-claim audit rows — keeps audit_log meaningful and the hot path light); no triggers on audit_log itself (no recursion).

### RLS (`30_rls.sql`)
- New login role **`conduit_app`** (init superuser always bypasses RLS, so a second role is required for a demoable story)
- Scoped grants: hot-path DML + sequences; **`REVOKE EXECUTE ON ALL FUNCTIONS FROM PUBLIC`** + explicit hot-path EXECUTE grants (default is PUBLIC-executable — a real hardening fix); `ALTER DEFAULT PRIVILEGES` so future functions stay private
- RLS on **message + dead_letter_message only** (decided scope); policies keyed on `current_setting('app.user_id')`: SELECT = any access, INSERT = produce access, UPDATE = consume access; admin role passes all; GUC unset → default-deny
- Hot-path functions stay **invoker-rights** so RLS genuinely applies inside them; maintenance/admin functions are admin-connection-only → settles M5's two-connection-mode API design

### Views (`40_views.sql`)
`v_consumer_lag` (lag = head − committed), `v_topic_stats` (FILTER aggregates + DLQ depth), `v_throughput_by_minute` (window functions + running total), `v_audit_recent` (joined audit trail), `mv_topic_stats` materialized + `refresh_dashboard()` with `REFRESH CONCURRENTLY`. All views `security_invoker = true` so dashboards respect RLS.

### Verification plan
`tests/smoke_m3.sql`: audit assertions per event type, monotonic rejection, RLS allow/deny matrix as `conduit_app` (alice granted / bob denied / anonymous zero-visibility), view-vs-function consistency, matview refresh consistency; regression re-run of `smoke_m2.sql`; parallel-session LISTEN/NOTIFY demo.

## Planning Decisions (Q&A)

| Question | Options presented | Chosen | Rationale |
|---|---|---|---|
| Which broker events should the audit triggers record? | Terminal events only (rec.) / Every claim too | Terminal events only | PRODUCE / DELIVERED / DLQ / ACL / CONFIG / topic-schema lifecycle / AUTH_FAIL cover the graded story; skipping transient per-claim rows keeps audit_log meaningful and the hot path light |
| How much of the schema should row-level security cover? | `message` + `dead_letter_message` (rec.) / Everything sensitive | Message + DLQ | Clearest demo, least risk of blocking admin/maintenance flows; other tables remain guarded by grants + triggers |

## What Was Implemented

All three files deployed cleanly on fresh init (`00 → 10 → 20 → 30 → 40`): 15 triggers, 10 trigger functions + `log_auth_failure`, 1 role + 14 grants + 5 policies + 3 policy helpers, 4 views + 1 materialized view + refresh function.

### Design refinements discovered during implementation
1. **AUTH_FAIL rows can't be written by the failing trigger itself** — the raised exception aborts the transaction, which would roll back the audit insert. Pattern: triggers raise clean `CDT17/CDT18`; the *caller* catches and calls the public `log_auth_failure()` function in a fresh statement (smoke test and the M5 API both do this). This replaced the planned "audit-before-raise".
2. **Upsert INSERT branch doesn't fire UPDATE triggers** — `update_broker_config` on a new key emitted no CONFIG_CHANGE row; added an AFTER INSERT audit trigger on broker_config (old_value = null).
3. **Partition ACLs**: access via the partitioned parent checks only the parent's ACL; partitions get no direct grants for `conduit_app`, so direct partition access is ACL-denied — the RLS story can't be bypassed by touching `message_2026_09` directly. Verified working via the conduit_app smoke section.
4. Views are created after the `REVOKE EXECUTE FROM PUBLIC` default-privileges change, so `refresh_dashboard()` is automatically admin-only.

### Verification evidence

**`tests/smoke_m3.sql` — all green (fresh volume):**
- [1] Fixtures: secadmin (admin role), alice (producer, granted produce+consume), bob (consumer, **no grants**), 2-partition topic, group
- [2] 2 PRODUCE audit rows, correctly attributed to alice, details carry partition/offset/key/size/seq
- [3] 2 DELIVERED audit rows after consume+ack
- [4] Poison message → 3 claim+nack cycles → dead + 1 DLQ audit row
- [5] ACL_GRANT ×2, TOPIC_CREATE, SCHEMA_PUBLISH, CONFIG_CHANGE audit rows all present; `updated_at` auto-bumped despite a manual `2000-01-01` override
- [6] Offset regression rejected with `CDT19`
- [7] **RLS matrix as `conduit_app`**: alice sees 3 messages, produces + consumes + acks through the RLS path; bob sees **0** rows, his produce raises `CDT17`/`42501`, AUTH_FAIL logged and persisted; anonymous (GUC reset) sees **0**
- [8] `v_consumer_lag` shows per-partition lag (1 and 0); `v_topic_stats` agrees exactly with `topic_stats()`; throughput view shows 4 messages in the current minute; `v_audit_recent` shows the full joined trail; `refresh_dashboard()` → matview agrees with live view

**Regression:** `smoke_m2.sql` re-run green on a fresh volume with triggers + RLS active.

**LISTEN/NOTIFY demo (`benchmarks/notify_session.txt`):** a listening session received
`Asynchronous notification "conduit_events" with payload {"event": "PRODUCE", "topic_id": 1, "msg_offset": 4, "partition_id": 2}` —
matching the concurrent produce's returned location exactly. (Gotcha found: psql `-c` exits before draining queued notifications; the listener must be a multi-statement script so psql polls between statements.)

## Files

| File | Contents |
|---|---|
| `db/sql/20_triggers.sql` | 15 triggers, audit + ACL + monotonic + updated_at + notify, `log_auth_failure` |
| `db/sql/30_rls.sql` | `conduit_app` role, grants/revokes, default privileges, 5 RLS policies, 3 policy helper functions |
| `db/sql/40_views.sql` | 4 security_invoker views, `mv_topic_stats` + unique index, `refresh_dashboard()`, view grants |
| `tests/smoke_m3.sql` | 8-section verification suite with `fn_assert` |

## How to run

```powershell
docker compose down -v
docker compose up -d db
Get-Content -Raw tests\smoke_m3.sql | docker exec -i conduit-db psql -U conduit -d conduit -v ON_ERROR_STOP=1
```

## Next

Milestone 4 — `50_seed.sql` (realistic demo dataset) + admin CRUD verification, feeding Review-2 deliverable D2 (data insertion & management).
