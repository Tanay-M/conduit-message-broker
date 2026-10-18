"""Reporting workspace: server-rendered pages over the verified SQL reporting service."""

import asyncio
import uuid
from datetime import datetime

import psycopg
from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from reporting import service

from .. import db
from ..api.reporting import ReportInput
from .router import _page, _require_admin_ctx, session, templates

router = APIRouter(tags=["reporting workspace"])

DESCRIPTIONS = {
    "customer_statement": "Itemised purchases and totals for a customer, or a statement for every customer.",
    "product_sales": "Rank products by sales value with quantities and category breakdowns.",
    "monthly_sales": "Monthly sales, order counts and a running total across your selected period.",
}


def date_label(value, pattern="%d %b %Y"):
    if not value:
        return "—"
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(pattern)


templates.env.filters["date_label"] = date_label
templates.env.filters["number"] = lambda value: f"{value or 0:,}"
templates.env.filters["short_id"] = lambda value: str(value)[:8].upper()


async def admin_context(request):
    ctx = await session(request)
    if ctx is not None:
        _require_admin_ctx(ctx)
    return ctx


RUNS = """SELECT v.*,r.start_date,r.end_date,r.bulk,r.customer_id,r.error,t.title,c.full_name,
    CASE WHEN v.preparation_status='failed' OR v.failed>0 THEN 'attention'
         WHEN v.preparation_status='ready' AND v.completed=v.expected AND v.expected>0 THEN 'completed'
         ELSE 'active' END AS display_status
    FROM reporting.v_run_progress v JOIN reporting.report_run r USING(run_id)
    JOIN reporting.template_version t ON t.template_id=r.template_id
    LEFT JOIN reporting.customer c ON c.customer_id=r.customer_id"""


async def run_rows(q="", status="all"):
    if status not in ("all", "completed", "active", "attention"):
        raise HTTPException(422, "Unknown report status")
    return await db.run(
        "SELECT * FROM ("
        + RUNS
        + """) runs
        WHERE (%s='all' OR display_status=%s)
          AND (%s='' OR title ILIKE %s OR run_id::text ILIKE %s)
        ORDER BY created_at DESC LIMIT 50""",
        (status, status, q, "%" + q + "%", "%" + q + "%"),
        pool=db.admin_pool,
    )


async def totals():
    return await db.run(
        """SELECT
        (SELECT count(*) FROM reporting.report_run) AS runs,
        count(*) FILTER(WHERE state='completed') AS completed,
        count(*) FILTER(WHERE state IN ('queued','processing')) AS active,
        count(*) FILTER(WHERE state='failed') AS failed
        FROM reporting.report_request""",
        pool=db.admin_pool,
        one=True,
    )


async def home(request, ctx):
    q = request.query_params.get("q", "")[:100]
    status = request.query_params.get("status", "all")
    return _page(
        request,
        ctx,
        "reports",
        "reports",
        runs=await run_rows(q, status),
        totals=await totals(),
        q=q,
        status=status,
    )


@router.get("/reports")
async def reports_page(request: Request):
    ctx = await admin_context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    return await home(request, ctx)


@router.get("/fragments/report-runs")
async def runs_fragment(request: Request, q: str = "", status: str = "all"):
    ctx = await admin_context(request)
    if ctx is None:
        raise HTTPException(401)
    return templates.TemplateResponse(
        request,
        "fragments/_report_runs.html",
        {
            "runs": await run_rows(q[:100], status),
            "q": q[:100],
            "status": status,
            "refresh_totals": True,
            "totals": await totals(),
        },
    )


async def form_page(request, ctx, values=None, error=None, status_code=200):
    catalog = await db.run(
        "SELECT template_id,code,version,title,sql_text FROM reporting.template_version ORDER BY code,version",
        pool=db.admin_pool,
    )
    values = values or {
        "template": request.query_params.get("template", "customer_statement"),
        "start": "2026-01-01",
        "end": "2027-01-01",
        "top_n": 10,
        "scope": "single",
        "customer_id": "",
        "customer_search": "",
        "submission_key": str(uuid.uuid4()),
    }
    if values["template"] not in DESCRIPTIONS:
        values["template"] = "customer_statement"
    return templates.TemplateResponse(
        request,
        "pages/report_new.html",
        {
            "ctx": ctx,
            "active": "reports",
            "catalog": catalog,
            "descriptions": DESCRIPTIONS,
            "values": values,
            "error": error,
        },
        status_code=status_code,
    )


@router.get("/reports/new")
async def new_report(request: Request):
    ctx = await admin_context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    return await form_page(request, ctx)


@router.get("/web/report-customers")
async def customers(request: Request, q: str = "", limit: int = Query(12, ge=1, le=20)):
    ctx = await admin_context(request)
    if ctx is None:
        raise HTTPException(401)
    return await db.run(
        """SELECT customer_id,customer_ref,full_name FROM reporting.customer
        WHERE full_name ILIKE %s OR customer_ref ILIKE %s ORDER BY customer_id LIMIT %s""",
        ("%" + q[:100] + "%", "%" + q[:100] + "%", limit),
        pool=db.admin_pool,
    )


@router.post("/web/reports")
async def create_report(
    request: Request,
    template: str = Form(...),
    start: str = Form(...),
    end: str = Form(...),
    scope: str = Form("single"),
    customer_id: str = Form(""),
    customer_search: str = Form(""),
    top_n: str = Form("10"),
    submission_key: str = Form(...),
):
    ctx = await admin_context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    values = {
        "template": template,
        "start": start,
        "end": end,
        "scope": scope,
        "customer_id": customer_id,
        "customer_search": customer_search,
        "top_n": top_n,
        "submission_key": submission_key,
    }
    try:
        payload = ReportInput(
            template=template,
            start=start,
            end=end,
            customer_id=int(customer_id)
            if customer_id and template == "customer_statement" and scope == "single"
            else None,
            top_n=int(top_n) if template == "product_sales" else 10,
            bulk=template == "customer_statement" and scope == "bulk",
            submission_key=submission_key,
        )
        run_id = await asyncio.to_thread(
            service.submit,
            payload.template,
            payload.start,
            payload.end,
            payload.customer_id,
            payload.top_n,
            payload.bulk,
            payload.submission_key,
        )
    except (ValidationError, ValueError, psycopg.Error) as exc:
        if isinstance(exc, ValidationError):
            error = " ".join(
                item["msg"].removeprefix("Value error, ") for item in exc.errors()
            )
        elif isinstance(exc, psycopg.Error):
            error = (
                exc.diag.message_primary
                or "The database could not accept this request."
            )
        else:
            error = "Choose a valid customer and reporting period."
        return await form_page(request, ctx, values, error, 422)
    return RedirectResponse("/reports/runs/" + str(run_id), 303)


@router.get("/reports/runs/{run_id}")
async def run_page(
    request: Request, run_id: uuid.UUID, page: int = Query(1, ge=1), state: str = "all"
):
    ctx = await admin_context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    if state not in ("all", "completed", "queued", "processing", "failed"):
        raise HTTPException(422, "Unknown request state")
    run = await db.run(
        "SELECT * FROM (" + RUNS + ") r WHERE run_id=%s",
        (run_id,),
        pool=db.admin_pool,
        one=True,
    )
    if run is None:
        raise HTTPException(404, "Report run not found")
    count = await db.run(
        "SELECT count(*) AS n FROM reporting.report_request WHERE run_id=%s AND (%s='all' OR state=%s)",
        (run_id, state, state),
        pool=db.admin_pool,
        one=True,
    )
    rows = await db.run(
        """SELECT q.*,c.customer_ref,c.full_name,x.row_count,x.completed_at AS output_at
        FROM reporting.report_request q LEFT JOIN reporting.customer c USING(customer_id)
        LEFT JOIN reporting.report_result x USING(request_id)
        WHERE q.run_id=%s AND (%s='all' OR q.state=%s) ORDER BY q.subject_key LIMIT 25 OFFSET %s""",
        (run_id, state, state, (page - 1) * 25),
        pool=db.admin_pool,
    )
    return _page(
        request,
        ctx,
        "report_run",
        "reports",
        run=run,
        rows=rows,
        page=page,
        state=state,
        total=count["n"],
    )


@router.get("/reports/requests/{request_id}")
async def request_page(request: Request, request_id: uuid.UUID, view: str = "preview"):
    ctx = await admin_context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    if view not in ("preview", "sql", "history"):
        raise HTTPException(422, "Unknown inspector view")
    item = await asyncio.to_thread(service.evidence, request_id)
    if item is None:
        raise HTTPException(404, "Prepared report not found")
    history = await db.run(
        "SELECT * FROM reporting.report_audit WHERE request_id=%s ORDER BY audit_id",
        (request_id,),
        pool=db.admin_pool,
    )
    return _page(
        request,
        ctx,
        "report_inspector",
        "reports",
        item=item,
        view=view,
        history=history,
        preview=item["rows"][:50],
        columns=list(item["rows"][0]) if item["rows"] else [],
    )


DATASETS = {
    "customers": (
        "reporting.customer",
        "customer_id",
        ["customer_id", "customer_ref", "full_name", "email", "region"],
        "concat_ws(' ',full_name,customer_ref,email,region)",
    ),
    "products": (
        "reporting.product",
        "product_id",
        ["product_id", "sku", "product_name", "category", "catalogue_price"],
        "concat_ws(' ',product_name,sku,category)",
    ),
    "orders": (
        "reporting.sales_order",
        "order_id",
        ["order_id", "order_ref", "customer_id", "ordered_at", "status"],
        "order_ref",
    ),
    "order-items": (
        "reporting.order_item",
        "order_id,line_number",
        ["order_id", "line_number", "product_id", "quantity", "unit_price"],
        None,
    ),
}


@router.get("/data")
async def data_page(
    request: Request, table: str = "customers", q: str = "", page: int = Query(1, ge=1)
):
    ctx = await admin_context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    if table not in DATASETS:
        raise HTTPException(422, "Unknown dataset")
    relation, order, columns, search = DATASETS[table]
    clause = f" WHERE {search} ILIKE %s" if search and q else ""
    params = ["%" + q[:100] + "%"] if clause else []
    count = await db.run(
        f"SELECT count(*) AS n FROM {relation}" + clause,
        params,
        pool=db.admin_pool,
        one=True,
    )
    rows = await db.run(
        f"SELECT * FROM {relation}" + clause + f" ORDER BY {order} LIMIT 25 OFFSET %s",
        params + [(page - 1) * 25],
        pool=db.admin_pool,
    )
    return _page(
        request,
        ctx,
        "report_data",
        "data",
        table=table,
        q=q,
        rows=rows,
        columns=columns,
        page=page,
        total=count["n"],
        relation=relation,
        datasets=DATASETS,
    )
