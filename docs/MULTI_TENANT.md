# Multi-tenant workspace (organisation)

## Terminology: `is_platform_user` (same as former `is_system_user`)

**`is_system_user` and `is_platform_user` are the same flag** — one concept (product/platform operator with full-tenant access). The **canonical** database and API field is **`is_platform_user`**. Older patches and clients may still say “system user” or expose **`is_system_user`** in JSON; treat it as **identical** to **`is_platform_user`**. New code and docs should use **`is_platform_user`** only.

## Data model

- Catalog rows (`categories`, `brands`, `products`) are scoped by `organisation_id`.
- Users link to organisations via `ryunova_user_organisations` (many-to-many).
- **`is_platform_user`**: product/platform operators — see **all** organisations, optional `X-Organisation-Id` to scope; can **create organisations** (name, slug, description, logo) and **invite users to any org**; can **PATCH** `/admin/users/{id}` (`is_platform_user`, `user_admin_access`). At least one platform user must always exist.
- **`user_admin_access`**: organisation **user admin** — can **invite users only into organisations they belong to** (same invite API; membership checked server-side). Cannot create organisations or grant platform access.

**Legacy databases** that still have **`is_system_user`**: migrate to **`is_platform_user`** (same meaning) by copying the flag, then drop **`is_system_user`**, or diff your schema against **`db/mvp1_schema.sql`** / **`docs/DATABASE_SCHEMA.md`**. Incremental patch files are no longer shipped in this repo.

## Web (Django)

- Session stores `access_token`, `is_platform_user`, `user_admin_access`, `organisations`, optional `organisation_id`, and **`workspace_scope_confirmed`** after the user completes the org picker (or single-org auto scope at login).
- **After sign-in**, **platform users** always land on **Choose organisation** first (pick **All organisations** or a specific org), then the dashboard and catalog.
- **Non–platform users** with **more than one** organisation → **Choose organisation** before the dashboard/catalog (same picker).
- **Non–platform users** with exactly one organisation skip the picker; `organisation_id` is set at login.
- Platform users working in **All organisations** keep `organisation_id` unset; they can scope one org from the switcher anytime.
- **Header**: **Platform** users see **RyuNova Platform** next to the logo; **non–platform** users see their **organisation name** (org chip is hidden when they only have one org to avoid duplication; multi-org shows a **Switch organisation** chip with the current org name in the tooltip).
- **Menus**: under the profile avatar → **Profile**, **Users** submenu (platform: **Organisation users**, **Invite user (any organisation)**, **New organisation**; org user-admin: **Invite team member**; platform + org admin see both groups), **Sign out**.
- Catalog API calls send `X-Organisation-Id` when `organisation_id` is set in session.

## API (FastAPI)

- `OrganisationContextDep` (`X-Organisation-Id`): platform users may omit header for global read; others must send a header for a member org.
- `POST /organisations` (multipart or form): **platform only** — create org + optional logo.
- `POST /admin/users/invite`: **platform** (any org) **or** **user_admin_access** + member of target org.
- `GET /admin/organisations/{organisation_id}/users`: **platform only** — list members (for the organisation-users UI).
- `PATCH /admin/users/{user_id}`: **platform only** — set `is_platform_user`, `user_admin_access`.
- `GET /auth/me` / login include **`is_platform_user`** (canonical), **`user_admin_access`**, and **`is_system_user`** (same value as `is_platform_user`, kept for older clients only).

## Invites & email

- Invite flows send verification + temporary password email. Configure **`SITE_URL`** and SMTP — see **[EMAIL_SETTINGS.md](EMAIL_SETTINGS.md)**.

## Bootstrap

- Ensure at least one **platform user** remains.
- New databases: apply **`db/mvp1_schema.sql`** only — it includes **`is_platform_user`** / **`user_admin_access`** (no **`is_system_user`** column).

### SQL: grant `is_platform_user` by email

Run in `psql` after the user row exists (adjust email):

```sql
UPDATE ryunova_users
SET is_platform_user = true,
    email_verified_at = COALESCE(email_verified_at, now())
WHERE lower(trim(email)) = lower('admin@example.com');

SELECT id, email, is_platform_user, user_admin_access,
       email_verified_at IS NOT NULL AS email_verified
FROM ryunova_users
WHERE lower(trim(email)) = lower('admin@example.com');
```

After creating users, link them to organisations with **`ryunova_user_organisations`** (see optional snippet at the end of **`db/mvp1_schema.sql`**).
