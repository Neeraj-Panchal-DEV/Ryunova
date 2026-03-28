#!/usr/bin/env python3
"""Emit a single .env for EC2 Docker (api + web). Used by deploy-prod.yml.

Django calls FastAPI on the Docker network: RYUNOVA_API_BASE=http://api:8010/api/v1
(api_client uses this when RYUNOVA_API_BASE_INTERNAL is unset).

Public URLs in API JSON use API_PUBLIC_URL / RYUNOVA_API_PUBLIC (typically https://api host).

Optional PROD_API_PUBLIC_HOST: if unset, defaults to api.<PROD_SITE_DOMAIN> for public API URLs.

S3 bucket/region vars are reserved for future boto3 uploads. MEDIA_PUBLIC_BASE_URL: only set PROD_MEDIA_PUBLIC_BASE_URL
when media is actually on S3/CloudFront. If unset, generated .env leaves it empty so public_media_url() uses
API_PUBLIC_URL + /api/v1/media (files served from the API container disk — see docker-compose volume).

SMTP: defaults to smtp.hostinger.com:587 + TLS. Set EMAIL_HOST_VAL / EMAIL_PORT_VAL / EMAIL_USE_TLS_VAL from
GitHub Actions env (see deploy-prod.yml). FastAPI and Django both read EMAIL_* from the same .env.
"""
from __future__ import annotations

import os
from urllib.parse import quote_plus


def esc(s: str | None) -> str:
    if s is None:
        s = ""
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# Production media bucket (arn:aws:s3:::ryunova-channels-organisations-media)
DEFAULT_S3_MEDIA_BUCKET = "ryunova-channels-organisations-media"
DEFAULT_AWS_REGION = "ap-southeast-2"


def main() -> None:
    db_port = os.environ.get("DB_PORT_VAL", "5432")
    db_name = os.environ.get("DB_NAME_VAL", "latrobe_apps_db")
    appl_user = os.environ.get("APPL_USER", "")
    appl_pw = os.environ.get("APPL_PW", "")
    site_domain = (os.environ.get("SITE_DOMAIN_VAL") or "").strip() or "ryunova.example.com"
    api_public_override = (os.environ.get("API_HOST_VAL") or "").strip()
    django_secret = os.environ.get("DJANGO_SECRET_KEY_VAL", "")
    email_pw = os.environ.get("EMAIL_HOST_PASSWORD_VAL", "") or ""
    email_user = os.environ.get("EMAIL_HOST_USER_VAL", "") or ""
    # Same Hostinger-style SMTP as FinText; override host/port via GitHub secrets when needed
    email_host = (os.environ.get("EMAIL_HOST_VAL") or "").strip() or "smtp.hostinger.com"
    email_port = (os.environ.get("EMAIL_PORT_VAL") or "").strip() or "587"
    email_use_tls = (os.environ.get("EMAIL_USE_TLS_VAL") or "true").strip().lower() in ("1", "true", "yes")
    default_from = (os.environ.get("DEFAULT_FROM_EMAIL_VAL") or "").strip() or email_user
    from_name = os.environ.get("EMAIL_FROM_NAME_VAL", "") or "RyuNova Platform"

    s3_bucket = (os.environ.get("AWS_S3_MEDIA_BUCKET_VAL") or "").strip() or DEFAULT_S3_MEDIA_BUCKET
    aws_region = (os.environ.get("AWS_S3_REGION_VAL") or "").strip() or DEFAULT_AWS_REGION
    media_public_override = (os.environ.get("MEDIA_PUBLIC_BASE_URL_VAL") or "").strip()
    if media_public_override:
        media_public_base = media_public_override.rstrip("/")
    else:
        # Avatars/products are stored on API disk, not S3, until uploads are wired — do not point browsers at S3.
        media_public_base = ""

    host_only = site_domain.split(":")[0]
    site_url = f"https://{host_only}"
    if api_public_override:
        api_host_only = api_public_override.split(":")[0]
    else:
        api_host_only = "api." + host_only if not host_only.startswith("api.") else host_only
    api_public = f"https://{api_host_only}"

    db_docker_host = "host.docker.internal"
    database_url = (
        "postgresql+psycopg://"
        f"{quote_plus(appl_user)}:{quote_plus(appl_pw)}@{db_docker_host}:{db_port}/{db_name}"
    )

    cors = f"https://{host_only},http://127.0.0.1:8011"
    allowed = f"{host_only},{api_host_only},localhost,127.0.0.1"
    csrf = f"{site_url},{api_public}"

    lines = [
        f'DATABASE_URL="{esc(database_url)}"',
        f'SECRET_KEY="{esc(django_secret)}"',
        f'CORS_ORIGINS="{esc(cors)}"',
        f'SITE_URL="{esc(site_url)}"',
        f'API_PUBLIC_URL="{esc(api_public)}"',
        f'DJANGO_SECRET_KEY="{esc(django_secret)}"',
        'DEBUG="false"',
        'USE_WHITENOISE="true"',
        'USE_TLS_BEHIND_PROXY="true"',
        # Server-side Django → FastAPI (same Compose network)
        'RYUNOVA_API_BASE="http://api:8010/api/v1"',
        f'RYUNOVA_API_PUBLIC="{esc(api_public)}"',
        'RYUNOVA_API_PUBLIC_PORT="443"',
        'RYUNOVA_REWRITE_API_PUBLIC_IN_RESPONSES="false"',
        f'ALLOWED_HOSTS="{esc(allowed)}"',
        f'CSRF_TRUSTED_ORIGINS="{esc(csrf)}"',
        f'SITE_DOMAIN="{esc(host_only)}"',
        f'EMAIL_HOST="{esc(email_host)}"',
        f'EMAIL_PORT="{esc(email_port)}"',
        f'EMAIL_USE_TLS="{"true" if email_use_tls else "false"}"',
        f'EMAIL_HOST_USER="{esc(email_user)}"',
        f'EMAIL_HOST_PASSWORD="{esc(email_pw)}"',
        f'DEFAULT_FROM_EMAIL="{esc(default_from)}"',
        f'EMAIL_HOST_USER_NAME="{esc(from_name)}"',
        f'AWS_S3_MEDIA_BUCKET="{esc(s3_bucket)}"',
        f'AWS_S3_REGION="{esc(aws_region)}"',
        f'MEDIA_PUBLIC_BASE_URL="{esc(media_public_base)}"',
    ]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
