from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from conduit.errors import ConduitError

from . import db
from .api import admin, broker, events, monitor, sql
from .webui import router as webui


STATUS_MAP = {
    "CDT01": 404,
    "CDT02": 409,
    "CDT03": 403,
    "CDT04": 422,
    "CDT05": 413,
    "CDT06": 404,
    "CDT07": 409,
    "CDT09": 409,
    "CDT11": 422,
    "CDT12": 404,
    "CDT13": 422,
    "CDT14": 404,
    "CDT15": 422,
    "CDT16": 409,
    "CDT17": 403,
    "CDT18": 403,
    "CDT19": 409,
    "CDT20": 403,
    "CDT22": 401,
    "42501": 403,
    "23505": 409,
    "23503": 409,
    "23514": 422,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.app_pool.open()
    await db.admin_pool.open()
    yield
    await db.app_pool.close()
    await db.admin_pool.close()


app = FastAPI(title="Conduit", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ConduitError)
async def conduit_error_handler(request: Request, exc: ConduitError):
    return JSONResponse(
        status_code=STATUS_MAP.get(exc.code, 400),
        content={"error": exc.code, "message": exc.message},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(broker.router)
app.include_router(monitor.router)
app.include_router(admin.router)
app.include_router(sql.router)
app.include_router(events.router)
app.include_router(webui.router)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
