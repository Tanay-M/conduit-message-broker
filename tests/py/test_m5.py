import threading
import time
import uuid

import httpx
import pytest
import conduit

API = "http://localhost:8000"
ADMIN = {"Authorization": "Bearer conduit-admin-token"}
DB_DSN = "postgresql://conduit_app:conduit_app_dev@db:5432/conduit"


@pytest.fixture(scope="session")
def api():
    with httpx.Client(base_url=API, timeout=30) as client:
        yield client


@pytest.fixture(scope="session")
def env(api):
    sfx = uuid.uuid4().hex[:8]
    user = f"m5user{sfx}"
    nogrants_user = f"m5nog{sfx}"
    app_name = f"m5app{sfx}"
    nogrants_app = f"m5nogapp{sfx}"
    topic = f"m5topic{sfx}"
    group = f"m5group{sfx}"

    r = api.post(
        "/api/admin/users",
        headers=ADMIN,
        json={"username": user, "email": f"{user}@conduit.io", "role": "producer"},
    )
    assert r.status_code == 200
    r = api.post(
        "/api/admin/users",
        headers=ADMIN,
        json={"username": nogrants_user, "email": f"{nogrants_user}@conduit.io", "role": "viewer"},
    )
    assert r.status_code == 200

    r = api.post(
        "/api/admin/apps",
        headers=ADMIN,
        json={"app_name": app_name, "owner_username": user, "app_type": "both"},
    )
    assert r.status_code == 200
    api_key = r.json()["api_key"]

    r = api.post(
        "/api/admin/apps",
        headers=ADMIN,
        json={"app_name": nogrants_app, "owner_username": nogrants_user, "app_type": "both"},
    )
    assert r.status_code == 200
    nogrants_key = r.json()["api_key"]

    r = api.post(
        "/api/admin/topics",
        headers=ADMIN,
        json={
            "name": topic,
            "partitions": 2,
            "schema": {"required": ["event"]},
            "owner_username": user,
            "description": "m5 test topic",
        },
    )
    assert r.status_code == 200

    for access_type in ("produce", "consume"):
        r = api.post(
            "/api/admin/access/grant",
            headers=ADMIN,
            json={"username": user, "topic": topic, "access_type": access_type, "granted_by": user},
        )
        assert r.status_code == 200

    r = api.post(
        "/api/admin/groups",
        headers=ADMIN,
        json={"name": group, "created_by_username": user},
    )
    assert r.status_code == 200
    r = api.post(
        f"/api/admin/groups/{group}/subscribe", headers=ADMIN, json={"topic": topic}
    )
    assert r.status_code == 200

    return {
        "user": user,
        "topic": topic,
        "group": group,
        "api_key": api_key,
        "nogrants_key": nogrants_key,
    }


def test_health(api):
    r = api.get("/health")
    assert r.status_code == 200


def test_admin_requires_token(api):
    assert api.get("/api/admin/users").status_code == 401
    assert (
        api.get("/api/admin/users", headers={"Authorization": "Bearer wrong-token"}).status_code
        == 403
    )


def test_unknown_api_key(api):
    r = api.get("/api/me", headers={"Authorization": f"Bearer {uuid.uuid4()}"})
    assert r.status_code == 401


def test_sdk_roundtrip_and_idempotency(env):
    c = conduit.Conduit(env["api_key"], dsn=DB_DSN)
    try:
        loc = c.produce(env["topic"], {"event": "sdk"}, 1, key="k1")
        assert loc["duplicate"] is False
        assert loc["msg_offset"] == 0

        dup = c.produce(env["topic"], {"event": "sdk"}, 1, key="k1")
        assert dup["duplicate"] is True
        assert dup["msg_offset"] == loc["msg_offset"]
        assert dup["partition_id"] == loc["partition_id"]

        msgs = c.consume(env["group"], env["topic"], 5)
        assert len(msgs) == 1
        assert msgs[0]["payload"]["event"] == "sdk"
        assert msgs[0]["location"]["msg_offset"] == loc["msg_offset"]

        assert c.ack(env["group"], [msgs[0]["location"]]) == 1

        topics = c.accessible_topics()
        assert any(t["topic_name"] == env["topic"] for t in topics)
    finally:
        c.close()


def test_api_roundtrip(api, env):
    h = {"Authorization": f"Bearer {env['api_key']}"}
    r = api.post(
        "/api/produce",
        headers=h,
        json={"topic": env["topic"], "payload": {"event": "api"}, "seq": 2},
    )
    assert r.status_code == 200
    assert r.json()["duplicate"] is False

    r = api.post(
        "/api/consume", headers=h, json={"group": env["group"], "topic": env["topic"], "batch": 5}
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["messages"]) == 1

    r = api.post(
        "/api/ack", headers=h, json={"group": env["group"], "locations": body["locations"]}
    )
    assert r.json()["acked"] == 1


def test_error_mapping_schema_violation(api, env):
    h = {"Authorization": f"Bearer {env['api_key']}"}
    r = api.post(
        "/api/produce",
        headers=h,
        json={"topic": env["topic"], "payload": {"nope": True}, "seq": 3},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "CDT04"


def test_rls_visibility(api, env):
    h_no = {"Authorization": f"Bearer {env['nogrants_key']}"}
    h_yes = {"Authorization": f"Bearer {env['api_key']}"}
    r = api.get(f"/api/messages?topic={env['topic']}", headers=h_no)
    assert r.status_code == 200
    assert r.json() == []
    r = api.get(f"/api/messages?topic={env['topic']}", headers=h_yes)
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_monitoring_endpoints(api, env):
    h = {"Authorization": f"Bearer {env['api_key']}"}
    assert api.get("/api/dashboard", headers=h).status_code == 200
    assert api.get("/api/lag", headers=h).status_code == 200
    assert api.get("/api/throughput", headers=h).status_code == 200
    r = api.get("/api/admin/audit?event_type=PRODUCE&limit=5", headers=ADMIN)
    assert r.status_code == 200
    assert all(row["event_type"] == "PRODUCE" for row in r.json())
    assert api.get("/api/audit", headers=h).status_code == 404


def test_sql_console(api):
    r = api.post("/api/admin/sql", headers=ADMIN, json={"query": "SELECT count(*) AS c FROM message"})
    assert r.status_code == 200
    assert r.json()["columns"] == ["c"]

    r = api.post(
        "/api/admin/sql", headers=ADMIN, json={"query": "UPDATE topic SET status = 'archived'"}
    )
    assert r.status_code == 400

    r = api.post("/api/admin/sql", json={"query": "SELECT 1"})
    assert r.status_code == 401


def test_sse_notification(api, env):
    c = conduit.Conduit(env["api_key"], dsn=DB_DSN)
    received = []
    try:
        t = threading.Thread(
            target=lambda: (time.sleep(1.5), c.produce(env["topic"], {"event": "sse"}, 99))
        )
        t.start()
        try:
            with api.stream("GET", "/api/events", headers=ADMIN, timeout=20) as r:
                assert r.status_code == 200
                for line in r.iter_lines():
                    if line.startswith("data:") and "PRODUCE" in line:
                        received.append(line)
                        break
        finally:
            t.join()
    finally:
        c.close()
    assert received
