-- Product comments (internal collaboration on product master rows).
SET search_path TO ryunova, public;

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
