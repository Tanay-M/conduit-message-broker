from fastapi import APIRouter, Depends
from pydantic import BaseModel
from psycopg.types.json import Json

from .. import db
from ..auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class RegisterUserReq(BaseModel):
    username: str
    email: str
    role: str


class RegisterAppReq(BaseModel):
    app_name: str
    owner_username: str
    app_type: str


class AppStatusReq(BaseModel):
    status: str


class CreateTopicReq(BaseModel):
    name: str
    partitions: int
    owner_username: str
    description: str | None = None
    schema: dict | None = None


class TopicConfigReq(BaseModel):
    retention_days: int | None = None
    max_message_bytes: int | None = None
    status: str | None = None


class CreateGroupReq(BaseModel):
    name: str
    created_by_username: str
    max_delivery_attempts: int = 3


class SubscribeReq(BaseModel):
    topic: str


class GrantReq(BaseModel):
    username: str
    topic: str
    access_type: str
    granted_by: str


class RevokeReq(BaseModel):
    username: str
    topic: str
    access_type: str


class PublishSchemaReq(BaseModel):
    topic: str
    definition: dict


class RequeueReq(BaseModel):
    producer_app_name: str
    target_topic: str | None = None


class ConfigReq(BaseModel):
    key: str
    value: str
    description: str | None = None
    updated_by: str | None = None


class PurgeReq(BaseModel):
    topic: str | None = None


class CreatePartitionReq(BaseModel):
    month: str


class DropPartitionsReq(BaseModel):
    keep_days: int = 90


@router.post("/users")
async def register_user(req: RegisterUserReq):
    row = await db.run(
        "SELECT register_user(%s, %s, %s) AS user_id",
        (req.username, req.email, req.role),
        pool=db.admin_pool,
        one=True,
    )
    return {"user_id": row["user_id"]}


@router.get("/users")
async def list_users():
    return await db.run(
        "SELECT u.user_id, u.username, u.email, u.status, r.role_name, u.created_at "
        "FROM app_user u JOIN role r ON r.role_id = u.role_id ORDER BY u.user_id",
        pool=db.admin_pool,
    )


@router.post("/users/{username}/suspend")
async def suspend_user(username: str):
    await db.run("SELECT suspend_user(%s)", (username,), pool=db.admin_pool)
    return {"ok": True}


@router.post("/users/{username}/activate")
async def activate_user(username: str):
    await db.run("SELECT activate_user(%s)", (username,), pool=db.admin_pool)
    return {"ok": True}


@router.post("/apps")
async def register_app(req: RegisterAppReq):
    row = await db.run(
        "SELECT app_id, api_key FROM register_application(%s, %s, %s)",
        (req.app_name, req.owner_username, req.app_type),
        pool=db.admin_pool,
        one=True,
    )
    return dict(row)


@router.get("/apps")
async def list_apps():
    return await db.run(
        "SELECT a.app_id, a.app_name, a.app_type, a.status, a.created_at, u.username AS owner "
        "FROM application a JOIN app_user u ON u.user_id = a.owner_user_id ORDER BY a.app_id",
        pool=db.admin_pool,
    )


@router.post("/apps/{app_name}/status")
async def set_app_status(app_name: str, req: AppStatusReq):
    await db.run(
        "SELECT set_application_status(%s, %s)", (app_name, req.status), pool=db.admin_pool
    )
    return {"ok": True}


@router.post("/topics")
async def create_topic(req: CreateTopicReq):
    row = await db.run(
        "SELECT create_topic(%s::text, %s::text, %s::int, %s::jsonb, %s::text) AS topic_id",
        (
            req.name,
            req.description,
            req.partitions,
            Json(req.schema) if req.schema is not None else None,
            req.owner_username,
        ),
        pool=db.admin_pool,
        one=True,
    )
    return {"topic_id": row["topic_id"]}


@router.get("/topics")
async def list_topics():
    return await db.run(
        "SELECT t.topic_id, t.topic_name, t.description, t.status, t.retention_days, "
        "t.max_message_bytes, t.created_at, u.username AS created_by, "
        "(SELECT count(*) FROM partition p WHERE p.topic_id = t.topic_id) AS partition_count "
        "FROM topic t JOIN app_user u ON u.user_id = t.created_by ORDER BY t.topic_id",
        pool=db.admin_pool,
    )


@router.patch("/topics/{name}/config")
async def update_topic_config(name: str, req: TopicConfigReq):
    await db.run(
        "SELECT update_topic_config(%s::text, %s::int, %s::int, %s::text)",
        (name, req.retention_days, req.max_message_bytes, req.status),
        pool=db.admin_pool,
    )
    return {"ok": True}


@router.post("/topics/{name}/archive")
async def archive_topic(name: str):
    await db.run("SELECT archive_topic(%s)", (name,), pool=db.admin_pool)
    return {"ok": True}


@router.post("/groups")
async def create_group(req: CreateGroupReq):
    row = await db.run(
        "SELECT create_group(%s::text, %s::text, %s::int) AS group_id",
        (req.name, req.created_by_username, req.max_delivery_attempts),
        pool=db.admin_pool,
        one=True,
    )
    return {"group_id": row["group_id"]}


@router.get("/groups")
async def list_groups():
    return await db.run(
        "SELECT cg.group_id, cg.group_name, cg.status, cg.max_delivery_attempts, cg.created_at, "
        "u.username AS created_by, "
        "(SELECT array_agg(t.topic_name ORDER BY t.topic_name) FROM group_subscription gs "
        " JOIN topic t ON t.topic_id = gs.topic_id WHERE gs.group_id = cg.group_id) AS subscriptions "
        "FROM consumer_group cg JOIN app_user u ON u.user_id = cg.created_by ORDER BY cg.group_id",
        pool=db.admin_pool,
    )


@router.post("/groups/{name}/subscribe")
async def subscribe_group(name: str, req: SubscribeReq):
    row = await db.run(
        "SELECT subscribe_group(%s, %s) AS partitions_wired",
        (name, req.topic),
        pool=db.admin_pool,
        one=True,
    )
    return {"partitions_wired": row["partitions_wired"]}


@router.post("/groups/{name}/pause")
async def pause_group(name: str):
    await db.run("SELECT pause_group(%s)", (name,), pool=db.admin_pool)
    return {"ok": True}


@router.post("/groups/{name}/activate")
async def activate_group(name: str):
    await db.run("SELECT activate_group(%s)", (name,), pool=db.admin_pool)
    return {"ok": True}


@router.get("/access")
async def list_access(topic: str | None = None):
    return await db.run(
        "SELECT a.access_id, u.username, t.topic_name, a.access_type, a.granted_at "
        "FROM access a JOIN app_user u ON u.user_id = a.user_id "
        "JOIN topic t ON t.topic_id = a.topic_id "
        "WHERE (%s::text IS NULL OR t.topic_name = %s) ORDER BY a.access_id",
        (topic, topic),
        pool=db.admin_pool,
    )


@router.post("/access/grant")
async def grant_access(req: GrantReq):
    row = await db.run(
        "SELECT grant_access(%s, %s, %s, %s) AS access_id",
        (req.username, req.topic, req.access_type, req.granted_by),
        pool=db.admin_pool,
        one=True,
    )
    return {"access_id": row["access_id"]}


@router.post("/access/revoke")
async def revoke_access(req: RevokeReq):
    row = await db.run(
        "SELECT revoke_access(%s, %s, %s) AS revoked",
        (req.username, req.topic, req.access_type),
        pool=db.admin_pool,
        one=True,
    )
    return {"revoked": row["revoked"]}


@router.get("/schemas")
async def list_schemas(topic: str | None = None):
    return await db.run(
        "SELECT sv.schema_id, t.topic_name, sv.version, sv.status, sv.definition, sv.created_at "
        "FROM schema_version sv JOIN topic t ON t.topic_id = sv.topic_id "
        "WHERE (%s::text IS NULL OR t.topic_name = %s) ORDER BY t.topic_name, sv.version",
        (topic, topic),
        pool=db.admin_pool,
    )


@router.post("/schemas/publish")
async def publish_schema(req: PublishSchemaReq):
    row = await db.run(
        "SELECT publish_schema_version(%s::text, %s::jsonb) AS version",
        (req.topic, Json(req.definition)),
        pool=db.admin_pool,
        one=True,
    )
    return {"version": row["version"]}


@router.get("/dlq")
async def list_dlq():
    return await db.run(
        "SELECT d.dlq_id, t.topic_name, d.original_offset, d.msg_key, d.payload, "
        "d.failure_reason, d.attempts, d.status, d.dead_at "
        "FROM dead_letter_message d JOIN topic t ON t.topic_id = d.original_topic_id "
        "ORDER BY d.dlq_id DESC",
        pool=db.admin_pool,
    )


@router.post("/dlq/{dlq_id}/requeue")
async def requeue_dlq(dlq_id: int, req: RequeueReq):
    row = await db.run(
        "SELECT * FROM requeue_dlq(%s::bigint, "
        "(SELECT a.app_id FROM application a WHERE a.app_name = %s::text), %s::text)",
        (dlq_id, req.producer_app_name, req.target_topic),
        pool=db.admin_pool,
        one=True,
    )
    return {
        "dlq_id": row["dlq_id"],
        "requeued": row["requeued"],
        "topic_id": row["loc_topic_id"],
        "partition_id": row["loc_partition_id"],
        "msg_offset": row["loc_msg_offset"],
    }


@router.get("/audit")
async def audit(event_type: str | None = None, limit: int = 100):
    return await db.run(
        "SELECT * FROM v_audit_recent WHERE (%s::text IS NULL OR event_type = %s) "
        "ORDER BY log_id DESC LIMIT %s",
        (event_type, event_type, min(max(limit, 1), 500)),
        pool=db.admin_pool,
    )


@router.get("/config")
async def list_config():
    return await db.run(
        "SELECT * FROM broker_config ORDER BY config_key", pool=db.admin_pool
    )


@router.post("/config")
async def set_config(req: ConfigReq):
    await db.run(
        "SELECT update_broker_config(%s, %s, %s, %s)",
        (req.key, req.value, req.description, req.updated_by),
        pool=db.admin_pool,
    )
    return {"ok": True}


@router.post("/maintenance/purge")
async def purge(req: PurgeReq):
    row = await db.run(
        "SELECT purge_retention(%s::text) AS purged", (req.topic,), pool=db.admin_pool, one=True
    )
    return {"purged": row["purged"]}


@router.post("/maintenance/reap")
async def reap():
    row = await db.run(
        "SELECT * FROM reap_expired_claims()", pool=db.admin_pool, one=True
    )
    return {"requeued": row["requeued"], "dead": row["dead"]}


@router.post("/maintenance/refresh-dashboard")
async def refresh_dashboard():
    await db.run("SELECT refresh_dashboard()", pool=db.admin_pool)
    return {"ok": True}


@router.post("/maintenance/create-partition")
async def create_partition(req: CreatePartitionReq):
    row = await db.run(
        "SELECT create_monthly_partition(%s::date) AS partition_name",
        (req.month,),
        pool=db.admin_pool,
        one=True,
    )
    return {"partition": row["partition_name"]}


@router.post("/maintenance/drop-old-partitions")
async def drop_old_partitions(req: DropPartitionsReq):
    row = await db.run(
        "SELECT drop_old_partitions(%s::int) AS dropped",
        (req.keep_days,),
        pool=db.admin_pool,
        one=True,
    )
    return {"dropped": row["dropped"]}
