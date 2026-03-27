-- Add product media type + cover flag (idempotent). Run if your DB predates these columns.
ALTER TABLE ryunova_product_image ADD COLUMN IF NOT EXISTS media_type VARCHAR(16) NOT NULL DEFAULT 'image';
ALTER TABLE ryunova_product_image ADD COLUMN IF NOT EXISTS is_cover BOOLEAN NOT NULL DEFAULT false;

-- Ensure each product has at most one cover: pick first row by sort_order if none marked.
WITH first_img AS (
  SELECT DISTINCT ON (product_id) id, product_id
  FROM ryunova_product_image
  ORDER BY product_id, sort_order ASC, created_at ASC
),
needs_cover AS (
  SELECT f.id FROM first_img f
  WHERE NOT EXISTS (
    SELECT 1 FROM ryunova_product_image x WHERE x.product_id = f.product_id AND x.is_cover = true
  )
)
UPDATE ryunova_product_image i SET is_cover = true
FROM needs_cover n WHERE i.id = n.id;
