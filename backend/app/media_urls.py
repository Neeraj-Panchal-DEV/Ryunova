"""Build public URLs for uploaded media (avatars, org logos, product images)."""

from __future__ import annotations

from app.config import get_settings
from app.media_storage import key_uses_object_storage


def public_media_url(s3_key: str | None) -> str | None:
    if not s3_key:
        return None
    s = get_settings()
    override = (s.media_public_base_url or "").strip()
    # orgs/ + users/ keys with USE_S3_MEDIA use the public bucket/CloudFront base; legacy paths stay on the API.
    if override and s.use_s3_media and key_uses_object_storage(s3_key):
        return f"{override.rstrip('/')}/{s3_key}"
    base = str(s.api_public_url).rstrip("/")
    prefix = s.media_url_prefix.rstrip("/")
    return f"{base}{prefix}/{s3_key}"
