-- =============================================================================
-- RyuNova Platform — MVP1 PostgreSQL schema (canonical / greenfield)
-- =============================================================================
-- Single DDL file for a new database. Apply once per empty DB:
--
--   psql -U ryunova -d ryunova -f db/mvp1_schema.sql
--
-- Consolidated (formerly separate patch scripts are folded in here):
--   • Multi-tenant: ryunova_organisations, ryunova_user_organisations, tenant-scoped
--     categories/brands/products, SKU unique per (organisation_id, sku).
--   • Users: is_platform_user, user_admin_access, email_verified_at, avatar_s3_key.
--   • Organisations: description, logo_s3_key; seed row slug default.
--   • Product master: colour, length_cm, width_cm, depth_cm.
--   • Product media: ryunova_product_image.media_type, is_cover.
--   • Email verification tokens table.
--
-- Uses IF NOT EXISTS / idempotent patterns where practical. Older databases with a
-- different shape: compare to this file and docs/DATABASE_SCHEMA.md, then migrate
-- manually or recreate — incremental SQL patches are not maintained in-repo.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

DO $$ BEGIN
  CREATE TYPE ryunova_product_condition AS ENUM ('new', 'used', 'refurbished');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS ryunova_organisations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL UNIQUE,
  description TEXT,
  logo_s3_key VARCHAR(512),
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

CREATE TABLE IF NOT EXISTS ryunova_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) NOT NULL UNIQUE,
  display_name VARCHAR(255),
  password_hash VARCHAR(255),
  avatar_s3_key VARCHAR(512),
  is_platform_user BOOLEAN NOT NULL DEFAULT false,
  user_admin_access BOOLEAN NOT NULL DEFAULT false,
  email_verified_at TIMESTAMPTZ,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ryunova_user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES ryunova_users(id) ON DELETE CASCADE,
  role VARCHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, role)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_user_roles_user_id ON ryunova_user_roles(user_id);

CREATE TABLE IF NOT EXISTS ryunova_user_organisations (
  user_id UUID NOT NULL REFERENCES ryunova_users(id) ON DELETE CASCADE,
  organisation_id UUID NOT NULL REFERENCES ryunova_organisations(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, organisation_id)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_user_organisations_org ON ryunova_user_organisations(organisation_id);

CREATE TABLE IF NOT EXISTS ryunova_oauth_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES ryunova_users(id) ON DELETE CASCADE,
  provider VARCHAR(64) NOT NULL,
  provider_subject VARCHAR(255),
  provider_email VARCHAR(255),
  access_token TEXT,
  refresh_token TEXT,
  token_type VARCHAR(32),
  scope TEXT,
  expires_at TIMESTAMPTZ,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, provider)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_oauth_tokens_user_id ON ryunova_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_oauth_tokens_provider ON ryunova_oauth_tokens(provider);

CREATE TABLE IF NOT EXISTS ryunova_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organisation_id UUID NOT NULL REFERENCES ryunova_organisations(id) ON DELETE RESTRICT,
  parent_id UUID REFERENCES ryunova_categories(id) ON DELETE SET NULL,
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255),
  description TEXT,
  sort_order INT DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT true,
  created_by_user_id UUID REFERENCES ryunova_users(id) ON DELETE SET NULL,
  updated_by_user_id UUID REFERENCES ryunova_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ryunova_categories_organisation_id ON ryunova_categories(organisation_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_categories_parent_id ON ryunova_categories(parent_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_categories_active ON ryunova_categories(active);
CREATE INDEX IF NOT EXISTS ix_ryunova_categories_created_by_user_id ON ryunova_categories(created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_categories_updated_by_user_id ON ryunova_categories(updated_by_user_id);

CREATE TABLE IF NOT EXISTS ryunova_brands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organisation_id UUID NOT NULL REFERENCES ryunova_organisations(id) ON DELETE RESTRICT,
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255),
  description TEXT,
  sort_order INT DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT true,
  created_by_user_id UUID REFERENCES ryunova_users(id) ON DELETE SET NULL,
  updated_by_user_id UUID REFERENCES ryunova_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organisation_id, name)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_brands_organisation_id ON ryunova_brands(organisation_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_brands_active ON ryunova_brands(active);
CREATE INDEX IF NOT EXISTS ix_ryunova_brands_created_by_user_id ON ryunova_brands(created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_brands_updated_by_user_id ON ryunova_brands(updated_by_user_id);

CREATE TABLE IF NOT EXISTS ryunova_product_master (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organisation_id UUID NOT NULL REFERENCES ryunova_organisations(id) ON DELETE RESTRICT,
  sku VARCHAR(128) NOT NULL,
  title VARCHAR(500) NOT NULL,
  description TEXT,
  "condition" ryunova_product_condition NOT NULL,
  brand_id UUID REFERENCES ryunova_brands(id) ON DELETE SET NULL,
  model VARCHAR(255),
  category_id UUID REFERENCES ryunova_categories(id) ON DELETE SET NULL,
  colour VARCHAR(255),
  length_cm NUMERIC(12, 3),
  width_cm NUMERIC(12, 3),
  depth_cm NUMERIC(12, 3),
  base_price NUMERIC(12,2) NOT NULL,
  compare_at_price NUMERIC(12,2),
  quantity INT NOT NULL DEFAULT 1,
  attributes JSONB,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by_user_id UUID REFERENCES ryunova_users(id) ON DELETE SET NULL,
  updated_by_user_id UUID REFERENCES ryunova_users(id) ON DELETE SET NULL,
  UNIQUE (organisation_id, sku)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_organisation_id ON ryunova_product_master(organisation_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_category_id ON ryunova_product_master(category_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_brand_id ON ryunova_product_master(brand_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_status ON ryunova_product_master(status);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_active ON ryunova_product_master(active);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_created_by_user_id ON ryunova_product_master(created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_updated_by_user_id ON ryunova_product_master(updated_by_user_id);

CREATE TABLE IF NOT EXISTS ryunova_product_image (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES ryunova_product_master(id) ON DELETE CASCADE,
  sort_order INT NOT NULL DEFAULT 0,
  media_type VARCHAR(16) NOT NULL DEFAULT 'image',
  is_cover BOOLEAN NOT NULL DEFAULT false,
  s3_bucket VARCHAR(255) NOT NULL,
  s3_key VARCHAR(512) NOT NULL,
  filename VARCHAR(255),
  content_type VARCHAR(128),
  size_bytes BIGINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ryunova_product_image_product_id ON ryunova_product_image(product_id);

CREATE TABLE IF NOT EXISTS ryunova_email_verification_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES ryunova_users(id) ON DELETE CASCADE,
  token_hash VARCHAR(128) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ryunova_email_verification_tokens_hash ON ryunova_email_verification_tokens(token_hash);

-- ---------------------------------------------------------------------------
-- Optional manual SQL (not run by default)
-- ---------------------------------------------------------------------------
-- After importing legacy rows, align sort_order with alphabetical name (0-based):
--
-- UPDATE ryunova_categories AS c
-- SET sort_order = sub.rn
-- FROM (
--   SELECT id, ROW_NUMBER() OVER (ORDER BY LOWER(name)) - 1 AS rn
--   FROM ryunova_categories
-- ) AS sub
-- WHERE c.id = sub.id;
--
-- UPDATE ryunova_brands AS b
-- SET sort_order = sub.rn
-- FROM (
--   SELECT id, ROW_NUMBER() OVER (ORDER BY LOWER(name)) - 1 AS rn
--   FROM ryunova_brands
-- ) AS sub
-- WHERE b.id = sub.id;
--
-- Link existing users to the default organisation (replace with your UUIDs if needed):
--
-- INSERT INTO ryunova_user_organisations (user_id, organisation_id)
-- SELECT u.id, '00000000-0000-4000-8000-000000000001'::uuid
-- FROM ryunova_users u
-- ON CONFLICT (user_id, organisation_id) DO NOTHING;
--
-- Grant platform access by email — see docs/MULTI_TENANT.md § Bootstrap.
