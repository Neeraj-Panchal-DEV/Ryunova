# Enabling Cloudflare Turnstile on RyuNova

This guide walks through turning on [Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/) for the **Django web app** login screens. Turnstile is **optional**: if you do not set the keys below, RyuNova keeps the built-in “Are you human?” quiz and honeypot (see `accounts/bot_gate.py`).

Turnstile only affects **HTML login** (`/accounts/login/`, `/accounts/login/code/`). It does not change direct calls to the FastAPI `/auth/login` endpoints.

---

## 1. What you need

- A Cloudflare account (free tier is enough for Turnstile).
- Access to **`web/.env`** on each environment (local laptop, staging, production). **Do not commit** real secret keys.
- The **exact hostnames** users use to open the app (e.g. `127.0.0.1`, `localhost`, or `app.example.com`), because Cloudflare validates the widget against allowed domains.

---

## 2. Create a Turnstile site in Cloudflare

1. Sign in to the [Cloudflare dashboard](https://dash.cloudflare.com/).
2. Open **Turnstile** from the sidebar (or go to **Security** → **Turnstile**, depending on the UI).
3. Click **Add widget** (or **Add site**).
4. Choose a **widget name** (e.g. `RyuNova login`).
5. Under **Domains**, add every hostname from which the Django UI will be served. Examples:
   - **Local:** `127.0.0.1` and `localhost` (Cloudflare documents support for local development; if the widget fails, confirm your widget’s domain list matches how you open the site, e.g. `http://127.0.0.1:8001`).
   - **Production:** your real site host only, e.g. `app.example.com` (no scheme, no path).
6. **Widget mode:** **Managed** is recommended (default challenge behaviour).
7. Save and copy:
   - **Site key** (public, safe to expose in HTML).
   - **Secret key** (private; server-side only).

Official reference: [Cloudflare Turnstile — Get started](https://developers.cloudflare.com/turnstile/get-started/).

---

## 3. Configure `web/.env`

In the **`web/`** project directory (same folder as `manage.py`), set **both** variables. If either is missing or empty, Turnstile is **off** and the fallback quiz is used.

```bash
# web/.env — example only; use your real keys from Cloudflare
TURNSTILE_SITE_KEY=0x4AAAAAAA...
TURNSTILE_SECRET_KEY=0x4AAAAAAA...
```

Notes:

- Keys belong in **`web/.env` only** (not `backend/.env`). Django reads them via `ryunova_web/settings.py`.
- After editing `.env`, **restart** the Django process (`runserver`, gunicorn, etc.) so new values load.

---

## 4. Align Django with your URL

So login POSTs and Turnstile succeed:

- **`ALLOWED_HOSTS`** must include the host users type in the browser.
- **`CSRF_TRUSTED_ORIGINS`** must include the full origin (scheme + host + port), e.g. `http://127.0.0.1:8001`.

See **`docs/ENVIRONMENT.md`** for LAN/production examples.

---

## 5. Verify it works

1. Start the stack (see **`docs/SERVICES.md`**): FastAPI on port **8000**, Django on **8001** (or your chosen ports).
2. Open the login page. You should see **“Security check (Cloudflare)”** and the Turnstile widget instead of the four-option human quiz.
3. Complete Turnstile, enter credentials (or email code flow), and submit. A successful login means `siteverify` accepted the token.

---

## 6. Turning Turnstile off (fallback)

Remove or blank **either** `TURNSTILE_SITE_KEY` or `TURNSTILE_SECRET_KEY`, restart Django, and the app returns to the **session-based multiple-choice** check plus honeypot.

---

## 7. Troubleshooting

| Symptom | Things to check |
|--------|------------------|
| Widget does not load or shows an error | Domain not listed in the Turnstile widget’s allowed hostnames; wrong hostname in the address bar vs what you registered; browser extensions blocking `challenges.cloudflare.com`. |
| “Complete the security verification below” every time | Secret key wrong or typo; `web/.env` not loaded (restart Django); server cannot reach `https://challenges.cloudflare.com/turnstile/v0/siteverify` (firewall). |
| Works locally but not behind nginx | Set **`X-Forwarded-For`** (and friends) correctly; the app passes the first client IP to Turnstile when verifying. |
| Strict **Content-Security-Policy** | Allow scripts and frames (or connect) for Cloudflare’s challenge domains per [Turnstile CSP](https://developers.cloudflare.com/turnstile/reference/content-security-policy/) if you use CSP headers. |

For API response details when debugging, Cloudflare returns JSON from `siteverify` (e.g. `success`, `error-codes`). RyuNova logs verification failures at **warning** level in `accounts.turnstile`.

---

## 8. Related docs

- **`docs/ENVIRONMENT.md`** — Where Turnstile fits with other `web/.env` variables.
- **`web/.env.example`** — Comment template for the two Turnstile variables.
- [Turnstile overview](https://developers.cloudflare.com/turnstile/) (Cloudflare).
