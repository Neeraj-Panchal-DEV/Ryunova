"""Cloudflare Turnstile server-side verification (optional)."""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def is_turnstile_enabled() -> bool:
    site = (getattr(settings, "TURNSTILE_SITE_KEY", "") or "").strip()
    secret = (getattr(settings, "TURNSTILE_SECRET_KEY", "") or "").strip()
    return bool(site and secret)


def verify_turnstile_token(token: str, remote_ip: str | None) -> bool:
    secret = (getattr(settings, "TURNSTILE_SECRET_KEY", "") or "").strip()
    if not secret or not token:
        return False
    data: dict[str, Any] = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        r = requests.post(VERIFY_URL, data=data, timeout=10)
        r.raise_for_status()
        body = r.json()
    except Exception as exc:
        logger.warning("Turnstile siteverify failed: %s", exc)
        return False
    return bool(body.get("success"))


def client_ip_for_turnstile(request) -> str | None:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip() or None
    ip = (request.META.get("REMOTE_ADDR") or "").strip()
    return ip or None
