# RyuNova — Production deployment (EC2, ALB, GitHub Actions)

Single source of truth for **deploying RyuNova to AWS**: EC2, Application Load Balancer, optional ECR, shared PostgreSQL. This matches the model used for **dragon-latrobe_fintext** (FinText); RyuNova stays separate except when you **reuse the same database** (`ryunova` schema, `ryunova_*` tables).

**Compose file:** `docker-compose.app-only.yml` at **`/opt/apps/app_ryunova`** (project name **`ryunova`**). There is **no nginx** container in this stack—**ALB** routes to host ports **8010** (FastAPI) and **8011** (Django).

**Related:** `deploy/ec2.env.example`, `.github/workflows/deploy-prod.yml`, `scripts/deploy_generate_ec2_env.py`, `LOCAL_DEVELOPMENT.md` (local only). **User and organisation authorisation (JWT, tenant scope, Django session):** **[SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md)**.

---

## 1. What runs where

| Piece | Location | Host ports |
|--------|-----------|------------|
| FinText (if co-located) | Same EC2 | e.g. **8000** (separate ALB rules) |
| RyuNova **FastAPI** (`api`) | Docker | **8010** |
| RyuNova **Django** (`web`) | Docker | **8011** |
| PostgreSQL | Host or RDS | **5432** (not public) |

**App directory on the instance:** **`/opt/apps/app_ryunova`** — git checkout, `docker-compose.app-only.yml`, **`.env`**, `data/uploads/`. The deploy workflow creates **`/opt/apps`** if needed; it does **not** manage FinText’s tree under **`/opt/apps/apps_fintext`**.

**Internal calls:** Django → FastAPI uses **`RYUNOVA_API_BASE=http://api:8010/api/v1`** on the Docker network (`web/ryunova_web/api_client.py`).

---

## 2. ALB, DNS, and security groups

1. **Browser UI (Django):** Listener rule for your **site hostname** (e.g. `ryunova.example.com`) → target group → EC2 instance port **8011**.  
   - FastAPI has **no route for `GET /`**; if the UI hostname points at **8010**, browsers see JSON `{"detail":"Not Found"}`. **8011** serves `/` and `/accounts/login/`.

2. **Public API + media (required for images):** The browser loads avatars and product photos from **`https://api.<your-domain>/api/v1/media/...`** (see **`API_PUBLIC_URL`** / **`RYUNOVA_API_PUBLIC`** in `.env`). You **must** route the **API hostname** to port **8010** (FastAPI), not **8011** (Django).  
   - **Route 53:** Create **`A`/`AAAA` alias** (or `CNAME`) for **`api.<site>`** → same ALB as the app host.  
   - **ALB listener rule:** **Host header** `api.<your-site-domain>` → target group → EC2 → port **8010**.  
   If **`api.*` traffic hits 8011** (Django), `/api/v1/media/...` is not served by Django and **images break** (404 or wrong app).

3. **Security groups:** ALB → EC2 allow **8010** and **8011** from the ALB security group as needed. **PostgreSQL** is not exposed to the internet. Containers reach Postgres via **`host.docker.internal:5432`** (see generated `.env`).

4. **Health checks:** API target group: `GET /health` on **8010** (`{"status":"ok"}`). The GitHub workflow checks **`http://127.0.0.1:8010/health` over SSH** (not from the runner) so security groups do not need to open 8010 to GitHub.

5. **Quick check from your laptop:** After DNS propagates, open **`https://api.<your-domain>/health`** — expect **`{"status":"ok"}`**. Then **`https://api.<your-domain>/api/v1/media/`** may 404 (no index), but a **real avatar path** from the DB should return **200** with image bytes if routing and files are correct.

### HTTPS certificate and nested API hostnames

Deploy sets **`API_PUBLIC_URL`** / **`RYUNOVA_API_PUBLIC`** to **`https://api.<PROD_SITE_DOMAIN>`** (unless **`PROD_API_PUBLIC_HOST`** / **`API_HOST_VAL`** overrides it). If **`PROD_SITE_DOMAIN`** is **`ryunova.example.com`**, the API host is **`api.ryunova.example.com`** — **two** labels under the registrable domain, not one.

A single ACM wildcard such as **`*.latrobecomputing.co.in`** covers only **one** subdomain level (e.g. **`ryunova.latrobecomputing.co.in`**). It does **not** cover **`api.ryunova.latrobecomputing.co.in`**. The ALB then serves a certificate whose **Subject Alternative Names** do not match the API hostname → browsers show a **security warning** when opening the API or loading **`<img src="https://api.ryunova…/api/v1/media/…">`**, and images on **`/products/`** appear to **spin or fail**.

**Fix (pick one):**

1. **Extend the ACM certificate** used on the ALB **HTTPS listener** to include **`api.ryunova.<your-domain>`** (or a wildcard **`*.ryunova.<your-domain>`** if that matches your DNS layout). Complete **DNS validation** in ACM, then **associate the new cert** with the listener (same region as the ALB).
2. **Or** use a **flatter** API hostname that your existing wildcard already covers, e.g. **`ryunova-api.latrobecomputing.co.in`**, by setting GitHub secret **`PROD_API_PUBLIC_HOST`** to that hostname (no `https://`). Point DNS and add an **ALB listener rule**: **Host** = that name → target group → port **8010**. Redeploy so **`.env`** gets the matching **`API_PUBLIC_URL`**.

After the certificate matches the hostname, **`https://api…/health`** should load **without** a warning and product images should load normally.

---

## 3. GitHub Actions (`.github/workflows/deploy-prod.yml`)

| Item | Detail |
|------|--------|
| **Trigger** | Push to **`prod`** or **workflow_dispatch** |
| **EC2** | Clone/pull **`/opt/apps/app_ryunova`**, reset to **`origin/prod`** |
| **PostgreSQL** | Runs **`scripts/run_ryunova_migrations.sh`** (DB create if allowed, app role, **`db/migrations/order.txt`**) |
| **`.env`** | **`scripts/deploy_generate_ec2_env.py`** → scp to **`/opt/apps/app_ryunova/.env`** (uses **`PROD_SITE_DOMAIN`**, DB secrets, etc.) |
| **Images** | Optional ECR push/pull (`api-<sha>`, `web-<sha>`); else **`docker compose up -d --build`** on the instance |
| **Django** | **`docker compose exec web python manage.py migrate --noinput`** after the stack is up (session DB / `django_session`) |
| **Smoke test** | Retries **`/health`** on **8010** via SSH to **127.0.0.1** |

**Secrets:** Same pattern as FinText where applicable — `PROD_EC2_HOST`, `PROD_EC2_USER`, `PROD_PEM_SSH_KEY`, `PROD_POSTGRES_*`, `DJANGO_SECRET_KEY`, **`PROD_SITE_DOMAIN`** (strongly recommended), optional **`PROD_API_PUBLIC_HOST`**, ECR/AWS keys. See the workflow header comments for the full list.

---

## 4. Secrets reference (short)

| Secret | Role |
|--------|------|
| **`PROD_SITE_DOMAIN`** | Public **Django** hostname only (no `https://`) — drives **`SITE_URL`**, **`ALLOWED_HOSTS`**, **`CSRF_TRUSTED_ORIGINS`**, CORS hints |
| **`PROD_API_PUBLIC_HOST`** | Optional; else defaults to **`api.<PROD_SITE_DOMAIN>`** for **`API_PUBLIC_URL`** / **`RYUNOVA_API_PUBLIC`** |
| **`PROD_USE_S3_MEDIA`** | Optional; set to **`true`** to store **`orgs/`** + **`users/`** keys in S3 (EC2 needs IAM instance profile for the bucket) |
| **`ECR_REGISTRY`** + AWS keys | Optional; push/pull images. Default ECR repo name **`prod/ryunova-channels`** unless **`PROD_ECR_REPOSITORY`** is set |

Image tags: **`api-<git-sha>`** and **`web-<git-sha>`** in the same repository.

---

## 5. Database

- **Database name:** Often **`latrobe_apps_db`** when shared with FinText; override with **`PROD_POSTGRES_DB_NAME`** / **`PROD_DB_NAME`**.
- **Schema:** **`ryunova`** — app tables and **`ryunova_*`** objects.
- **Deploy:** **`run_ryunova_migrations.sh`** applies SQL listed in **`db/migrations/order.txt`** (see **`db/README.md`**).

---

## 6. Django (web) — sessions and login

- Django uses **SQLite** under **`web/`** for **sessions only** (`django_session` table via **`manage.py migrate`**).
- **`web/Dockerfile`** runs **`migrate`** before **`collectstatic`** and Gunicorn.
- The **workflow** also runs **`migrate`** inside the **`web`** container after **`compose up`** so older images still get session tables.
- **Login** requires **`email_verified_at`** in PostgreSQL (FastAPI). **`backend/scripts/seed_user.py`** sets **`email_verified_at`**, **`is_platform_user`**, and **`admin`** role for CLI-created users. Run **inside the API container** so **`DATABASE_URL`** matches production:

  ```bash
  docker exec ryunova_api python scripts/seed_user.py you@domain.com 'your-password' 'Display Name'
  ```

  Quote passwords that contain **`$`**. Do **not** run **`seed_user.py`** from repo-root **`scripts/`** — it lives under **`backend/scripts/`**.

---

## 7. Email (SMTP)

- **Django** (verification links) and **FastAPI** (OTP, etc.) read **`EMAIL_HOST`**, **`EMAIL_PORT`**, **`EMAIL_USE_TLS`**, **`EMAIL_HOST_USER`**, **`EMAIL_HOST_PASSWORD`**, **`DEFAULT_FROM_EMAIL`** from the same generated **`.env`** (`scripts/deploy_generate_ec2_env.py`).
- **GitHub Actions** maps secrets into that file. Prefer **`PROD_*`** names; **`deploy-prod.yml`** also falls back to **`EMAIL_*`** / **`DEFAULT_FROM_EMAIL`** / **`EMAIL_FROM_NAME`** so you can reuse **organization-level** or **FinText-style** secret names. If this repository has **no** SMTP secrets, user/password end up empty and Django falls back to **console** email — **nothing is delivered**.
- **Same server as FinText:** copy the same SMTP user, password, and from-address into **this repo’s** GitHub **Secrets** (or add org secrets visible to this repo), then **redeploy** so **`/opt/apps/app_ryunova/.env`** is regenerated. Optional overrides: **`PROD_EMAIL_HOST`**, **`PROD_EMAIL_PORT`**, **`PROD_EMAIL_USE_TLS`**.
- **Hotfix on EC2 without redeploy:** edit **`/opt/apps/app_ryunova/.env`**, set the **`EMAIL_*`** lines to match FinText’s app **`.env`**, then restart **`api`** and **`web`**:  
  `docker compose -p ryunova -f docker-compose.app-only.yml up -d api web`

---

## 8. Media (disk vs S3)

**Until you enable S3 (`USE_S3_MEDIA=false`, the default), everything stays on the filesystem** under **`/app/uploads`** (host: **`data/uploads`**). **`PROD_USE_S3_MEDIA`** / **`USE_S3_MEDIA`** does not need to be set.

**Folder layout (one tree per organisation):** all tenant files use prefix **`orgs/<organisation_id>/`**:

```
orgs/<organisation_id>/
  products/<product_id>/     # product images / video
  branding/                  # organisation logo
  users/<user_id>/avatars/   # profile photos (scoped to that org’s folder)
```

The seeded **default organisation** (`slug` **`default`**, id **`00000000-0000-4000-8000-000000000001`**) uses the same layout under **`orgs/00000000-0000-4000-8000-000000000001/`**. On **API startup** and when **creating an organisation**, empty **`products`**, **`branding`**, and **`users`** directories are created on disk (skipped when **`USE_S3_MEDIA=true`** because S3 has no empty “folders”).

**Avatar storage:** the browser sends **`X-Organisation-Id`** (Django passes the session workspace org). The API stores the file under that org’s tree; if missing or invalid, it uses the user’s first membership (by org name), then the **default organisation** id above.

**S3 (`USE_S3_MEDIA=true`):** Set GitHub secret **`PROD_USE_S3_MEDIA`** to **`true`**. Deploy sets **`USE_S3_MEDIA=true`**, **`MEDIA_PUBLIC_BASE_URL`** to the bucket virtual-host URL (unless **`PROD_MEDIA_PUBLIC_BASE_URL`** overrides). IAM + bucket **`GetObject`** as before.

**Legacy DB keys** (`products/...`, top-level `users/...`, `org-logos/...`) still resolve via **`/api/v1/media/...`** until re-uploaded or migrated once with **`backend/scripts/migrate_media_paths.py`** (see **`db/README.md`** — not part of automated **`order.txt`** migrations).

**ALB:** For disk mode, **`api.*` → 8010** (§2). For S3 mode, **`orgs/`** URLs use **`MEDIA_PUBLIC_BASE_URL`**.

---

## 9. Laptop vs EC2 configuration

| Environment | Files |
|-------------|--------|
| **Local** | `backend/.env`, `web/.env` — **`docs/ENVIRONMENT.md`** |
| **EC2** | **`/opt/apps/app_ryunova/.env`** — generated by deploy; see **`deploy/ec2.env.example`** |

Important generated values: **`DATABASE_URL`** (must reach Postgres from containers, e.g. **`host.docker.internal`**), **`RYUNOVA_API_BASE=http://api:8010/api/v1`**, **`RYUNOVA_API_PUBLIC`**, **`USE_TLS_BEHIND_PROXY=true`** when behind ALB HTTPS.

---

## 10. Manual operations (on EC2)

```bash
cd /opt/apps/app_ryunova
docker compose -p ryunova -f docker-compose.app-only.yml ps
docker compose -p ryunova -f docker-compose.app-only.yml logs -f --tail=100 api
docker compose -p ryunova -f docker-compose.app-only.yml logs -f --tail=100 web
```

Verify API from host: **`curl -sS http://127.0.0.1:8010/health`**.  
Verify web → API inside Compose: **`docker exec ryunova_web python -c "import urllib.request; print(urllib.request.urlopen('http://api:8010/health').read())"`**

---

## 11. Troubleshooting

| Symptom | What to check |
|---------|----------------|
| **502** from ALB | Target group ports **8010/8011**, security groups, **`docker compose ps`**, container logs |
| **Broken images** (profile, product thumbnails) | **`api.<domain>`** DNS → ALB; **listener rule** `Host: api.<domain>` → target **8010** (not 8011). On EC2: **`curl -sI http://127.0.0.1:8010/health`**. In browser: **Network** tab on image URL — expect **200** from **`/api/v1/media/...`**. |
| **JSON `Not Found` on `/`** | Traffic hitting **8010** (API) instead of **8011** (Django) |
| **`DisallowedHost`** | Wrong app (e.g. FinText) or **`ALLOWED_HOSTS`** / **`PROD_SITE_DOMAIN`** |
| **500 on `/accounts/login/`** | **`docker exec ryunova_web python manage.py migrate --noinput`**; **`docker logs ryunova_web`** |
| **“Verify your email…”** on login | **`email_verified_at`** NULL in **`ryunova.ryunova_users`** — fix user row or re-seed with current **`seed_user.py`** |
| Django **“API unreachable”** | **`api`** container up, **`RYUNOVA_API_BASE`** in **`.env`** |

---

*FinText reference: `dragon-latrobe_fintext` `deploy-prod.yml`.*
