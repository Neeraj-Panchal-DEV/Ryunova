import os
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    # Optional: pip install -r requirements.txt (includes python-dotenv)
    pass

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-ryunova-dev-change-me")
DEBUG = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes")
USE_WHITENOISE = os.getenv("USE_WHITENOISE", "").lower() in ("1", "true", "yes")
# DEBUG: allow any Host (LAN / mDNS) when binding runserver to 0.0.0.0. Override with ALLOWED_HOSTS for production.
_default_allowed_hosts = "127.0.0.1,localhost,*" if DEBUG else "127.0.0.1,localhost"
ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", _default_allowed_hosts).split(",") if h.strip()
]
_extra_hosts = os.getenv("ALLOWED_HOSTS_EXTRA", "").strip()
if _extra_hosts:
    ALLOWED_HOSTS.extend([h.strip() for h in _extra_hosts.split(",") if h.strip()])
# Django 4+ Referer check for HTTPS/non-default ports; add your LAN UI origin when using http://<ip>:8001
_default_csrf_origins = "http://127.0.0.1:8001,http://localhost:8001"
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", _default_csrf_origins).split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.contenttypes",
    "accounts",
    "catalog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *(
        ["whitenoise.middleware.WhiteNoiseMiddleware"]
        if USE_WHITENOISE
        else []
    ),
    "django.contrib.sessions.middleware.SessionMiddleware",
    "ryunova_web.middleware.WorkspaceSessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "ryunova_web.middleware.RewriteApiPublicUrlMiddleware",
]

ROOT_URLCONF = "ryunova_web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "ryunova_web.context_processors.api_media",
                "ryunova_web.context_processors.workspace_context",
                "ryunova_web.context_processors.nav_user",
                "ryunova_web.context_processors.turnstile",
            ],
        },
    },
]

WSGI_APPLICATION = "ryunova_web.wsgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "django_session.sqlite3"}}
LANGUAGE_CODE = "en-au"
TIME_ZONE = "Australia/Sydney"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
if USE_WHITENOISE:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# FastAPI backend (JWT issued here). Default is local; in Docker set RYUNOVA_API_BASE=http://api:8010/api/v1
RYUNOVA_API_BASE = os.getenv("RYUNOVA_API_BASE", "http://127.0.0.1:8000/api/v1")
# Optional override: if set, api_client uses this instead of RYUNOVA_API_BASE (e.g. internal Docker URL).
RYUNOVA_API_BASE_INTERNAL = os.getenv("RYUNOVA_API_BASE_INTERNAL", "").strip()
RYUNOVA_API_PUBLIC = os.getenv("RYUNOVA_API_PUBLIC", "http://127.0.0.1:8000")
# When True, HTML/JSON responses have loopback API URLs rewritten to the browser host (LAN testing).
RYUNOVA_API_PUBLIC_PORT = os.getenv("RYUNOVA_API_PUBLIC_PORT", "8000")
RYUNOVA_REWRITE_API_PUBLIC_IN_RESPONSES = os.getenv(
    "RYUNOVA_REWRITE_API_PUBLIC_IN_RESPONSES",
    "true" if DEBUG else "false",
).lower() in ("1", "true", "yes")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Header nav: use cached GET /auth/me for up to this many seconds; login/profile call
# refresh_session_nav_user() to refresh immediately. Override via NAV_USER_ME_TTL_SECONDS in .env.
NAV_USER_ME_TTL_SECONDS = int(os.getenv("NAV_USER_ME_TTL_SECONDS", "300"))

# Behind AWS ALB / reverse proxy terminating TLS (set USE_TLS_BEHIND_PROXY=true in production)
if os.getenv("USE_TLS_BEHIND_PROXY", "").lower() in ("1", "true", "yes"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Cloudflare Turnstile (optional). If both are non-empty, login uses Turnstile instead of the built-in quiz.
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "").strip()
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "").strip()

# --- Public URL for emails and absolute links (pattern from dragon-latrobe_fintext / SITE_URL) ---
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "127.0.0.1:8001")
_site_host = SITE_DOMAIN.split(":")[0]
SITE_URL = os.getenv("SITE_URL") or (
    f"http://{SITE_DOMAIN}" if DEBUG else f"https://{_site_host}"
)

# --- Email (aligned with Fintext: config/settings/base.py + docs/EMAIL_SETTINGS.md) ---
# Hostinger-style defaults; override via .env. If EMAIL_HOST_PASSWORD is empty, console backend is used for local dev.
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.hostinger.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() in ("1", "true", "yes")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "noreply@localhost")
EMAIL_HOST_USER_NAME = os.getenv("EMAIL_HOST_USER_NAME", "Dragon and Peaches — RyuNova Platform")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "25"))
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Optional logo in HTML emails (same idea as Fintext logo_url)
EMAIL_LOGO_URL = os.getenv("EMAIL_LOGO_URL", "").strip()

# Google Maps Places (address autocomplete on organisation settings). Optional; leave empty to type address manually.
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
# Temporarily off by default; set GOOGLE_PLACES_ENABLED=true when Places should load (requires API key above).
GOOGLE_PLACES_ENABLED = os.getenv("GOOGLE_PLACES_ENABLED", "false").lower() in ("1", "true", "yes")

_email_smtp_ready = bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD)
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if _email_smtp_ready
    else "django.core.mail.backends.console.EmailBackend",
)
