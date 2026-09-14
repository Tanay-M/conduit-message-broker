import psycopg
from psycopg.types.json import Json

from .db import Database, DEFAULT_APP_DSN
from .errors import from_psycopg
from .security import auth_app


class Conduit:
    def __init__(self, api_key, dsn=DEFAULT_APP_DSN):
        self._db = Database(dsn, "conduit-app")
        try:
            with self._db.pool.connection() as conn:
                self.app = auth_app(conn, api_key)
        except psycopg.Error as e:
            self._db.close()
            raise from_psycopg(e) from e
        self.app_id = self.app["app_id"]
        self.user_id = self.app["owner_user_id"]
        self.app_name = self.app["app_name"]
        self.owner_username = self.app["owner_username"]

    def close(self):
        self._db.close()

    def produce(self, topic, payload, seq, key=None):
        row = self._db.call(
            "SELECT * FROM produce(%s::text, %s::text, %s::jsonb, %s::bigint, %s::bigint)",
            (topic, key, Json(payload), self.app_id, seq),
            user_id=self.user_id,
            one=True,
        )
        return {
            "topic_id": row["loc_topic_id"],
            "partition_id": row["loc_partition_id"],
            "msg_offset": row["loc_msg_offset"],
            "duplicate": row["is_duplicate"],
        }

    def produce_batch(self, topic, messages, seq_start=1):
        arr = [
            {"seq": seq_start + i, "key": m.get("key"), "payload": m["payload"]}
            for i, m in enumerate(messages)
        ]
        rows = self._db.call(
            "SELECT * FROM produce_batch(%s::text, %s::jsonb, %s::bigint)",
            (topic, Json(arr), self.app_id),
            user_id=self.user_id,
        )
        return [
            {
                "seq": r["producer_seq"],
                "topic_id": r["loc_topic_id"],
                "partition_id": r["loc_partition_id"],
                "msg_offset": r["loc_msg_offset"],
                "duplicate": r["is_duplicate"],
            }
            for r in rows
        ]

    def consume(self, group, topic, batch=10, visibility_timeout=30):
        rows = self._db.call(
            "SELECT * FROM consume(%s::text, %s::text, %s::int, %s::int)",
            (group, topic, batch, visibility_timeout),
            user_id=self.user_id,
        )
        return [
            {**r, "location": {"partition_id": r["partition_id"], "msg_offset": r["msg_offset"]}}
            for r in rows
        ]

    def ack(self, group, locations):
        row = self._db.call(
            "SELECT ack(%s::text, %s::jsonb) AS acked",
            (group, Json(locations)),
            user_id=self.user_id,
            one=True,
        )
        return row["acked"]

    def nack(self, group, locations, reason="rejected by consumer"):
        row = self._db.call(
            "SELECT * FROM nack(%s::text, %s::jsonb, %s::text)",
            (group, Json(locations), reason),
            user_id=self.user_id,
            one=True,
        )
        return {"retried": row["retried"], "dead": row["dead"]}

    def accessible_topics(self):
        return self._db.call(
            "SELECT t.topic_name, a.access_type FROM access a "
            "JOIN topic t ON t.topic_id = a.topic_id "
            "WHERE a.user_id = %s::bigint ORDER BY t.topic_name",
            (self.user_id,),
        )

    def query(self, sql, params=()):
        return self._db.call(sql, params, user_id=self.user_id)

    def log_auth_failure(self, topic_id, details):
        self._db.call(
            "SELECT log_auth_failure(%s::bigint, %s::bigint, %s::bigint, %s::jsonb)",
            (self.user_id, self.app_id, topic_id, Json(details)),
            user_id=self.user_id,
        )
