from fastapi import APIRouter, Depends
from pydantic import BaseModel
from psycopg.types.json import Json

from .. import db
from ..auth import require_app

router = APIRouter(prefix="/api", tags=["broker"])


class ProduceReq(BaseModel):
    topic: str
    payload: dict
    seq: int
    key: str | None = None


class ProduceBatchReq(BaseModel):
    topic: str
    messages: list[dict]
    seq_start: int = 1


class ConsumeReq(BaseModel):
    group: str
    topic: str
    batch: int = 10
    visibility_timeout_s: int = 30


class LocationsReq(BaseModel):
    group: str
    locations: list[dict]


class NackReq(LocationsReq):
    reason: str = "rejected by consumer"


@router.post("/produce")
async def produce(req: ProduceReq, app=Depends(require_app)):
    row = await db.run(
        "SELECT * FROM produce(%s::text, %s::text, %s::jsonb, %s::bigint, %s::bigint)",
        (req.topic, req.key, Json(req.payload), app["app_id"], req.seq),
        user_id=app["owner_user_id"],
        one=True,
    )
    return {
        "topic_id": row["loc_topic_id"],
        "partition_id": row["loc_partition_id"],
        "msg_offset": row["loc_msg_offset"],
        "duplicate": row["is_duplicate"],
    }


@router.post("/produce-batch")
async def produce_batch(req: ProduceBatchReq, app=Depends(require_app)):
    arr = [
        {"seq": req.seq_start + i, "key": m.get("key"), "payload": m["payload"]}
        for i, m in enumerate(req.messages)
    ]
    rows = await db.run(
        "SELECT * FROM produce_batch(%s::text, %s::jsonb, %s::bigint)",
        (req.topic, Json(arr), app["app_id"]),
        user_id=app["owner_user_id"],
    )
    return [
        {
            "seq": r["producer_seq"],
            "topic_id": r["loc_topic_id"],
            "partition_id": r["loc_partition_id"],
            "msg_offset": r["loc_msg_offset"],
            "duplicate": r["is_duplicate"],
        }
        for r in rows
    ]


@router.post("/consume")
async def consume(req: ConsumeReq, app=Depends(require_app)):
    rows = await db.run(
        "SELECT * FROM consume(%s::text, %s::text, %s::int, %s::int)",
        (req.group, req.topic, req.batch, req.visibility_timeout_s),
        user_id=app["owner_user_id"],
    )
    return {
        "messages": [
            {**r, "location": {"partition_id": r["partition_id"], "msg_offset": r["msg_offset"]}}
            for r in rows
        ],
        "locations": [
            {"partition_id": r["partition_id"], "msg_offset": r["msg_offset"]} for r in rows
        ],
    }


@router.post("/ack")
async def ack(req: LocationsReq, app=Depends(require_app)):
    row = await db.run(
        "SELECT ack(%s::text, %s::jsonb) AS acked",
        (req.group, Json(req.locations)),
        user_id=app["owner_user_id"],
        one=True,
    )
    return {"acked": row["acked"]}


@router.post("/nack")
async def nack(req: NackReq, app=Depends(require_app)):
    row = await db.run(
        "SELECT * FROM nack(%s::text, %s::jsonb, %s::text)",
        (req.group, Json(req.locations), req.reason),
        user_id=app["owner_user_id"],
        one=True,
    )
    return {"retried": row["retried"], "dead": row["dead"]}
