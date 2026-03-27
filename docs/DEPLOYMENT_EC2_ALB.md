# RyuNova — EC2, shared PostgreSQL, ALB, GitHub Actions

This guide matches the operational model used for **dragon-latrobe_fintext**: a single EC2 instance, **external PostgreSQL**, **GitHub Actions** deploy, optional **ECR**. RyuNova stays **separate from FinText** except when you **reuse the same database** (tables are prefixed `ryunova_*`).

**Traffic model:** **Docker Compose** publishes **FastAPI on host port 8010** and **Django on 8011** (see `docker-compose.app-only.yml`). There is **no nginx** container. Point your **ALB** at one or both ports using **separate target groups** (or a single host with path rules—your choice). **Django** talks to **FastAPI** on the Docker network using **`RYUNOVA_API_BASE=http://api:8010/api/v1`** (see `web/ryunova_web/api_client.py`).

For high-level architecture, see `DEPLOYMENT_DOCKER_EC2.md`. **This file is the EC2 + ALB runbook.**

---

## 1. What runs where

| Piece | Location | Host ports (example) |
|--------|-----------|----------------------|
| FinText (existing) | Same EC2 | e.g. **8000** |
| RyuNova **FastAPI** | Docker | **8010** → API |
| RyuNova **Django** | Docker | **8011** → web UI |
| PostgreSQL | Host or RDS | **5432** (not from the internet) |

Deploy directory (separate from FinText’s `/opt/apps/apps_fintext`):

- **`/opt/apps/apps_ryunova`** — git checkout, `docker-compose.app-only.yml`, `.env`, `data/uploads/`

Compose project: **`apps_ryunova`**.

---

## 2. GitHub Secrets — what each one means

### `PROD_SITE_DOMAIN` (strongly recommended)

- **What it is:** The **public hostname** for the **Django** UI (no `https://`, no path), e.g. `app.ryunova.example.com`.
- **What we use it for:** **`SITE_URL`**, **`ALLOWED_HOSTS`**, **`CSRF_TRUSTED_ORIGINS`**, and part of **CORS** on the API.
- **ALB:** Point your **web** listener / target group at instance port **8011** (unless you terminate TLS elsewhere).

### `PROD_API_PUBLIC_HOST` (optional)

- **What it is:** The hostname used for **`API_PUBLIC_URL`** and **`RYUNOVA_API_PUBLIC`** — the **browser-facing** base for absolute links in API JSON (media URLs, etc.), e.g. `api.ryunova.example.com`.
- **When unset:** The deploy script defaults to **`api.<PROD_SITE_DOMAIN>`** (e.g. `api.app.example.com` if `PROD_SITE_DOMAIN` is `app.example.com` — adjust DNS or set **`PROD_API_PUBLIC_HOST`** explicitly to match your real API DNS name).
- **When to set it:** Use a **custom API hostname** (or CloudFront/S3 base via **`MEDIA_PUBLIC_BASE_URL`** in `.env` — see §6).

### Other secrets (same names as FinText)

| Secret | Purpose |
|--------|---------|
| `PROD_EC2_HOST` / `EC2_HOST_PROD` | EC2 SSH host |
| `PROD_EC2_USER` | SSH user |
| `PROD_PEM_SSH_KEY` / `EC2_SSH_KEY_PROD` | SSH private key |
| `PROD_POSTGRES_*`, `PROD_DB_*` | DB connectivity (shared DB OK) |
| `DJANGO_SECRET_KEY` | Django + FastAPI `SECRET_KEY` in generated `.env` |
| Email secrets | Same pattern as FinText |

Optional **ECR** / **AWS** keys (see `.github/workflows/deploy-prod.yml`):

| Secret | Purpose |
|--------|---------|
| `ECR_REGISTRY` | Registry hostname only — **`123456789012.dkr.ecr.<region>.amazonaws.com`** (no path, no `https://`) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Push/pull images (CI pushes; EC2 pulls with instance role or same creds pattern) |
| `AWS_REGION` | ECR region (default **`ap-southeast-2`**) |
| `PROD_ECR_REPOSITORY` | Optional; ECR **repository name** including any prefix (default **`prod/ryunova-channels`**) |

**Image layout:** Both services use the **same** repository. Tags are **`api-<git-sha>`** (FastAPI) and **`web-<git-sha>`** (Django), e.g. `123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/prod/ryunova-channels:api-abc123…`.

---

## 3. Security groups and ALB

1. **ALB → EC2:** Allow **TCP 8010** (API) and **8011** (Django) from the **ALB security group** as needed for your listener rules.
2. **FinText** keeps its own target group (e.g. **8000**).
3. **Postgres:** Not exposed to the internet; app containers use `host.docker.internal` to reach the host DB.

### Health checks

- **API:** `GET /health` on **8010** (JSON `{"status":"ok"}`).
- **Web:** `GET /` on **8011** (200/302).

The GitHub Actions workflow verifies **`http://<EC2>:8010/health`**.

---

## 4. How requests flow

- **Browser → Django:** `https://<PROD_SITE_DOMAIN>/` → ALB → **8011**.
- **Browser → FastAPI** (e.g. OpenAPI, direct API calls): `https://<api-host>/...` → ALB → **8010** (or same host with different rules — your infra).
- **Django → FastAPI (server-side):** `http://api:8010/api/v1/...` inside Docker (**no ALB** hop).

---

## 5. Database

Shared PostgreSQL is fine; apply `db/*.sql` manually (see `db/README.md`). The workflow does not run DDL.

---

## 6. Media files and Amazon S3

**Production bucket (configured in deploy):** `arn:aws:s3:::ryunova-channels-organisations-media` (name **`ryunova-channels-organisations-media`**).

The GitHub Actions deploy script writes **`AWS_S3_MEDIA_BUCKET`**, **`AWS_S3_REGION`**, and **`MEDIA_PUBLIC_BASE_URL`** into `/opt/apps/apps_ryunova/.env` unless you override with secrets:

| Secret | Purpose |
|--------|---------|
| `PROD_AWS_S3_MEDIA_BUCKET` | Optional; defaults to **`ryunova-channels-organisations-media`** |
| `AWS_REGION` or `PROD_AWS_REGION` | Region for the S3 virtual-hosted URL (default **`ap-southeast-2`**) |
| `PROD_MEDIA_PUBLIC_BASE_URL` | Optional; set to a **CloudFront** URL (or another base) instead of `https://<bucket>.s3.<region>.amazonaws.com` |

`public_media_url()` in **`backend/app/media_urls.py`** prefixes object keys with **`MEDIA_PUBLIC_BASE_URL`** when set. The API may still write uploads to **local disk** until upload code uses **boto3** and this bucket.

1. **IAM (EC2 instance profile or role):** allow `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on `arn:aws:s3:::ryunova-channels-organisations-media/*` (tighten prefix if needed).
2. **Bucket policy / CORS:** allow browser **GET** from your Django origin if users load images directly from S3.
3. **CloudFront:** set GitHub secret **`PROD_MEDIA_PUBLIC_BASE_URL`** to the distribution URL.

---

## 7. Laptop vs EC2 configuration

| Environment | Config files |
|-------------|----------------|
| **Local dev** | `backend/.env`, `web/.env` — see `docs/ENVIRONMENT.md` |
| **EC2** | **`/opt/apps/apps_ryunova/.env`** — see `deploy/ec2.env.example` |

| Variable | Role |
|----------|------|
| `RYUNOVA_API_BASE` | Django → FastAPI: **`http://api:8010/api/v1`** on EC2 |
| `RYUNOVA_API_PUBLIC` | Public base for templates / links — **`https://<api-host>`** |
| `API_PUBLIC_URL` | FastAPI — public API base for non-S3 JSON URLs |
| `MEDIA_PUBLIC_BASE_URL` | Base URL for media keys (S3 or CloudFront) |
| `AWS_S3_MEDIA_BUCKET` / `AWS_S3_REGION` | Bucket name and region for future boto3 uploads |
| `DATABASE_URL` | Must use **`host.docker.internal`** from containers |

Optional **`RYUNOVA_API_BASE_INTERNAL`:** leave unset if **`RYUNOVA_API_BASE`** already points at `http://api:8010/api/v1`.

---

## 8. GitHub Actions

- **`.github/workflows/deploy-prod.yml`** — branch **`prod`**, optional ECR push/pull to **`prod/ryunova-channels`** (`api-<sha>` / `web-<sha>` tags).
- Post-deploy: **`http://<EC2>:8010/health`**.

---

## 9. Manual operations

```bash
cd /opt/apps/apps_ryunova
docker compose -p apps_ryunova -f docker-compose.app-only.yml ps
docker compose -p apps_ryunova -f docker-compose.app-only.yml logs -f --tail=100 api
docker compose -p apps_ryunova -f docker-compose.app-only.yml logs -f --tail=100 web
```

---

## 10. Troubleshooting

| Symptom | Check |
|---------|--------|
| 502 from ALB | Target group ports **8010/8011**, security groups, container logs. |
| Django “API unreachable” | `RYUNOVA_API_BASE=http://api:8010/api/v1`, `api` container up. |
| Media 404 | `API_PUBLIC_URL`, `data/uploads`, FastAPI routes. |

---

*FinText reference: `dragon-latrobe_fintext` `deploy-prod.yml`.*
