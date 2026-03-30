-- =============================================================================
-- RyuNova Platform — PostgreSQL schema (canonical / greenfield)
-- =============================================================================
-- Single DDL file: schema **ryunova**, tables **ryunova.ryunova_***. FinText uses
-- **fintext** in the same database when shared.
--
--   psql -U ryunova -d ryunova -f db/mvp1_schema.sql
--
-- Includes (formerly separate patches / migrations, now merged):
--   • Multi-tenant orgs, user–org links, OAuth tokens, login OTP codes
--   • Users: public_code, profile fields, social_handles, pending_email, platform flags
--   • Email verification tokens: token_kind, new_email (email change flow)
--   • Categories, brands, products (dimensions, condition enum, listing_readiness), product media
--   • Product comments (internal collaboration)
--   • Listing channels / marketplace matrix (per-product flags; seed rows for Amazon, eBay, …)
--
-- New environments: run this file only (see **db/README.md**). Production deploy no longer
-- applies SQL automatically; use **`scripts/run_ryunova_migrations.sh`** manually if needed.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS ryunova;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

DO $$ BEGIN
  CREATE TYPE ryunova.ryunova_product_condition AS ENUM ('new', 'used', 'refurbished');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS ryunova.ryunova_organisations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL UNIQUE,
  description TEXT,
  logo_s3_key VARCHAR(512),
  currency_code VARCHAR(3) NOT NULL DEFAULT 'AUD',
  website_url VARCHAR(512),
  address_line1 VARCHAR(255),
  address_line2 VARCHAR(255),
  address_locality VARCHAR(128),
  address_region VARCHAR(128),
  address_postal_code VARCHAR(32),
  address_country VARCHAR(2),
  address_place_id VARCHAR(256),
  tax_identifier VARCHAR(64),
  key_contact_name VARCHAR(255),
  key_contact_email VARCHAR(255),
  key_contact_phone VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO ryunova.ryunova_organisations (id, name, slug)
VALUES (
  '00000000-0000-4000-8000-000000000001'::uuid,
  'Default organization',
  'default'
)
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS ryunova.ryunova_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  public_code VARCHAR(40) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  display_name VARCHAR(255),
  first_name VARCHAR(128),
  last_name VARCHAR(128),
  date_of_birth DATE,
  phone_e164 VARCHAR(24),
  job_title VARCHAR(255),
  social_handles JSONB NOT NULL DEFAULT '{}'::jsonb,
  pending_email VARCHAR(255),
  password_hash VARCHAR(255),
  avatar_s3_key VARCHAR(512),
  is_platform_user BOOLEAN NOT NULL DEFAULT false,
  user_admin_access BOOLEAN NOT NULL DEFAULT false,
  email_verified_at TIMESTAMPTZ,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ryunova_users_public_code_key UNIQUE (public_code)
);

CREATE TABLE IF NOT EXISTS ryunova.ryunova_user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES ryunova.ryunova_users(id) ON DELETE CASCADE,
  role VARCHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, role)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_user_roles_user_id ON ryunova.ryunova_user_roles(user_id);

CREATE TABLE IF NOT EXISTS ryunova.ryunova_user_organisations (
  user_id UUID NOT NULL REFERENCES ryunova.ryunova_users(id) ON DELETE CASCADE,
  organisation_id UUID NOT NULL REFERENCES ryunova.ryunova_organisations(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, organisation_id)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_user_organisations_org ON ryunova.ryunova_user_organisations(organisation_id);

CREATE TABLE IF NOT EXISTS ryunova.ryunova_oauth_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES ryunova.ryunova_users(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS ix_ryunova_oauth_tokens_user_id ON ryunova.ryunova_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_oauth_tokens_provider ON ryunova.ryunova_oauth_tokens(provider);

CREATE TABLE IF NOT EXISTS ryunova.ryunova_login_codes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES ryunova.ryunova_users(id) ON DELETE CASCADE,
  code_hash VARCHAR(128) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ryunova_login_codes_user_created
  ON ryunova.ryunova_login_codes (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_ryunova_login_codes_code_hash ON ryunova.ryunova_login_codes (code_hash);

CREATE TABLE IF NOT EXISTS ryunova.ryunova_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organisation_id UUID NOT NULL REFERENCES ryunova.ryunova_organisations(id) ON DELETE RESTRICT,
  parent_id UUID REFERENCES ryunova.ryunova_categories(id) ON DELETE SET NULL,
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255),
  description TEXT,
  sort_order INT DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT true,
  created_by_user_id UUID REFERENCES ryunova.ryunova_users(id) ON DELETE SET NULL,
  updated_by_user_id UUID REFERENCES ryunova.ryunova_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ryunova_categories_organisation_id ON ryunova.ryunova_categories(organisation_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_categories_parent_id ON ryunova.ryunova_categories(parent_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_categories_active ON ryunova.ryunova_categories(active);
CREATE INDEX IF NOT EXISTS ix_ryunova_categories_created_by_user_id ON ryunova.ryunova_categories(created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_categories_updated_by_user_id ON ryunova.ryunova_categories(updated_by_user_id);

CREATE TABLE IF NOT EXISTS ryunova.ryunova_brands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organisation_id UUID NOT NULL REFERENCES ryunova.ryunova_organisations(id) ON DELETE RESTRICT,
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255),
  description TEXT,
  sort_order INT DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT true,
  created_by_user_id UUID REFERENCES ryunova.ryunova_users(id) ON DELETE SET NULL,
  updated_by_user_id UUID REFERENCES ryunova.ryunova_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organisation_id, name)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_brands_organisation_id ON ryunova.ryunova_brands(organisation_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_brands_active ON ryunova.ryunova_brands(active);
CREATE INDEX IF NOT EXISTS ix_ryunova_brands_created_by_user_id ON ryunova.ryunova_brands(created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_brands_updated_by_user_id ON ryunova.ryunova_brands(updated_by_user_id);

CREATE TABLE IF NOT EXISTS ryunova.ryunova_product_master (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organisation_id UUID NOT NULL REFERENCES ryunova.ryunova_organisations(id) ON DELETE RESTRICT,
  sku VARCHAR(128) NOT NULL,
  title VARCHAR(500) NOT NULL,
  description TEXT,
  "condition" ryunova.ryunova_product_condition NOT NULL,
  brand_id UUID REFERENCES ryunova.ryunova_brands(id) ON DELETE SET NULL,
  model VARCHAR(255),
  category_id UUID REFERENCES ryunova.ryunova_categories(id) ON DELETE SET NULL,
  colour VARCHAR(255),
  length_cm NUMERIC(12, 3),
  width_cm NUMERIC(12, 3),
  depth_cm NUMERIC(12, 3),
  base_price NUMERIC(12,2) NOT NULL,
  currency_code VARCHAR(3) NOT NULL DEFAULT 'AUD',
  compare_at_price NUMERIC(12,2),
  quantity INT NOT NULL DEFAULT 1,
  attributes JSONB,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  listing_readiness VARCHAR(32) NOT NULL DEFAULT 'draft',
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by_user_id UUID REFERENCES ryunova.ryunova_users(id) ON DELETE SET NULL,
  updated_by_user_id UUID REFERENCES ryunova.ryunova_users(id) ON DELETE SET NULL,
  UNIQUE (organisation_id, sku),
  CONSTRAINT chk_ryunova_product_listing_readiness CHECK (listing_readiness IN ('draft', 'ready_to_post'))
);

CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_organisation_id ON ryunova.ryunova_product_master(organisation_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_category_id ON ryunova.ryunova_product_master(category_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_brand_id ON ryunova.ryunova_product_master(brand_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_status ON ryunova.ryunova_product_master(status);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_active ON ryunova.ryunova_product_master(active);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_created_by_user_id ON ryunova.ryunova_product_master(created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_product_master_updated_by_user_id ON ryunova.ryunova_product_master(updated_by_user_id);

CREATE TABLE IF NOT EXISTS ryunova.ryunova_product_image (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES ryunova.ryunova_product_master(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS ix_ryunova_product_image_product_id ON ryunova.ryunova_product_image(product_id);

-- Listing channels (e-commerce / marketplaces) and per-product posting matrix
CREATE TABLE IF NOT EXISTS ryunova.ryunova_listing_channel (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  integration_requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
  active BOOLEAN NOT NULL DEFAULT true,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_ryunova_listing_channel_code UNIQUE (code)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_listing_channel_active ON ryunova.ryunova_listing_channel(active);
CREATE INDEX IF NOT EXISTS ix_ryunova_listing_channel_sort ON ryunova.ryunova_listing_channel(sort_order);

CREATE TABLE IF NOT EXISTS ryunova.ryunova_product_channel_listing (
  product_id UUID NOT NULL REFERENCES ryunova.ryunova_product_master(id) ON DELETE CASCADE,
  channel_id UUID NOT NULL REFERENCES ryunova.ryunova_listing_channel(id) ON DELETE CASCADE,
  enabled BOOLEAN NOT NULL DEFAULT false,
  last_refreshed_at TIMESTAMPTZ,
  posted_at TIMESTAMPTZ,
  PRIMARY KEY (product_id, channel_id)
);

CREATE INDEX IF NOT EXISTS ix_ryunova_pcl_channel ON ryunova.ryunova_product_channel_listing(channel_id);
CREATE INDEX IF NOT EXISTS ix_ryunova_pcl_product ON ryunova.ryunova_product_channel_listing(product_id);

INSERT INTO ryunova.ryunova_listing_channel (code, name, sort_order, integration_requirements, description)
VALUES
  ('amazon', 'Amazon', 10, '{"oauth": false, "notes": "Seller Central; SP-API / MWS credentials and marketplace IDs."}'::jsonb, 'Amazon marketplace listings.'),
  ('ebay', 'eBay', 20, '{"oauth": true, "notes": "Trading API / OAuth application keys."}'::jsonb, 'eBay fixed-price or auction.'),
  ('shopify', 'Shopify', 30, '{"oauth": true, "notes": "Store URL, Admin API access token."}'::jsonb, 'Shopify store sync.'),
  ('facebook', 'Facebook', 40, '{"oauth": true, "notes": "Meta Commerce / Catalog; Business Manager."}'::jsonb, 'Facebook / Instagram shopping surfaces.'),
  ('usedcoffeegear', 'UsedCoffeeGear', 50, '{"oauth": false, "notes": "Site-specific listing API or manual export."}'::jsonb, 'UsedCoffeeGear marketplace.'),
  ('gumtree', 'Gumtree', 60, '{"oauth": false, "notes": "Region-specific; often manual or partner API."}'::jsonb, 'Gumtree classifieds.')
ON CONFLICT (code) DO NOTHING;

-- Product comments (internal collaboration on product master rows)
CREATE TABLE IF NOT EXISTS ryunova.ryunova_product_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES ryunova.ryunova_product_master(id) ON DELETE CASCADE,
  organisation_id UUID NOT NULL REFERENCES ryunova.ryunova_organisations(id) ON DELETE RESTRICT,
  user_id UUID NOT NULL REFERENCES ryunova.ryunova_users(id) ON DELETE RESTRICT,
  body TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ryunova_product_comments_product_created
  ON ryunova.ryunova_product_comments (product_id, created_at DESC);

COMMENT ON TABLE ryunova.ryunova_product_comments IS 'User comments on products; newest first in API.';

CREATE TABLE IF NOT EXISTS ryunova.ryunova_email_verification_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES ryunova.ryunova_users(id) ON DELETE CASCADE,
  token_hash VARCHAR(128) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  token_kind VARCHAR(32) NOT NULL DEFAULT 'signup',
  new_email VARCHAR(255),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ryunova_email_verification_tokens_hash ON ryunova.ryunova_email_verification_tokens(token_hash);

COMMENT ON COLUMN ryunova.ryunova_email_verification_tokens.token_kind IS 'signup | email_change';
COMMENT ON COLUMN ryunova.ryunova_email_verification_tokens.new_email IS 'Target email when token_kind is email_change';

-- ---------------------------------------------------------------------------
-- Optional manual SQL (not run by default)
-- ---------------------------------------------------------------------------
-- After importing legacy rows, align sort_order with alphabetical name (0-based):
--
-- UPDATE ryunova.ryunova_categories AS c
-- SET sort_order = sub.rn
-- FROM (
--   SELECT id, ROW_NUMBER() OVER (ORDER BY LOWER(name)) - 1 AS rn
--   FROM ryunova.ryunova_categories
-- ) AS sub
-- WHERE c.id = sub.id;
--
-- UPDATE ryunova.ryunova_brands AS b
-- SET sort_order = sub.rn
-- FROM (
--   SELECT id, ROW_NUMBER() OVER (ORDER BY LOWER(name)) - 1 AS rn
--   FROM ryunova.ryunova_brands
-- ) AS sub
-- WHERE b.id = sub.id;
--
-- Link existing users to the default organisation (replace with your UUIDs if needed):
--
-- INSERT INTO ryunova.ryunova_user_organisations (user_id, organisation_id)
-- SELECT u.id, '00000000-0000-4000-8000-000000000001'::uuid
-- FROM ryunova.ryunova_users u
-- ON CONFLICT (user_id, organisation_id) DO NOTHING;
--
-- Grant platform access by email — see docs/MULTI_TENANT.md § Bootstrap.
