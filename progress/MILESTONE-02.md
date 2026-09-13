# Milestone 2 — Procedural Broker API (COMPLETE)

**Date:** 2026-09-13 · **Owner:** Team 17 · **Feeds Review-2 deliverable:** D4 (Advanced features: procedures, functions, transactions, concurrency)

## Goal

Implement the entire broker as database code in `db/sql/10_functions.sql` — producing, consuming, acknowledging, retrying, dead-lettering, retention, and administration all as stored functions, so the database (not application code) is the message broker.

## What was built

### Hot path
| Function | Mechanism |
|---|---|
| `produce(topic, key, payload, app, seq)` | `pg_advisory_xact_lock(app, seq)` serializes duplicate sends → PRODUCER_SEQUENCE ledger returns original location on replay (idempotency) → key-hash routing or least-loaded partition → `FOR UPDATE` on PARTITION row assigns gap-free offset → schema + size validation → insert |
| `produce_batch(topic, messages[], app)` | One transaction, per-message routing, returns all locations |
| `consume(group, topic, batch, timeout)` | `FOR UPDATE SKIP LOCKED` claim of pending & visibility-eligible rows, ordered by offset; marks `claimed`, sets `visible_at = now()+timeout`, `attempts+1` |
| `ack(group, locations)` | One transaction: `claimed → delivered` **and** `GROUP_OFFSET.committed_offset = GREATEST(committed, max(offset)+1)` |
| `nack(group, locations, reason)` | Below attempt threshold → back to `pending`; at/above → snapshot into DEAD_LETTER_MESSAGE + `dead` |
| `reap_expired_claims()` | Crashed-consumer recovery: expired claims re-queued or dead-lettered per group policy |
| `requeue_dlq(dlq, app, target?)` | DLQ entry re-produced as a fresh message, DLQ row marked `requeued` |

### Admin & maintenance
`register_user`, `register_application` (returns API key), `create_topic` (topic + partitions + schema v1 in one txn), `create_group`, `subscribe_group` (wires GROUP_OFFSET rows), `grant_access`, `revoke_access`, `update_broker_config`, `topic_stats`, `validate_schema`, `create_monthly_partition`, `purge_retention` (per-topic DELETE), `drop_old_partitions` (global DETACH+DROP floor).

### Error handling
Custom SQLSTATE codes `CDT01`–`CDT16` (unknown/inactive topic, revoked app, schema violation, oversize, unknown group, not subscribed, DLQ state, partition limits…) — ready to map to HTTP errors in M5.

## Verification evidence

**12-step smoke test (`tests/smoke_m2.sql`) — all green on a fresh volume:**
1. Setup: user, app, 3-partition topic with schema, group, subscription, grants
2. 10 messages: keyed ones hash-routed consistently (`order-1` → same partition every time), unkeyed spread to least-loaded partitions, per-partition offsets gap-free (0,1,2…)
3. Duplicate produce returned `is_duplicate = t` with the **original** location — zero double-insert
4. Expected errors caught with correct codes: `CDT04` schema violation, `CDT01` unknown topic
5. `consume(5)` claimed 5 rows
6. `ack` delivered all 5; `committed_offset` advanced to exactly `max(offset)+1` on each partition
7. `nack` returned 1 message to pending
8. Poison message: 3rd claim+nack hit `attempts = 3 = max` → DLQ row created, message `dead`
9. `requeue_dlq` produced it fresh (new offset), `dlq_pending` back to 0
10. Claim with 2s timeout + `pg_sleep(3)` + `reap_expired_claims()` → 3 expired claims requeued
11. Config upsert, `create_monthly_partition('2027-04-15')` → `message_2027_04` created, purge/drop no-ops
12. Final `group_offset` vs partition `next_offset` coherent

**SKIP LOCKED race demo (two concurrent sessions, `benchmarks/race_session_{a,b}.txt`):**
- Session A: `consume(batch 6)` + `pg_sleep(10)` holding row locks
- Session B: `consume(batch 6)` concurrently → claimed the **other 6 rows** (A: offsets 0–2, B: offsets 3–5 on both partitions)
- 12 messages, 12 claims, **zero overlap** — the canonical DBMS-queue concurrency proof

**EXPLAIN artifacts (`benchmarks/explain_consume*.txt`):**
- Plan shows `LockRows → Sort → Limit` (locks only the returned top-N), partition pruning via per-partition index scans on `topic_id`
- Honest finding for the defense: at demo scale (≤ ~200 rows/partition) the planner correctly prefers a **seq scan** on the populated partition over any index — the partial `status='pending'` index becomes optimal at larger scale; proving that with real numbers is scheduled for Milestone 8 (benchmarks)

## Issues found & fixed during implementation

1. `jsonb` cannot cast directly to `text[]` — `validate_schema` rewritten to iterate `jsonb_array_elements_text`
2. `RETURN QUERY` requires exact type match — `msg_key` is `varchar(128)` but OUT column was `text`; fixed with an explicit `::TEXT` cast in RETURNING
3. `set_config` is a **PostgreSQL built-in** (session GUC setter) — our config procedure renamed `update_broker_config`
4. `\gset` is a psql meta-command, unusable inside `-c` strings — smoke test uses script piping instead

## Design decisions (deviations from PLAN.md, now recorded there)

- **`attempts` increments at claim time** (SQS ReceiveCount semantics), not at nack — makes the DLQ threshold robust no matter how a claim ends (nack, crash, timeout)
- **Retention split into two mechanisms**: `purge_retention()` (per-topic DELETE, correct per-topic semantics) + `drop_old_partitions()` (global DETACH+DROP age floor) — because partitions are shared across topics by time, partition-drop cannot honor per-topic retention; the tradeoff is itself good defense material
- Role reference rows moved into `00_schema.sql` (they're schema, not demo data)

## How to run

```powershell
docker compose down -v
docker compose up -d db
Get-Content -Raw tests\smoke_m2.sql | docker exec -i conduit-db psql -U conduit -d conduit -v ON_ERROR_STOP=1
```

## Next

Milestone 3 — `20_triggers.sql` (audit, ACL enforcement, monotonic offset guard), `30_rls.sql` (row-level security), `40_views.sql` (lag/throughput/audit views).
