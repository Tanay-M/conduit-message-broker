from psycopg.types.json import Json

from .db import Database, DEFAULT_ADMIN_DSN


class ConduitAdmin:
    def __init__(self, dsn=DEFAULT_ADMIN_DSN):
        self._db = Database(dsn, "conduit-admin")

    def close(self):
        self._db.close()

    def run(self, sql, params=()):
        return self._db.call(sql, params)

    def register_user(self, username, email, role):
        row = self._db.call(
            "SELECT register_user(%s, %s, %s) AS user_id", (username, email, role), one=True
        )
        return row["user_id"]

    def register_application(self, app_name, owner_username, app_type):
        return dict(
            self._db.call(
                "SELECT app_id, api_key FROM register_application(%s, %s, %s)",
                (app_name, owner_username, app_type),
                one=True,
            )
        )

    def create_topic(self, name, partitions, owner_username, schema=None, description=None):
        row = self._db.call(
            "SELECT create_topic(%s::text, %s::text, %s::int, %s::jsonb, %s::text) AS topic_id",
            (name, description, partitions, Json(schema) if schema is not None else None, owner_username),
            one=True,
        )
        return row["topic_id"]

    def grant_access(self, username, topic, access_type, granted_by):
        row = self._db.call(
            "SELECT grant_access(%s, %s, %s, %s) AS access_id",
            (username, topic, access_type, granted_by),
            one=True,
        )
        return row["access_id"]

    def revoke_access(self, username, topic, access_type):
        row = self._db.call(
            "SELECT revoke_access(%s, %s, %s) AS revoked",
            (username, topic, access_type),
            one=True,
        )
        return row["revoked"]

    def create_group(self, group_name, created_by_username, max_delivery_attempts=3):
        row = self._db.call(
            "SELECT create_group(%s::text, %s::text, %s::int) AS group_id",
            (group_name, created_by_username, max_delivery_attempts),
            one=True,
        )
        return row["group_id"]

    def subscribe_group(self, group_name, topic):
        row = self._db.call(
            "SELECT subscribe_group(%s, %s) AS partitions_wired", (group_name, topic), one=True
        )
        return row["partitions_wired"]

    def suspend_user(self, username):
        self._db.call("SELECT suspend_user(%s)", (username,))

    def activate_user(self, username):
        self._db.call("SELECT activate_user(%s)", (username,))

    def set_application_status(self, app_name, status):
        self._db.call("SELECT set_application_status(%s, %s)", (app_name, status))

    def update_topic_config(self, topic, retention_days=None, max_message_bytes=None, status=None):
        self._db.call(
            "SELECT update_topic_config(%s::text, %s::int, %s::int, %s::text)",
            (topic, retention_days, max_message_bytes, status),
        )

    def archive_topic(self, topic):
        self._db.call("SELECT archive_topic(%s)", (topic,))

    def pause_group(self, group_name):
        self._db.call("SELECT pause_group(%s)", (group_name,))

    def activate_group(self, group_name):
        self._db.call("SELECT activate_group(%s)", (group_name,))

    def publish_schema_version(self, topic, definition):
        row = self._db.call(
            "SELECT publish_schema_version(%s::text, %s::jsonb) AS version",
            (topic, Json(definition)),
            one=True,
        )
        return row["version"]

    def update_broker_config(self, key, value, description=None, updated_by=None):
        self._db.call(
            "SELECT update_broker_config(%s, %s, %s, %s)", (key, value, description, updated_by)
        )

    def requeue_dlq(self, dlq_id, producer_app_name, target_topic=None):
        row = self._db.call(
            "SELECT * FROM requeue_dlq(%s::bigint, (SELECT a.app_id FROM application a WHERE a.app_name = %s::text), %s::text)",
            (dlq_id, producer_app_name, target_topic),
            one=True,
        )
        return {
            "dlq_id": row["dlq_id"],
            "requeued": row["requeued"],
            "topic_id": row["loc_topic_id"],
            "partition_id": row["loc_partition_id"],
            "msg_offset": row["loc_msg_offset"],
        }

    def reap_expired(self):
        row = self._db.call("SELECT * FROM reap_expired_claims()", one=True)
        return {"requeued": row["requeued"], "dead": row["dead"]}

    def purge_retention(self, topic=None):
        row = self._db.call("SELECT purge_retention(%s::text) AS purged", (topic,), one=True)
        return row["purged"]

    def drop_old_partitions(self, keep_days=90):
        row = self._db.call("SELECT drop_old_partitions(%s::int) AS dropped", (keep_days,), one=True)
        return row["dropped"]

    def create_monthly_partition(self, month):
        row = self._db.call(
            "SELECT create_monthly_partition(%s::date) AS partition_name", (month,), one=True
        )
        return row["partition_name"]

    def refresh_dashboard(self):
        self._db.call("SELECT refresh_dashboard()")

    def topic_stats(self, topic):
        return dict(self._db.call("SELECT * FROM topic_stats(%s::text)", (topic,), one=True))
