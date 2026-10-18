BEGIN;

CREATE TABLE reporting.web_account (
    account_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username text NOT NULL UNIQUE CHECK (length(trim(username)) BETWEEN 1 AND 64),
    password_hash text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reporting.web_session (
    token_hash char(64) PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES reporting.web_account(account_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '8 hours',
    CHECK (expires_at > created_at)
);
CREATE INDEX idx_web_session_expiry ON reporting.web_session(expires_at);
REVOKE ALL ON reporting.web_account, reporting.web_session FROM PUBLIC;

COMMIT;
