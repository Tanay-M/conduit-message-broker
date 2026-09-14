import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from .. import db
from ..auth import require_any

router = APIRouter(prefix="/api", tags=["events"], dependencies=[Depends(require_any)])


@router.get("/events")
async def events():
    conn = await db.app_pool.getconn()
    try:
        await conn.execute("LISTEN conduit_events")
    except Exception:
        await db.app_pool.putconn(conn)
        raise

    async def gen():
        try:
            notifies = conn.notifies()
            while True:
                try:
                    n = await asyncio.wait_for(anext(notifies), timeout=15)
                    yield f"event: {n.channel}\ndata: {n.payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except StopAsyncIteration:
                    break
        finally:
            try:
                await conn.execute("UNLISTEN conduit_events")
            finally:
                await db.app_pool.putconn(conn)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
