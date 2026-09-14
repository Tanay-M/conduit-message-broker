import os
import time
import uuid

from conduit import Conduit, ConduitAdmin

DSN = os.environ.get("CONDUIT_APP_DSN", "postgresql://conduit_app:conduit_app_dev@db:5432/conduit")
ADMIN_DSN = os.environ.get("CONDUIT_ADMIN_DSN", "postgresql://conduit:conduit_dev@db:5432/conduit")


def banner(title):
    print()
    print("=" * 64)
    print(f" {title}")
    print("=" * 64)


def step(msg):
    print(f"  -> {msg}")


def info(msg):
    print(f"     {msg}")


def check(cond, msg):
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
    if not cond:
        raise SystemExit(f"demo failed: {msg}")


def done():
    print()
    print("  DEMO COMPLETE - all checks passed")
    print()


def timed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    ms = (time.perf_counter() - t0) * 1000
    return result, ms


def fixtures(admin, tag, partitions=2, schema=None, grants=("produce", "consume")):
    sfx = uuid.uuid4().hex[:8]
    user = f"{tag}user{sfx}"
    app_name = f"{tag}app{sfx}"
    topic = f"{tag}topic{sfx}"
    group = f"{tag}group{sfx}"
    admin.register_user(user, f"{user}@conduit.io", "producer")
    app = admin.register_application(app_name, user, "both")
    topic_id = admin.create_topic(topic, partitions, user, schema=schema)
    for access_type in grants:
        admin.grant_access(user, topic, access_type, user)
    admin.create_group(group, user)
    admin.subscribe_group(group, topic)
    return {
        "user": user,
        "app_name": app_name,
        "app": app,
        "topic": topic,
        "topic_id": topic_id,
        "group": group,
    }


def new_client(fx):
    return Conduit(fx["app"]["api_key"], dsn=DSN)


def new_admin():
    return ConduitAdmin(dsn=ADMIN_DSN)
