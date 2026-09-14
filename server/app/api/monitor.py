from fastapi import APIRouter, Depends

from .. import db
from ..auth import require_any, require_app

router = APIRouter(prefix="/api", tags=["monitor"])


def _pools(ctx):
    if ctx["mode"] == "admin":
        return db.admin_pool, None
    return db.app_pool, ctx["owner_user_id"]


@router.get("/me")
async def me(app=Depends(require_app)):
    topics = await db.run(
        "SELECT t.topic_name, a.access_type FROM access a "
        "JOIN topic t ON t.topic_id = a.topic_id "
        "WHERE a.user_id = %s::bigint ORDER BY t.topic_name",
        (app["owner_user_id"],),
    )
    return {"app": app, "accessible_topics": topics}


@router.get("/my-groups")
async def my_groups(app=Depends(require_app)):
    return await db.run(
        "SELECT cg.group_name, cg.status, cg.max_delivery_attempts, "
        "(SELECT array_agg(t.topic_name ORDER BY t.topic_name) FROM group_subscription gs "
        " JOIN topic t ON t.topic_id = gs.topic_id WHERE gs.group_id = cg.group_id) AS subscriptions "
        "FROM consumer_group cg WHERE cg.created_by = %s::bigint ORDER BY cg.group_name",
        (app["owner_user_id"],),
    )


@router.get("/dashboard")
async def dashboard(ctx=Depends(require_any)):
    pool, _ = _pools(ctx)
    return await db.run("SELECT * FROM v_topic_stats ORDER BY topic_name", pool=pool)


@router.get("/lag")
async def lag(ctx=Depends(require_any)):
    pool, _ = _pools(ctx)
    return await db.run("SELECT * FROM v_consumer_lag", pool=pool)


@router.get("/throughput")
async def throughput(minutes: int = 120, ctx=Depends(require_any)):
    pool, _ = _pools(ctx)
    return await db.run("SELECT * FROM v_throughput_by_minute ORDER BY topic_name, minute_ts", pool=pool)


@router.get("/messages")
async def messages(
    topic: str,
    status: str | None = None,
    limit: int = 100,
    ctx=Depends(require_any),
):
    pool, user_id = _pools(ctx)
    sql = (
        "SELECT m.created_at, t.topic_name, pt.partition_number, m.msg_offset, m.msg_key, "
        "m.payload, m.status, m.attempts, m.producer_app_id "
        "FROM message m JOIN topic t ON t.topic_id = m.topic_id "
        "JOIN partition pt ON pt.partition_id = m.partition_id "
        "WHERE t.topic_name = %s::text"
    )
    params = [topic]
    if status:
        sql += " AND m.status = %s::text"
        params.append(status)
    sql += " ORDER BY m.created_at DESC, m.msg_offset DESC LIMIT %s"
    params.append(min(max(limit, 1), 500))
    return await db.run(sql, params, pool=pool, user_id=user_id)
