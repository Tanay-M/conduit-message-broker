"""Bounded native workers; SQL prepares data, Python only renders retained rows."""

import argparse
import json
import time
import uuid

from psycopg.types.json import Jsonb

from .render import documents, publish
from .service import connect
from .settings import settings


def claim(conn, group, topic, timeout):
    return conn.execute(
        "SELECT * FROM consume(%s,%s,1,%s)", (group, topic, timeout)
    ).fetchone()


def settle(conn, group, message, error=None):
    location = Jsonb(
        [{"partition_id": message["partition_id"], "msg_offset": message["msg_offset"]}]
    )
    if error is None:
        conn.execute("SELECT ack(%s,%s)", (group, location))
        return None
    return conn.execute(
        "SELECT * FROM nack(%s,%s,%s)", (group, location, str(error)[:2000])
    ).fetchone()


def prepare(conn, message):
    run_id = uuid.UUID(message["payload"]["run_id"])
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        count = conn.execute(
            "SELECT reporting.prepare_run(%s) AS count", (run_id,)
        ).fetchone()["count"]
    # Commit the consistent dataset before publishing a bounded chunk of jobs.
    while conn.execute(
        "SELECT reporting.enqueue_ready_requests(%s,100) AS n", (run_id,)
    ).fetchone()["n"]:
        pass
    with conn.transaction():
        settle(conn, "report-preparers", message)
    return count


def render(conn, message, name):
    request_id = uuid.UUID(message["payload"]["request_id"])
    sql_started = time.perf_counter()
    with conn.transaction():
        request = conn.execute(
            "SELECT * FROM reporting.report_request WHERE request_id=%s FOR UPDATE",
            (request_id,),
        ).fetchone()
        if request is None:
            raise ValueError("Report request does not exist")
        if conn.execute(
            "SELECT 1 FROM reporting.report_result WHERE request_id=%s", (request_id,)
        ).fetchone():
            settle(conn, "report-workers", message)
            return
        conn.execute(
            "UPDATE reporting.report_request SET state='processing',attempts=attempts+1,last_error=NULL WHERE request_id=%s",
            (request_id,),
        )
        report = conn.execute(
            "SELECT reporting.replay_request(%s) AS report", (request_id,)
        ).fetchone()["report"]
        if report is None:
            raise ValueError("Prepared report data is missing")
    sql_seconds = time.perf_counter() - sql_started
    started = time.perf_counter()
    files = publish(settings.output_dir, request_id, documents(report))
    render_seconds = time.perf_counter() - started
    with conn.transaction():
        conn.execute(
            "SELECT 1 FROM reporting.report_request WHERE request_id=%s FOR UPDATE",
            (request_id,),
        )
        conn.execute(
            """INSERT INTO reporting.report_result
            (request_id,csv_path,html_path,csv_sha256,html_sha256,row_count,worker_name,sql_seconds,render_seconds)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(request_id) DO NOTHING""",
            (
                request_id,
                files["csv_path"],
                files["html_path"],
                files["csv_sha256"],
                files["html_sha256"],
                len(report["rows"]),
                name,
                sql_seconds,
                render_seconds,
            ),
        )
        conn.execute(
            "UPDATE reporting.report_request SET state='completed',completed_at=now(),last_error=NULL WHERE request_id=%s",
            (request_id,),
        )
        settle(conn, "report-workers", message)


def fail(conn, group, message, error):
    with conn.transaction():
        result = settle(conn, group, message, error)
        key = "run_id" if group == "report-preparers" else "request_id"
        try:
            identity = uuid.UUID(str(message["payload"][key]))
        except (KeyError, ValueError, TypeError):
            # Poison queue payloads have no business record; nack/DLQ is still committed.
            return
        if group == "report-preparers":
            conn.execute(
                "UPDATE reporting.report_run SET status='failed',error=%s WHERE run_id=%s AND status<>'ready'",
                (str(error)[:2000], identity),
            )
        else:
            state = "failed" if result["dead"] else "queued"
            conn.execute(
                "UPDATE reporting.report_request SET state=%s,last_error=%s WHERE request_id=%s AND state<>%s",
                (
                    state,
                    str(error)[:2000],
                    identity,
                    "completed",
                ),
            )


def tick(conn, name, timeout=120):
    # Reap periodically even if no rendering work is available.
    reaped = conn.execute("SELECT * FROM reap_expired_claims()").fetchone()
    if reaped["dead"]:
        conn.execute("SELECT reporting.reconcile_failed_requests()")
    # Also repair a preparation worker stopping after dataset commit or between enqueue chunks.
    conn.execute("SELECT reporting.enqueue_ready_requests(NULL,100)")
    message = claim(conn, "report-preparers", "report-prepare", timeout)
    if message:
        try:
            count = prepare(conn, message)
            print(
                json.dumps(
                    {
                        "worker": name,
                        "prepared": message["payload"]["run_id"],
                        "requests": count,
                    }
                ),
                flush=True,
            )
        except Exception as error:
            fail(conn, "report-preparers", message, error)
            print(json.dumps({"worker": name, "error": str(error)}), flush=True)
        return True
    message = claim(conn, "report-workers", "report-render", timeout)
    if message:
        try:
            render(conn, message, name)
        except Exception as error:
            fail(conn, "report-workers", message, error)
            print(json.dumps({"worker": name, "error": str(error)}), flush=True)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="worker-1")
    parser.add_argument(
        "--drain",
        action="store_true",
        help="Exit when no immediately available work remains",
    )
    parser.add_argument("--visibility", type=int, default=120)
    args = parser.parse_args()
    with connect() as conn:
        conn.execute("SELECT reporting.reconcile_failed_requests()")
        while True:
            worked = tick(conn, args.name, args.visibility)
            if not worked:
                if args.drain:
                    break
                time.sleep(0.5)


if __name__ == "__main__":
    main()
