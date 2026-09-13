# Conduit

A message broker where **PostgreSQL is the broker** — messages are rows, producing is a transaction, consuming is `SELECT … FOR UPDATE SKIP LOCKED`, durability is the database's own WAL.

Team 17 · G Anirudh · Tanay Mohta · Dhyey Dhumasia

Read [`PLAN.md`](./PLAN.md) for the full design, schema, milestones, and defense plan.

## Prerequisites

- Docker Desktop installed and running (whale icon steady in system tray)

## Run the database

```powershell
docker compose up -d db
```

First start initializes the cluster and applies every file in `db/sql/` in order (currently `00_schema.sql`; procedures, triggers, RLS, views, and seed land in later milestones).

## Connect

From inside the container:

```powershell
docker exec -it conduit-db psql -U conduit -d conduit
```

From the host (psql / pgAdmin / DBeaver): `localhost:5433`, database `conduit`, user `conduit`, password `conduit_dev`.

## Reset (after changing any SQL file)

SQL files only run against a **fresh** data volume. After editing anything in `db/sql/`:

```powershell
docker compose down -v
docker compose up -d db
```

## Demo dataset (seed)

By default a fresh volume starts **empty**. To initialize with the ~2,000-message demo dataset (4 topics, 6 users, 6 apps, 5 groups, full audit trail):

```powershell
docker compose down -v
$env:CONDUIT_SEED='true'
docker compose up -d db
Remove-Item Env:\CONDUIT_SEED
```

Wait until `docker inspect --format '{{.State.Health.Status}}' conduit-db` reports `healthy` AND `docker exec conduit-db psql -U conduit -d conduit -t -c "SELECT count(*) FROM message"` shows `2000` (the seed takes a minute or two after the container reports healthy).

## Run the broker smoke tests

Each suite expects a **fresh volume**. M2 (broker loop) and M3 (triggers/RLS/views) run on a clean, unseeded volume; M4 (seed + data management) runs on a seeded one.

```powershell
docker compose down -v
docker compose up -d db
Get-Content -Raw tests\smoke_m2.sql | docker exec -i conduit-db psql -U conduit -d conduit -v ON_ERROR_STOP=1
Get-Content -Raw tests\smoke_m3.sql | docker exec -i conduit-db psql -U conduit -d conduit -v ON_ERROR_STOP=1
```

```powershell
docker compose down -v
$env:CONDUIT_SEED='true'
docker compose up -d db
Remove-Item Env:\CONDUIT_SEED
Get-Content -Raw tests\smoke_m4.sql | docker exec -i conduit-db psql -U conduit -d conduit -v ON_ERROR_STOP=1
```

Defense artifacts (SKIP LOCKED race outputs, EXPLAIN plans, LISTEN/NOTIFY demo) live in `benchmarks/`.

## Project layout

| Path | Contents |
|---|---|
| `db/sql/` | The graded core: schema, functions, triggers, RLS, views, seed |
| `server/` | FastAPI app — thin REST/SSE layer over the procedures (upcoming) |
| `web/` | React + TS + Tailwind dashboard (upcoming) |
| `client/` | Python `conduit` SDK (upcoming) |
| `tests/` | pytest + pgTAP suites (upcoming) |
