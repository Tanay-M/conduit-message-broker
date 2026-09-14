import uuid

from fastapi import Header, HTTPException, Request

from . import db
from .config import settings

SESSION_COOKIE = "conduit_session"


def _extract_token(request: Request, authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.cookies.get(SESSION_COOKIE)


async def require_any(request: Request, authorization: str | None = Header(default=None)) -> dict:
    token = _extract_token(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="missing session or bearer token")
    if token == settings.admin_token:
        return {
            "mode": "admin",
            "app_id": None,
            "owner_user_id": None,
            "app_name": "admin",
            "owner_username": "admin",
            "owner_role": "admin",
            "app_type": None,
            "status": "active",
        }
    try:
        uuid.UUID(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token")
    row = await db.run("SELECT * FROM fn_auth_app(%s::uuid)", (token,), one=True)
    return {"mode": "app", **row}


async def require_app(request: Request, authorization: str | None = Header(default=None)) -> dict:
    ctx = await require_any(request, authorization)
    if ctx["mode"] != "app":
        raise HTTPException(
            status_code=403,
            detail="broker operations require an app api key session (log in with an app key)",
        )
    return ctx


def require_admin(request: Request, authorization: str | None = Header(default=None)) -> bool:
    token = _extract_token(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="missing session or bearer token")
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="admin token required")
    return True
