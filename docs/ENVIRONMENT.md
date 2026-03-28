# Environment configuration (local vs server)

RyuNova uses **two processes**: FastAPI (`backend/`, port 8000) and Django (`web/`, port 8001). Each loads its own `.env` from its directory (via `python-dotenv` / Pydantic Settings).

Use **one mental model**, **two files**:

| Concern | `backend/.env` | `web/.env` |
|--------|-----------------|------------|
| PostgreSQL / JWT / CORS / uploads | Required | — |
| Django secret / sessions | — | Optional (see `settings.py` defaults) |
| Public URLs (`SITE_URL`, API base, CSRF) | `SITE_URL` for sign-in code emails | `SITE_URL`, `RYUNOVA_API_*`, `CSRF_TRUSTED_ORIGINS` |
| SMTP (invitations, HTML mail) | Same variables for **sign-in codes** sent by the API | Same variables for **invitations** sent by Django |
| Login anti-bot (Turnstile) | — | Optional: `TURNSTILE_SITE_KEY` + `TURNSTILE_SECRET_KEY` in `web/.env` |

**Recommendation:** Keep a **single reference** (this doc + `.env.example` files). For production, copy the **same** email and site URL values into **both** `backend/.env` and `web/.env` so invitations (Django) and OTP mail (API) behave the same.

### Cloudflare Turnstile (optional, `web/.env` only)

When **both** `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` are set, Django shows the Cloudflare widget on password login and email-code login and verifies tokens with Cloudflare before calling the API. If either variable is **missing or empty**, the app keeps the **built-in “Are you human?”** multiple-choice flow (no Turnstile script loaded).

- Create a Turnstile site in the [Cloudflare dashboard](https://dash.cloudflare.com/) and allow your real UI origins in the widget hostnames (for local dev, include e.g. `127.0.0.1` / `localhost` as documented by Cloudflare).
- The **secret** must stay server-side (`web/.env`); the **site key** is public and is rendered in HTML.
- Behind a reverse proxy, ensure `X-Forwarded-For` is set correctly if you rely on Turnstile’s optional IP binding (the app forwards the first hop to `siteverify` when present).

For step-by-step Turnstile setup (dashboard, domains, `.env`, verification), see **`docs/TURNSTILE.md`**. For running the stack locally, see **`docs/SERVICES.md`**.

## Local development (typical)

- `DEBUG=true` on Django; `SITE_URL=http://127.0.0.1:8001` (or your LAN IP).
- `RYUNOVA_API_BASE=http://127.0.0.1:8000/api/v1` on Django.
- Leave `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` **empty** on **web** if you only want invite text in the Django console; the UI will warn you.
- For **email codes** from the API, either set SMTP in **`backend/.env`** as well or read the uvicorn log (the API logs the code when SMTP is not configured).

## Production / server

- `DEBUG=false`, `SITE_URL=https://your-app.example.com`, matching TLS host.
- Set `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` on Django.
- Set `CORS_ORIGINS` on the API to your Django origin(s).
- On **EC2 Docker** (see `docs/DEPLOYMENT_EC2_ALB.md`): set **`RYUNOVA_API_BASE=http://api:8010/api/v1`** so Django’s server-side HTTP calls use the Compose network. Optionally set **`RYUNOVA_API_BASE_INTERNAL`** if you need a different override; **`RYUNOVA_API_PUBLIC`** is the browser-facing API base (HTTPS).
- Configure SMTP on **both** apps (see `docs/EMAIL_SETTINGS.md`).

## Aligning with FinText (dragon-latrobe_fintext)

FinText uses the same style of variables (`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `EMAIL_HOST_USER_NAME`, `SITE_DOMAIN` / `SITE_URL`). **Do not commit real passwords.** Copy structure from FinText’s `.env.example` into RyuNova’s `web/.env.example` / `backend/.env.example` and fill values only on the machine that deploys.

## Database schema

Apply **`db/mvp1_schema.sql`** once to an empty database (includes login codes, profile fields, and all MVP1 tables — see **`db/README.md`**).
