-- Physical attributes: colour + L×W×D in centimetres (nullable).
-- Run after mvp1_schema.sql on existing databases.

ALTER TABLE ryunova_product_master
  ADD COLUMN IF NOT EXISTS colour VARCHAR(255),
  ADD COLUMN IF NOT EXISTS length_cm NUMERIC(12, 3),
  ADD COLUMN IF NOT EXISTS width_cm NUMERIC(12, 3),
  ADD COLUMN IF NOT EXISTS depth_cm NUMERIC(12, 3);
