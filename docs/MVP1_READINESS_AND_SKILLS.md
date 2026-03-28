# RyuNova Platform – MVP1 readiness and skills

**First milestone (MVP1):** Foundation and product hub – single place to add/edit products (SKU, title, description, price, condition, images), product list and basic search, auth. No channel sync yet. (Weeks 1–2 per proposal.)

This document answers: (1) **Do we have all information to build MVP1?** (2) **What skills are needed to build and run the application?**

---

## 1. Do we have all information to build MVP1?

**Yes – with one small addition.** The existing docs are enough to start MVP1. You already have PostgreSQL locally; the rest is below.

### 1.1 What we have (and where)

| Need | Document / source | Status |
|------|-------------------|--------|
| **Database schema** | [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Complete. All `ryunova_*` tables and enums. For MVP1 use: `ryunova_users`, `ryunova_user_roles`, `ryunova_categories`, `ryunova_product_master`, `ryunova_product_image`; enums `ryunova_product_condition`. Optional for MVP1: `ryunova_oauth_tokens` if OAuth in scope. |
| **Tech stack** | [README.md](README.md), architecture plans | Confirmed: **FastAPI** (API), **Django** (frontend), PostgreSQL, Redis, Celery. For MVP1 you can defer Redis/Celery until MVP2 (listing jobs). |
| **API scope (MVP1)** | Architecture + schema | Product CRUD, Categories CRUD, Auth (login/session or JWT). Endpoints derivable from schema (e.g. GET/POST /products, GET/PUT /products/{id}, GET/POST /categories, POST /auth/login). |
| **Frontend scope (MVP1)** | Proposal plan + [UX_REQUIREMENTS_AND_STANDARDS.md](UX_REQUIREMENTS_AND_STANDARDS.md) | Product list (compact table), product add/edit form, category selection, login. Minimalist, compact layout. |
| **Deployment (later)** | [DEPLOYMENT_EC2_ALB.md](DEPLOYMENT_EC2_ALB.md) | For MVP1 you can run locally (see below); EC2/ALB when you deploy. |
| **Local database** | You | You have PostgreSQL installed locally. |

### 1.2 MVP1 schema subset (create first)

For a minimal MVP1 database, create in this order:

1. **Enums:** `ryunova_product_condition` (required for product).
2. **Tables:** `ryunova_users`, `ryunova_user_roles`, `ryunova_categories`, `ryunova_product_master`, `ryunova_product_image`.

Copy the `CREATE TYPE` and `CREATE TABLE` (and indexes) for these from [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) (Sections 2, 3.1, 3.2, 6.1, 7.1, 8.1). You can add the rest of the schema in later MVPs.

### 1.3 Optional gap (nice to have before coding)

- **Local development one-pager:** See **[LOCAL_DEVELOPMENT.md](../LOCAL_DEVELOPMENT.md)**. Production: **[DEPLOYMENT_EC2_ALB.md](DEPLOYMENT_EC2_ALB.md)**.

**Conclusion:** You have enough to build MVP1. Create the MVP1 schema subset in your local DB, then implement FastAPI (Product + Categories + Auth) and Django (product list, product form, login) against it.

---

## 2. Skills needed to build and run the application

### 2.1 Core (required for MVP1)

| Skill | Level | Why |
|-------|--------|-----|
| **Python 3.11+** | Solid | FastAPI and Django are Python. You need to write API routes, Django views, and use async/sync appropriately. |
| **FastAPI** | Working | Build REST endpoints (Product CRUD, Categories, Auth). Pydantic models from schema; connect to PostgreSQL (e.g. SQLAlchemy or asyncpg). |
| **Django** | Working | Frontend: project setup, views, templates, static files. Login (Django auth or call FastAPI for token). Forms for product create/edit. Consume FastAPI (e.g. `requests` or fetch from templates/JS). |
| **PostgreSQL** | Working | Create DB and apply `db/mvp1_schema.sql` (see LOCAL_DEVELOPMENT.md). Connection strings, basic tuning. You already have it installed. |
| **SQL** | Working | Queries and schema; understand ryunova_* tables and FKs. |
| **HTML / CSS / JS (basics)** | Working | Django templates, compact table/list UI per [UX_REQUIREMENTS_AND_STANDARDS.md](UX_REQUIREMENTS_AND_STANDARDS.md). Optional: minimal JS for form submit or dynamic list. |

### 2.2 Important for full MVP1 and MVP2

| Skill | Level | Why |
|-------|--------|-----|
| **REST APIs** | Working | Design and consume REST (FastAPI for backend; Django or browser calls FastAPI). |
| **Auth** | Basic | Login flow: Django session or JWT from FastAPI; password hashing, secure cookies. |
| **File storage (S3 or local)** | Basic | Product images: schema expects S3 (bucket/key). MVP1 can use local storage or S3 from day one. |

### 2.3 Needed for MVP2 and beyond

| Skill | Level | Why |
|-------|--------|-----|
| **Redis** | Basic | Celery broker for listing jobs (MVP2). |
| **Celery** | Basic | Listing Orchestrator worker (MVP2). |
| **Docker / Docker Compose** | Working | Local parity and deployment per [DEPLOYMENT_EC2_ALB.md](DEPLOYMENT_EC2_ALB.md). |
| **Channel APIs (eBay, Shopify, etc.)** | Per channel | OAuth/API keys, rate limits, payload mapping for adapters (MVP2). |
| **Git / GitHub Actions** | Working | Version control and deploy to EC2 (when you deploy). |

### 2.4 Nice to have

| Skill | Why |
|-------|-----|
| **Pydantic / SQLAlchemy** | FastAPI models and DB layer. |
| **Django REST or HTMX** | If you want Django to call FastAPI in a structured way or add interactivity without heavy JS. |
| **Linux / EC2** | When you deploy to a single server. |
| **Nginx / reverse proxy** | TLS and routing in production. |

---

## 3. Summary

- **MVP1 readiness:** Yes. You have schema (full and MVP1 subset above), stack (FastAPI + Django + PostgreSQL), UX standards, and deployment outline. With PostgreSQL already installed, you can create the MVP1 tables and start building.
- **Skills for MVP1:** Python, FastAPI, Django, PostgreSQL, SQL, and basic HTML/CSS/JS. Auth and (optionally) file storage round out MVP1. Redis/Celery and Docker become important from MVP2 and for deployment.
- **Next step:** Create the MVP1 schema in your local database, then implement the FastAPI app (products, categories, auth) and the Django app (product list, product form, login) against it.
