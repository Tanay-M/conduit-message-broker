"""Minimal authenticated reporting API. UI design is deliberately deferred."""

import asyncio
from datetime import date
import hashlib
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, model_validator
import psycopg
from conduit.errors import from_psycopg

from .. import db
from ..auth import require_admin
from reporting.settings import settings
from reporting import service
from reporting.render import documents

router = APIRouter(
    prefix="/api/reports", tags=["reporting"], dependencies=[Depends(require_admin)]
)


class ReportInput(BaseModel):
    template: Literal["customer_statement", "product_sales", "monthly_sales"]
    start: date
    end: date
    customer_id: int | None = Field(default=None, gt=0)
    top_n: int = Field(default=10, ge=1, le=100)
    bulk: bool = False
    submission_key: uuid.UUID = Field(default_factory=uuid.uuid4)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.start >= self.end or (self.end - self.start).days > 3660:
            raise ValueError(
                "Date range must be increasing and at most 3660 days; end is exclusive"
            )
        return self


@router.get("/templates")
async def templates():
    return await db.run(
        "SELECT template_id,code,version,title,sql_text FROM reporting.template_version ORDER BY code,version",
        pool=db.admin_pool,
    )


@router.post("/runs", status_code=202)
async def submit(body: ReportInput):
    try:
        run_id = await asyncio.to_thread(
            service.submit,
            body.template,
            body.start,
            body.end,
            body.customer_id,
            body.top_n,
            body.bulk,
            body.submission_key,
        )
    except psycopg.Error as error:
        raise from_psycopg(error) from error
    return {
        "run_id": run_id,
        "submission_key": body.submission_key,
        "status_url": f"/api/reports/runs/{run_id}",
    }


@router.get("/runs")
async def runs():
    return await db.run(
        "SELECT * FROM reporting.v_run_progress ORDER BY created_at DESC LIMIT 100",
        pool=db.admin_pool,
    )


@router.get("/runs/{run_id}")
async def run(run_id: uuid.UUID):
    row = await db.run(
        "SELECT * FROM reporting.v_run_progress WHERE run_id=%s",
        (run_id,),
        pool=db.admin_pool,
        one=True,
    )
    if row is None:
        raise HTTPException(404, "Unknown report run")
    return row


@router.get("/runs/{run_id}/requests")
async def requests(
    run_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return await db.run(
        "SELECT * FROM reporting.report_request WHERE run_id=%s ORDER BY subject_key LIMIT %s OFFSET %s",
        (run_id, limit, offset),
        pool=db.admin_pool,
    )


@router.get("/requests/{request_id}/evidence")
async def evidence(request_id: uuid.UUID):
    row = await asyncio.to_thread(service.evidence, request_id)
    if row is None:
        raise HTTPException(404, "Unknown prepared report request")
    return row


@router.get("/requests/{request_id}/replay", response_class=HTMLResponse)
async def replay(request_id: uuid.UUID):
    report = await asyncio.to_thread(service.replay, request_id)
    if report is None:
        raise HTTPException(404, "Unknown prepared report request")
    return HTMLResponse(documents(report)["html"])


@router.get("/requests/{request_id}/download/{format}")
async def download(request_id: uuid.UUID, format: Literal["csv", "html"]):
    row = await db.run(
        "SELECT csv_path,html_path,csv_sha256,html_sha256 FROM reporting.report_result WHERE request_id=%s",
        (request_id,),
        pool=db.admin_pool,
        one=True,
    )
    if row is None:
        raise HTTPException(404, "No completed output")
    root = settings.output_dir.resolve()
    path = (root / row[format + "_path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(409, "Output file is missing; replay remains available")
    if hashlib.sha256(path.read_bytes()).hexdigest() != row[format + "_sha256"]:
        raise HTTPException(409, "Output checksum mismatch")
    return FileResponse(
        path,
        media_type="text/csv" if format == "csv" else "text/html",
        filename=f"{request_id}.{format}",
    )


@router.post("/requests/{request_id}/retry")
async def retry(request_id: uuid.UUID):
    # Redrive the existing failed message, preserving its DLQ history and request identity.
    async with db.admin_pool.connection() as conn, conn.transaction():
        row = await (
            await conn.execute(
                "SELECT * FROM reporting.report_request WHERE request_id=%s FOR UPDATE",
                (request_id,),
            )
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Unknown request")
        if row["state"] != "failed":
            raise HTTPException(409, "Only permanently failed requests can be redriven")
        dead = await (
            await conn.execute(
                "SELECT dlq_id FROM dead_letter_message WHERE msg_key=%s AND status='pending' ORDER BY dlq_id DESC LIMIT 1 FOR UPDATE",
                (str(request_id),),
            )
        ).fetchone()
        if dead is None:
            raise HTTPException(409, "No pending dead-letter entry")
        await conn.execute(
            "SELECT * FROM requeue_dlq(%s,(SELECT app_id FROM application WHERE app_name='reporting-service'),NULL)",
            (dead["dlq_id"],),
        )
        await conn.execute(
            "UPDATE reporting.report_request SET state='queued',last_error=NULL WHERE request_id=%s",
            (request_id,),
        )
    return {"request_id": request_id, "state": "queued"}
