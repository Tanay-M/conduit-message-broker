"""Submission, retained SQL evidence, and replay. Calculations live in PostgreSQL."""

from datetime import date
import uuid

import psycopg
from psycopg.rows import dict_row

from .settings import settings


def connect():
    return psycopg.connect(settings.admin_dsn, autocommit=True, row_factory=dict_row)


def submit(
    template, start, end, customer_id=None, top_n=10, bulk=False, submission_key=None
):
    key = uuid.UUID(str(submission_key)) if submission_key else uuid.uuid4()
    with connect() as conn, conn.transaction():
        owner = conn.execute(
            "SELECT user_id FROM app_user WHERE username=%s", (settings.admin_username,)
        ).fetchone()
        if owner is None:
            raise ValueError("Configured reporting administrator does not exist")
        row = conn.execute(
            "CALL reporting.submit_run(%s,%s,%s,%s,%s,%s,%s,%s,NULL)",
            (
                key,
                template,
                customer_id,
                date.fromisoformat(str(start)),
                date.fromisoformat(str(end)),
                top_n,
                bulk,
                owner["user_id"],
            ),
        ).fetchone()
    return row["p_run"]


def progress(run_id):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM reporting.v_run_progress WHERE run_id=%s", (run_id,)
        ).fetchone()


def evidence(request_id):
    with connect() as conn:
        return conn.execute(
            """SELECT q.request_id,q.state,r.run_id,r.start_date,r.end_date,r.top_n,
          q.customer_id,t.code,t.version,t.sql_text,d.captured_at,d.rows,
          x.csv_sha256,x.html_sha256,x.row_count,x.completed_at
          FROM reporting.report_request q JOIN reporting.report_run r USING(run_id)
          JOIN reporting.template_version t USING(template_id)
          JOIN reporting.report_dataset d USING(request_id)
          LEFT JOIN reporting.report_result x USING(request_id) WHERE q.request_id=%s""",
            (request_id,),
        ).fetchone()


def replay(request_id):
    with connect() as conn:
        return conn.execute(
            "SELECT reporting.replay_request(%s) AS report", (request_id,)
        ).fetchone()["report"]
