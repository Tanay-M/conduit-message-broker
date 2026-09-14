# Milestone 5 — Python SDK + FastAPI Service (COMPLETE)

**Date:** 2026-09-13 · **Owner:** Team 17 · **Feeds:** M6 (dashboard), M7 (demo scripts), M8 (benchmarks)

## The Plan (as decided before implementation)

### Architecture
- **SDK = sync psycopg calling the stored procedures directly** (the database *is* the API; zero HTTP overhead for benchmarks). Two client classes mirroring the M3 connection design: `Conduit(api_key)` on the `conduit_app` role with `SET LOCAL app.user_id` (RLS applies), `ConduitAdmin(dsn)` on the superuser connection.
- **FastAPI = async, deliberately thin** — Pydantic validates at the boundary, calls the same procedures via two async pools; reuses the SDK's `conduit.errors` module so `CDTxx` codes map to typed exceptions everywhere.
- **SSE**: dedicated LISTENing connection streams `conduit_events` at `GET /api/events` with 15s keepalives.

### Auth (as chosen: api-key only + env admin token)
- Broker/monitor endpoints: `Authorization: Bearer <app api_key>` → new `fn_auth_app(api_key)` resolves app + owner (raises `CDT22` unknown, `CDT03` revoked, `CDT22` suspended owner) → server sets `app.user_id` per request
- Admin endpoints: `Authorization: Bearer <ADMIN_TOKEN>` from `CONDUIT_ADMIN_TOKEN` env (compose default `conduit-admin-token`)
- One DB addition only: `fn_auth_app` + EXECUTE grant — no schema change

### API surface
Broker (produce / produce-batch / consume / ack / nack), monitoring (me / dashboard / lag / throughput / messages-browser — RLS-scoped), admin (users, apps, topics, groups, access, schemas, DLQ, config, maintenance), **SQL console** (admin-only, single SELECT/EXPLAIN, `BEGIN TRANSACTION READ ONLY`, 5s statement timeout, 500-row cap), SSE events. Global exception handler maps `CDTxx` SQLSTATEs → HTTP (404/403/422/409/401/413…).

### Verification plan
`tests/py/test_m5.py` (10 tests) run inside the api container; regressions m2/m3 (clean volume) and m4 (seeded volume).

## Planning Decisions (Q&A)

| Question | Options presented | Chosen | Rationale |
|---|---|---|---|
| Authentication model? | pgcrypto bcrypt + JWT sessions (rec.) / Api-key only + env admin token | **Api-key only + env admin token** (chosen against the recommendation) | Zero schema change and fastest to build; acceptable because DB-level security (RLS + ACL triggers) is the real boundary — tradeoff noted: dashboard login is token-based rather than per-user |
| SDK transport? | Direct-to-DB psycopg (rec.) / Over HTTP | Direct-to-DB | Zero HTTP overhead for benchmarks; strongest DBMS-core thesis; FastAPI remains a separate thin layer |
| SQL console endpoint timing? | Build endpoint in M5 (rec.) / Defer all of it to M6 | Build in M5 | It is API-side work; only the UI lands in M6 |

## What Was Implemented

All of the above, deployed as compose service `api` (port 8000, docs at `/docs`), and verified.

| Component | Contents |
|---|---|
| `client/conduit/` | `errors.py` (20+ typed exceptions + `from_psycopg`), `db.py` (pool + GUC transaction helper), `security.py`, `broker.py` (`Conduit`: produce/batch/consume/ack/nack/accessible_topics), `admin.py` (`ConduitAdmin`: 20 admin procedures) |
| `server/app/` | `config.py` (env settings), `db.py` (two async pools + `run()`), `auth.py` (require_app / require_admin), `main.py` (lifespan, CORS, CDT→HTTP map), routers: `broker`, `monitor`, `admin` (28 endpoints), `events` (SSE), `sql` (console) |
| `db/sql/10_functions.sql` | `fn_auth_app` (+ grant in `30_rls.sql`) |
| `docker-compose.yml` | `api` service (build context repo root, depends on healthy db, tests mounted) |

### Issues found & fixed during implementation
1. **psycopg typed-parameter mismatch** (the big one): psycopg adapts small Python ints as `smallint` and `Json(...)` as `json`, so `create_topic(unknown, unknown, smallint, json, unknown)` didn't resolve. Every procedure call in SDK and server now uses explicit casts (`%s::int`, `%s::bigint`, `%s::jsonb`, `%s::text`). psql smoke tests never caught this because untyped literals let PG infer types.
2. **Audit endpoint placement**: `/api/audit` through the app pool failed with 403 — `v_audit_recent` is `security_invoker` and `conduit_app` deliberately has INSERT-only on `audit_log`. Moved the endpoint under `/api/admin/audit` (admin pool + admin token) — audit stays admin-only, matching the M3 grant design.

### Verification evidence

**`tests/py/test_m5.py` — 10/10 passed** (inside the api container):
- health; admin gating (401 no token / 403 wrong token); unknown api key → 401
- **SDK round-trip**: produce → duplicate produce returns the *same* location (`duplicate: true`) → consume returns the payload → ack → accessible topics listed
- **API round-trip** over HTTP: produce → consume (messages + locations) → ack
- **Error mapping**: schema-violation payload → HTTP 422 with `{"error": "CDT04"}`
- **RLS through the API**: ungranted user's key sees `[]` on `/api/messages`; granted key sees rows
- Monitoring: dashboard / lag / throughput 200; audit admin-only (admin 200, app key 404 outside admin prefix)
- **SQL console**: `SELECT count(*)` works; `UPDATE` → 400; no token → 401
- **SSE**: live stream received a `PRODUCE` notification triggered by a concurrent SDK produce

**Regressions**: `smoke_m2` ✓ and `smoke_m3` ✓ on a clean volume (with the new function + grant active); `smoke_m4` ✓ on a fresh seeded volume (2,000 messages).

## How to run

```powershell
docker compose up -d db api
# API: http://localhost:8000  (interactive docs at /docs)
# run the M5 suite inside the container:
docker compose exec api python -m pytest tests/py -v
```

SDK from Python (host or container):

```python
import conduit
c = conduit.Conduit("<app api key>")          # hot path (RLS applies)
loc = c.produce("orders", {"event": "created", "order_id": 1}, seq=1, key="order-1")
msgs = c.consume("billing-workers", "orders", batch=10)
c.ack("billing-workers", [m["location"] for m in msgs])

admin = conduit.ConduitAdmin()                # admin connection
admin.create_topic("payments", 2, "sysadmin", schema={"required": ["event"]})
```

## Next

Milestone 6 — React + TS + Tailwind dashboard: Overview (lag/throughput charts), Topics, Groups, **Message Browser** (live status flips via SSE), **Playground** (produce/consumer panels — the send→stored→read demo), Audit, DLQ, ACL manager, and the **read-only SQL console** UI, all on the API built here.
