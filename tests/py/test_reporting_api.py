import os
import uuid

import httpx

from reporting import service, worker

API = os.environ.get("CONDUIT_API_URL", "http://127.0.0.1:8000")
AUTH = {"Authorization": "Bearer conduit-admin-token"}


def test_reporting_auth_and_parameter_validation():
    assert httpx.get(API + "/api/reports/templates").status_code == 401
    assert httpx.get(API + "/api/reports/templates", headers=AUTH).status_code == 200
    response = httpx.post(
        API + "/api/reports/runs",
        headers=AUTH,
        json={"template": "monthly_sales", "start": "2027-01-01", "end": "2026-01-01"},
    )
    assert response.status_code == 422


def test_real_report_download_replay_and_evidence():
    response = httpx.post(
        API + "/api/reports/runs",
        headers=AUTH,
        json={"template": "monthly_sales", "start": "2026-01-01", "end": "2027-01-01"},
    )
    assert response.status_code == 202, response.text
    run = response.json()["run_id"]
    with service.connect() as conn:
        for _ in range(20):
            worker.tick(conn, "api-test")
            if service.progress(run)["completed"] == 1:
                break
    status = httpx.get(API + f"/api/reports/runs/{run}", headers=AUTH)
    assert status.json()["completed"] == 1
    request = httpx.get(API + f"/api/reports/runs/{run}/requests", headers=AUTH).json()[
        0
    ]["request_id"]
    for extension in ("csv", "html"):
        result = httpx.get(
            API + f"/api/reports/requests/{request}/download/{extension}", headers=AUTH
        )
        assert result.status_code == 200 and len(result.content) > 0
    evidence = httpx.get(
        API + f"/api/reports/requests/{request}/evidence", headers=AUTH
    ).json()
    assert "running_sales" in evidence["sql_text"] and evidence["csv_sha256"]
    assert (
        httpx.get(
            API + f"/api/reports/requests/{request}/replay", headers=AUTH
        ).status_code
        == 200
    )
    assert (
        httpx.get(
            API + f"/api/reports/requests/{uuid.uuid4()}/evidence", headers=AUTH
        ).status_code
        == 404
    )


def test_big_sequence_and_out_of_order_acknowledgement():
    suffix = uuid.uuid4().hex[:10]
    topic = "regression-" + suffix
    group = "regression-workers-" + suffix
    with service.connect() as conn:
        app = conn.execute(
            "SELECT app_id FROM application WHERE app_name='reporting-service'"
        ).fetchone()["app_id"]
        conn.execute("SELECT create_topic(%s,NULL,1,NULL,'sysadmin')", (topic,))
        conn.execute("SELECT create_group(%s,'sysadmin',3)", (group,))
        conn.execute("SELECT subscribe_group(%s,%s)", (group, topic))
        seq = uuid.uuid4().int & ((1 << 62) - 1)
        for n in range(2):
            conn.execute(
                "SELECT * FROM produce(%s,NULL,'{}',%s,%s)", (topic, app, seq + n)
            )
        messages = sorted(
            conn.execute(
                "SELECT * FROM consume(%s,%s,2,30)", (group, topic)
            ).fetchall(),
            key=lambda m: m["msg_offset"],
        )
        from psycopg.types.json import Jsonb

        later = Jsonb([{"partition_id": messages[1]["partition_id"], "msg_offset": 1}])
        assert (
            conn.execute("SELECT ack(%s,%s) AS n", (group, later)).fetchone()["n"] == 1
        )
        assert (
            conn.execute("SELECT ack(%s,%s) AS n", (group, later)).fetchone()["n"] == 0
        )
        assert (
            conn.execute(
                "SELECT committed_offset FROM group_offset WHERE group_id=(SELECT group_id FROM consumer_group WHERE group_name=%s)",
                (group,),
            ).fetchone()["committed_offset"]
            == 0
        )
        first = Jsonb([{"partition_id": messages[0]["partition_id"], "msg_offset": 0}])
        conn.execute("SELECT ack(%s,%s)", (group, first))
        assert (
            conn.execute(
                "SELECT committed_offset FROM group_offset WHERE group_id=(SELECT group_id FROM consumer_group WHERE group_name=%s)",
                (group,),
            ).fetchone()["committed_offset"]
            == 2
        )


def test_private_dlq_and_seeded_admin_grant():
    suffix = uuid.uuid4().hex[:10]
    topic = "private-" + suffix
    group = "private-workers-" + suffix
    user = "viewer-" + suffix
    marker = "PRIVATE-" + suffix
    with service.connect() as conn:
        conn.execute(
            "SELECT register_user(%s,%s,'viewer')", (user, user + "@example.test")
        )
        viewer = conn.execute(
            "SELECT * FROM register_application(%s,%s,'both')",
            ("viewer-app-" + suffix, user),
        ).fetchone()
        app = conn.execute(
            "SELECT app_id FROM application WHERE app_name='reporting-service'"
        ).fetchone()["app_id"]
        conn.execute("SELECT create_topic(%s,NULL,1,NULL,'sysadmin')", (topic,))
        conn.execute("SELECT create_group(%s,'sysadmin',3)", (group,))
        conn.execute("SELECT subscribe_group(%s,%s)", (group, topic))
        from psycopg.types.json import Jsonb

        conn.execute(
            "SELECT * FROM produce(%s,%s,%s,%s,%s)",
            (
                topic,
                marker,
                Jsonb({"private": marker}),
                app,
                uuid.uuid4().int & ((1 << 62) - 1),
            ),
        )
        for _ in range(3):
            msg = conn.execute(
                "SELECT * FROM consume(%s,%s,1,30)", (group, topic)
            ).fetchone()
            conn.execute(
                "SELECT * FROM nack(%s,%s,'controlled failure')",
                (
                    group,
                    Jsonb(
                        [
                            {
                                "partition_id": msg["partition_id"],
                                "msg_offset": msg["msg_offset"],
                            }
                        ]
                    ),
                ),
            )
    cookies = {"conduit_session": str(viewer["api_key"])}
    for path in ("/dlq", "/fragments/dlq", "/audit", "/fragments/audit"):
        response = httpx.get(API + path, cookies=cookies)
        assert response.status_code == 200 and marker not in response.text
    admin_cookie = {"conduit_session": "conduit-admin-token"}
    assert marker in httpx.get(API + "/dlq", cookies=admin_cookie).text
    response = httpx.post(
        API + "/web/access/grant",
        cookies=admin_cookie,
        data={"username": user, "topic": topic, "access_type": "produce"},
    )
    assert response.status_code == 200, response.text
