from pathlib import Path

import psycopg
from conduit.errors import ConduitError, from_psycopg
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from psycopg.types.json import Json

from .. import db
from ..api.sql import _sanitize
from ..auth import SESSION_COOKIE, _extract_token, require_any
from ..config import settings

router = APIRouter(tags=["webui"])

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

TOPICS_SQL = (
    "SELECT t.topic_id, t.topic_name, t.description, t.status, t.retention_days, "
    "t.max_message_bytes, t.created_at, u.username AS created_by, "
    "(SELECT count(*) FROM partition p WHERE p.topic_id = t.topic_id) AS partition_count "
    "FROM topic t JOIN app_user u ON u.user_id = t.created_by ORDER BY t.topic_id"
)
GROUPS_SQL = (
    "SELECT cg.group_id, cg.group_name, cg.status, cg.max_delivery_attempts, cg.created_at, "
    "u.username AS created_by, "
    "(SELECT array_agg(t.topic_name ORDER BY t.topic_name) FROM group_subscription gs "
    " JOIN topic t ON t.topic_id = gs.topic_id WHERE gs.group_id = cg.group_id) AS subscriptions "
    "FROM consumer_group cg JOIN app_user u ON u.user_id = cg.created_by ORDER BY cg.group_id"
)
USERS_SQL = (
    "SELECT u.user_id, u.username, u.email, u.status, r.role_name, u.created_at "
    "FROM app_user u JOIN role r ON r.role_id = u.role_id ORDER BY u.user_id"
)
APPS_SQL = (
    "SELECT a.app_id, a.app_name, a.app_type, a.status, a.api_key, a.created_at, "
    "u.username AS owner FROM application a JOIN app_user u ON u.user_id = a.owner_user_id "
    "ORDER BY a.app_id"
)
ACCESS_SQL = (
    "SELECT a.access_id, u.username, t.topic_name, a.access_type, a.granted_at "
    "FROM access a JOIN app_user u ON u.user_id = a.user_id "
    "JOIN topic t ON t.topic_id = a.topic_id ORDER BY a.access_id"
)
CONFIG_SQL = "SELECT * FROM broker_config ORDER BY config_key"
DLQ_SQL = (
    "SELECT d.dlq_id, t.topic_name, d.original_offset, d.msg_key, d.payload, "
    "d.failure_reason, d.attempts, d.status, d.dead_at "
    "FROM dead_letter_message d JOIN topic t ON t.topic_id = d.original_topic_id "
    "ORDER BY d.dlq_id DESC"
)
AUDIT_SQL = (
    "SELECT * FROM v_audit_recent WHERE (%s::text IS NULL OR event_type = %s) "
    "ORDER BY log_id DESC LIMIT %s"
)
MESSAGES_SQL = (
    "SELECT m.created_at, t.topic_name, pt.partition_number, m.msg_offset, m.msg_key, "
    "m.payload, m.status, m.attempts, m.producer_app_id "
    "FROM message m JOIN topic t ON t.topic_id = m.topic_id "
    "JOIN partition pt ON pt.partition_id = m.partition_id "
    "WHERE t.topic_name = %s::text"
)
LAG_SQL = "SELECT * FROM v_consumer_lag"
STATS_SQL = "SELECT * FROM v_topic_stats ORDER BY topic_name"


async def session(request: Request) -> dict | None:
    token = _extract_token(request, None)
    if not token:
        return None
    try:
        return await require_any(request, None)
    except (HTTPException, ConduitError):
        return None


async def _q(ctx, sql, params=()):
    if ctx["mode"] == "admin":
        return await db.run(sql, params, pool=db.admin_pool)
    return await db.run(sql, params, pool=db.app_pool, user_id=ctx["owner_user_id"])


def _require_admin_ctx(ctx):
    if ctx is None:
        raise HTTPException(status_code=401, detail="admin session required")
    if ctx["mode"] != "admin":
        raise HTTPException(status_code=403, detail="admin session required")
    return ctx


def _page(request, ctx, name, active, **extra):
    return templates.TemplateResponse(
        request, f"pages/{name}.html", {"ctx": ctx, "active": active, **extra}
    )


def _fragment(request, name, **extra):
    return templates.TemplateResponse(request, f"fragments/{name}", extra)


@router.get("/web/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/web/login")
async def login(request: Request, mode: str = Form(...), token: str = Form(...)):
    token = token.strip()
    if mode == "admin":
        if token != settings.admin_token:
            return templates.TemplateResponse(
                request, "login.html", {"error": "invalid admin token"}, status_code=401
            )
    else:
        try:
            import uuid as _uuid

            _uuid.UUID(token)
            await db.run("SELECT * FROM fn_auth_app(%s::uuid)", (token,), one=True)
        except (ValueError, ConduitError, psycopg.Error):
            return templates.TemplateResponse(
                request, "login.html", {"error": "invalid api key"}, status_code=401
            )
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return resp


@router.get("/web/logout")
async def logout():
    resp = RedirectResponse("/web/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@router.get("/")
async def overview(request: Request):
    ctx = await session(request)
    if ctx is None:
        return RedirectResponse("/web/login", status_code=303)
    stats = await _q(ctx, STATS_SQL)
    lag = await _q(ctx, LAG_SQL)
    recent = await db.run(AUDIT_SQL, (None, None, 8), pool=db.admin_pool)
    return _page(request, ctx, "overview", "overview", stats=stats, lag=lag, recent=recent)


async def _accessible_topics(ctx):
    return await _q(
        ctx,
        "SELECT DISTINCT t.topic_name FROM topic t "
        "LEFT JOIN access a ON a.topic_id = t.topic_id AND a.user_id = %s::bigint "
        "WHERE (%s::boolean OR a.access_id IS NOT NULL) ORDER BY t.topic_name",
        (ctx.get("owner_user_id"), ctx["mode"] == "admin"),
    )


async def _messages_rows(ctx, topic, status=None):
    sql = MESSAGES_SQL
    params = [topic]
    if status:
        sql += " AND m.status = %s::text"
        params.append(status)
    sql += " ORDER BY m.created_at DESC, m.msg_offset DESC LIMIT 100"
    return await _q(ctx, sql, params)


@router.get("/messages")
async def browser(request: Request, topic: str | None = None, status: str | None = None):
    ctx = await session(request)
    if ctx is None:
        return RedirectResponse("/web/login", status_code=303)
    topics = await _accessible_topics(ctx)
    sel_topic = topic or (topics[0]["topic_name"] if topics else None)
    rows = await _messages_rows(ctx, sel_topic, status) if sel_topic else []
    return _page(
        request, ctx, "browser", "messages", topics=topics, topic=sel_topic, status=status, rows=rows
    )


@router.get("/playground")
async def playground(request: Request):
    ctx = await session(request)
    if ctx is None:
        return RedirectResponse("/web/login", status_code=303)
    topics = await _accessible_topics(ctx)
    sel_topic = topics[0]["topic_name"] if topics else None
    rows = await _messages_rows(ctx, sel_topic) if sel_topic else []
    return _page(request, ctx, "playground", "playground", topics=topics, topic=sel_topic, rows=rows)


@router.get("/topics")
async def topics_page(request: Request):
    ctx = await session(request)
    if ctx is None:
        return RedirectResponse("/web/login", status_code=303)
    rows = await db.run(TOPICS_SQL, pool=db.admin_pool)
    return _page(request, ctx, "topics", "topics", topics=rows)


@router.get("/groups")
async def groups_page(request: Request):
    ctx = await session(request)
    if ctx is None:
        return RedirectResponse("/web/login", status_code=303)
    rows = await db.run(GROUPS_SQL, pool=db.admin_pool)
    return _page(request, ctx, "groups", "groups", groups=rows)


@router.get("/audit")
async def audit_page(request: Request, event_type: str | None = None):
    ctx = await session(request)
    if ctx is None:
        return RedirectResponse("/web/login", status_code=303)
    rows = await db.run(AUDIT_SQL, (event_type, event_type, 100), pool=db.admin_pool)
    return _page(request, ctx, "audit", "audit", audit=rows, event_type=event_type)


@router.get("/dlq")
async def dlq_page(request: Request):
    ctx = await session(request)
    if ctx is None:
        return RedirectResponse("/web/login", status_code=303)
    rows = await db.run(DLQ_SQL, pool=db.admin_pool)
    apps = await db.run(APPS_SQL, pool=db.admin_pool)
    return _page(request, ctx, "dlq", "dlq", dlq=rows, apps=apps)


@router.get("/admin")
async def admin_page(request: Request):
    ctx = await session(request)
    if ctx is None:
        return RedirectResponse("/web/login", status_code=303)
    _require_admin_ctx(ctx)
    return _page(
        request,
        ctx,
        "admin",
        "admin",
        users=await db.run(USERS_SQL, pool=db.admin_pool),
        apps=await db.run(APPS_SQL, pool=db.admin_pool),
        grants=await db.run(ACCESS_SQL, pool=db.admin_pool),
        config=await db.run(CONFIG_SQL, pool=db.admin_pool),
    )


@router.get("/sql")
async def sql_page(request: Request):
    ctx = await session(request)
    if ctx is None:
        return RedirectResponse("/web/login", status_code=303)
    _require_admin_ctx(ctx)
    return _page(request, ctx, "sql", "sql")


@router.get("/fragments/messages")
async def messages_fragment(request: Request, topic: str, status: str | None = None):
    ctx = await session(request)
    if ctx is None:
        raise HTTPException(status_code=401)
    sql = MESSAGES_SQL
    params = [topic]
    if status:
        sql += " AND m.status = %s::text"
        params.append(status)
    sql += " ORDER BY m.created_at DESC, m.msg_offset DESC LIMIT 100"
    rows = await _q(ctx, sql, params)
    return _fragment(request, "_messages_table.html", rows=rows, topic=topic, status=status)


@router.get("/fragments/stats")
async def stats_fragment(request: Request):
    ctx = await session(request)
    if ctx is None:
        raise HTTPException(status_code=401)
    rows = await _q(ctx, STATS_SQL)
    return _fragment(request, "_stats_cards.html", stats=rows)


@router.get("/fragments/lag")
async def lag_fragment(request: Request):
    ctx = await session(request)
    if ctx is None:
        raise HTTPException(status_code=401)
    rows = await _q(ctx, LAG_SQL)
    return _fragment(request, "_lag_table.html", lag=rows)


@router.get("/fragments/audit")
async def audit_fragment(request: Request, event_type: str | None = None):
    ctx = await session(request)
    if ctx is None:
        raise HTTPException(status_code=401)
    rows = await db.run(AUDIT_SQL, (event_type, event_type, 100), pool=db.admin_pool)
    return _fragment(request, "_audit_table.html", audit=rows, event_type=event_type)


@router.get("/fragments/dlq")
async def dlq_fragment(request: Request):
    ctx = await session(request)
    if ctx is None:
        raise HTTPException(status_code=401)
    rows = await db.run(DLQ_SQL, pool=db.admin_pool)
    return _fragment(request, "_dlq_table.html", dlq=rows)


async def _admin_action(request):
    ctx = await session(request)
    _require_admin_ctx(ctx)
    return ctx


@router.post("/web/topics")
async def create_topic(
    request: Request,
    name: str = Form(...),
    partitions: int = Form(2),
    owner_username: str = Form(...),
    description: str = Form(""),
    schema_json: str = Form(""),
):
    await _admin_action(request)
    definition = None
    if schema_json.strip():
        try:
            import json

            definition = Json(json.loads(schema_json))
        except ValueError:
            raise HTTPException(status_code=422, detail="schema is not valid JSON")
    try:
        await db.run(
            "SELECT create_topic(%s::text, %s::text, %s::int, %s::jsonb, %s::text)",
            (name, description or None, partitions, definition, owner_username),
            pool=db.admin_pool,
        )
    except psycopg.Error as e:
        raise from_psycopg(e) from e
    rows = await db.run(TOPICS_SQL, pool=db.admin_pool)
    return _fragment(request, "_topics_table.html", topics=rows)


@router.post("/web/topics/{name}/archive")
async def archive_topic(request: Request, name: str):
    await _admin_action(request)
    await db.run("SELECT archive_topic(%s::text)", (name,), pool=db.admin_pool)
    rows = await db.run(TOPICS_SQL, pool=db.admin_pool)
    return _fragment(request, "_topics_table.html", topics=rows)


@router.post("/web/groups")
async def create_group(
    request: Request,
    name: str = Form(...),
    created_by_username: str = Form(...),
    max_delivery_attempts: int = Form(3),
):
    await _admin_action(request)
    try:
        await db.run(
            "SELECT create_group(%s::text, %s::text, %s::int)",
            (name, created_by_username, max_delivery_attempts),
            pool=db.admin_pool,
        )
    except psycopg.Error as e:
        raise from_psycopg(e) from e
    rows = await db.run(GROUPS_SQL, pool=db.admin_pool)
    return _fragment(request, "_groups_table.html", groups=rows)


@router.post("/web/groups/subscribe")
async def subscribe_group(request: Request, group: str = Form(...), topic: str = Form(...)):
    await _admin_action(request)
    try:
        await db.run(
            "SELECT subscribe_group(%s::text, %s::text)", (group, topic), pool=db.admin_pool
        )
    except psycopg.Error as e:
        raise from_psycopg(e) from e
    rows = await db.run(GROUPS_SQL, pool=db.admin_pool)
    return _fragment(request, "_groups_table.html", groups=rows)


@router.post("/web/groups/{name}/pause")
async def pause_group(request: Request, name: str):
    await _admin_action(request)
    await db.run("SELECT pause_group(%s::text)", (name,), pool=db.admin_pool)
    rows = await db.run(GROUPS_SQL, pool=db.admin_pool)
    return _fragment(request, "_groups_table.html", groups=rows)


@router.post("/web/groups/{name}/activate")
async def activate_group(request: Request, name: str):
    await _admin_action(request)
    await db.run("SELECT activate_group(%s::text)", (name,), pool=db.admin_pool)
    rows = await db.run(GROUPS_SQL, pool=db.admin_pool)
    return _fragment(request, "_groups_table.html", groups=rows)


@router.post("/web/users")
async def register_user(
    request: Request, username: str = Form(...), email: str = Form(...), role: str = Form(...)
):
    await _admin_action(request)
    try:
        await db.run(
            "SELECT register_user(%s::text, %s::text, %s::text)",
            (username, email, role),
            pool=db.admin_pool,
        )
    except psycopg.Error as e:
        raise from_psycopg(e) from e
    rows = await db.run(USERS_SQL, pool=db.admin_pool)
    return _fragment(request, "_admin_users.html", users=rows)


@router.post("/web/users/{username}/suspend")
async def suspend_user(request: Request, username: str):
    await _admin_action(request)
    await db.run("SELECT suspend_user(%s::text)", (username,), pool=db.admin_pool)
    rows = await db.run(USERS_SQL, pool=db.admin_pool)
    return _fragment(request, "_admin_users.html", users=rows)


@router.post("/web/users/{username}/activate")
async def activate_user(request: Request, username: str):
    await _admin_action(request)
    await db.run("SELECT activate_user(%s::text)", (username,), pool=db.admin_pool)
    rows = await db.run(USERS_SQL, pool=db.admin_pool)
    return _fragment(request, "_admin_users.html", users=rows)


@router.post("/web/apps")
async def register_app(
    request: Request,
    app_name: str = Form(...),
    owner_username: str = Form(...),
    app_type: str = Form("both"),
):
    await _admin_action(request)
    try:
        await db.run(
            "SELECT register_application(%s::text, %s::text, %s::text)",
            (app_name, owner_username, app_type),
            pool=db.admin_pool,
        )
    except psycopg.Error as e:
        raise from_psycopg(e) from e
    rows = await db.run(APPS_SQL, pool=db.admin_pool)
    return _fragment(request, "_admin_apps.html", apps=rows)


@router.post("/web/access/grant")
async def grant_access(
    request: Request,
    username: str = Form(...),
    topic: str = Form(...),
    access_type: str = Form(...),
):
    await _admin_action(request)
    await db.run(
        "SELECT grant_access(%s::text, %s::text, %s::text, %s::text)",
        (username, topic, access_type, "admin"),
        pool=db.admin_pool,
    )
    rows = await db.run(ACCESS_SQL, pool=db.admin_pool)
    return _fragment(request, "_admin_access.html", grants=rows)


@router.post("/web/access/revoke")
async def revoke_access(
    request: Request, username: str = Form(...), topic: str = Form(...), access_type: str = Form(...)
):
    await _admin_action(request)
    await db.run(
        "SELECT revoke_access(%s::text, %s::text, %s::text)",
        (username, topic, access_type),
        pool=db.admin_pool,
    )
    rows = await db.run(ACCESS_SQL, pool=db.admin_pool)
    return _fragment(request, "_admin_access.html", grants=rows)


@router.post("/web/config")
async def set_config(
    request: Request, key: str = Form(...), value: str = Form(...), description: str = Form("")
):
    await _admin_action(request)
    await db.run(
        "SELECT update_broker_config(%s::text, %s::text, %s::text, %s::text)",
        (key, value, description or None, None),
        pool=db.admin_pool,
    )
    rows = await db.run(CONFIG_SQL, pool=db.admin_pool)
    return _fragment(request, "_admin_config.html", config=rows)


@router.post("/web/dlq/{dlq_id}/requeue")
async def requeue_dlq(request: Request, dlq_id: int, producer_app_name: str = Form(...)):
    await _admin_action(request)
    try:
        await db.run(
            "SELECT * FROM requeue_dlq(%s::bigint, "
            "(SELECT a.app_id FROM application a WHERE a.app_name = %s::text), NULL)",
            (dlq_id, producer_app_name),
            pool=db.admin_pool,
        )
    except psycopg.Error as e:
        raise from_psycopg(e) from e
    rows = await db.run(DLQ_SQL, pool=db.admin_pool)
    return _fragment(request, "_dlq_table.html", dlq=rows, apps=await db.run(APPS_SQL, pool=db.admin_pool))


@router.post("/web/maintenance/{action}")
async def maintenance(request: Request, action: str):
    await _admin_action(request)
    if action == "purge":
        await db.run("SELECT purge_retention(NULL)", pool=db.admin_pool)
    elif action == "reap":
        await db.run("SELECT reap_expired_claims()", pool=db.admin_pool)
    elif action == "refresh":
        await db.run("SELECT refresh_dashboard()", pool=db.admin_pool)
    else:
        raise HTTPException(status_code=404)
    return HTMLResponse('<span class="text-success text-sm">done</span>')


@router.post("/web/sql")
async def sql_run(request: Request, query: str = Form(...)):
    await _admin_action(request)
    stmt = _sanitize(query)
    async with db.admin_pool.connection() as conn:
        try:
            await conn.execute("BEGIN TRANSACTION READ ONLY")
            try:
                await conn.execute("SET LOCAL statement_timeout = '5s'")
                cur = await conn.execute(stmt)
                columns = [d.name for d in cur.description] if cur.description else []
                rows = await cur.fetchmany(500) if cur.description else []
            finally:
                await conn.execute("ROLLBACK")
        except psycopg.errors.QueryCanceled as e:
            raise HTTPException(status_code=408, detail="query exceeded the 5 second timeout") from e
        except psycopg.Error as e:
            raise from_psycopg(e) from e
    return _fragment(request, "_sql_results.html", columns=columns, rows=rows)
