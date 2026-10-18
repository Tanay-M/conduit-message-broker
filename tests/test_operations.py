"""Database integrity tests for final-review retail workflows, on a disposable DB."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import httpx
import psycopg
import pytest
from psycopg import sql

from reporting import ai, analysis, assistant, imports, inventory, service
from reporting.local import migrate
from reporting.seed import seed
from reporting.settings import settings


@pytest.fixture(scope="module", autouse=True)
def database():
    original = settings.admin_dsn
    name = "conduit_operations_" + uuid.uuid4().hex[:10]
    with psycopg.connect(original, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    settings.admin_dsn = original.rsplit("/", 1)[0] + "/" + name
    try:
        migrate()
        seed(4, 2)
        yield
    finally:
        settings.admin_dsn = original
        with psycopg.connect(original, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (name,),
            )
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def test_stock_atomic_sale_rejection_and_reference():
    inventory.post("SKU-1", "receipt", 50, "TEST-RECEIVE", actor="tester")
    movement = inventory.post(
        "SKU-1",
        "sale",
        7,
        "TEST-SALE",
        actor="tester",
        customer_ref="DEMO-000001",
        unit_price="12.50",
        posted_on="2026-10-01",
    )
    assert (
        inventory.post(
            "SKU-1",
            "sale",
            7,
            "TEST-SALE",
            actor="tester",
            customer_ref="DEMO-000001",
            unit_price="12.50",
            posted_on="2026-10-01",
        )
        == movement
    )
    with pytest.raises(psycopg.errors.CheckViolation, match="Insufficient stock"):
        inventory.post(
            "SKU-1",
            "sale",
            45,
            "TEST-OVERSELL",
            actor="tester",
            customer_ref="DEMO-000001",
            unit_price="12.50",
        )
    with pytest.raises(psycopg.errors.UniqueViolation):
        inventory.post("SKU-1", "receipt", 51, "TEST-RECEIVE", actor="tester")
    with service.connect() as conn:
        row = conn.execute(
            "SELECT * FROM reporting.v_inventory WHERE sku='SKU-1'"
        ).fetchone()
        assert (
            row["quantity"] == 43 and row["ledger_quantity"] == 43 and row["reconciled"]
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM reporting.sales_order WHERE order_ref='STOCK-TEST-OVERSELL'"
            ).fetchone()["n"]
            == 0
        )
        assert conn.execute(
            "SELECT sum(line_total) AS n FROM reporting.v_sales_lines WHERE order_ref='STOCK-TEST-SALE'"
        ).fetchone()["n"] == Decimal("87.50")
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "UPDATE reporting.stock_movement SET note=note WHERE movement_id=%s",
                (movement,),
            )


def test_concurrent_stock_sales_do_not_oversell():
    inventory.post("SKU-2", "receipt", 10, "RACE-OPEN", actor="tester")

    def sell(i):
        try:
            inventory.post(
                "SKU-2",
                "sale",
                7,
                "RACE-" + str(i),
                actor="tester",
                customer_ref="DEMO-000001",
                unit_price="1.00",
            )
            return True
        except psycopg.errors.CheckViolation:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(sell, [1, 2]))
    assert sorted(outcomes) == [False, True]
    with service.connect() as conn:
        row = conn.execute(
            "SELECT * FROM reporting.v_inventory WHERE sku='SKU-2'"
        ).fetchone()
        assert row["quantity"] == 3 and row["reconciled"]


HEADER = "OrderNo,ClientCode,OrderDate,LineNo,ItemCode,Qty,Rate\n"


def test_import_whole_order_quarantine_and_duplicate_retry():
    text = (
        HEADER
        + "IMPORT-GOOD,DEMO-000001,2026-02-01,1,SKU-1,2,12.50\nIMPORT-BAD,DEMO-000001,2026-02-01,1,SKU-1,1,25\nIMPORT-BAD,DEMO-000001,2026-02-01,2,SKU-2,1,-1\n"
    )
    key = imports.stage(text.encode(), "orders.csv")
    before = imports.detail(key)
    assert before["counts"]["valid"] == 1 and before["counts"]["rejected"] == 2
    imports.commit(key)
    imports.commit(key)
    assert imports.detail(key)["counts"] == {
        "valid": 0,
        "rejected": 2,
        "imported": 1,
        "duplicate": 0,
    }
    retry = imports.stage(text.encode(), "retry.csv")
    imports.commit(retry)
    assert imports.detail(retry)["counts"]["duplicate"] == 1
    with service.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM reporting.sales_order WHERE order_ref='IMPORT-GOOD'"
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM reporting.sales_order WHERE order_ref='IMPORT-BAD'"
            ).fetchone()["n"]
            == 0
        )
    conflicting = imports.stage(
        (HEADER + "IMPORT-GOOD,DEMO-000001,2026-02-01,1,SKU-1,3,12.50\n").encode(),
        "conflict.csv",
    )
    assert imports.detail(conflicting)["counts"]["rejected"] == 1


def test_manual_mapping_and_commit_revalidation():
    text = "A,B,C,D,E,F,G\nMAPPED,DEMO-000001,2026-03-01,1,SKU-1,1,25\n"
    key = imports.stage(text.encode(), "different.csv")
    assert imports.detail(key)["counts"]["rejected"] == 1
    imports.remap(key, dict(zip(imports.FIELDS, "ABCDEFG")))
    assert imports.detail(key)["counts"]["valid"] == 1
    # Simulate another actor inserting conflicting content after preview.
    other = imports.stage(
        (HEADER + "MAPPED,DEMO-000001,2026-03-01,1,SKU-1,2,25\n").encode(), "other.csv"
    )
    imports.commit(other)
    imports.commit(key)
    assert imports.detail(key)["counts"]["rejected"] == 1


def test_import_rejects_bad_shapes_and_nonfinite_prices():
    for content in (b"", b"A,A\n1,2\n", b"A,B\n1\n", b"x" * 2_000_001):
        with pytest.raises(ValueError):
            imports.stage(content, "bad.csv")
    for price in ("NaN", "Infinity", "0.001"):
        key = imports.stage(
            (
                HEADER + f"PRICE-{price},DEMO-000001,2026-02-01,1,SKU-1,1,{price}\n"
            ).encode(),
            "price.csv",
        )
        assert imports.detail(key)["counts"]["rejected"] == 1


def test_approved_natural_language_queries_and_ai_boundary(monkeypatch):
    record = assistant.plan("Top 5 products by revenue in February 2026")
    assert record["interpretation"]["start"] == "2026-02-01"
    result = assistant.execute(record["request_id"])
    assert len(result["rows"]) <= 5 and "sales" in result["columns"]
    queued = assistant.queue_report(record["request_id"])
    assert assistant.queue_report(record["request_id"]) == queued
    assert (
        assistant.execute(assistant.plan("Show low stock")["request_id"])["columns"][0]
        == "sku"
    )
    assert assistant.execute(
        assistant.plan("Statement for DEMO-000001 in 2026")["request_id"]
    )["rows"]
    with pytest.raises(ValueError):
        assistant.plan("drop all tables")
    with pytest.raises(ValueError):
        assistant.plan("top 5 products by profit")
    with pytest.raises(ValueError):
        assistant.plan("statement for UNKNOWN in 2026")
    monkeypatch.setattr(
        ai,
        "structured",
        lambda *args: {
            "kind": "monthly_sales",
            "start": "2026-01-01",
            "end": "2027-01-01",
            "top_n": 10,
            "customer_ref": None,
            "sql": "DROP TABLE reporting.product",
        },
    )
    with pytest.raises(ValueError):
        assistant.plan("monthly sales", use_ai=True)


def test_analysis_facts_calendar_and_saved_evidence():
    result = analysis.run("2026-01-01", "2027-01-01")
    assert len(result["facts"]["months"]) == 12
    assert Decimal(str(result["facts"]["totals"]["revenue"])) == sum(
        Decimal(str(r["revenue"])) for r in result["facts"]["categories"]
    )
    assert result["source"].startswith("SQL facts")
    with service.connect() as conn:
        row = conn.execute(
            "SELECT * FROM reporting.analysis_run WHERE analysis_id=%s",
            (result["analysis_id"],),
        ).fetchone()
        assert (
            row["facts"] == result["facts"] and row["narrative"] == result["narrative"]
        )


def test_analysis_decline_rule_and_partial_month_guard():
    content = (
        HEADER
        + "DECLINE-JAN,DEMO-000001,2025-01-20,1,SKU-1,1,1000\nDECLINE-FEB,DEMO-000001,2025-02-20,1,SKU-1,1,600\n"
    )
    batch = imports.stage(content.encode(), "decline.csv")
    imports.commit(batch)
    result = analysis.run("2025-01-01", "2025-03-01")
    assert len(result["facts"]["alerts"]) == 1
    assert Decimal(result["facts"]["alerts"][0]["change_percent"]) == -40
    assert analysis.run("2025-01-15", "2025-03-01")["facts"]["alerts"] == []


def test_ai_mapping_and_intent_validation(monkeypatch):
    mapping = dict(
        zip(
            imports.FIELDS,
            ("OrderNo", "ClientCode", "OrderDate", "LineNo", "ItemCode", "Qty", "Rate"),
        )
    )
    monkeypatch.setattr(ai, "structured", lambda *args: mapping)
    batch = imports.stage(
        (HEADER + "AI-IMPORT,DEMO-000001,2026-02-01,1,SKU-1,1,25\n").encode(),
        "ai.csv",
        use_ai=True,
    )
    assert imports.detail(batch)["counts"]["valid"] == 1
    monkeypatch.setattr(
        ai, "structured", lambda *args: {**mapping, "sql": "DROP TABLE something"}
    )
    with pytest.raises(ValueError):
        imports.stage(
            (HEADER + "A,B,C,D,E,F,G\n").encode(), "invalid-ai.csv", use_ai=True
        )
    monkeypatch.setattr(
        ai,
        "structured",
        lambda *args: {
            "kind": "monthly_sales",
            "start": "2026-01-01",
            "end": "2027-01-01",
            "top_n": 10,
            "customer_ref": None,
        },
    )
    record = assistant.plan("monthly sales", use_ai=True)
    assert (
        record["source"] == "Gemini AI"
        and assistant.execute(record["request_id"])["rows"]
    )


def test_gemini_adapter_success_and_failure_without_live_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(ai.AIUnavailable):
        ai.structured("test", {}, {})
    monkeypatch.setattr(settings, "gemini_api_key", "test-only-not-a-real-key")

    def handler(request):
        assert request.headers["x-goog-api-key"] == "test-only-not-a-real-key"
        assert "test-only" not in str(request.url)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": '{"summary":"test"}'}]}}]
            },
        )

    original = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert ai.structured("test", {}, {}) == {"summary": "test"}
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(429, text="private provider details")
            ),
            **kwargs,
        ),
    )
    with pytest.raises(ai.AIUnavailable) as error:
        ai.structured("test", {}, {})
    assert "private provider details" not in str(error.value)
