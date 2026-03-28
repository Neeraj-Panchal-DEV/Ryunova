# Database

## Canonical DDL

**`mvp1_schema.sql`** is the **only** required file for a new database. It creates schema **`ryunova`**, all **`ryunova.ryunova_*`** tables, indexes, enum type, and comments (including login codes, full user profile columns, email-change token fields, product dimensions, media cover flags — everything that used to live in separate `patch_*.sql` files).

```bash
psql -U ryunova -d ryunova -f db/mvp1_schema.sql
```

- **Bootstrap / ops** (platform user, org membership): see **`docs/MULTI_TENANT.md`** and the commented optional section at the end of **`mvp1_schema.sql`**.
- **Optional data-only SQL** (not in deploy order): **`patch_taxonomy_sort_by_name.sql`** — one-time sort_order backfill; run manually if needed.
- **`patch_public_code_10_alnum.sql`** — notes only (10-char codes; optional **`backend/scripts/backfill_public_codes.py`**).
- **`patch_multi_tenant.sql`** — **legacy** (old **public**-schema upgrades); do not use on a greenfield **`ryunova`** database.

---

## Production / EC2 (GitHub Actions)

Deploy (`.github/workflows/deploy-prod.yml`) runs **`scripts/run_ryunova_migrations.sh`** on the instance after `git pull`. It:

1. Creates the target database **if it does not exist** (admin must be allowed to `CREATE DATABASE`, or create the DB manually).
2. Ensures the **app role** from `PROD_POSTGRES_APPL_*` exists and sets password.
3. Applies SQL files listed in **`db/migrations/order.txt`** in order (typically **`mvp1_schema.sql`** only), skipping any filename already recorded in **`ryunova.ryunova_schema_migrations`**.
4. Grants DML on **`ryunova.ryunova_*`** app tables (not **`ryunova.ryunova_schema_migrations`**) to the app role.

FinText continues to use schema **`fintext`** in the same **`latrobe_apps_db`** when shared.

### Future schema changes

1. Add **`db/migrations/002_add_feature.sql`** (or similar), idempotent **`IF NOT EXISTS`** / **`ADD COLUMN IF NOT EXISTS`** where possible.
2. Append **only the filename** to the end of **`db/migrations/order.txt`**.
3. Merge to **`prod`** and deploy.

---

## Local database reset (after consolidating patches)

If you previously applied old **`patch_*.sql`** files to a dev DB, either **drop and recreate** the database and run **`mvp1_schema.sql`** once, or diff your DB against this repo and write your own `ALTER` scripts.

For a full greenfield install, align with **`docs/DATABASE_SCHEMA.md`** as needed.
