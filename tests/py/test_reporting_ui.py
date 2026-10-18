"""Reporting page contracts and actual HTML-form submission against the local API."""

import os
import re
import time
import uuid

import httpx
import pytest

API = os.environ.get("CONDUIT_API_URL", "http://127.0.0.1:8000")


@pytest.fixture
def session_client():
    with httpx.Client(base_url=API, timeout=20) as client:
        assert (
            client.post(
                "/web/login", data={"username": "admin", "password": "Conduit@123"}
            ).status_code
            == 303
        )
        yield client


def form_key(client):
    response = client.get("/reports/new")
    assert response.status_code == 200
    return re.search(r'name="submission_key" value="([^"]+)"', response.text).group(1)


def test_report_pages_require_session():
    with httpx.Client(base_url=API) as client:
        for path in (
            "/reports",
            "/reports/new",
            "/data",
            "/reports/runs/" + str(uuid.uuid4()),
        ):
            assert client.get(path).status_code == 303
        assert client.get("/web/report-customers").status_code == 401


def test_workspace_data_filters_and_guardrails(session_client):
    client = session_client
    assert "<h1>Reports</h1>" in client.get("/").text
    assert "No matching reports" in client.get("/?q=there-is-no-such-report").text
    fragment = client.get("/fragments/report-runs")
    assert fragment.status_code == 200 and 'hx-swap-oob="outerHTML"' in fragment.text
    for table in ("customers", "products", "orders", "order-items"):
        response = client.get("/data", params={"table": table})
        assert response.status_code == 200 and "Read only" in response.text
    assert client.get("/data?table=not-a-table").status_code == 422
    assert client.get("/data?page=0").status_code == 422
    assert client.get("/reports/runs/" + str(uuid.uuid4())).status_code == 404
    assert client.get("/web/report-customers?limit=1000").status_code == 422


def test_form_error_is_visible_and_preserves_values(session_client):
    response = session_client.post(
        "/web/reports",
        data={
            "template": "monthly_sales",
            "start": "2027-01-01",
            "end": "2026-01-01",
            "submission_key": form_key(session_client),
        },
    )
    assert response.status_code == 422
    assert (
        'role="alert"' in response.text
        and "Date range must be increasing" in response.text
    )
    assert 'value="2027-01-01"' in response.text


def test_sql_workspace_renders_database_types_and_escaped_text(session_client):
    response = session_client.post(
        "/web/sql",
        data={
            "query": "SELECT 12.50::numeric AS amount, DATE '2026-01-01' AS day, now() AS recorded, gen_random_uuid() AS reference, NULL AS missing, '<script>alert(1)</script>' AS label"
        },
    )
    assert response.status_code == 200
    assert "12.50" in response.text and "2026-01-01" in response.text
    assert "NULL" in response.text and "&lt;script&gt;" in response.text
    assert "<script>alert" not in response.text
    for query in (
        "SELECT category,sum(line_total) AS sales FROM reporting.v_sales_lines GROUP BY category",
        "SELECT * FROM reporting.v_sales_lines LIMIT 2",
        "SELECT * FROM reporting.v_run_progress LIMIT 2",
    ):
        assert session_client.post("/web/sql", data={"query": query}).status_code == 200


def test_form_submission_run_inspector_and_idempotency(session_client):
    client = session_client
    data = {
        "template": "monthly_sales",
        "start": "2026-01-01",
        "end": "2027-01-01",
        "submission_key": form_key(client),
    }
    response = client.post("/web/reports", data=data)
    assert response.status_code == 303
    location = response.headers["location"]
    assert client.post("/web/reports", data=data).headers["location"] == location
    run = location.rsplit("/", 1)[1]
    for _ in range(60):
        status = client.get("/api/reports/runs/" + run).json()
        if status["completed"] == 1:
            break
        time.sleep(0.2)
    assert status["completed"] == 1
    request = client.get("/api/reports/runs/" + run + "/requests").json()[0][
        "request_id"
    ]
    assert "100%" in client.get(location).text
    for view, label in [
        ("preview", "Saved result data"),
        ("sql", "Bound parameters"),
        ("history", "State changes recorded automatically"),
    ]:
        response = client.get("/reports/requests/" + request, params={"view": view})
        assert response.status_code == 200 and label in response.text
    assert (
        client.get("/api/reports/requests/" + request + "/download/csv").status_code
        == 200
    )
