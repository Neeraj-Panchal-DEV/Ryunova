# Database

- **`mvp1_schema.sql`** — Full MVP1 PostgreSQL DDL for a **new** database (multi-tenant orgs, users, catalog, product media, email verification). Run once on an empty DB.

```bash
psql -U ryunova -d ryunova -f db/mvp1_schema.sql
```

- **Bootstrap / ops** (platform user, org membership): see **`docs/MULTI_TENANT.md`** and the commented optional section at the end of `mvp1_schema.sql`.

Incremental patches (run in order when upgrading an existing DB):

- **`patch_login_otp.sql`** — `ryunova_login_codes` for email sign-in codes (`POST /auth/login-otp/*`).

- **`patch_user_profile.sql`** — Extended profile fields (`public_code`, names, DOB, phone E.164, job title, social handles JSON, pending email) and email-change verification token columns.

- **`patch_public_code_10_alnum.sql`** — Notes only: new users get 10-character `A–Z0–9` public codes; optional `backend/scripts/backfill_public_codes.py` to rewrite legacy values.

For a full greenfield install, compare `mvp1_schema.sql` with `docs/DATABASE_SCHEMA.md` and apply any newer patches not yet merged into the main DDL.
