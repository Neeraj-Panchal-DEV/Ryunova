-- One-time: set sort_order from name (A→Z), 0-based. Run manually if you want DB order
-- aligned with alphabetical name before using the admin “Order A–Z by name” button.
UPDATE ryunova_categories AS c
SET sort_order = sub.rn
FROM (
  SELECT id, ROW_NUMBER() OVER (ORDER BY LOWER(name)) - 1 AS rn
  FROM ryunova_categories
) AS sub
WHERE c.id = sub.id;

UPDATE ryunova_brands AS b
SET sort_order = sub.rn
FROM (
  SELECT id, ROW_NUMBER() OVER (ORDER BY LOWER(name)) - 1 AS rn
  FROM ryunova_brands
) AS sub
WHERE b.id = sub.id;
