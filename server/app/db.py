import psycopg
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

from conduit.errors import from_psycopg

from .config import settings

app_pool = AsyncConnectionPool(
    settings.app_dsn,
    name="conduit-api-app",
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row, "autocommit": True},
    open=False,
)

admin_pool = AsyncConnectionPool(
    settings.admin_dsn,
    name="conduit-api-admin",
    min_size=1,
    max_size=4,
    kwargs={"row_factory": dict_row, "autocommit": True},
    open=False,
)


async def run(sql, params=(), pool=None, user_id=None, one=False):
    pool = pool or app_pool
    async with pool.connection() as conn:
        try:
            async with conn.transaction():
                if user_id is not None:
                    await conn.execute(f"SET LOCAL app.user_id = {int(user_id)}")
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)
                    if cur.description is None:
                        return None
                    rows = await cur.fetchall()
            if one:
                return rows[0] if rows else None
            return rows
        except psycopg.Error as e:
            raise from_psycopg(e) from e
