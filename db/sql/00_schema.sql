BEGIN;

CREATE TABLE role (
    role_id     SERIAL PRIMARY KEY,
    role_name   VARCHAR(32)  NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE app_user (
    user_id    BIGSERIAL    PRIMARY KEY,
    username   VARCHAR(64)  NOT NULL UNIQUE,
    email      VARCHAR(255) NOT NULL UNIQUE,
    role_id    INT          NOT NULL REFERENCES role(role_id) ON DELETE RESTRICT,
    status     VARCHAR(16)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE application (
    app_id       BIGSERIAL   PRIMARY KEY,
    app_name     VARCHAR(128) NOT NULL UNIQUE,
    api_key      UUID        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    owner_user_id BIGINT     NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    app_type     VARCHAR(16) NOT NULL CHECK (app_type IN ('producer', 'consumer', 'both')),
    status       VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_application_owner ON application (owner_user_id);

CREATE TABLE topic (
    topic_id          BIGSERIAL   PRIMARY KEY,
    topic_name        VARCHAR(128) NOT NULL UNIQUE,
    description       VARCHAR(512),
    created_by        BIGINT      NOT NULL REFERENCES app_user(user_id) ON DELETE RESTRICT,
    retention_days    INT         NOT NULL DEFAULT 7 CHECK (retention_days BETWEEN 1 AND 3650),
    max_message_bytes INT         NOT NULL DEFAULT 1048576 CHECK (max_message_bytes > 0),
    status            VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE partition (
    partition_id     BIGSERIAL PRIMARY KEY,
    topic_id         BIGINT    NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    partition_number INT       NOT NULL CHECK (partition_number >= 0),
    next_offset      BIGINT    NOT NULL DEFAULT 0 CHECK (next_offset >= 0),
    CONSTRAINT uq_partition_topic_number UNIQUE (topic_id, partition_number)
);

CREATE TABLE schema_version (
    schema_id  BIGSERIAL   PRIMARY KEY,
    topic_id   BIGINT      NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    version    INT         NOT NULL CHECK (version >= 1),
    format     VARCHAR(16) NOT NULL DEFAULT 'json' CHECK (format IN ('json')),
    definition JSONB       NOT NULL,
    status     VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deprecated')),
    created_by BIGINT      REFERENCES app_user(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_schema_topic_version UNIQUE (topic_id, version)
);

CREATE TABLE message (
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    topic_id        BIGINT      NOT NULL,
    partition_id    BIGINT      NOT NULL,
    msg_offset      BIGINT      NOT NULL CHECK (msg_offset >= 0),
    msg_key         VARCHAR(128),
    payload         JSONB       NOT NULL,
    size_bytes      INT         NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    producer_app_id BIGINT      NOT NULL,
    producer_seq    BIGINT      NOT NULL CHECK (producer_seq >= 0),
    status          VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'claimed', 'delivered', 'dead')),
    claimed_by      BIGINT,
    visible_at      TIMESTAMPTZ,
    attempts        INT         NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    CONSTRAINT message_pk PRIMARY KEY (created_at, topic_id, partition_id, msg_offset)
) PARTITION BY RANGE (created_at);

CREATE TABLE message_2026_09 PARTITION OF message FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE message_2026_10 PARTITION OF message FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE message_2026_11 PARTITION OF message FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE message_2026_12 PARTITION OF message FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE message_2027_01 PARTITION OF message FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
CREATE TABLE message_2027_02 PARTITION OF message FOR VALUES FROM ('2027-02-01') TO ('2027-03-01');
CREATE TABLE message_2027_03 PARTITION OF message FOR VALUES FROM ('2027-03-01') TO ('2027-04-01');
CREATE TABLE message_default PARTITION OF message DEFAULT;

CREATE INDEX idx_message_topic_partition_offset ON message (topic_id, partition_id, msg_offset);
CREATE INDEX idx_message_pending ON message (topic_id, partition_id, msg_offset) WHERE status = 'pending';
CREATE INDEX idx_message_claimed_visible_at ON message (visible_at) WHERE status = 'claimed';
CREATE INDEX idx_message_created_brin ON message USING brin (created_at);
CREATE INDEX idx_message_producer ON message (producer_app_id, producer_seq);

ALTER TABLE message ADD CONSTRAINT fk_message_topic FOREIGN KEY (topic_id) REFERENCES topic(topic_id) ON DELETE RESTRICT;
ALTER TABLE message ADD CONSTRAINT fk_message_partition FOREIGN KEY (partition_id) REFERENCES partition(partition_id) ON DELETE RESTRICT;
ALTER TABLE message ADD CONSTRAINT fk_message_producer_app FOREIGN KEY (producer_app_id) REFERENCES application(app_id) ON DELETE RESTRICT;

CREATE TABLE producer_sequence (
    producer_app_id BIGINT      NOT NULL REFERENCES application(app_id) ON DELETE CASCADE,
    producer_seq    BIGINT      NOT NULL CHECK (producer_seq >= 0),
    topic_id        BIGINT      NOT NULL,
    partition_id    BIGINT      NOT NULL,
    msg_offset      BIGINT      NOT NULL CHECK (msg_offset >= 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_producer_sequence PRIMARY KEY (producer_app_id, producer_seq)
);

CREATE TABLE consumer_group (
    group_id             BIGSERIAL   PRIMARY KEY,
    group_name           VARCHAR(128) NOT NULL UNIQUE,
    created_by           BIGINT      REFERENCES app_user(user_id) ON DELETE SET NULL,
    max_delivery_attempts INT        NOT NULL DEFAULT 3 CHECK (max_delivery_attempts BETWEEN 1 AND 10),
    status               VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE message ADD CONSTRAINT fk_message_claimed_by FOREIGN KEY (claimed_by) REFERENCES consumer_group(group_id) ON DELETE SET NULL;

CREATE TABLE group_subscription (
    group_id       BIGINT      NOT NULL REFERENCES consumer_group(group_id) ON DELETE CASCADE,
    topic_id       BIGINT      NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    subscribed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_group_subscription PRIMARY KEY (group_id, topic_id)
);
CREATE INDEX idx_group_subscription_topic ON group_subscription (topic_id);

CREATE TABLE group_offset (
    group_id        BIGINT      NOT NULL REFERENCES consumer_group(group_id) ON DELETE CASCADE,
    partition_id    BIGINT      NOT NULL REFERENCES partition(partition_id) ON DELETE CASCADE,
    committed_offset BIGINT     NOT NULL DEFAULT 0 CHECK (committed_offset >= 0),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_group_offset PRIMARY KEY (group_id, partition_id)
);
CREATE INDEX idx_group_offset_partition ON group_offset (partition_id);

CREATE TABLE access (
    access_id   BIGSERIAL   PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    topic_id    BIGINT      NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    access_type VARCHAR(16) NOT NULL CHECK (access_type IN ('produce', 'consume', 'admin')),
    granted_by  BIGINT      REFERENCES app_user(user_id) ON DELETE SET NULL,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_access UNIQUE (user_id, topic_id, access_type)
);
CREATE INDEX idx_access_topic ON access (topic_id);

CREATE TABLE dead_letter_message (
    dlq_id            BIGSERIAL   PRIMARY KEY,
    original_topic_id BIGINT      NOT NULL REFERENCES topic(topic_id) ON DELETE RESTRICT,
    original_offset   BIGINT      NOT NULL CHECK (original_offset >= 0),
    msg_key           VARCHAR(128),
    payload           JSONB       NOT NULL,
    failed_group_id   BIGINT      REFERENCES consumer_group(group_id) ON DELETE SET NULL,
    failure_reason    TEXT,
    attempts          INT         NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    status            VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'requeued')),
    dead_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_dlq_status ON dead_letter_message (status, dead_at);
CREATE INDEX idx_dlq_group ON dead_letter_message (failed_group_id);

CREATE TABLE audit_log (
    log_id         BIGSERIAL   PRIMARY KEY,
    user_id        BIGINT      REFERENCES app_user(user_id) ON DELETE SET NULL,
    app_id         BIGINT      REFERENCES application(app_id) ON DELETE SET NULL,
    topic_id       BIGINT      REFERENCES topic(topic_id) ON DELETE SET NULL,
    event_type     VARCHAR(32) NOT NULL,
    status         VARCHAR(16) NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'failure')),
    details        JSONB,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_event_type_time ON audit_log (event_type, event_timestamp);
CREATE INDEX idx_audit_timestamp_brin ON audit_log USING brin (event_timestamp);
CREATE INDEX idx_audit_user ON audit_log (user_id);
CREATE INDEX idx_audit_topic ON audit_log (topic_id);

CREATE TABLE broker_config (
    config_id    SERIAL      PRIMARY KEY,
    config_key   VARCHAR(64) NOT NULL UNIQUE,
    config_value TEXT        NOT NULL,
    description  VARCHAR(255),
    updated_by   BIGINT      REFERENCES app_user(user_id) ON DELETE SET NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE role IS 'System roles used for role-based access control';
COMMENT ON TABLE app_user IS 'Registered human users of the Conduit broker';
COMMENT ON TABLE application IS 'Registered client applications (producers/consumers) identified by API key';
COMMENT ON TABLE topic IS 'Message topics; the publish/subscribe naming endpoint';
COMMENT ON TABLE partition IS 'Per-topic partitions; each owns a monotonically increasing offset counter';
COMMENT ON TABLE schema_version IS 'Versioned JSON message contracts enforced at produce time';
COMMENT ON TABLE message IS 'The messages themselves; range-partitioned monthly by created_at';
COMMENT ON TABLE producer_sequence IS 'Producer idempotency ledger: one row per (app, seq); a duplicate produce returns the original message location';
COMMENT ON TABLE consumer_group IS 'Named consumer groups with shared delivery-attempt policy';
COMMENT ON TABLE group_subscription IS 'M:N subscriptions between consumer groups and topics';
COMMENT ON TABLE group_offset IS 'Per (group, partition) committed offset; monotonic, enforced by trigger';
COMMENT ON TABLE access IS 'Topic-level access grants (produce/consume/admin) per user';
COMMENT ON TABLE dead_letter_message IS 'Snapshot of messages that exceeded max delivery attempts';
COMMENT ON TABLE audit_log IS 'Trigger-written audit trail of all broker and admin events';
COMMENT ON TABLE broker_config IS 'Key/value broker runtime configuration';

INSERT INTO role (role_name, description) VALUES
    ('admin',    'Full broker administration'),
    ('operator', 'Topic and group management'),
    ('producer', 'May register producer applications'),
    ('consumer', 'May register consumer applications'),
    ('viewer',   'Read-only dashboard access');

COMMIT;
