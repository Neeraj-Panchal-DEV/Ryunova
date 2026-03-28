# RyuNova Platform — local development

Monorepo: **FastAPI** (`backend/`) + **Django** (`web/`), **PostgreSQL** database `ryunova`, JWT auth.

**You must run both servers.** Django (`:8001`) calls the API on **`:8000`**. If you only run `runserver`, login fails with “connection refused” until FastAPI is up:

1. **Terminal A — API:** `cd backend` → `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
2. **Terminal B — UI:** `cd web` → `python manage.py runserver 0.0.0.0:8001`

`0.0.0.0` binds all interfaces so **other devices on your LAN** can reach the app (see below). For laptop-only dev you can use `127.0.0.1` instead of `0.0.0.0`.

**Production (AWS EC2, ALB, GitHub Actions):** see **`docs/DEPLOYMENT_EC2_ALB.md`** — not this file.

**Important:** `manage.py` lives only under **`web/`**. If you see `can't open file '.../backend/manage.py'`, you ran Django from `backend/` — use `cd web` first. Each app can use its own `.venv` inside `backend/` and `web/`.

## Prerequisites

- Python 3.11+
- PostgreSQL with database `ryunova`, user `ryunova`, password `ryunova` (adjust `backend/.env` if different)

## 1. Database schema (once)

The canonical DDL is **`db/mvp1_schema.sql`** only (schema **`ryunova`**: users with profile + `public_code`, roles, OAuth, **login codes**, categories, brands, products, images, email verification tokens). Run against an **empty** database (or accept that `CREATE TABLE IF NOT EXISTS` will skip objects that already exist).

```bash
# From repo root (dragon-ryunova/)
psql -U ryunova -d ryunova -f db/mvp1_schema.sql
```

If `psql` is not found on macOS, install the client: `brew install postgresql@16` or `brew install libpq`, then add the `bin` directory to your `PATH` (Homebrew prints a hint after install).

With password:

```bash
PGPASSWORD=ryunova psql -h localhost -U ryunova -d ryunova -f db/mvp1_schema.sql
```

**Existing database from an older layout?** This repo no longer ships incremental SQL migrations. Either **drop and recreate** the database (then run `mvp1_schema.sql` and re-seed), or write your own `ALTER`/`UPDATE` scripts by diffing against `docs/DATABASE_SCHEMA.md` and `db/mvp1_schema.sql`.

## 2. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optional; defaults match ryunova/ryunova DB
python scripts/seed_user.py admin@example.com admin123 "Admin"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://127.0.0.1:8000/api/v1  
- Health: http://127.0.0.1:8000/health  
- Login (JSON): `POST /api/v1/auth/login` with `{"email":"...","password":"..."}`
- List products: `GET /api/v1/products` returns a **page** object: `{ "items": [...], "total", "page", "page_size", "total_pages" }`. Query params: `page` (1-based, default 1), `page_size` one of **10, 20, 50, 100** (default **20**), plus existing `q`, `status_filter`, `include_inactive`.

## 3. Web (Django)

```bash
cd web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8001
```

Optional: copy **`web/.env.example`** to **`web/.env`** and set LAN URLs / `CSRF_TRUSTED_ORIGINS` (see §3b).

- UI: http://127.0.0.1:8001/ — **landing** (public intro). **Dashboard (signed in):** http://127.0.0.1:8001/dashboard/ · **Catalog:** http://127.0.0.1:8001/products/ · **Login:** http://127.0.0.1:8001/accounts/login/  
- Sign in with the seeded user (e.g. `admin@example.com` / `admin123`). Avoid `@something.local` — the API rejects `.local` addresses (reserved domain).

If you already created `admin@ryunova.local` in the database, either sign in is impossible via the API for that address; add a new user with  
`python scripts/seed_user.py admin@example.com admin123 "Admin"`  
or delete the old row from `ryunova_users` and run the seed again.

`ryunova_web/settings.py` sets `RYUNOVA_API_BASE` to `http://127.0.0.1:8000/api/v1`. If the API runs elsewhere, change that and `API_PUBLIC_URL` in `backend/.env` for image URLs.

## 3b. Other computers / phones on the same Wi‑Fi

1. **Find your machine’s LAN IP** (e.g. `192.168.1.10`) — macOS: **System Settings → Network**; Windows: `ipconfig`; Linux: `ip a` or `hostname -I`.

2. **Bind both processes to all interfaces** (commands above already use `0.0.0.0`).

3. **Django (`web/`)** — With `DEBUG=true`, **`ALLOWED_HOSTS`** defaults include `*` so any `Host` header works. For **CSRF** on POST/login from `http://<LAN-IP>:8001`, append that origin to **`CSRF_TRUSTED_ORIGINS`** (env var or see `web/.env.example`). Example:
   ```bash
   export CSRF_TRUSTED_ORIGINS="http://127.0.0.1:8001,http://localhost:8001,http://192.168.1.10:8001"
   ```

4. **FastAPI (`backend/.env`)** — Add your Django origin to **`CORS_ORIGINS`** (comma-separated), e.g. `http://192.168.1.10:8001`.

5. **Public media URLs** — Set **`API_PUBLIC_URL`** in `backend/.env` to `http://<LAN-IP>:8000` so avatars and product images work in the browser on other devices (they cannot load `http://127.0.0.1:8000` from a phone). Optionally set **`RYUNOVA_API_PUBLIC`** (and **`RYUNOVA_API_BASE`**) in the Django environment to the same LAN host if anything still points at localhost.

6. **Firewall** — Allow inbound TCP **8000** and **8001** on the dev machine if the OS blocks them.

7. Open **`http://<LAN-IP>:8001/`** from the other device.

**Media / product image URLs:** With `DEBUG=true`, Django rewrites loopback API URLs in HTML/JSON responses to match the browser host (see `RYUNOVA_REWRITE_API_PUBLIC_IN_RESPONSES` and `RYUNOVA_API_PUBLIC_PORT` in `web/ryunova_web/settings.py`). You can still set **`API_PUBLIC_URL`** in `backend/.env` to your LAN IP if you prefer the API to emit correct URLs directly.

## 4. Typical workflow

1. Start PostgreSQL.
2. Terminal A: `uvicorn … --host 0.0.0.0` in `backend/`.
3. Terminal B: `runserver 0.0.0.0:8001` in `web/`.
4. Open http://127.0.0.1:8001/ for the home page, then **Sign in** (or go to `/accounts/login/`) and use **Products** in the nav for `/products/`.

## MVP1 scope

- Users, roles, categories, **brands** (lookup), products (brand chosen from list), product images (stored under `backend/uploads/`, metadata in `ryunova_product_image` with `s3_bucket = local`).
- No Celery, Redis, or channel listing yet (later MVPs).
