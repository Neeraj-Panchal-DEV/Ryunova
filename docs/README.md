# RyuNova Platform — documentation

**Application:** RyuNova Platform — multi-channel listing and product hub (FastAPI + Django).

## Deployment and operations

| Document | Description |
|----------|-------------|
| **[DEPLOYMENT_EC2_ALB.md](DEPLOYMENT_EC2_ALB.md)** | **Production:** EC2, ALB, GitHub Actions, secrets, Postgres migrations, Django, bootstrap user, troubleshooting |
| [DEPLOYMENT_DOCKER_EC2.md](DEPLOYMENT_DOCKER_EC2.md) | Short pointer to the runbook above |
| [ENVIRONMENT.md](ENVIRONMENT.md) | Local `web/.env` vs `backend/.env` |
| [EMAIL_SETTINGS.md](EMAIL_SETTINGS.md) | SMTP / transactional email |

## Schema and product

| Document | Description |
|----------|-------------|
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Full PostgreSQL schema (`ryunova_*`) |
| [MULTI_TENANT.md](MULTI_TENANT.md) | Organisations, platform vs org admin, bootstrap |
| [MVP1_BUILD_AND_DELIVERY.md](MVP1_BUILD_AND_DELIVERY.md) | MVP1 scope and handoff |
| [SERVICES.md](SERVICES.md) | Service overview |
| [TURNSTILE.md](TURNSTILE.md) | Optional Cloudflare Turnstile on login |

## UX and design history

| Document | Description |
|----------|-------------|
| [UX_REQUIREMENTS_AND_STANDARDS.md](UX_REQUIREMENTS_AND_STANDARDS.md) | UX standards |
| [DESIGN_DEVELOPMENT_HISTORY.md](DESIGN_DEVELOPMENT_HISTORY.md) | How the design evolved |

## Other

| Document | Description |
|----------|-------------|
| [MVP1_READINESS_AND_SKILLS.md](MVP1_READINESS_AND_SKILLS.md) | Readiness checklist |

Local development: **[../LOCAL_DEVELOPMENT.md](../LOCAL_DEVELOPMENT.md)** (repo root).
