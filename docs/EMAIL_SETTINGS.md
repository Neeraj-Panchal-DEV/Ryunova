# Email settings (RyuNova web)

Configuration mirrors **dragon-latrobe_fintext** (`config/settings/base.py` and `docs/EMAIL_SETTINGS.md`): Hostinger-friendly SMTP defaults and env-driven overrides.

## Sign-in codes (email OTP)

The **FastAPI** app sends 6-digit login codes when `POST /auth/login-otp/request` is used. It reads the **same** `EMAIL_*` variables from **`backend/.env`** (see `backend/.env.example`). If SMTP is not set there, codes are **only logged** by the API process (similar to Django’s console backend).

## Why invitees do not get email in their inbox

1. **Console backend (most common in local dev)**  
   If `EMAIL_HOST_USER` **or** `EMAIL_HOST_PASSWORD` is missing in `web/.env`, Django uses **`django.core.mail.backends.console.EmailBackend`**. The full message is printed in the **terminal where `runserver` is running**—nothing is sent over the internet. The UI will show a **warning** explaining this after you invite someone.

2. **SMTP configured but still failing**  
   Check the Django terminal and logs for connection/auth errors (wrong password, port 587 vs 465 + TLS/SSL, firewall). The UI will show a warning with the exception text.

3. **Deliverability**  
   If mail sends but lands in **spam**, align `DEFAULT_FROM_EMAIL` with your domain’s SPF/DKIM (your DNS / mail host documentation).

## Environment variables

| Variable | Default | Notes |
|----------|---------|--------|
| `EMAIL_HOST` | `smtp.hostinger.com` | SMTP hostname |
| `EMAIL_PORT` | `587` | Use `465` with `EMAIL_USE_SSL=true` if needed |
| `EMAIL_USE_TLS` | `true` | STARTTLS (typical for 587) |
| `EMAIL_USE_SSL` | `false` | SSL (typical for 465) |
| `EMAIL_HOST_USER` | *(empty)* | Sender login; when set with password, SMTP backend is used |
| `EMAIL_HOST_PASSWORD` | *(empty)* | App password |
| `DEFAULT_FROM_EMAIL` | `EMAIL_HOST_USER` or `noreply@localhost` | From address |
| `EMAIL_HOST_USER_NAME` | `Dragon and Peaches — RyuNova Platform` | Display name in the From header (Fintext uses `EMAIL_HOST_USER_NAME`) |
| `EMAIL_TIMEOUT` | `25` | Seconds |
| `EMAIL_BACKEND` | *(auto)* | If `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` are set → SMTP; else **console** (dev) |
| `SITE_DOMAIN` | `127.0.0.1:8001` | Used to build `SITE_URL` when `SITE_URL` unset |
| `SITE_URL` | from `SITE_DOMAIN` + `DEBUG` | **Must match the Django app URL** so invite emails link to the correct login/verify pages |
| `EMAIL_LOGO_URL` | *(empty)* | Optional absolute URL to a logo image (same role as Fintext `logo_url` in templates) |
| `DEBUG` | `true` | When true and `SITE_URL` unset, `SITE_URL` defaults to `http://{SITE_DOMAIN}` |

## HTML template

Invite emails use `accounts/templates/accounts/emails/invite_user.html`, structurally aligned with Fintext’s `apps/accounts/templates/accounts/emails/verify_email.html` (600px card, `#f4f4f5` background, `#2563eb` CTA, footer panel).

## Example `.env` (production-style)

```bash
DEBUG=false
SITE_DOMAIN=channels.example.com
SITE_URL=https://channels.example.com
EMAIL_HOST_USER=no_reply@yourdomain.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=no_reply@yourdomain.com
EMAIL_HOST_USER_NAME="Dragon and Peaches — RyuNova Platform"
```
