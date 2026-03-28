-- Elevate a user to platform user (is_platform_user = true).
-- Change v_email in the DO block and the final SELECT to the same address. Run e.g.:
--   psql -U ryunova -d ryunova -f db/elevate_platform_user.sql
--
-- Works after db/mvp1_schema.sql (is_platform_user / user_admin_access on ryunova.ryunova_users).
-- If you still only have is_system_user (before that patch), the DO block sets that instead.

DO $$
DECLARE
  v_email text := lower(trim('admin@example.com'));  -- <-- edit here
  n int;
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'ryunova' AND table_name = 'ryunova_users' AND column_name = 'is_platform_user'
  ) THEN
    UPDATE ryunova.ryunova_users SET is_platform_user = true WHERE lower(trim(email)) = v_email;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n = 0 THEN
      RAISE NOTICE 'No row updated: no user with email %', v_email;
    ELSE
      RAISE NOTICE 'Updated % user(s) to is_platform_user for email %', n, v_email;
    END IF;
  ELSIF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'ryunova' AND table_name = 'ryunova_users' AND column_name = 'is_system_user'
  ) THEN
    UPDATE ryunova.ryunova_users SET is_system_user = true WHERE lower(trim(email)) = v_email;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n = 0 THEN
      RAISE NOTICE 'No row updated: no user with email %', v_email;
    ELSE
      RAISE NOTICE 'Updated % user(s) to is_system_user for email %', n, v_email;
    END IF;
  ELSE
    RAISE EXCEPTION 'ryunova.ryunova_users has neither is_platform_user nor is_system_user — apply patches first.';
  END IF;

  -- Optional: ensure they can sign in if your app requires verified email
  UPDATE ryunova.ryunova_users
  SET email_verified_at = COALESCE(email_verified_at, now())
  WHERE lower(trim(email)) = v_email;
END $$;

-- Show result (same email as v_email above)
SELECT id, email, is_platform_user, user_admin_access, email_verified_at IS NOT NULL AS email_verified
FROM ryunova.ryunova_users
WHERE lower(trim(email)) = lower(trim('admin@example.com'));
