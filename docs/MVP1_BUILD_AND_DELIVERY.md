# RyuNova Platform — MVP1 build and delivery summary

This document records **what was built** to reach **MVP1**: a working product hub with authentication, catalog data (categories, brands, products), images, and admin UI—**without** channel listing, sync, or background jobs.

Use it as a handoff: scope achieved, major actions, where things live, and what is intentionally deferred.

### Recent refinements (cumulative, not exhaustive)

- **Product audit** — `ryunova_product_master.updated_by_user_id`, API `created_by_label` / `updated_by_label`, Django product list + edit “Record details”, and setting `updated_by_user_id` on product update and image upload.
- **Taxonomy parity** — Categories and brands already had audit fields and UI; products were aligned to the same pattern.
- **Schema delivery** — All MVP1 DDL lives in **`db/mvp1_schema.sql`** only (multi-tenant orgs, platform flags, product media, etc.); no separate `db/patch_*.sql` files (see **LOCAL_DEVELOPMENT.md** for existing-DB guidance).

---

## 1. MVP1 goal (what “done” means)

| In scope (MVP1) | Out of scope (later MVPs) |
|------------------|---------------------------|
| PostgreSQL schema for users, roles, taxonomy, products, images | Redis, Celery, listing jobs |
| REST API (FastAPI) + JWT auth | eBay, Shopify, Amazon adapters |
| Django admin-style UI calling the API | Docker/EC2 deploy automation (documented, not required locally) |
| Product CRUD, search/filter, pagination | `ryunova_listing`, inventory, orders (full schema in docs only) |
| Categories & brands CRUD + enable/disable + audit display | OAuth provider flows beyond token table readiness |
| Product images (local upload path + metadata) | Real S3 production pipeline |

---

## 2. Architecture put in place

| Layer | Technology | Location |
|-------|------------|----------|
| API | FastAPI, Pydantic v2, SQLAlchemy 2, JWT (python-jose) | `backend/app/` |
| Database | PostgreSQL, `ryunova_*` naming | `db/mvp1_schema.sql` |
| UI | Django templates + static CSS/JS; server-side calls to API with Bearer token | `web/` |
| Config | `.env` / `pydantic-settings` (API), Django settings for API base URL | `backend/.env.example`, `web/ryunova_web/settings.py` |

**Pattern:** Django does not own product rows; it proxies JSON to FastAPI. Session stores the JWT after login (or equivalent pattern in your auth views).

---

## 3. Database actions (canonical schema)

All MVP1 DDL is consolidated in **`db/mvp1_schema.sql`** (greenfield: no incremental SQL migration files in-repo).

**Created / represented:**

1. **Extension:** `pgcrypto` (UUID generation).
2. **Enum:** `ryunova_product_condition` (`new`, `used`, `refurbished`).
3. **Tables:**
   - `ryunova_organisations`, `ryunova_user_organisations` (multi-tenant; default org seed)
   - `ryunova_users` — **`is_platform_user`**, **`user_admin_access`**, **`email_verified_at`**, **`avatar_s3_key`**, `ryunova_user_roles`
   - `ryunova_oauth_tokens` (structure for future SSO; not fully wired in UI)
   - `ryunova_email_verification_tokens`
   - `ryunova_categories` / `ryunova_brands` — `organisation_id`, parent/child (categories), `slug`, `description`, `sort_order`, `active`, audit columns, timestamps
   - `ryunova_product_master` — tenant-scoped SKU, title, description, condition, `brand_id`, `category_id`, **`colour`**, **`length_cm`**, **`width_cm`**, **`depth_cm`**, pricing, qty, `status`, `active`, attributes JSONB, audit columns, timestamps
   - `ryunova_product_image` — `product_id`, `sort_order`, **`media_type`** (`image` \| `video`), **`is_cover`**, bucket/key/filename/metadata (MVP1 uses local disk under `upload_dir` with `s3_bucket = local`)
4. **Indexes:** FKs, `active`, status, audit user ids, product image by `product_id`, org-scoped uniqueness (brands, SKU).

**Documentation:** Full long-form schema and future tables remain in **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)**; MVP1 implements the subset above.

**Repo hygiene:** No `db/patch_*.sql` or `db/migration_*.sql` in-repo; upgrades to old databases are “drop/recreate or hand-written `ALTER`” per **LOCAL_DEVELOPMENT.md** and **`db/mvp1_schema.sql`**.

---

## 4. Backend (FastAPI) — modules and behaviour

### 4.1 Core infrastructure

- **`app/main.py`** — Mounts `/api/v1` with routers; `/health`; serves uploaded media under `/api/v1/media/…` from `upload_dir`.
- **`app/database.py`** — SQLAlchemy engine and session.
- **`app/config.py`** — DB URL, JWT secret, CORS, `upload_dir`, public API URL for media links.
- **`app/security.py`** — Password hashing, JWT create/verify.
- **`app/dependencies.py`** — `CurrentUser` from Bearer token.

### 4.2 Auth

- **`routers/auth.py`** — `POST /auth/login` → JWT; `GET /auth/me` → user + roles + **`avatar_url`** + **`has_password`**; `PATCH /auth/me` (display name); `POST /auth/me/password`; `POST /auth/me/avatar` (multipart image, JPEG/PNG/GIF/WebP, max 5MB).

### 4.3 Taxonomy (categories & brands)

- **`routers/categories.py`**, **`routers/brands.py`** — List (with `include_inactive`, sort/order), get, create, patch, delete; **`POST /reorder`** (body `ordered_ids`) renumbers `sort_order`; **`POST /sort-by-name`** sets order A→Z by name; create with **`sort_order: null`** appends at end (`max+1`). Django: **`/categories/reorder/`**, **`/categories/sort-by-name/`** (and brand equivalents) + list UI drag handles when sorted by Sort ascending.
- **`models/category.py`**, **`models/brand.py`** — SQLAlchemy models + relationships to users for audit.
- **`schemas/category.py`**, **`schemas/brand.py`** — Pydantic IO models; read models include **`created_by_label`** / **`updated_by_label`**.
- **`taxonomy_display.py`** — Shared **`user_audit_label`** and **`enrich_*_read`** helpers for API responses.

### 4.4 Products

- **`routers/products.py`** — Paginated list (`q`, `status_filter`, `include_inactive`, `page`, `page_size`), get, create, patch, delete; **media upload** `POST /products/{id}/images` (multipart `file` + optional `is_cover`; images + video); **`POST /products/{id}/images/from-url`** (JSON `url`, optional `is_cover`) imports a **public image URL** (JPEG/PNG/GIF/WebP) with SSRF checks, stored under a filename derived from the product title; **`PATCH /products/{id}/images/{image_id}`** to set cover. List/read return **`images` ordered cover-first** for listings/channels. Product **`description`** is stored as **HTML** (admin rich text) for future channel sync (e.g. Shopify).
- **`models/product.py`** — `RyunovaProductMaster`, `RyunovaProductImage`; **`updated_by_user_id`**; relationships to `created_by_user` / `updated_by_user`.
- **`schemas/product.py`** — `ProductRead` includes audit ids + labels; list wrapper `ProductListPage`.
- **Audit rules:** On create, set both `created_by_user_id` and `updated_by_user_id`. On patch and on **image upload**, set `updated_by_user_id`. Responses use **`product_audit_labels()`** from `taxonomy_display.py`.

### 4.5 Tooling

- **`backend/scripts/seed_user.py`** — Create admin user + `admin` role (for first login).

---

## 5. Django (web) — UI actions

### 5.1 Routes (catalog)

| URL | Purpose |
|-----|---------|
| `/` | Landing / marketing-style intro |
| `/dashboard/` | Signed-in dashboard (demo-style content) |
| `/accounts/login/` | Login (Uber-style; social stubs as applicable) |
| `/products/` | Product list (filters, pagination, audit columns) |
| `/products/new/`, `/products/<uuid>/` | Create / edit product + multi image/video upload + cover selection |
| `/categories/`, `/categories/<uuid>/edit/` | Category management (JS-driven list + drawers per `taxonomy.js`) |
| `/brands/`, `/brands/<uuid>/edit/` | Brand management (same pattern) |

Defined in **`web/catalog/urls.py`**; views in **`web/catalog/views.py`** (API helpers: GET/POST/PATCH/DELETE with stored JWT).

### 5.2 Templates & static assets

- **Products:** `templates/catalog/product_list.html`, `product_form.html` — list shows date added / last modified / added by / updated by; edit form shows **Record details** block (aligned with taxonomy styling via `taxonomy.css`).
- **Taxonomy:** `category_list.html`, `brand_list.html`, edit templates; **`static/taxonomy.js`**, **`taxonomy.css`** — sorting, drawers, detail panel with audit fields.
- **Global:** `static/app.css` — tables, forms, layout; utilities (e.g. `text-nowrap` for tables).

### 5.3 Django’s own DB

- **`manage.py migrate`** — Django apps (sessions, auth tables, etc.) only; **not** the `ryunova_*` product schema.

---

## 6. Documentation and developer experience

| Document | Role |
|----------|------|
| **[LOCAL_DEVELOPMENT.md](../LOCAL_DEVELOPMENT.md)** | One path: create DB → `mvp1_schema.sql` → seed user → run uvicorn + runserver |
| **[README.md](../README.md)** | Repo overview and quick start pointer |
| **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)** | Full target schema (MVP1 + future); reference for extensions |
| **[MVP1_READINESS_AND_SKILLS.md](MVP1_READINESS_AND_SKILLS.md)** | Readiness checklist and skills |
| **[UX_REQUIREMENTS_AND_STANDARDS.md](UX_REQUIREMENTS_AND_STANDARDS.md)** | UI principles (compact, minimalist) |

---

## 7. Verification checklist (smoke test)

1. `psql` … `-f db/mvp1_schema.sql` on empty DB `ryunova`.
2. `python scripts/seed_user.py …` in `backend/`.
3. API: `uvicorn` on **8000** — `/health` 200; login returns JWT; CRUD categories, brands, products via `/api/v1/...`.
4. UI: `runserver` on **8001** — login, open products and taxonomy pages, create/edit rows, confirm audit columns populate after actions.

---

## 8. Summary

MVP1 delivery = **single PostgreSQL DDL file** + **FastAPI domain API** (auth, categories, brands, products, images, audit enrichment) + **Django shell** that **delegates persistence to the API** + **docs** for schema and local run. Channel listing, workers, and most tables in DATABASE_SCHEMA.md are **specified but not implemented**—that is the boundary for MVP2+.

---

*Last aligned with repo layout: MVP1 product hub + taxonomy + audit + consolidated `mvp1_schema.sql`.*
