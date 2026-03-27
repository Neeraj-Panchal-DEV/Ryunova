-- Extended profile fields, immutable public_code, email-change pending, verification token kind.
-- Run against your RyuNova PostgreSQL database (see db/README.md).

-- --- ryunova_users ------------------------------------------------------------
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS public_code VARCHAR(40);
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS first_name VARCHAR(128);
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS last_name VARCHAR(128);
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS date_of_birth DATE;
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS phone_e164 VARCHAR(24);
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS job_title VARCHAR(255);
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS social_handles JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS pending_email VARCHAR(255);

-- Backfill public_code: deterministic from user id (unique)
UPDATE ryunova_users
SET public_code = 'RN-' || replace(id::text, '-', '')
WHERE public_code IS NULL;

ALTER TABLE ryunova_users ALTER COLUMN public_code SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ryunova_users_public_code_key'
  ) THEN
    ALTER TABLE ryunova_users ADD CONSTRAINT ryunova_users_public_code_key UNIQUE (public_code);
  END IF;
END $$;

-- --- ryunova_email_verification_tokens ----------------------------------------
ALTER TABLE ryunova_email_verification_tokens ADD COLUMN IF NOT EXISTS token_kind VARCHAR(32) NOT NULL DEFAULT 'signup';
ALTER TABLE ryunova_email_verification_tokens ADD COLUMN IF NOT EXISTS new_email VARCHAR(255);

COMMENT ON COLUMN ryunova_email_verification_tokens.token_kind IS 'signup | email_change';
COMMENT ON COLUMN ryunova_email_verification_tokens.new_email IS 'Target email when token_kind is email_change';
