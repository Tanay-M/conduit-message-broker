"""Exercise password login, database-backed sessions and the reporting-only shell."""

import hashlib
import os
import uuid

import httpx
import pytest

from reporting import service
from server.app.web_sessions import password_hash

API = os.environ.get("CONDUIT_API_URL", "http://127.0.0.1:8000")


@pytest.fixture
def account():
    username = "login-test-" + uuid.uuid4().hex[:12]
    password = "Example-login!567"
    with service.connect() as conn:
        row = conn.execute(
            "INSERT INTO reporting.web_account(username,password_hash) VALUES (%s,%s) RETURNING account_id,password_hash",
            (username, password_hash(password)),
        ).fetchone()
    try:
        yield {**row, "username": username, "password": password}
    finally:
        with service.connect() as conn:
            conn.execute(
                "DELETE FROM reporting.web_account WHERE account_id=%s",
                (row["account_id"],),
            )


def sign_in(client, account):
    response = client.post(
        "/web/login",
        data={"username": account["username"], "password": account["password"]},
    )
    assert response.status_code == 303
    return response


def test_simple_login_form_and_invalid_credentials():
    with httpx.Client(base_url=API) as client:
        page = client.get("/web/login").text
        assert 'name="username"' in page and 'name="password"' in page
        assert (
            'name="mode"' not in page
            and "Admin token" not in page
            and "api key" not in page.lower()
        )
        for username in ("admin", "unknown-user"):
            response = client.post(
                "/web/login", data={"username": username, "password": "wrong-password"}
            )
            assert (
                response.status_code == 401
                and "Incorrect username or password." in response.text
            )
            assert 'value="' + username + '"' in response.text
            assert "wrong-password" not in response.text
        assert (
            client.post(
                "/web/login", data={"mode": "admin", "token": "conduit-admin-token"}
            ).status_code
            == 422
        )


def test_session_rotation_and_logout_revoke_access(account):
    with httpx.Client(base_url=API) as client:
        response = sign_in(client, account)
        token = response.cookies["conduit_session"]
        cookie = response.headers["set-cookie"].lower()
        assert token.startswith("ws_") and token != account["password"]
        assert (
            "httponly" in cookie
            and "samesite=lax" in cookie
            and "max-age=28800" in cookie
        )
        page = client.get("/").text
        assert "<h1>Reports</h1>" in page
        nav = page.split("<nav>", 1)[1].split("</nav>", 1)[0]
        assert 'href="/data"' in nav and 'href="/sql"' in nav
        for path in (
            "/operations",
            "/playground",
            "/admin",
            "/messages",
            "/topics",
            "/groups",
            "/dlq",
        ):
            assert 'href="' + path + '"' not in nav
        assert client.get("/api/reports/templates").status_code == 200
        sign_in(client, account)
        replacement = client.cookies["conduit_session"]
        assert replacement != token
        assert (
            httpx.get(
                API + "/api/reports/templates",
                headers={"Cookie": "conduit_session=" + token},
            ).status_code
            == 401
        )
        assert client.get("/web/logout").status_code == 303
        assert (
            httpx.get(
                API + "/api/reports/templates",
                headers={"Cookie": "conduit_session=" + replacement},
            ).status_code
            == 401
        )
        assert client.get("/").status_code == 303


def test_expiry_and_disabled_accounts(account):
    with httpx.Client(base_url=API) as client, service.connect() as conn:
        sign_in(client, account)
        token = client.cookies["conduit_session"]
        digest = hashlib.sha256(token.encode()).hexdigest()
        stored = conn.execute(
            "SELECT token_hash FROM reporting.web_session WHERE account_id=%s",
            (account["account_id"],),
        ).fetchone()
        assert stored["token_hash"] == digest and stored["token_hash"] != token
        assert account["password_hash"] != account["password"]
        conn.execute(
            "UPDATE reporting.web_session SET created_at=now()-interval '2 hours', expires_at=now()-interval '1 hour' WHERE token_hash=%s",
            (digest,),
        )
        assert client.get("/").status_code == 303
        assert client.get("/api/reports/templates").status_code == 401
        sign_in(client, account)
        conn.execute(
            "UPDATE reporting.web_account SET enabled=false WHERE account_id=%s",
            (account["account_id"],),
        )
        assert client.get("/").status_code == 303
        assert client.get("/api/reports/templates").status_code == 401
        assert (
            client.post(
                "/web/login",
                data={"username": account["username"], "password": account["password"]},
            ).status_code
            == 401
        )
