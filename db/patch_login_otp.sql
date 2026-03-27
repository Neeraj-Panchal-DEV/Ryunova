-- Sign-in email codes (Slack-style). Apply after main schema.
CREATE TABLE IF NOT EXISTS ryunova_login_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES ryunova_users(id) ON DELETE CASCADE,
    code_hash VARCHAR(128) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ryunova_login_codes_user_created
    ON ryunova_login_codes (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_ryunova_login_codes_code_hash ON ryunova_login_codes (code_hash);
