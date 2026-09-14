import psycopg
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

from .errors import from_psycopg

DEFAULT_APP_DSN = "postgresql://conduit_app:conduit_app_dev@localhost:5433/conduit"
DEFAULT_ADMIN_DSN = "postgresql://conduit:conduit_dev@localhost:5433/conduit"


class Database:
    def __init__(self, dsn, name, min_size=1, max_size=8):
        self.pool = ConnectionPool(
            dsn,
            name=name,
            min_size=min_size,
            max_size=max_size,
            open=True,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )

    def close(self):
        self.pool.close()

    def call(self, sql, params=(), user_id=None, one=False):
        with self.pool.connection() as conn:
            try:
                with conn.transaction():
                    if user_id is not None:
                        conn.execute(f"SET LOCAL app.user_id = {int(user_id)}")
                    with conn.cursor() as cur:
                        cur.execute(sql, params)
                        if cur.description is None:
                            return None
                        rows = cur.fetchall()
                if one:
                    return rows[0] if rows else None
                return rows
            except psycopg.Error as e:
                raise from_psycopg(e) from e
