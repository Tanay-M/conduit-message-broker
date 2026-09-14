import re

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from conduit.errors import from_psycopg

from .. import db
from ..auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["sql-console"], dependencies=[Depends(require_admin)])


class SqlReq(BaseModel):
    query: str


def _sanitize(raw: str) -> str:
    stmt = re.sub(r"--.*?$", " ", raw, flags=re.M)
    stmt = re.sub(r"/\*.*?\*/", " ", stmt, flags=re.S)
    stmt = stmt.strip().rstrip(";").strip()
    lowered = stmt.lower()
    if not lowered.startswith(("select", "explain")) or ";" in stmt:
        raise HTTPException(status_code=400, detail="only a single SELECT or EXPLAIN statement is allowed")
    return stmt


@router.post("/sql")
async def sql_console(req: SqlReq):
    stmt = _sanitize(req.query)
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
            return {"columns": columns, "rows": rows, "row_count": len(rows)}
        except psycopg.errors.QueryCanceled as e:
            raise HTTPException(status_code=408, detail="query exceeded the 5 second timeout") from e
        except psycopg.Error as e:
            raise from_psycopg(e) from e
