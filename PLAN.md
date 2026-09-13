# Conduit — Project Hand-off & Plan Report

**A Message Broker built on PostgreSQL — DBMS as the Core**
Team 17 · G Anirudh (24BDS0335) · Tanay Mohta (24BDS0294) · Dhyey Dhumasia (24BCE0529)

---

## 1. What Conduit Is

Conduit is a **message broker** for asynchronous, decoupled communication between services — functionally in the spirit of Kafka/SQS: producers publish messages to **topics**, organized into **partitions**; **consumer groups** consume them with offset tracking, crash recovery, retention, dead-lettering, and access control.

The project's thesis: **the DBMS is not an accessory to the broker — the DBMS is the broker.** Messages are rows. Producing is a transaction. Consuming is `SELECT … FOR UPDATE SKIP LOCKED`. Durability is PostgreSQL's own WAL. Access control is row-level security. Observability is SQL views. Every core DBMS concept from the course appears on the broker's hot path, not in a side admin panel.

## 2. History & Pivot (context for whoever picks this up)

- **Review 1** (submitted): hybrid architecture — a custom data plane (hand-rolled append-only log + WAL + in-memory indexes) for messages, and an RDBMS control plane (6 entities: USER, TOPIC, CONSUMER_GROUP, AUDIT_LOG, BROKER_CONFIG, ACCESS) purely for metadata.
- **Problem identified**: the relational model never touched a MESSAGE. As designed, it read as "a distributed systems project with a DBMS admin panel bolted on."
- **Decision (final)**: go **full RDBMS-core**. The custom log/WAL data plane is dropped entirely. PostgreSQL stores and serves the messages themselves; its WAL replaces hand-rolled recovery. Prior art justifying this approach: **pgmq**, **Message DB**, **graphile-worker**, Quartz's JDBC store.
- **Review 2** (upcoming, 10 marks): database implementation, data insertion/management, queries/joins/aggregation, advanced features (views, procedures, triggers, functions, indexing, transactions), presentation. The plan below is built to saturate every line of that rubric.

## 3. Architecture

```
┌─────────────────────────────────────────────────────┐
│                PostgreSQL 16 (the core)             │
│  Tables · Constraints · Indexes · Partitioning      │
│  Procedures (produce/consume/commit/purge)          │
│  Triggers (audit, ACL) · RLS policies               │
│  Views (lag, throughput) · LISTEN/NOTIFY            │
│  WAL = durability & crash recovery                  │
└──────────────▲───────────────────────▲──────────────┘
               │ SQL / procedure calls │
   ┌───────────┴─────────┐   ┌─────────┴──────────┐
   │  FastAPI (thin)     │   │  Python SDK        │
   │  psycopg 3 async    │   │  `conduit` client  │
   │  SSE: NOTIFY→UI     │   │  (for demo apps)   │
   └───────────┬─────────┘   └────────────────────┘
               │ REST + SSE
   ┌───────────▼─────────────────────┐
   │ React + TS + Tailwind + Recharts│
   │ Admin dashboard + demo console  │
   └─────────────────────────────────┘
```

All business logic lives in the database (procedures/triggers). FastAPI is deliberately thin — it authenticates, maps HTTP → procedure calls, and streams `NOTIFY` events to the UI via SSE. The React app is presentation only.

## 4. Relational Model — 15 Tables

### 4.1 Identity & security

**1. ROLE**

| column | type | notes |
|---|---|---|
| role_id | SERIAL PK | |
| role_name | VARCHAR UNIQUE NOT NULL | `admin`, `operator`, `producer`, `consumer`, `viewer` |
| description | VARCHAR | |

*(Role normalized out of USER — a normalization talking-point vs. Review 1's inline string.)*

**2. USER**

| column | type | notes |
|---|---|---|
| user_id | BIGSERIAL PK | |
| username | VARCHAR(64) UNIQUE NOT NULL | |
| email | VARCHAR(255) UNIQUE NOT NULL | |
| role_id | FK → ROLE NOT NULL | |
| status | VARCHAR CHECK IN (`active`,`suspended`) DEFAULT `active` | |
| created_at | TIMESTAMPTZ DEFAULT now() | |

**3. APPLICATION** *(fixes Review-1 gap: "register client applications" had no entity)*

| column | type | notes |
|---|---|---|
| app_id | BIGSERIAL PK | |
| app_name | VARCHAR UNIQUE NOT NULL | |
| api_key | UUID UNIQUE DEFAULT gen_random_uuid() | |
| owner_user_id | FK → USER NOT NULL | |
| app_type | CHECK IN (`producer`,`consumer`,`both`) | |
| status | CHECK IN (`active`,`revoked`) DEFAULT `active` | |
| created_at | TIMESTAMPTZ DEFAULT now() | |

**4. ACCESS** — topic-level ACL grants

| column | type | notes |
|---|---|---|
| access_id | BIGSERIAL PK | |
| user_id | FK → USER NOT NULL | |
| topic_id | FK → TOPIC NOT NULL | |
| access_type | CHECK IN (`produce`,`consume`,`admin`) | |
| granted_by | FK → USER | |
| granted_at | TIMESTAMPTZ DEFAULT now() | |
| | UNIQUE(user_id, topic_id, access_type) | prevents duplicate grants |

### 4.2 Messaging domain

**5. TOPIC**

| column | type | notes |
|---|---|---|
| topic_id | BIGSERIAL PK | |
| topic_name | VARCHAR UNIQUE NOT NULL | |
| description | VARCHAR | |
| created_by | FK → USER NOT NULL | |
| retention_days | INT CHECK > 0 DEFAULT 7 | drives partition purge |
| max_message_bytes | INT DEFAULT 1048576 | |
| status | CHECK IN (`active`,`archived`) DEFAULT `active` | |
| created_at | TIMESTAMPTZ DEFAULT now() | |

**6. PARTITION** *(new entity — Review 1 had only a `partition_count` number)*

| column | type | notes |
|---|---|---|
| partition_id | BIGSERIAL PK | |
| topic_id | FK → TOPIC NOT NULL | |
| partition_number | INT CHECK >= 0 | |
| next_offset | BIGINT DEFAULT 0 | monotonic counter, incremented under `FOR UPDATE` lock during produce |
| | UNIQUE(topic_id, partition_number) | |

**7. SCHEMA_VERSION** *(new entity — Review 1 had a text blob on TOPIC)*

| column | type | notes |
|---|---|---|
| schema_id | BIGSERIAL PK | |
| topic_id | FK → TOPIC NOT NULL | |
| version | INT CHECK >= 1 | |
| format | CHECK IN (`json`) | |
| definition | JSONB NOT NULL | message contract |
| status | CHECK IN (`active`,`deprecated`) DEFAULT `active` | |
| created_by | FK → USER | |
| created_at | TIMESTAMPTZ DEFAULT now() | |
| | UNIQUE(topic_id, version) | |

**8. MESSAGE** — the heart of the system; **range-partitioned by `created_at` (monthly)**

| column | type | notes |
|---|---|---|
| topic_id | BIGINT FK → TOPIC | FKs from partitioned tables verified working on PG16 |
| partition_id | BIGINT FK → PARTITION | |
| msg_offset | BIGINT NOT NULL | per-partition, gap-free, assigned in-txn (renamed from `offset` — reserved word in constraint/index lists) |
| msg_key | VARCHAR(128) | routing: hash(key) → partition; NULL = round-robin |
| payload | JSONB NOT NULL | validated against active SCHEMA_VERSION |
| size_bytes | INT | |
| producer_app_id | BIGINT FK → APPLICATION | |
| producer_seq | BIGINT NOT NULL | producer-side sequence |
| status | CHECK IN (`pending`,`claimed`,`delivered`,`dead`) DEFAULT `pending` | claim-based delivery |
| claimed_by | BIGINT FK → CONSUMER_GROUP | consumer group id |
| visible_at | TIMESTAMPTZ | visibility timeout for crashed consumers |
| attempts | INT DEFAULT 0 | delivery attempts → DLQ threshold |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | **partition key** |
| | **PRIMARY KEY (created_at, topic_id, partition_id, msg_offset)** | |

**9. PRODUCER_SEQUENCE** — idempotency ledger *(added during Milestone 1: unique constraints on a partitioned table must include the partition key, so `(producer_app_id, producer_seq)` dedupe cannot live on MESSAGE — a retry would get a new `created_at` and slip past it)*

| column | type | notes |
|---|---|---|
| producer_app_id | BIGINT FK → APPLICATION | composite PK |
| producer_seq | BIGINT CHECK >= 0 | composite PK |
| topic_id | BIGINT | location of the original message |
| partition_id | BIGINT | |
| msg_offset | BIGINT CHECK >= 0 | |
| created_at | TIMESTAMPTZ DEFAULT now() | |

**10. CONSUMER_GROUP** *(no topic FK — fixed: subscription is M:N)*

| column | type | notes |
|---|---|---|
| group_id | BIGSERIAL PK | |
| group_name | VARCHAR UNIQUE NOT NULL | |
| created_by | FK → USER | |
| max_delivery_attempts | INT DEFAULT 3 CHECK 1..10 | before DLQ |
| status | CHECK IN (`active`,`paused`) DEFAULT `active` | |
| created_at | TIMESTAMPTZ DEFAULT now() | |

**11. GROUP_SUBSCRIPTION** — resolves the M:N

| column | type | notes |
|---|---|---|
| group_id | FK → CONSUMER_GROUP | composite PK |
| topic_id | FK → TOPIC | |
| subscribed_at | TIMESTAMPTZ DEFAULT now() | |

**12. GROUP_OFFSET** *(fixes Review-1 flaw: single scalar `committed_offset` breaks with multiple partitions)*

| column | type | notes |
|---|---|---|
| group_id | FK → CONSUMER_GROUP | composite PK |
| partition_id | FK → PARTITION | |
| committed_offset | BIGINT DEFAULT 0 CHECK >= 0 | monotonic — regression blocked by trigger |
| updated_at | TIMESTAMPTZ DEFAULT now() | |

**13. DEAD_LETTER_MESSAGE** *(new entity)*

| column | type | notes |
|---|---|---|
| dlq_id | BIGSERIAL PK | |
| original_topic_id | INT FK → TOPIC | snapshot fields — original row may be purged by retention |
| original_offset | BIGINT | |
| msg_key | VARCHAR(128) | |
| payload | JSONB NOT NULL | |
| failed_group_id | BIGINT FK → CONSUMER_GROUP | |
| failure_reason | TEXT | |
| attempts | INT | |
| status | CHECK IN (`pending`,`requeued`) DEFAULT `pending` | |
| dead_at | TIMESTAMPTZ DEFAULT now() | |

### 4.3 Operations & governance

**14. AUDIT_LOG** — populated exclusively by triggers

| column | type | notes |
|---|---|---|
| log_id | BIGSERIAL PK | |
| user_id | FK → USER NULL | NULL = system/trigger-generated |
| app_id | FK → APPLICATION NULL | |
| topic_id | FK → TOPIC NULL | |
| event_type | VARCHAR NOT NULL | `PRODUCE`,`DELIVER`,`DLQ`,`TOPIC_CREATE`,`ACL_GRANT`,`ACL_REVOKE`,`CONFIG_CHANGE`,`AUTH_FAIL`… |
| status | CHECK IN (`success`,`failure`) | |
| details | JSONB | |
| event_timestamp | TIMESTAMPTZ DEFAULT now() | BRIN-indexed |

**15. BROKER_CONFIG**

| column | type | notes |
|---|---|---|
| config_id | SERIAL PK | |
| config_key | VARCHAR UNIQUE NOT NULL | e.g. `default_visibility_timeout_s` |
| config_value | TEXT NOT NULL | |
| description | VARCHAR | |
| updated_by | FK → USER | |
| updated_at | TIMESTAMPTZ DEFAULT now() | bumped by trigger |

### 4.4 Relationships summary

```
ROLE 1─M USER 1─M APPLICATION
USER 1─M TOPIC 1─M PARTITION 1─M MESSAGE ─M─1 APPLICATION (producer)
TOPIC 1─M SCHEMA_VERSION
TOPIC 1─M ACCESS M─1 USER
CONSUMER_GROUP 1─M GROUP_SUBSCRIPTION M─1 TOPIC          (M:N)
CONSUMER_GROUP 1─M GROUP_OFFSET M─1 PARTITION
CONSUMER_GROUP 1─M DEAD_LETTER_MESSAGE
APPLICATION 1─M PRODUCER_SEQUENCE (idempotency ledger)
USER / APPLICATION / TOPIC 1─M AUDIT_LOG
```

## 5. Database Artifacts (the graded core, in `db/sql/`)

### 5.1 Procedures & functions (`10_functions.sql`)

| Routine | What it does | DBMS concept demonstrated |
|---|---|---|
| `create_topic(name, n_partitions, schema JSONB, owner)` | One transaction: TOPIC + N PARTITION rows + SCHEMA_VERSION v1 | Transactions |
| `produce(topic, key, payload, app, seq)` | First claims `(app, seq)` in PRODUCER_SEQUENCE via `ON CONFLICT DO NOTHING` (duplicate produce returns the original message location — idempotency). Then resolves partition (hash(key) mod N / round-robin), `LOCK PARTITION FOR UPDATE`, assigns gap-free offset, validates against active schema, inserts, `pg_notify` | Transactions, isolation, error handling |
| `produce_batch(...)` | Batched variant | Performance/latency story |
| `consume(group, topic, batch, timeout)` | `SELECT … WHERE status='pending' AND visible_at <= now() ORDER BY offset LIMIT n FOR UPDATE SKIP LOCKED` → mark `claimed`, set `visible_at = now()+timeout`; commit releases locks | **Concurrency control** — the canonical DBMS-queue pattern |
| `ack(group, message_ids)` | `claimed → delivered` + advance `GROUP_OFFSET.committed_offset` to `max(offset)+1` **in the same transaction** | Atomic multi-table txn (exactly-once delivery) |
| `nack(group, message_ids, reason)` | Back to `pending`, `attempts++`; if `attempts >= max` → DLQ insert + `dead` | Transactions, error paths |
| `requeue_dlq(dlq_id, producer_app, target_topic)` | DLQ → fresh produce with a requeue-sequence id | Procedures composing procedures |
| `purge_retention(topic?)` | Per-topic `DELETE` of messages older than the topic's `retention_days` | Physical design, DELETE + vacuum discussion |
| `drop_old_partitions(keep_days)` | Global floor: `DETACH PARTITION` + drop of month partitions older than keep_days (retention is per-topic, so partition-drop cannot be per-topic — both mechanisms shipped and the tradeoff documented) | Partition lifecycle |
| `register_user`, `grant_access`, `revoke_access`, `create_group`, `subscribe_group`, `set_config` | Admin ops with audit | Full lifecycle |
| `fn_validate_schema(payload, schema)` | JSONB contract validation | Functions |
| `fn_topic_stats(topic_id)` | Aggregated stats | Aggregation in SQL |

### 5.2 Triggers (`20_triggers.sql`)

- **Audit trigger** on MESSAGE insert/status-change, ACCESS/TOPIC/BROKER_CONFIG changes → AUDIT_LOG rows (the audit trail is *guaranteed* by the DB, not by app code).
- **ACL enforcement trigger** on MESSAGE insert: raises exception if the producer app's owner lacks `produce` access on the topic.
- **Monotonic-offset trigger** on GROUP_OFFSET: rejects `committed_offset` regression.
- **`updated_at` bump** trigger on BROKER_CONFIG.
- **NOTIFY trigger** on MESSAGE insert → `pg_notify('conduit_events', …)`.

### 5.3 Row-level security (`30_rls.sql`)

Policies on MESSAGE/TOPIC keyed to ACCESS grants for `current_setting('app.user_id')`, set per-request by FastAPI via `SET LOCAL`. Demo: even the application's DB login cannot bypass topic-level ACLs.

### 5.4 Views (`40_views.sql`)

- `v_consumer_lag` — GROUP_OFFSET vs `max(offset)` per (group, partition): JOIN + aggregate.
- `v_topic_stats` — counts, DLQ depth, oldest pending message.
- `v_throughput_by_minute` — window functions over MESSAGE/AUDIT_LOG.
- `v_audit_search` — filtered audit trail for the dashboard.
- Materialized variant refreshed on NOTIFY for dashboard snapshots.

### 5.5 Indexing plan

- Composite `(topic_id, partition_id, msg_offset)` — consume scans.
- Partial index `WHERE status='pending'` — the hot consume path.
- Partial index `WHERE status='claimed'` on `visible_at` — reaping crashed consumers.
- BRIN on `MESSAGE.created_at` and `AUDIT_LOG.event_timestamp` — append-only tables.
- PK on `(producer_app_id, producer_seq)` in PRODUCER_SEQUENCE — idempotency.
- `(event_type, event_timestamp)` on AUDIT_LOG — filtered audit search.
- `EXPLAIN (ANALYZE, BUFFERS)` artifacts collected for the presentation.

### 5.6 Delivery & recovery semantics (defense script)

- **At-least-once** by default (crashed consumer's claims reappear when `visible_at` passes); **exactly-once effect** via idempotent produce + atomic ack+offset commit.
- **Crash recovery demo**: kill Postgres mid-transaction → WAL replay restores all acknowledged messages; uncommitted work vanishes. This *replaces* Review 1's hand-rolled WAL objective.

## 6. Tech Stack (final, locked)

| Layer | Choice | Rationale |
|---|---|---|
| Database | PostgreSQL 16 + pgTAP | SKIP LOCKED, LISTEN/NOTIFY, BRIN, RLS, JSONB, partitioning |
| DB artifacts | Hand-written numbered SQL files | The DDL/procedures/triggers *are* the graded project |
| DB access | psycopg 3 async, raw SQL / procedure calls, **no ORM** | Keeps the "DBMS as core" thesis honest |
| Backend | FastAPI + Pydantic (validation only at API boundary) | Async; SSE; auto API docs |
| Frontend | React + TypeScript (Vite) + Tailwind CSS + Recharts | Dashboard, charts, SSE live updates via `EventSource` |
| Client SDK | Pure-Python `conduit` package | Demo producers/consumers |
| Runtime | Docker Compose: `db` + `api` + `web`, init SQL auto-loaded on first start | Identical envs for 3 teammates + demo machine |
| Tests | pytest (disposable container DB) + pgTAP (in-database tests) | Procedures/triggers tested in-database |

## 7. Repository Layout

```
Conduit/
├── PLAN.md                  # this document
├── docker-compose.yml
├── db/
│   ├── sql/
│   │   ├── 00_schema.sql    # DDL, constraints, indexes, partitioning
│   │   ├── 10_functions.sql # produce/consume/commit/purge/admin procedures
│   │   ├── 20_triggers.sql  # audit, ACL, monotonic offset, updated_at, notify
│   │   ├── 30_rls.sql       # row-level security policies
│   │   ├── 40_views.sql     # lag/stats/throughput/audit views
│   │   └── 50_seed.sql      # demo dataset
│   └── init/                # docker-entrypoint-initdb.d wiring
├── server/                  # FastAPI app (thin): auth, REST → procedures, SSE
│   ├── app/main.py
│   ├── app/api/             # admin.py, broker.py, events.py (SSE)
│   ├── app/db.py            # psycopg pool + SET LOCAL app.user_id
│   └── app/templates/       # error pages if any (Jinja minimal)
├── web/                     # Vite React+TS SPA
│   ├── src/pages/           # Dashboard, Topics, Groups, Audit, DLQ, Playground
│   └── src/api/             # REST + EventSource SSE client
├── client/                  # python `conduit` SDK: produce/consume/ack/admin
├── tests/
│   ├── pg/                  # pgTAP suites
│   └── py/                  # pytest: API + SDK integration
└── benchmarks/              # throughput scripts + EXPLAIN artifacts
```

## 8. Milestones (each tagged to Review-2 deliverables)

| # | Milestone | Deliverable fed |
|---|---|---|
| 1 | Docker Compose + `00_schema.sql` (15 tables, constraints, indexes, partitioning) + updated ER diagram | D1 (implementation) |
| 2 | `10_functions.sql` — produce/consume/ack/nack with SKIP LOCKED + transactions | D4 (advanced) |
| 3 | `20_triggers.sql` + `30_rls.sql` + `40_views.sql` | D4, D3 |
| 4 | `50_seed.sql` (CONDUIT_SEED-gated demo dataset) + admin management functions + suspend-cuts-access semantics | D2 (insertion & management) |
| 5 | Python `conduit` SDK + FastAPI surface (auth, REST → procedures, SSE from NOTIFY, two connection modes) | — |
| 6 | React dashboard: Overview (lag/throughput charts), Topics, Groups, **Message Browser** (real rows, live status flips via SSE), **Playground** (produce panel + consumer panel with claims and Ack — the send→stored→read demo), Audit, DLQ, ACL manager, **read-only SQL console** (admin-only, `BEGIN READ ONLY` + statement validation) | D3, D5 |
| 7 | `demos/` — 7 narrated Python scenario scripts on the SDK: basic flow, SKIP LOCKED race, idempotency, poison→DLQ→requeue, crash recovery, security denials, exactly-once | D5 |
| 8 | `benchmarks/` — produce/consume throughput + latency percentiles across batch sizes and concurrency; "price of guarantees" overhead measurement (broker path vs raw INSERT); EXPLAIN-at-scale proving the partial pending index | Defense |

## 9. Demo & Defense Plan

- **Guaranteed question**: "Your own Review-1 doc said RDBMS-as-queue is overhead — why?" Answer: correctness-first (real transactions, atomic ack+offset, in-DB ACL/audit), free WAL recovery, prior art (pgmq, Message DB, graphile-worker), honest measured tradeoff.
- **Live demos**: (a) two consumer-group members racing via SKIP LOCKED — no message served twice; (b) kill DB mid-txn → WAL recovery; (c) duplicate produce → `ON CONFLICT` idempotency; (d) message failing 3× → DLQ → requeue; (e) RLS blocking an unauthorized app at the DB level.
- **Numbers**: produce/consume throughput at batch sizes 1/10/100/1000, 1 vs 5 groups; `EXPLAIN (ANALYZE, BUFFERS)` proving index usage.

## 10. Decisions Log

| Decision | Choice | Date |
|---|---|---|
| DBMS-core vs hybrid | Full RDBMS core; custom log/WAL dropped | locked |
| Engine | PostgreSQL 16 | locked |
| DB access | Raw psycopg 3 + stored procedures, no ORM | locked |
| Frontend | React + TS + Tailwind + Recharts (revised from HTMX) | locked |
| Runtime | Full Docker Compose (db + api + web) | locked |
| Delivery model | Claim-based (pending→claimed→delivered) + group offsets for lag | planned |
| Offset assignment | In-txn counter on PARTITION row under row lock (gap-free) | planned |
| Message offset column | Renamed `offset` → `msg_offset` (`offset` is a reserved word in PG constraint/index column lists — hit during Milestone 1) | done |
| Produce idempotency | Dedicated PRODUCER_SEQUENCE ledger table; unique constraints on a partitioned table must include the partition key, so dedupe can't live on MESSAGE | done |
| MESSAGE referential integrity | FKs from partitioned tables ARE supported on PG16 — 4 real FKs added (topic, partition, application, claimed_by) | done |
| Milestone 1 status | Schema deployed via `docker compose up -d db`; 15 tables, 157 constraints, 8 partitions verified | done |
| Attempts semantics | `attempts` incremented at claim time (SQS ReceiveCount style); nack/reap route to DLQ when `attempts >= max` | done |
| Config procedure name | `set_config` renamed `update_broker_config` (`set_config` is a PostgreSQL built-in) | done |
| Retention mechanism | Split: per-topic `purge_retention` (DELETE) + global `drop_old_partitions` (DETACH+DROP floor) | done |
| Role reference data | 5 role rows moved into `00_schema.sql` (reference data, not demo data) | done |
| Milestone 2 status | `10_functions.sql` deployed; 12-step smoke test green; SKIP LOCKED race demo disjoint; EXPLAIN artifacts captured | done |
| Audit granularity | Terminal events only (PRODUCE/DELIVERED/DLQ/ACL/CONFIG/TOPIC/SCHEMA/AUTH_FAIL) — no per-claim rows | done |
| RLS scope | `message` + `dead_letter_message`; policies keyed on `current_setting('app.user_id')`; admin role bypass; GUC unset = default-deny | done |
| DB roles | `conduit_app` login role for the hot path; superuser `conduit` for admin/maintenance → M5 API uses two connection modes | done |
| Function execute hardening | `REVOKE EXECUTE ON ALL FUNCTIONS FROM PUBLIC` + explicit grants + default-privileges change so future functions stay private | done |
| AUTH_FAIL pattern | Triggers raise clean errors only (a raising trigger's own audit insert would roll back); callers catch and invoke `log_auth_failure()` | done |
| Milestone 3 status | 15 triggers, RLS matrix verified (granted/denied/anonymous), views + matview consistent, LISTEN/NOTIFY demo captured; smoke_m2 regression green | done |
| Admin management | 7 functions (suspend/activate user, app status, topic config/archive, group pause/activate, schema publish) | done |
| Suspend semantics | Suspended users lose access at BOTH trigger and RLS layers (`status='active'` required); `produce` also enforces `app_type` (`CDT20`) | done |
| Seed gating | `CONDUIT_SEED` env var (default **false**) — clean volumes for smoke tests, seeded volumes for the demo machine | done |
| Healthcheck | TCP-based `pg_isready -h 127.0.0.1` (socket-based reports healthy during initdb and let tests run against a half-seeded DB) | done |
| Dashboard SQL console | Read-only SQL runner included in M6 (admin-only, `BEGIN READ ONLY` + statement validation) | planned |
| Scenario/benchmark scripts | Python on the `conduit` SDK (same code path as API/dashboard), in `demos/` (M7) and `benchmarks/` (M8) | planned |
| Milestone 4 status | 2,000-message seed verified to exact shape (1580/390/29/1); smoke_m4 all 10 sections green; m2+m3 regression green on clean volume | done |
   