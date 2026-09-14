# Milestone 6 — Web Dashboard (COMPLETE)

**Date:** 2026-09-13 · **Owner:** Team 17 · **Feeds Review-2 deliverable:** D5 (Presentation) + D3 (visual SQL over the views)

## The Plan (as decided before implementation)

### Stack (user decision: replace the earlier React+TS+Vite plan)
**Jinja2 server-rendered + HTMX + Alpine.js + Tailwind/DaisyUI + Chart.js**, all served by the existing FastAPI container — Python-only codebase, no node/npm/build step, and appearance changes are centralized: DaisyUI themes switch with one `data-theme` attribute; deeper restyling lives in one `app.css`; layout in one `base.html`.

### Architecture
- Cookie sessions (admin token or app api-key, validated server-side per request) — same-origin serving means cookies flow to HTMX, fetch, and EventSource (SSE) alike
- JSON API (M5) untouched and reused by charts/Playground; new `webui` router adds pages + HTML fragments
- All frontend libraries **vendored** into `static/vendor/` (htmx, sse ext, alpine, chart.js, tailwind, daisyUI ≈ 3.6 MB) so the demo machine works fully **offline**
- Monitor endpoints generalized (`require_any`): app sessions see RLS-scoped data, admin sessions see everything; SSE now requires a session

### Pages
Login · Overview (stat cards, 2 charts, lag table, recent audit, maintenance buttons) · **Message Browser** (live table flipping row status via SSE + filters) · **Playground** (produce panel → location chip; consumer panel → claimed messages with Ack/Nack; embedded live table — the send→stored→read demo) · Topics · Groups · Audit · DLQ (+ requeue) · Admin (users/apps/access/config with api-key reveal) · **SQL Console** (server-enforced SELECT-only).

## Planning Decisions (Q&A)

| Question | Options presented | Chosen | Rationale |
|---|---|---|---|
| Frontend approach (replacing the earlier React+TS plan)? | Jinja + HTMX server-rendered (rec.) / Vanilla HTML/CSS/JS | Jinja + HTMX | Team stays in Python, no node/npm/build step, SSE support built in; hand-written vanilla DOM across 9 pages would work against the maintainability requirement |
| Visual layer? | Tailwind + DaisyUI (rec.) / Tailwind only, hand-styled | Tailwind + DaisyUI | Polished minimalist components out of the box; 30+ themes switchable via one `data-theme` attribute — directly satisfies the "easily change appearance later" requirement |

## What Was Implemented

All of the above: 11 templates + 12 fragments, ~30 new routes (9 pages, 5 fragments, 15 form actions + login/logout + SQL runner), ~200 lines of client JS (charts + Alpine Playground component), vendored libs, cookie auth.

### Issues found & fixed during implementation
1. **Direct dependency call got raw `Header` sentinel** — `session()` invoked `require_any(request)` directly, so the `authorization` parameter held the `Header(default=None)` object instead of `None` → `AttributeError` on every page/fragment. Fix: pass `None` explicitly when calling outside FastAPI's dependency injection.
2. **Jinja parsed Alpine interpolation** — `{{ pResult?.topic_id }}` in the Playground template was Jinja syntax (`?.` invalid) → TemplateSyntaxError. Fix: Alpine `x-text` with a JS template literal.
3. **Fragment helper double-appended `.html`** → `TemplateNotFound: _messages_table.html.html`. Callers already pass extensions; helper no longer appends.
4. **SSE generator leaked `StopAsyncIteration`** (RuntimeError when the notification stream ends) — now caught and the stream closes cleanly.
5. **Test hygiene** — the shared httpx client persisted login cookies across tests, polluting "unauthenticated" assertions; those now use clean clients. Also `_require_admin_ctx` now returns 401 (no session) vs 403 (non-admin session) correctly.

### Verification evidence

**`tests/py/test_m6.py` — 10/10, full suite 20/20** (M5+M6 in the api container):
- Login: admin + app flows set the right cookie; invalid token/key → 401
- All 9 pages redirect (303) without a session; render 200 with admin; app sessions get 403 on Admin/SQL
- Fragments render HTML with both session types; 401 clean-client
- **Cookie auth on the JSON API**: `/api/dashboard` works with app AND admin cookies; `/api/admin/users` with admin cookie
- **Playground flow entirely over cookies**: produce → consume → ack → delivered row visible in the messages fragment
- Web SQL console: SELECT renders table, DELETE → 400, no session → 401
- `/api/events` requires a session (401 clean client)

**Rendered-HTML marker check**: theme attribute, both canvases, SSE wiring (`sse-connect`, `sse:conduit_events` trigger), Playground Alpine component, SQL editor, login page — all present.

**Regressions**: fresh clean volume → `smoke_m2` ✓ `smoke_m3` ✓ + 20/20 pytest; fresh seeded volume → `smoke_m4` ✓. No `db/` files changed in this milestone.

## How to run / demo

```powershell
$env:CONDUIT_SEED='true'; docker compose down -v; docker compose up -d; Remove-Item Env:\CONDUIT_SEED
```

Open **http://localhost:8000** → sign in with the admin token (`conduit-admin-token`).

**The walkthrough demo** (send → stored → read):
1. Admin → Applications → reveal an app api key (e.g. `fraud-detector`, owned by maya.ops who holds grants + groups) → copy
2. Logout → sign in with that **api key** → Playground
3. Produce panel: pick topic, paste payload, **Send** → green chip shows *stored at topic/partition/offset* — the live table below flashes the new **pending** row as the SSE event lands
4. Consumer panel: pick group + topic, **Consume** → claimed messages appear with payloads; row flips **claimed** (amber)
5. **Ack** → row flips **delivered** (green). Try **Nack** 3× to watch a message die into the DLQ page, then requeue it from there.

## Next

Milestone 7 — `demos/` scenario scripts (Python on the SDK): basic flow, SKIP LOCKED race, idempotency, poison→DLQ→requeue, crash recovery, security denials, exactly-once.
