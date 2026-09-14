# Milestone 7 — Scenario Demo Scripts (COMPLETE)

**Date:** 2026-09-13 · **Owner:** Team 17 · **Feeds Review-2 deliverable:** D5 (Presentation)

## The Plan (as decided before implementation)

Eight narrated, self-asserting scripts riding the `conduit` SDK — each prints a step-by-step story with per-op latency and a PASS/FAIL verdict, exiting non-zero on any failed check. Every script **self-provisions its fixtures** (unique-suffix user/app/topic/group), so they run on any volume state. Python demos run inside the api container; the WAL demo is a host-level PowerShell script that kills the database and watches it recover.

| # | Script | Story |
|---|---|---|
| 1 | `01_basic_flow.py` | produce → show stored locations → SELECT the rows back → consume → ack → offsets advanced |
| 2 | `02_concurrency_race.py` | 3 barrier-synchronized consumers race; zero duplicate claims proven |
| 3 | `03_idempotency.py` | same (app, seq) × 6 → one row on disk, original location returned every time |
| 4 | `04_poison_dlq.py` | 3 failed deliveries → DLQ row → requeue → delivered |
| 5 | `05_crash_recovery.py` | crashed consumer (unacked claims) → visibility timeout → reaper → second worker completes |
| 6 | `06_security.py` | ACL denial CDT17 + AUTH_FAIL audit, RLS zero-visibility, suspend semantics, app revocation CDT03 |
| 7 | `07_exactly_once.py` | partial ack → offsets = exactly the acked prefix; duplicate ack no-ops; regression → CDT19 |
| 8 | `08_wal_recovery.ps1` | 5 acknowledged messages → `docker kill` (SIGKILL, no checkpoint) → restart → WAL replay restores everything → post-crash produce works |

SDK additions (purely additive): `Conduit.query()` (RLS-subjected reads), `Conduit.log_auth_failure()`, `ConduitAdmin.run()`.

## Planning Decisions (Q&A)

| Question | Options presented | Chosen | Rationale |
|---|---|---|---|
| Include the host-level WAL crash-recovery demo? | Add `08_wal_recovery.ps1` (rec.) / Skip, manual presenter step | Add the script | The single strongest "the DBMS WAL is our durability" moment, automatable from the host with docker |
| Where should demo scripts run? | In the api container (rec.) / On the host | In container | psycopg + SDK guaranteed present; no host setup; output appears in the presenter's terminal either way |
| Fixture style? | Self-provisioned unique-suffix fixtures (rec.) / Reuse seeded personas | Self-provisioned | Scripts run on any volume state and are endlessly re-runnable; the dashboard walkthrough separately covers the seeded personas |

## What Was Implemented

All eight scripts, the `_common.py` narration/fixture toolkit, the three SDK additions, and the compose `./demos` mount.

### Issues found & fixed during implementation
1. **Demo 05 attempt-counter expectation wrong at the wrong point in the flow** — after the reaper (before worker B re-claims) attempts is still 1; it becomes 2 only after worker B's claim. Split into two checks at the correct moments.
2. **WAL demo left the stack half-dead** — `docker kill` of the DB invalidates the api container's pooled connections (pytest afterward: stale-connection errors). The script now restarts the api container at the end so the whole stack is healthy again.
3. PowerShell `-c` with an embedded multiline Python string is quoting-fragile — the post-crash produce step switched to the stdin-pipe pattern.

### Verification evidence

- **All 7 Python demos: `DEMO COMPLETE — all checks passed`, exit 0** on a clean volume — including the race (30 messages, 3 workers, zero duplicate locations), the retry storm (6 identical produces → 1 row), the poison cycle (attempts 1→2→3 → DLQ → requeue → delivered), and the security matrix (CDT17 + AUTH_FAIL audit row + RLS zero rows + suspend cuts both layers + CDT03 revocation).
- **`08_wal_recovery.ps1`: PASS** — 5/5 acknowledged messages present after SIGKILL + restart via WAL replay, committed offsets intact (2 partitions), post-crash produce succeeded, api restarted, stack whole.
- **Sample outputs captured** as artifacts in `benchmarks/demos/01…08.txt`.
- **Regression:** full pytest suite 20/20 after the SDK additions (run pre- and post-WAL-kill with the api restart between).

## How to run

```powershell
docker compose exec -T api python demos/01_basic_flow.py     # ...through 07
powershell -ExecutionPolicy Bypass -File demos\08_wal_recovery.ps1   # host-level; kills + recovers the db
```

Any Python demo works on any volume state (they provision their own fixtures). The WAL demo requires the full stack running and restarts the api at the end.

## Next

Milestone 8 — `benchmarks/`: produce/consume throughput + latency percentiles across batch sizes and concurrency, the "price of guarantees" overhead measurement (broker path vs raw INSERT), and EXPLAIN-at-scale proving the partial pending index.
