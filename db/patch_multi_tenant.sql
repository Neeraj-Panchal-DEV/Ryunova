-- After this patch, run db/patch_platform_org_admin.sql: is_system_user and is_platform_user are the
-- same flag — that patch adds is_platform_user, copies from is_system_user, drops is_system_user.
--
-- Multi-tenant organisations, user–org membership, platform users (column is_system_user here; same meaning as is_platform_user), email verification,
-- tenant-scoped categories/brands/products (SKU unique per org).
-- Run once on existing DBs after prior patches. Uses fixed default org UUID for stable FKs.

CREATE TABLE IF NOT EXISTS ryunova_organisations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO ryunova_organisations (id, name, slug)
VALUES (
  '00000000-0000-4000-8000-000000000001'::uuid,
  'Default organization',
  'default'
)
ON CONFLICT (slug) DO NOTHING;

ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS is_system_user BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;

UPDATE ryunova_users SET email_verified_at = COALESCE(email_verified_at, now()) WHERE email_verified_at IS NULL;

UPDATE ryunova_users u
SET is_system_user = true
FROM (SELECT id FROM ryunova_users ORDER BY created_at ASC NULLS LAST LIMIT 1) first_u
WHERE u.id = first_u.id
  AND NOT EXISTS (SELECT 1 FROM ryunova_users su WHERE su.is_system_user = true);

CREATE TABLE IF NOT EXISTS ryunova_user_organisations (
  user_id UUID NOT NULL REFERENCES ryunova_users(id) ON DELETE CASCADE,
  organisation_id UUID NOT NULL REFERENCES ryunova_organisations(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, organisation_id)
);

INSERT INTO ryunova_user_organisations (user_id, organisation_id)
SELECT u.id, '00000000-0000-4000-8000-000000000001'::uuid
FROM ryunova_users u
ON CONFLICT (user_id, organisation_id) DO NOTHING;

ALTER TABLE ryunova_categories ADD COLUMN IF NOT EXISTS organisation_id UUID REFERENCES ryunova_organisations(id);
UPDATE ryunova_categories SET organisation_id = '00000000-0000-4000-8000-000000000001'::uuid WHERE organisation_id IS NULL;
ALTER TABLE ryunova_categories ALTER COLUMN organisation_id SET NOT NULL;

ALTER TABLE ryunova_brands ADD COLUMN IF NOT EXISTS organisation_id UUID REFERENCES ryunova_organisations(id);
UPDATE ryunova_brands SET organisation_id = '00000000-0000-4000-8000-000000000001'::uuid WHERE organisation_id IS NULL;
ALTER TABLE ryunova_brands ALTER COLUMN organisation_id SET NOT NULL;

ALTER TABLE ryunova_brands DROP CONSTRAINT IF EXISTS ryunova_brands_name_key;
DROP INDEX IF EXISTS ix_ryunova_brands_name_unique;
CREATE UNIQUE INDEX IF NOT EXISTS ix_ryunova_brands_org_name ON ryunova_brands(organisation_id, name);

ALTER TABLE ryunova_product_master ADD COLUMN IF NOT EXISTS organisation_id UUID REFERENCES ryunova_organisations(id);
UPDATE ryunova_product_master SET organisation_id = '00000000-0000-4000-8000-000000000001'::uuid WHERE organisation_id IS NULL;
ALTER TABLE ryunova_product_master ALTER COLUMN organisation_id SET NOT NULL;

ALTER TABLE ryunova_product_master DROP CONSTRAINT IF EXISTS ryunova_product_master_sku_key;
CREATE UNIQUE INDEX IF NOT EXISTS ix_ryunova_product_org_sku ON ryunova_product_master(organisation_id, sku);

CREATE INDEX IF NOT EXISTS ix_ryunova_categories_organisation_id ON ryunova_categories(organisation_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_brands_organisation_id ON ryunova_brands(organisation_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_organisation_id ON ryunova_product_master(organisation_id);

CREATE TABLE IF NOT EXISTS ryunova_email_verification_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES ryunova_users(id) ON DELETE CASCADE,
  token_hash VARCHAR(128) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ryunova_email_verification_tokens_hash ON ryunova_email_verification_tokens(token_hash);
