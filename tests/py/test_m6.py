import uuid

import httpx
import pytest

API = "http://localhost:8000"
ADMIN_TOKEN = "conduit-admin-token"
ADMIN = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture(scope="session")
def api():
    with httpx.Client(base_url=API, timeout=30, follow_redirects=False) as client:
        yield client


@pytest.fixture(scope="session")
def admin_session(api):
    r = api.post("/web/login", data={"mode": "admin", "token": ADMIN_TOKEN})
    assert r.status_code == 303
    cookie = r.cookies.get("conduit_session")
    assert cookie == ADMIN_TOKEN
    return {"Cookie": f"conduit_session={cookie}"}


@pytest.fixture(scope="session")
def app_env(api):
    sfx = uuid.uuid4().hex[:8]
    user = f"m6user{sfx}"
    topic = f"m6topic{sfx}"
    group = f"m6group{sfx}"
    r = api.post(
        "/api/admin/users",
        headers=ADMIN,
        json={"username": user, "email": f"{user}@conduit.io", "role": "producer"},
    )
    assert r.status_code == 200
    r = api.post(
        "/api/admin/apps",
        headers=ADMIN,
        json={"app_name": f"m6app{sfx}", "owner_username": user, "app_type": "both"},
    )
    api_key = r.json()["api_key"]
    r = api.post(
        "/api/admin/topics",
        headers=ADMIN,
        json={"name": topic, "partitions": 2, "owner_username": user, "schema": {"required": ["event"]}},
    )
    assert r.status_code == 200
    for at in ("produce", "consume"):
        api.post(
            "/api/admin/access/grant",
            headers=ADMIN,
            json={"username": user, "topic": topic, "access_type": at, "granted_by": user},
        )
    api.post("/api/admin/groups", headers=ADMIN, json={"name": group, "created_by_username": user})
    api.post(f"/api/admin/groups/{group}/subscribe", headers=ADMIN, json={"topic": topic})
    return {"user": user, "topic": topic, "group": group, "api_key": api_key}


@pytest.fixture(scope="session")
def app_session(api, app_env):
    r = api.post("/web/login", data={"mode": "app", "token": app_env["api_key"]})
    assert r.status_code == 303
    cookie = r.cookies.get("conduit_session")
    assert cookie == app_env["api_key"]
    return {"Cookie": f"conduit_session={cookie}"}


def test_login_page(api):
    assert api.get("/web/login").status_code == 200
    r = api.post("/web/login", data={"mode": "admin", "token": "wrong"})
    assert r.status_code == 401
    r = api.post("/web/login", data={"mode": "app", "token": "not-a-uuid"})
    assert r.status_code == 401


def test_pages_redirect_without_session(api):
    for path in ("/", "/messages", "/playground", "/topics", "/groups", "/audit", "/dlq", "/admin", "/sql"):
        r = api.get(path)
        assert r.status_code == 303, path
        assert "/web/login" in r.headers["location"]


def test_admin_pages_render(api, admin_session):
    for path in ("/", "/messages", "/playground", "/topics", "/groups", "/audit", "/dlq", "/admin", "/sql"):
        r = api.get(path, headers=admin_session)
        assert r.status_code == 200, path
        assert "Conduit" in r.text
    assert 'data-mode="admin"' in api.get("/", headers=admin_session).text


def test_app_pages_render(api, app_session):
    for path in ("/", "/messages", "/playground", "/topics", "/groups", "/audit", "/dlq"):
        r = api.get(path, headers=app_session)
        assert r.status_code == 200, path
    assert api.get("/admin", headers=app_session).status_code == 403
    assert api.get("/sql", headers=app_session).status_code == 403


def test_fragments(api, admin_session, app_session, app_env):
    r = api.get(f"/fragments/messages?topic={app_env['topic']}", headers=admin_session)
    assert r.status_code == 200 and "messages-table" in r.text
    r = api.get(f"/fragments/messages?topic={app_env['topic']}", headers=app_session)
    assert r.status_code == 200
    for frag in ("/fragments/stats", "/fragments/lag", "/fragments/audit", "/fragments/dlq"):
        assert api.get(frag, headers=admin_session).status_code == 200
    with httpx.Client(base_url=API, timeout=10) as clean:
        assert clean.get("/fragments/stats").status_code == 401


def test_cookie_auth_on_json_api(api, app_session, admin_session):
    assert api.get("/api/dashboard", headers=app_session).status_code == 200
    assert api.get("/api/dashboard", headers=admin_session).status_code == 200
    assert api.get("/api/admin/users", headers=admin_session).status_code == 200
    assert api.get("/api/me", headers=app_session).status_code == 200


def test_playground_flow_via_cookies(api, app_session, app_env):
    r = api.post(
        "/api/produce",
        headers=app_session,
        json={"topic": app_env["topic"], "payload": {"event": "m6"}, "seq": 1},
    )
    assert r.status_code == 200
    r = api.post(
        "/api/consume",
        headers=app_session,
        json={"group": app_env["group"], "topic": app_env["topic"], "batch": 5},
    )
    body = r.json()
    assert r.status_code == 200 and len(body["messages"]) == 1
    r = api.post(
        "/api/ack", headers=app_session, json={"group": app_env["group"], "locations": body["locations"]}
    )
    assert r.json()["acked"] == 1
    r = api.get(
        f"/fragments/messages?topic={app_env['topic']}&status=delivered", headers=app_session
    )
    assert "delivered" in r.text


def test_web_sql_console(api, admin_session):
    r = api.post("/web/sql", headers=admin_session, data={"query": "SELECT count(*) AS c FROM message"})
    assert r.status_code == 200
    assert "table" in r.text
    r = api.post("/web/sql", headers=admin_session, data={"query": "DELETE FROM message"})
    assert r.status_code == 400
    with httpx.Client(base_url=API, timeout=10) as clean:
        assert clean.post("/web/sql", data={"query": "SELECT 1"}).status_code == 401


def test_sse_requires_session():
    with httpx.Client(base_url=API, timeout=10) as clean:
        assert clean.get("/api/events").status_code == 401


def test_logout(api, admin_session):
    assert api.get("/web/logout", headers=admin_session).status_code == 303
