# RyuNova Platform (application)

Multi-channel listing and product hub — **Phase 0 + MVP1** implemented here.

| Part | Stack | Path |
|------|--------|------|
| API | FastAPI, JWT, SQLAlchemy, PostgreSQL | `backend/` |
| Admin UI | Django (calls API with Bearer token) | `web/` |
| Schema | `ryunova_*` tables | `db/mvp1_schema.sql` |

Design docs live in [`docs/`](docs/README.md). **Security (users + organisations):** [docs/SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md). **MVP1 build summary (what was delivered):** [docs/MVP1_BUILD_AND_DELIVERY.md](docs/MVP1_BUILD_AND_DELIVERY.md). **Production deployment (EC2, ALB):** [docs/DEPLOYMENT_EC2_ALB.md](docs/DEPLOYMENT_EC2_ALB.md).

## Quick start

See **[LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md)** for PostgreSQL setup, seed user, and run commands.

Summary:

1. Apply `db/mvp1_schema.sql` to database `ryunova`.
2. **Terminal A —** `backend/`: install deps, `python scripts/seed_user.py`, `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
3. **Terminal B —** `web/`: install deps, `python manage.py migrate`, `runserver 0.0.0.0:8001`.

Django talks to the API on port **8000**; if the API isn’t running, sign-in will fail until you start it.

**Web routes:** `/` — landing; `/dashboard/` — home dashboard (signed in, demo stats for now); `/products/` — catalog; `/accounts/login/` — Uber-style login (+ Google/Apple stubs).

Default seed: `admin@example.com` / `admin123` (change after first login). Do not use `@*.local` for login — validation rejects `.local` emails.
