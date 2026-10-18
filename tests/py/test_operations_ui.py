"""Real authenticated final-review pages/forms against the running local server."""

import os
import re
import uuid

import httpx
import pytest

API = os.environ.get("CONDUIT_API_URL", "http://127.0.0.1:8000")


@pytest.fixture
def client():
    with httpx.Client(base_url=API, timeout=30) as c:
        assert (
            c.post(
                "/web/login", data={"username": "admin", "password": "Conduit@123"}
            ).status_code
            == 303
        )
        yield c


def test_operations_pages_require_login():
    with httpx.Client(base_url=API) as c:
        for path in (
            "/inventory",
            "/imports",
            "/analysis",
            "/assistant",
            "/imports/sample.csv",
        ):
            assert c.get(path).status_code == 303
        assert c.post("/web/inventory/post", data={}).status_code == 303


def test_inventory_forms_and_cross_origin_guard(client):
    assert client.get("/inventory").status_code == 200
    reference = "HTTP-" + uuid.uuid4().hex[:12]
    response = client.post(
        "/web/inventory/post",
        data={
            "sku": "SKU-1",
            "kind": "receipt",
            "quantity": 2,
            "reference": reference,
            "posted_on": "2026-10-01",
        },
    )
    assert response.status_code == 303
    assert reference in client.get("/inventory").text
    response = client.post(
        "/web/inventory/post",
        data={
            "sku": "SKU-1",
            "kind": "sale",
            "quantity": 1000000,
            "reference": reference + "-FAIL",
            "customer_ref": "DEMO-000001",
            "unit_price": "25",
            "posted_on": "2026-10-01",
        },
    )
    assert response.status_code == 422 and "Insufficient stock" in response.text
    assert (
        client.post(
            "/web/inventory/reorder",
            headers={"Origin": "https://unrelated.example"},
            data={"sku": "SKU-1", "reorder_level": 10},
        ).status_code
        == 403
    )


def test_import_preview_commit_duplicate_and_escaped_filename(client):
    reference = "HTTP-IMPORT-" + uuid.uuid4().hex[:10]
    data = (
        "OrderNo,ClientCode,OrderDate,LineNo,ItemCode,Qty,Rate\n"
        + reference
        + ",DEMO-000001,2026-02-01,1,SKU-1,1,25\n"
        + reference
        + "-BAD,DEMO-000001,2026-02-01,1,SKU-1,1,-1\n"
    )
    response = client.post(
        "/web/imports", files={"file": ("<script>.csv", data.encode(), "text/csv")}
    )
    assert response.status_code == 303
    location = response.headers["location"]
    key = location.rsplit("/", 1)[1]
    preview = client.get(location)
    assert preview.status_code == 200 and "Quarantined lines" in preview.text
    assert "&lt;script&gt;.csv" in preview.text and "<h1><script>" not in preview.text
    assert client.post("/web/imports/" + key + "/commit").status_code == 303
    assert "imported" in client.get(location).text
    assert client.post("/web/imports/" + key + "/commit").status_code == 303
    assert (
        client.get("/imports/sample.csv").headers["content-type"].startswith("text/csv")
    )


def test_assistant_preview_execution_and_analysis(client):
    response = client.post(
        "/web/assistant/plan",
        data={"prompt": "top 5 products by revenue in February 2026"},
    )
    assert response.status_code == 200 and "Local rule parser (not AI)" in response.text
    path = re.search(r'action="(/web/assistant/[a-f0-9-]+/execute)"', response.text)[1]
    result = client.post(path)
    assert result.status_code == 200 and "Query result" in result.text
    report_path = path.removesuffix("/execute") + "/report"
    queued = client.post(report_path)
    assert queued.status_code == 303 and "/reports/runs/" in queued.headers["location"]
    assert client.post(report_path).headers["location"] == queued.headers["location"]
    assert (
        client.post("/web/assistant/plan", data={"prompt": "drop tables"}).status_code
        == 422
    )
    response = client.post(
        "/web/analysis", data={"start": "2026-01-01", "end": "2027-01-01"}
    )
    assert (
        response.status_code == 200
        and "SQL facts and deterministic explanation" in response.text
    )
    assert "Monthly comparison" in response.text and "SQL evidence" in response.text
