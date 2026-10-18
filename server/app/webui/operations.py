"""Authenticated retail workflow pages over the database services."""

import asyncio
import uuid
from datetime import date

import psycopg
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from reporting import analysis, assistant, imports, inventory
from reporting.settings import settings

from .reports import admin_context
from .router import _page

router = APIRouter(tags=["retail operations"])


async def context(request):
    ctx = await admin_context(request)
    if not ctx:
        if request.url.path.startswith("/api/"):
            raise HTTPException(401, "Sign in first")
        return None
    origin = request.headers.get("origin")
    if (
        request.method == "POST"
        and origin
        and origin.rstrip("/") != str(request.base_url).rstrip("/")
    ):
        raise HTTPException(403, "Submit from this workspace")
    return ctx


def message(exc):
    return (
        (exc.diag.message_primary or "The database rejected this operation")
        if isinstance(exc, psycopg.Error)
        else str(exc)
    )


async def inventory_page(request, ctx, error=None, success=None, status_code=200):
    result = await asyncio.to_thread(inventory.dashboard)
    response = _page(
        request,
        ctx,
        "inventory",
        "inventory",
        **result,
        error=error,
        success=success,
        today=date.today(),
        reference=uuid.uuid4().hex[:16],
    )
    response.status_code = status_code
    return response


@router.get("/inventory")
async def inventory_get(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    return await inventory_page(
        request, ctx, success=request.query_params.get("success")
    )


@router.post("/web/inventory/post")
async def stock_post(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    form = await request.form()
    try:
        movement = await asyncio.to_thread(
            inventory.post,
            form.get("sku", ""),
            form.get("kind", ""),
            int(form.get("quantity", "0")),
            form.get("reference", ""),
            form.get("note", ""),
            ctx["owner_username"],
            form.get("customer_ref") or None,
            form.get("unit_price") or None,
            form.get("posted_on") or None,
        )
    except (ValueError, psycopg.Error) as exc:
        return await inventory_page(request, ctx, error=message(exc), status_code=422)
    return RedirectResponse("/inventory?success=Posted+movement+" + str(movement), 303)


@router.post("/web/inventory/reorder")
async def reorder_post(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    form = await request.form()
    try:
        await asyncio.to_thread(
            inventory.reorder, form.get("sku", ""), form.get("reorder_level", "")
        )
    except (ValueError, psycopg.Error) as exc:
        return await inventory_page(request, ctx, error=message(exc), status_code=422)
    return RedirectResponse("/inventory?success=Reorder+level+updated", 303)


@router.get("/imports")
async def imports_get(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    return _page(
        request,
        ctx,
        "imports",
        "imports",
        batches=await asyncio.to_thread(imports.recent),
        error=None,
        ai_ready=bool(settings.gemini_api_key),
    )


@router.get("/imports/sample.csv")
async def sample_csv(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    text = "OrderNo,ClientCode,OrderDate,LineNo,ItemCode,Qty,Rate\nREVIEW-IMPORT-001,DEMO-000001,2026-10-01,1,SKU-1,2,25.00\nREVIEW-IMPORT-001,DEMO-000001,2026-10-01,2,SKU-2,1,50.00\nREVIEW-IMPORT-BAD,DEMO-000001,2026-10-02,1,SKU-1,1,-10.00\n"
    if request.query_params.get("corrected") == "1":
        text = text.replace("1,-10.00", "1,10.00")
    return Response(
        text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="conduit-sales-demo.csv"'
        },
    )


@router.post("/web/imports")
async def import_upload(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    try:
        async with request.form(
            max_files=1, max_fields=10, max_part_size=2_000_001
        ) as form:
            file = form.get("file")
            if not file or not hasattr(file, "read"):
                raise ValueError("Choose a CSV file")
            content = await file.read(2_000_001)
            batch = await asyncio.to_thread(
                imports.stage,
                content,
                file.filename or "sales.csv",
                ctx["owner_username"],
                form.get("use_ai") == "on",
            )
    except (ValueError, psycopg.Error) as exc:
        response = _page(
            request,
            ctx,
            "imports",
            "imports",
            batches=await asyncio.to_thread(imports.recent),
            error=message(exc),
            ai_ready=bool(settings.gemini_api_key),
        )
        response.status_code = 422
        return response
    return RedirectResponse("/imports/" + str(batch), 303)


async def batch_page(request, ctx, batch_id, error=None):
    try:
        batch = await asyncio.to_thread(imports.detail, batch_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _page(
        request,
        ctx,
        "import_batch",
        "imports",
        batch=batch,
        fields=imports.FIELDS,
        error=error,
    )


@router.get("/imports/{batch_id}")
async def batch_get(request: Request, batch_id: uuid.UUID):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    return await batch_page(request, ctx, batch_id)


@router.post("/web/imports/{batch_id}/mapping")
async def batch_mapping(request: Request, batch_id: uuid.UUID):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    form = await request.form()
    try:
        await asyncio.to_thread(
            imports.remap, batch_id, {f: form.get(f, "") for f in imports.FIELDS}
        )
    except (ValueError, psycopg.Error) as exc:
        return await batch_page(request, ctx, batch_id, message(exc))
    return RedirectResponse("/imports/" + str(batch_id), 303)


@router.post("/web/imports/{batch_id}/commit")
async def batch_commit(request: Request, batch_id: uuid.UUID):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    try:
        await asyncio.to_thread(imports.commit, batch_id)
    except (ValueError, psycopg.Error) as exc:
        return await batch_page(request, ctx, batch_id, message(exc))
    return RedirectResponse("/imports/" + str(batch_id), 303)


@router.get("/assistant")
async def assistant_get(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    return _page(
        request,
        ctx,
        "assistant",
        "assistant",
        record=None,
        result=None,
        error=None,
        prompt="",
        ai_ready=bool(settings.gemini_api_key),
    )


@router.post("/web/assistant/plan")
async def assistant_plan(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    form = await request.form()
    prompt = form.get("prompt", "")
    try:
        record = await asyncio.to_thread(
            assistant.plan, prompt, ctx["owner_username"], form.get("use_ai") == "on"
        )
    except (ValueError, psycopg.Error) as exc:
        response = _page(
            request,
            ctx,
            "assistant",
            "assistant",
            record=None,
            result=None,
            error=message(exc),
            prompt=prompt,
            ai_ready=bool(settings.gemini_api_key),
        )
        response.status_code = 422
        return response
    return _page(
        request,
        ctx,
        "assistant",
        "assistant",
        record=record,
        result=None,
        error=None,
        prompt=prompt,
        ai_ready=bool(settings.gemini_api_key),
    )


@router.post("/web/assistant/{request_id}/execute")
async def assistant_execute(request: Request, request_id: uuid.UUID):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    try:
        result = await asyncio.to_thread(assistant.execute, request_id)
    except (ValueError, psycopg.Error) as exc:
        raise HTTPException(422, message(exc)) from exc
    return _page(
        request,
        ctx,
        "assistant",
        "assistant",
        record=result["record"],
        result=result,
        error=None,
        prompt=result["record"]["prompt"],
        ai_ready=bool(settings.gemini_api_key),
    )


@router.get("/analysis")
async def analysis_get(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    return _page(
        request,
        ctx,
        "analysis",
        "analysis",
        result=None,
        error=None,
        start="2026-01-01",
        end="2027-01-01",
        ai_ready=bool(settings.gemini_api_key),
    )


@router.post("/web/assistant/{request_id}/report")
async def assistant_report(request: Request, request_id: uuid.UUID):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    try:
        run_id = await asyncio.to_thread(assistant.queue_report, request_id)
    except (ValueError, psycopg.Error) as exc:
        raise HTTPException(422, message(exc)) from exc
    return RedirectResponse("/reports/runs/" + str(run_id), 303)


@router.post("/web/analysis")
async def analysis_post(request: Request):
    ctx = await context(request)
    if ctx is None:
        return RedirectResponse("/web/login", 303)
    form = await request.form()
    start = form.get("start", "")
    end = form.get("end", "")
    try:
        result = await asyncio.to_thread(
            analysis.run, start, end, ctx["owner_username"], form.get("use_ai") == "on"
        )
    except (ValueError, psycopg.Error) as exc:
        response = _page(
            request,
            ctx,
            "analysis",
            "analysis",
            result=None,
            error=message(exc),
            start=start,
            end=end,
            ai_ready=bool(settings.gemini_api_key),
        )
        response.status_code = 422
        return response
    return _page(
        request,
        ctx,
        "analysis",
        "analysis",
        result=result,
        error=None,
        start=start,
        end=end,
        ai_ready=bool(settings.gemini_api_key),
    )
