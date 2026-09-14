# Milestone 1 — Schema & Runtime (COMPLETE)

**Date:** 2026-09-13 · **Owner:** Team 17 · **Feeds Review-2 deliverable:** D1 (Database implementation: tables, constraints/validation)

## Goal

Stand up the Dockerized PostgreSQL runtime and deploy the full relational schema — every entity the broker needs, with real constraints, indexes, and monthly partitioning of the MESSAGE table.

## Planning Decisions (Q&A)

| Question | Options presented | Chosen | Rationale |
|---|---|---|---|
| How far should the DBMS be the core? | Full RDBMS core (rec.) / Deepened hybrid | Full RDBMS core | Messages as rows, procedures as the broker, PostgreSQL's WAL replaces hand-rolled recovery — the cleanest DBMS-project narrative; keeping the custom log data plane would dilute the DBMS focus |
| Which RDBMS? | PostgreSQL (rec.) / MySQL | PostgreSQL | SKIP LOCKED, LISTEN/NOTIFY, BRIN, row-level security, materialized views — the full feature showcase the project needs |
| DB access pattern? | Raw psycopg 3 + stored procedures (rec.) / SQLAlchemy Core | Raw psycopg + procedures | All SQL lives in reviewable `.sql` files; no ORM keeps the "DBMS as core" thesis honest |
| How to run locally + at the demo? | Full Docker Compose (rec.) / Native installs / Dockerized Postgres only | Full Docker Compose | Identical environments for 3 teammates + demo machine; one command up |
| Verification environment (no Docker on the machine)? | Install Docker Desktop (rec.) / WSL Postgres (needs sudo password) / Portable PG16 in temp | Install Docker Desktop | The project runtime is Docker Compose anyway; the existing WSL2 backend made it a one-time setup |
| Web interface (initial choice)? | FastAPI + Jinja + HTMX (rec.) / React SPA / Jinja only | Jinja + HTMX | Python-only stack, least effort at the time — later revised by direct instruction to React+TS, then finalized back to Jinja+HTMX in Milestone 6 (see its decisions table) |

## What was built

| File | Contents |
|---|---|
| `db/Dockerfile` | postgres:16 + pgTAP (apt from PGDG repo) |
| `docker-compose.yml` | `db` service: port 5433 host-mapped, `db/sql` mounted as `docker-entrypoint-initdb.d` (files apply in lexical order on fresh volume), healthcheck, named volume `conduit_pgdata` |
| `db/sql/00_schema.sql` | 15 tables, 157 constraints, 8 message partitions, full index set |
| `README.md` | Team quickstart (run, connect, reset) |
| `PLAN.md` | Updated with deployment findings (see below) |

## Schema summary

- **15 tables**: role, app_user, application, topic, partition, schema_version, message, producer_sequence, consumer_group, group_subscription, group_offset, access, dead_letter_message, audit_log, broker_config
- **Constraint types in use**: PRIMARY KEY (single + composite), FOREIGN KEY with deliberate ON DELETE behavior (CASCADE / RESTRICT / SET NULL per relationship), CHECK (status enums, offset/attempt/version bounds, retention range), UNIQUE (natural keys, ACL triple, idempotency ledger PK)
- **MESSAGE partitioning**: `PARTITION BY RANGE (created_at)`, monthly partitions 2026-09 → 2027-03 + DEFAULT partition; PK includes the partition key `(created_at, topic_id, partition_id, msg_offset)`
- **Indexes**: composite `(topic_id, partition_id, msg_offset)` consume scan; partial `WHERE status='pending'` (hot path); partial `WHERE status='claimed'` on `visible_at` (reaper); BRIN on `message.created_at` + `audit_log.event_timestamp`; `(producer_app_id, producer_seq)` lookup; `(event_type, event_timestamp)` audit search

## Verification evidence

- `docker compose up -d db` → container reaches `healthy` state; init logs clean (no ERROR/FATAL)
- `\dt` lists all 15 tables + 8 partition relations
- `pg_inherits` query confirms 7 range partitions bound correctly + DEFAULT
- `pg_constraint` count: **157** across the schema
- FK-from-partitioned-table probe: `ALTER TABLE message ADD FOREIGN KEY (topic_id) REFERENCES topic(topic_id)` **accepted on PG16** → 4 real FKs added on MESSAGE (topic, partition, application, claimed_by)

## Issues found & fixed during deployment (good defense material)

1. **`offset` is a reserved word** in PostgreSQL constraint/index column lists — `PRIMARY KEY (..., offset)` and `CREATE INDEX (... offset)` both fail to parse. Renamed the column to **`msg_offset`**. Lesson: keyword-class awareness (`offset` is unreserved in some positions, restricted in others).
2. **Idempotency couldn't live on MESSAGE**: unique constraints on a partitioned table must include the partition key (`created_at`), but `(producer_app_id, producer_seq, created_at)` would let a duplicate retry with a fresh timestamp slip through. Solution: dedicated **PRODUCER_SEQUENCE ledger table** with composite PK `(producer_app_id, producer_seq)` — the textbook outbox-idempotency pattern. This became the 15th table.
3. **"FKs can't reference from partitioned tables" was false on PG16** — verified empirically and added 4 real FKs, upgrading the design from trigger-enforced integrity to constraint-enforced integrity.

## How to run

```powershell
docker compose up -d db
docker exec -it conduit-db psql -U conduit -d conduit
```

Reset after changing SQL (init only runs on a fresh volume):

```powershell
docker compose down -v
docker compose up -d db
```

Host connection: `localhost:5433`, db `conduit`, user `conduit`, password `conduit_dev`.
