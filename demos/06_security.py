import uuid

from conduit.errors import ConduitError

from _common import banner, check, done, fixtures, info, new_admin, new_client, step

banner("DEMO 06 - SECURITY: ACL triggers, RLS zero-visibility, suspend semantics, app revocation")

admin = new_admin()
fx = fixtures(admin, "d6", schema={"required": ["event"]})
step(f"provisioned granted user={fx['user']} app={fx['app_name']} topic={fx['topic']}")

step("creating a second user + app with NO grants on the topic")
sfx = uuid.uuid4().hex[:8]
intruder = f"d6intruder{sfx}"
admin.register_user(intruder, f"{intruder}@conduit.io", "viewer")
intruder_app = admin.register_application(f"d6intruderapp{sfx}", intruder, "both")
intruder_client = new_client({"app": intruder_app})
step(f"intruder={intruder} (no access rows anywhere)")

granted = new_client(fx)

step("granted app produces -> allowed")
loc = granted.produce(fx["topic"], {"event": "legit"}, 1, key="ok")
info(f"produced at partition={loc['partition_id']} offset={loc['msg_offset']}")
check(loc["duplicate"] is False, "granted produce succeeded")

step("intruder produces -> BLOCKED by the ACL trigger (CDT17)")
try:
    intruder_client.produce(fx["topic"], {"event": "sneaky"}, 1, key="hack")
    check(False, "intruder produce should have been denied")
except ConduitError as e:
    info(f"caught typed exception: [{e.code}] {e.message}")
    check(e.code in ("CDT17", "42501"), "produce denied at the database layer")
    intruder_client.log_auth_failure(fx["topic_id"], {"reason": "produce denied in security demo"})
    auth_fails = admin.run(
        "SELECT count(*) AS n FROM audit_log WHERE event_type = 'AUTH_FAIL' AND user_id = %s::bigint",
        (intruder_client.user_id,),
    )
    check(auth_fails[0]["n"] == 1, "AUTH_FAIL recorded in the audit trail")

step("RLS row visibility: SELECT * FROM message through the app role")
granted_rows = granted.query("SELECT count(*) AS n FROM message")
intruder_rows = intruder_client.query("SELECT count(*) AS n FROM message")
info(f"granted app sees {granted_rows[0]['n']} message rows; intruder sees {intruder_rows[0]['n']}")
check(intruder_rows[0]["n"] == 0, "ungranted app sees ZERO rows - row-level security")
check(granted_rows[0]["n"] >= 1, "granted app sees its topic's rows")

step("suspending the granted user -> access cut at BOTH trigger and RLS layers")
admin.suspend_user(fx["user"])
try:
    granted.produce(fx["topic"], {"event": "after-suspend"}, 2, key="nope")
    check(False, "suspended user produce should have been denied")
except ConduitError as e:
    info(f"caught typed exception: [{e.code}] {e.message}")
    check(e.code in ("CDT17", "42501"), "suspension cuts access (trigger layer)")
can_read = granted.query("SELECT count(*) AS n FROM message")
check(can_read[0]["n"] == 0, "suspension cuts access (RLS layer: zero rows visible)")
admin.activate_user(fx["user"])
restored = granted.produce(fx["topic"], {"event": "restored"}, 2, key="back")
check(restored["duplicate"] is False, "reactivation restores access")

step("revoking the app -> CDT03 even though the user is active")
admin.set_application_status(fx["app_name"], "revoked")
try:
    granted.produce(fx["topic"], {"event": "revoked-app"}, 3, key="nope")
    check(False, "revoked app produce should have been denied")
except ConduitError as e:
    info(f"caught typed exception: [{e.code}] {e.message}")
    check(e.code == "CDT03", "revoked application blocked (CDT03)")
admin.set_application_status(fx["app_name"], "active")

granted.close()
intruder_client.close()
admin.close()
done()
