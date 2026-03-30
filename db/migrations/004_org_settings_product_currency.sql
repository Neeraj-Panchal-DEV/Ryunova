-- Organisation profile fields + default currency; product price currency (default AUD).

ALTER TABLE ryunova.ryunova_organisations
  ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'AUD',
  ADD COLUMN IF NOT EXISTS website_url VARCHAR(512),
  ADD COLUMN IF NOT EXISTS address_line1 VARCHAR(255),
  ADD COLUMN IF NOT EXISTS address_line2 VARCHAR(255),
  ADD COLUMN IF NOT EXISTS address_locality VARCHAR(128),
  ADD COLUMN IF NOT EXISTS address_region VARCHAR(128),
  ADD COLUMN IF NOT EXISTS address_postal_code VARCHAR(32),
  ADD COLUMN IF NOT EXISTS address_country VARCHAR(2),
  ADD COLUMN IF NOT EXISTS address_place_id VARCHAR(256),
  ADD COLUMN IF NOT EXISTS tax_identifier VARCHAR(64),
  ADD COLUMN IF NOT EXISTS key_contact_name VARCHAR(255),
  ADD COLUMN IF NOT EXISTS key_contact_email VARCHAR(255),
  ADD COLUMN IF NOT EXISTS key_contact_phone VARCHAR(64);

ALTER TABLE ryunova.ryunova_product_master
  ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'AUD';

COMMENT ON COLUMN ryunova.ryunova_organisations.tax_identifier IS 'ABN, VAT ID, EIN, etc.';
COMMENT ON COLUMN ryunova.ryunova_organisations.address_place_id IS 'Google Places place_id when using address autocomplete';
