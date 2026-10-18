"""Integration tests run SQL/worker code against a disposable native database."""

import csv
from decimal import Decimal
import hashlib
import uuid

import psycopg
from psycopg import sql
import pytest

from reporting import service, worker
from reporting.local import migrate
from reporting.seed import seed
from reporting.settings import settings


@pytest.fixture(scope="module", autouse=True)
def database(tmp_path_factory):
    original = settings.admin_dsn
    output = settings.output_dir
    database = "conduit_verify_" + uuid.uuid4().hex[:12]
    with psycopg.connect(original, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    settings.admin_dsn = original.rsplit("/", 1)[0] + "/" + database
    settings.output_dir = tmp_path_factory.mktemp("conduit-report-artifacts")
    try:
        migrate(settings.admin_dsn)
        seed(4, 2)
        yield
    finally:
        settings.admin_dsn = original
        settings.output_dir = output
        with psycopg.connect(original, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (database,),
            )
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


@pytest.fixture(scope="module")
def known_customer():
    with service.connect() as conn, conn.transaction():
        customer = conn.execute(
            "INSERT INTO reporting.customer(customer_ref,full_name,email,region) VALUES('KNOWN','Known <Customer>','known@example.test','North') RETURNING customer_id"
        ).fetchone()["customer_id"]
        product = conn.execute(
            "INSERT INTO reporting.product(sku,product_name,category,catalogue_price) VALUES('KNOWN-P','Known Product','Test',99) RETURNING product_id"
        ).fetchone()["product_id"]
        order = conn.execute(
            "INSERT INTO reporting.sales_order(order_ref,customer_id,ordered_at) VALUES('KNOWN-O',%s,'2026-02-01') RETURNING order_id",
            (customer,),
        ).fetchone()["order_id"]
        conn.execute(
            "INSERT INTO reporting.order_item(order_id,line_number,product_id,quantity,unit_price) VALUES(%s,1,%s,2,12.50),(%s,2,%s,3,7.50)",
            (order, product, order, product),
        )
    return customer, order, product


def drain():
    with service.connect() as conn:
        for _ in range(200):
            if not worker.tick(conn, "test-worker"):
                return
    raise AssertionError("Worker did not drain")


def request_for(run):
    with service.connect() as conn:
        return conn.execute(
            "SELECT request_id FROM reporting.report_request WHERE run_id=%s", (run,)
        ).fetchone()["request_id"]


def test_real_statement_and_sql_totals(known_customer):
    customer, _, _ = known_customer
    run = service.submit("customer_statement", "2026-01-01", "2027-01-01", customer)
    drain()
    assert service.progress(run)["completed"] == 1

    request = request_for(run)
    saved = service.replay(request)
    assert {Decimal(str(row["statement_total"])) for row in saved["rows"]} == {
        Decimal("47.50")
    }
    assert sum(Decimal(str(row["line_total"])) for row in saved["rows"]) == Decimal(
        "47.50"
    )
    with service.connect() as conn:
        result = conn.execute(
            "SELECT * FROM reporting.report_result WHERE request_id=%s", (request,)
        ).fetchone()
        audit = conn.execute(
            "SELECT new_state FROM reporting.report_audit WHERE request_id=%s ORDER BY audit_id",
            (request,),
        ).fetchall()
    assert [row["new_state"] for row in audit] == ["queued", "processing", "completed"]
    csv_path = settings.output_dir / result["csv_path"]
    assert len(list(csv.DictReader(csv_path.open(encoding="utf-8")))) == 2
    assert hashlib.sha256(csv_path.read_bytes()).hexdigest() == result["csv_sha256"]
    assert (
        "Known &lt;Customer&gt;"
        in (settings.output_dir / result["html_path"]).read_text()
    )
    assert (
        "JOIN" in service.evidence(request)["sql_text"]
        or "v_sales_lines" in service.evidence(request)["sql_text"]
    )


def test_expired_final_claim_updates_report_state(known_customer):
    run = service.submit(
        "customer_statement", "2026-01-01", "2027-01-01", known_customer[0]
    )
    with service.connect() as conn:
        worker.prepare(
            conn, worker.claim(conn, "report-preparers", "report-prepare", 30)
        )
        for _ in range(3):
            msg = worker.claim(conn, "report-workers", "report-render", 30)
            conn.execute(
                "UPDATE message SET visible_at=now()-interval '1 second' WHERE partition_id=%s AND msg_offset=%s",
                (msg["partition_id"], msg["msg_offset"]),
            )
            conn.execute("SELECT * FROM reap_expired_claims()")
        conn.execute("SELECT reporting.reconcile_failed_requests()")
    assert service.progress(run)["failed"] == 1


def test_constraints(known_customer):
    _, order, product = known_customer
    with service.connect() as conn:
        for statement, params, error in [
            (
                "INSERT INTO reporting.order_item VALUES(%s,99,%s,0,1)",
                (order, product),
                psycopg.errors.CheckViolation,
            ),
            (
                "INSERT INTO reporting.sales_order(order_ref,customer_id,ordered_at) VALUES('BAD-FK',999999,'2026-01-01')",
                (),
                psycopg.errors.ForeignKeyViolation,
            ),
            (
                "INSERT INTO reporting.customer(customer_ref,full_name,email,region) VALUES('KNOWN','X','other@example.test','North')",
                (),
                psycopg.errors.UniqueViolation,
            ),
        ]:
            with pytest.raises(error), conn.transaction():
                conn.execute(statement, params)
    with pytest.raises(psycopg.errors.CheckViolation):
        service.submit("monthly_sales", "2027-01-01", "2026-01-01")
    with pytest.raises(psycopg.errors.CheckViolation):
        service.submit("monthly_sales", "2026-01-01", "2027-01-01", known_customer[0])


def test_transaction_rollback_has_no_orphan_job(known_customer):
    key = uuid.uuid4()
    with service.connect() as conn:
        before = conn.execute(
            "SELECT count(*) AS n FROM message WHERE msg_key IS NOT NULL"
        ).fetchone()["n"]
        owner = conn.execute(
            "SELECT user_id FROM app_user WHERE username='sysadmin'"
        ).fetchone()["user_id"]
        with pytest.raises(RuntimeError), conn.transaction():
            conn.execute(
                "CALL reporting.submit_run(%s,'customer_statement',%s,'2026-01-01','2027-01-01',10,false,%s,NULL)",
                (key, known_customer[0], owner),
            )
            raise RuntimeError("Controlled failure before commit")
        assert (
            conn.execute(
                "SELECT 1 FROM reporting.report_run WHERE submission_key=%s", (key,)
            ).fetchone()
            is None
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM message WHERE msg_key IS NOT NULL"
            ).fetchone()["n"]
            == before
        )


def test_idempotent_submission_and_conflicting_parameters(known_customer):
    key = uuid.uuid4()
    run = service.submit(
        "customer_statement",
        "2026-01-01",
        "2027-01-01",
        known_customer[0],
        submission_key=key,
    )
    assert (
        service.submit(
            "customer_statement",
            "2026-01-01",
            "2027-01-01",
            known_customer[0],
            submission_key=key,
        )
        == run
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        service.submit(
            "customer_statement",
            "2026-01-01",
            "2026-03-01",
            known_customer[0],
            submission_key=key,
        )
    drain()
    assert service.progress(run)["expected"] == 1


def test_replay_survives_source_edit(known_customer):
    customer, order, _ = known_customer
    old = service.submit("customer_statement", "2026-01-01", "2027-01-01", customer)
    drain()
    original = service.replay(request_for(old))
    with service.connect() as conn:
        conn.execute(
            "UPDATE reporting.order_item SET unit_price=unit_price+1 WHERE order_id=%s AND line_number=1",
            (order,),
        )
    assert service.replay(request_for(old)) == original
    fresh = service.submit("customer_statement", "2026-01-01", "2027-01-01", customer)
    drain()
    assert service.replay(request_for(fresh))["rows"][0]["statement_total"] == 49.5
    with service.connect() as conn:
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "UPDATE reporting.report_dataset SET rows='[]' WHERE request_id=%s",
                (request_for(old),),
            )


def test_summary_and_bulk_counts():
    first = service.submit("product_sales", "2026-01-01", "2027-01-01", top_n=3)
    second = service.submit("monthly_sales", "2026-01-01", "2027-01-01")
    bulk = service.submit("customer_statement", "2026-01-01", "2027-01-01", bulk=True)
    drain()
    assert len(service.replay(request_for(first))["rows"]) <= 3
    rows = service.replay(request_for(second))["rows"]
    with service.connect() as conn:
        total = conn.execute(
            "SELECT sum(line_total) AS n FROM reporting.v_sales_lines"
        ).fetchone()["n"]
        customers = conn.execute(
            "SELECT count(*) AS n FROM reporting.customer"
        ).fetchone()["n"]
    assert Decimal(str(rows[-1]["running_sales"])) == total
    status = service.progress(bulk)
    assert status["expected"] == status["completed"] == customers
    assert status["queued"] == status["processing"] == status["failed"] == 0


def test_duplicate_delivery_after_publication(known_customer, monkeypatch):
    run = service.submit(
        "customer_statement", "2026-01-01", "2027-01-01", known_customer[0]
    )
    with service.connect() as conn:
        worker.prepare(
            conn, worker.claim(conn, "report-preparers", "report-prepare", 30)
        )
        message = worker.claim(conn, "report-workers", "report-render", 30)

        def crash(*args, **kwargs):
            raise RuntimeError("Crash after files, before database publication")

        with monkeypatch.context() as context:
            context.setattr(worker, "settle", crash)
            with pytest.raises(RuntimeError):
                worker.render(conn, message, "crash-worker")
        request = request_for(run)
        assert (
            conn.execute(
                "SELECT 1 FROM reporting.report_result WHERE request_id=%s", (request,)
            ).fetchone()
            is None
        )
        worker.render(conn, message, "recovery-worker")
        worker.render(conn, message, "duplicate-worker")
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM reporting.report_result WHERE request_id=%s",
                (request,),
            ).fetchone()["n"]
            == 1
        )
        assert service.progress(run)["completed"] == 1


def test_poison_uuid_job_is_dead_lettered():
    from psycopg.types.json import Jsonb

    marker = "poison-" + uuid.uuid4().hex
    with service.connect() as conn:
        app = conn.execute(
            "SELECT app_id FROM application WHERE app_name='reporting-service'"
        ).fetchone()["app_id"]
        conn.execute(
            "SELECT * FROM produce(%s,%s,%s,%s,%s)",
            (
                "report-render",
                marker,
                Jsonb({"request_id": "not-a-uuid"}),
                app,
                uuid.uuid4().int & ((1 << 62) - 1),
            ),
        )
    drain()
    with service.connect() as conn:
        dead = conn.execute(
            "SELECT attempts FROM dead_letter_message WHERE msg_key=%s", (marker,)
        ).fetchone()
        assert dead["attempts"] == 3


def test_failed_render_reaches_dlq(known_customer, monkeypatch):
    run = service.submit(
        "customer_statement", "2026-01-01", "2027-01-01", known_customer[0]
    )
    with monkeypatch.context() as context:

        def broken(*args):
            raise OSError("Controlled output destination failure")

        context.setattr(worker, "publish", broken)
        drain()
    request = request_for(run)
    assert service.progress(run)["failed"] == 1
    with service.connect() as conn:
        dead = conn.execute(
            "SELECT * FROM dead_letter_message WHERE msg_key=%s AND status='pending'",
            (str(request),),
        ).fetchone()
        assert dead["attempts"] == 3
        conn.execute(
            "SELECT * FROM requeue_dlq(%s,(SELECT app_id FROM application WHERE app_name='reporting-service'),NULL)",
            (dead["dlq_id"],),
        )
        conn.execute(
            "UPDATE reporting.report_request SET state='queued' WHERE request_id=%s",
            (request,),
        )
    drain()
    assert service.progress(run)["completed"] == 1
