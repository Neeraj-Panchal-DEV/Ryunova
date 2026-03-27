"""Build public URLs for uploaded media (avatars, org logos)."""

from __future__ import annotations

from app.config import get_settings


def public_media_url(s3_key: str | None) -> str | None:
    if not s3_key:
        return None
    s = get_settings()
    override = (s.media_public_base_url or "").strip()
    if override:
        return f"{override.rstrip('/')}/{s3_key}"
    base = str(s.api_public_url).rstrip("/")
    prefix = s.media_url_prefix.rstrip("/")
    return f"{base}{prefix}/{s3_key}"
