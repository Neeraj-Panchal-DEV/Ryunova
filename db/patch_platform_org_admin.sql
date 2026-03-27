-- is_platform_user is the same concept as legacy is_system_user (one flag). This patch adds
-- is_platform_user / user_admin_access, copies from is_system_user if present, then drops is_system_user.
-- Also: org user admins, organisation logo/description.
-- Run after patch_multi_tenant.sql (or any DB that has ryunova_users / ryunova_organisations).

ALTER TABLE ryunova_organisations ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE ryunova_organisations ADD COLUMN IF NOT EXISTS logo_s3_key VARCHAR(512);

ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS is_platform_user BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE ryunova_users ADD COLUMN IF NOT EXISTS user_admin_access BOOLEAN NOT NULL DEFAULT false;

-- Migrate legacy system-user flag into platform_user
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'ryunova_users' AND column_name = 'is_system_user'
  ) THEN
    UPDATE ryunova_users SET is_platform_user = true WHERE is_system_user = true;
  END IF;
END $$;

-- Ensure at least one platform user (first created user), if none marked
UPDATE ryunova_users u
SET is_platform_user = true
FROM (SELECT id FROM ryunova_users ORDER BY created_at ASC NULLS LAST LIMIT 1) first_u
WHERE u.id = first_u.id
  AND NOT EXISTS (SELECT 1 FROM ryunova_users p WHERE p.is_platform_user = true);

ALTER TABLE ryunova_users DROP COLUMN IF EXISTS is_system_user;
