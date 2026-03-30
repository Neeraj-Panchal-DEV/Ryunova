-- Listing channels (e-commerce), product readiness, and per-channel posting matrix.
-- listing_readiness: draft = work in progress; ready_to_post = channel flags may be enabled.

DO $lr$ BEGIN
  ALTER TABLE ryunova.ryunova_product_master
    ADD COLUMN listing_readiness VARCHAR(32) NOT NULL DEFAULT 'draft';
EXCEPTION
  WHEN duplicate_column THEN NULL;
END $lr$;

DO $lrchk$ BEGIN
  ALTER TABLE ryunova.ryunova_product_master
    ADD CONSTRAINT chk_ryunova_product_listing_readiness
    CHECK (listing_readiness IN ('draft', 'ready_to_post'));
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $lrchk$;

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
