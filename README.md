# Conduit

A message broker where **PostgreSQL is the broker** — messages are rows, producing is a transaction, consuming is `SELECT … FOR UPDATE SKIP LOCKED`, durability is the database's own WAL.

Team 17 · G Anirudh · Tanay Mohta · Dhyey Dhumasia

Read [`PLAN.md`](./PLAN.md) for the full design and [`progress/`](./progress/) for per-milestone implementation reports.

## Prerequisites

- Docker Desktop installed and running (whale icon steady in system tray)

## Run everything (database + API + web dashboard)

```powershell
$env:CONDUIT_SEED='true'   # optional: start with the 2,000-message demo dataset
docker compose down -v
docker compose up -d
Remove-Item Env:\CONDUIT_SEED
```

- **Dashboard + API**: http://localhost:8000 — sign in with the admin token (`conduit-admin-token`) or an app api key (revealed under Admin → Applications)
- **DB**: `localhost:5433`, database `conduit`, user `conduit`, password `conduit_dev`; inside the container: `docker exec -it conduit-db psql -U conduit -d conduit`
- First start initializes the cluster and applies every file in `db/sql/`. With seeding on, wait until `docker exec conduit-db psql -U conduit -d conduit -t -c "SELECT count(*) FROM message"` shows `2000` before demoing
- All frontend libraries are vendored in `server/app/static/vendor/` — the dashboard works fully **offline**

## Reset (after changing any SQL file)

SQL files only run against a **fresh** data volume:

```powershell
docker compose down -v
docker compose up -d
```

## The walkthrough demo (send → stored → read)

1. Sign in as admin → **Admin → Applications** → reveal an api key (e.g. `fraud-detector`) → copy it, logout
2. Sign in with the **api key** → **Playground**
3. Produce panel: pick a topic, send a payload → the chip shows *stored at topic/partition/offset*, and the live table below flashes the new **pending** row
4. Consumer panel: pick group + topic → **Consume** → claimed messages appear with payloads; rows flip amber
5. **Ack** → rows flip green (**delivered**). Nack the same message 3× → it lands on the **DLQ** page → requeue it from there

## Run the test suites

```powershell
Get-Content -Raw tests\smoke_m2.sql | docker exec -i conduit-db psql -U conduit -d conduit -v ON_ERROR_STOP=1
Get-Content -Raw tests\smoke_m3.sql | docker exec -i conduit-db psql -U conduit -d conduit -v ON_ERROR_STOP=1
Get-Content -Raw tests\smoke_m4.sql | docker exec -i conduit-db psql -U conduit -d conduit -v ON_ERROR_STOP=1
docker compose exec api python -m pytest tests/py -v
```

`smoke_m2`/`smoke_m3` expect a clean (unseeded) fresh volume; `smoke_m4` expects a seeded one.

## Scenario demo scripts

Eight narrated, self-asserting demos (any volume state — they provision their own fixtures):

```powershell
docker compose exec -T api python demos/01_basic_flow.py        # send -> stored -> read -> ack
docker compose exec -T api python demos/02_concurrency_race.py # 3 racing consumers, zero duplicates
docker compose exec -T api python demos/03_idempotency.py      # retry storm -> one row on disk
docker compose exec -T api python demos/04_poison_dlq.py       # poison -> DLQ -> requeue
docker compose exec -T api python demos/05_crash_recovery.py   # crashed consumer -> reaper
docker compose exec -T api python demos/06_security.py         # ACL/RLS denials + audit
docker compose exec -T api python demos/07_exactly_once.py     # atomic ack + offsets
powershell -ExecutionPolicy Bypass -File demos\08_wal_recovery.ps1   # kill -9 the DB -> WAL replay
```

Sample outputs are captured in `benchmarks/demos/`.

## Python SDK

Installable package in `client/` (`pip install -e client`). Talks to the stored procedures directly:

```python
import conduit
c = conduit.Conduit("<app api key>")
c.produce("orders", {"event": "created", "order_id": 1}, seq=1, key="order-1")
msgs = c.consume("billing-workers", "orders", batch=10)
c.ack("billing-workers", [m["location"] for m in msgs])
```

## Benchmarks (defense numbers)

```powershell
docker compose exec -T api python benchmarks/bench_produce.py       # batch sweep + contention
docker compose exec -T api python benchmarks/bench_consume.py       # batch sweep + 5-worker drain
docker compose exec -T api python benchmarks/bench_overhead.py      # price of guarantees (3 tiers)
docker compose exec -T api python benchmarks/explain_at_scale.py    # 30k-message partial-index proof
```

Results land in `benchmarks/results/*.json`; the EXPLAIN artifact in `benchmarks/explain_at_scale.txt`. Headline numbers and analysis in `progress/MILESTONE-08.md`.

## Project layout

| Path | Contents |
|---|---|
| `db/sql/` | The graded core: schema, procedures, triggers, RLS, views, gated seed |
| `server/` | FastAPI: JSON API + SSE + Jinja/HTMX dashboard (single container) |
| `client/` | Python `conduit` SDK |
| `tests/` | psql smoke suites + pytest integration |
| `progress/` | Per-milestone reports (plan + what was implemented) |
| `benchmarks/` | Defense artifacts (SKIP LOCKED race, EXPLAIN plans, LISTEN/NOTIFY) |
