# Milestone 4 — Demo Dataset & Data Management (COMPLETE)

**Date:** 2026-09-13 · **Owner:** Team 17 · **Feeds Review-2 deliverable:** D2 (Data insertion and management)

## The Plan (as decided before implementation)

### A. Admin-management functions (extend `10_functions.sql`)
`suspend_user` / `activate_user`, `set_application_status` (revoke/restore apps), `update_topic_config` (retention / max size / status), `pause_group` / `activate_group`, `publish_schema_version` (next version + auto-deprecate previous — the schema-evolution story), `archive_topic`.

### B. Suspend-cuts-access semantics
A suspended user's grants must stop working: both ACL triggers and the three `fn_user_can_*` RLS policy helpers require the acting user's `status='active'`. Plus `produce()` now enforces `app_type IN ('producer','both')` (`CDT20`) — consumer-only apps cannot produce.

### C. `50_seed.sql` — realistic e-commerce dataset built entirely through the real functions
6 users across all 5 roles (incl. ungranted `guest.viewer` persona) · 6 service apps · 4 topics (orders 4-partition/schema, payments 2/schema, notifications 2/schema/7-day retention, user-activity 3/schemaless) · 16 grants · 5 groups with 6 subscriptions (incl. a two-topic group) · 3 config defaults · 2,000 messages via `produce_batch` · poison message → DLQ · shaped consumption (85% delivered, in-flight claims, nacked retries, pending backlog) · backdated timestamps (2-hour spread for the throughput chart; 30 notifications aged 8 days for a live retention-purge demo). Gated by `CONDUIT_SEED` env var — default **off** so smoke tests keep getting clean volumes.

### D. Verification (`tests/smoke_m4.sql`)
Dataset-shape assertions; audit coverage counts; lag/throughput views populated; purge deletes exactly 30; schema evolution accept/reject; suspend → blocked at trigger **and** RLS layers; app revocation → `CDT03`; paused group → `CDT06`; archived topic → `CDT02`; final ledger balance; matview consistency. Regression: m2 + m3 on a clean volume.

## Planning Decisions (Q&A)

| Question | Options presented | Chosen | Rationale |
|---|---|---|---|
| How large should the seeded dataset be? | ~2,000 messages (rec.) / ~8,000 | ~2,000 | Init stays fast and every dashboard view looks alive; M8 benchmarks generate their own bulk data |
| Include admin-management functions? | Admin functions + suspend-cuts-access semantics (rec.) / Seed only | Admin functions + suspend semantics | A real data-management surface for deliverable D2; suspension must genuinely cut access (trigger + RLS layers) to be a security control, not a cosmetic flag |

## What Was Implemented

All of the above, deployed and verified. Final dataset shape achieved **exactly as designed**:

| Status | Count |
|---|---|
| delivered | 1,580 |
| pending (backlog + nacked) | 390 |
| claimed (in-flight) | 29 |
| dead (poison → DLQ) | 1 |
| **total** | **2,000** |

Per-topic: orders 580/210/10, payments 425/66/8 + 1 dead, notifications 285/8/7, user-activity 290/106/4 (delivered/pending/claimed). Audit trail after seed: 3,600+ rows (2,000 PRODUCE, 1,580 DELIVERED, 1 DLQ, 16 ACL_GRANT, 3 CONFIG_CHANGE, 4 TOPIC_CREATE, 3 SCHEMA_PUBLISH).

### Issues found & fixed during implementation
1. **psql variable quoting**: `:var::JSONB` interpolates the JSON text unquoted → syntax error; the quoted form `:'var'::JSONB` is required. Hit in the seed's subset-ack expressions.
2. **Ambiguous column in a join display query** (`status` exists on both `schema_version` and `topic`) — qualified as `sv.status`.
3. **Healthcheck lied during init**: socket-based `pg_isready` answers while the initdb temp server is still running the seed → the first smoke run executed against a half-seeded database (1,600 messages, all pending). Fixed by switching the compose healthcheck to **TCP** (`pg_isready -h 127.0.0.1`), which only answers after init completes and the real server starts. (README also documents a belt-and-braces `SELECT count(*) FROM message` check.)

### Verification evidence
- Seeded volume: `smoke_m4` **all 10 sections green** — shape asserts (2000/1580/390/29/1), audit coverage, lag max 288, throughput timeline covering 461 minute-rows, purge = exactly 30, payments v2 published (v1 deprecated, old shape `CDT04`, new shape accepted), suspend → RLS helper false + produce `CDT17` → reactivate → produce OK, revoked app `CDT03` → restored OK, paused group `CDT06` → reactivated consumes+acks, archived topic `CDT02` → reactivated accepts, final ledger 1,974 = 2,000 − 30 + 4 new, matview consistent after `REFRESH CONCURRENTLY`.
- Clean volume (seed off): `smoke_m2` and `smoke_m3` both **COMPLETE** — no regression from the new `app_type` check, suspend semantics, or admin functions.

## Files

| File | Contents |
|---|---|
| `db/sql/10_functions.sql` | +8 functions (7 admin management + `app_type` enforcement in produce) |
| `db/sql/20_triggers.sql`, `db/sql/30_rls.sql` | active-user requirement in ACL triggers + RLS helpers |
| `db/sql/50_seed.sql` | CONDUIT_SEED-gated demo dataset |
| `docker-compose.yml` | CONDUIT_SEED passthrough + TCP healthcheck |
| `tests/smoke_m4.sql` | 10-section verification suite |
| `README.md` | seed + smoke-test instructions |

## How to run

```powershell
docker compose down -v
$env:CONDUIT_SEED='true'
docker compose up -d db
Remove-Item Env:\CONDUIT_SEED
Get-Content -Raw tests\smoke_m4.sql | docker exec -i conduit-db psql -U conduit -d conduit -v ON_ERROR_STOP=1
```

## Next

Milestone 5 — Python `conduit` SDK + FastAPI service (auth, REST → procedures, SSE from `NOTIFY`, two connection modes). The playground/dashboard (M6) and demo/benchmark scripts (M7/M8) all build on this SDK.
