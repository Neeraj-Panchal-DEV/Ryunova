-- =============================================================================
-- One-time: move legacy public.ryunova_* tables into schema ryunova
-- =============================================================================
-- The FastAPI app and canonical DDL use **ryunova.ryunova_*** (see backend/app/database.py
-- and db/mvp1_schema.sql). Older setups had the same table names in **public**.
--
-- Symptoms: `relation "ryunova.ryunova_users" does not exist` while
-- `public.ryunova_users` exists.
--
-- Do **not** add this file to db/migrations/order.txt — greenfield installs already
-- create objects under schema ryunova via mvp1_schema.sql.
--
-- Usage (from repo root, adjust connection flags as needed):
--   psql -U ryunova -d ryunova -v ON_ERROR_STOP=1 -f db/move_public_tables_to_ryunova_schema.sql
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS ryunova;

-- Enum used by ryunova_product_master."condition" — must move before that table if it lives in public.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'public' AND t.typname = 'ryunova_product_condition'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'ryunova' AND t.typname = 'ryunova_product_condition'
  ) THEN
    ALTER TYPE public.ryunova_product_condition SET SCHEMA ryunova;
  END IF;
END $$;

-- Dependency order: parents before referencing tables.
DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'ryunova_organisations',
    'ryunova_users',
    'ryunova_user_roles',
    'ryunova_categories',
    'ryunova_brands',
    'ryunova_product_master',
    'ryunova_product_image',
    'ryunova_user_organisations',
    'ryunova_oauth_tokens',
    'ryunova_login_codes',
    'ryunova_email_verification_tokens',
    'ryunova_product_comments'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables
  LOOP
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = tbl) THEN
      IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'ryunova' AND tablename = tbl) THEN
        RAISE EXCEPTION 'Both public.% and ryunova.% exist — resolve duplicate manually before re-running.', tbl, tbl;
      END IF;
      EXECUTE format('ALTER TABLE public.%I SET SCHEMA ryunova', tbl);
      RAISE NOTICE 'Moved public.% to ryunova.%', tbl, tbl;
    END IF;
  END LOOP;
END $$;
