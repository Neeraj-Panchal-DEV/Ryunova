"""Persist uploaded media to local disk or S3 (see USE_S3_MEDIA + key prefix orgs/)."""
#backend/app/media_storage.py
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_s3_client: Any = None

# Layout under upload_dir (and S3) — all tenant data lives under orgs/<organisation_id>/:
#   products/<product_id>/...
#   branding/...
#   users/<user_id>/avatars/...


def key_uses_object_storage(key: str) -> bool:
    """Only keys under orgs/ are stored in S3 when USE_S3_MEDIA is true."""
    return bool(key) and key.startswith("orgs/")


def _client():
    global _s3_client
    if _s3_client is None:
        import boto3

        s = get_settings()
        region = (s.aws_s3_region or "ap-southeast-2").strip()
        _s3_client = boto3.client("s3", region_name=region)
    return _s3_client


def write_bytes(key: str, data: bytes, content_type: str) -> None:
    """Write file bytes. Uses S3 when configured; otherwise local upload_dir."""
    s = get_settings()
    if s.use_s3_media and key_uses_object_storage(key):
        bucket = (s.aws_s3_media_bucket or "").strip()
        if not bucket:
            raise RuntimeError("USE_S3_MEDIA is true but AWS_S3_MEDIA_BUCKET is empty")
        _client().put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=(content_type or "application/octet-stream").split(";")[0].strip(),
        )
        return
    root = Path(s.upload_dir)
    dest = root / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def ensure_org_media_folders(organisation_id: uuid.UUID) -> None:
    """Create empty directory layout for one organisation on local disk (no-op when USE_S3_MEDIA)."""
    s = get_settings()
    if s.use_s3_media:
        return
    root = Path(s.upload_dir)
    oid = str(organisation_id)
    base = root / "orgs" / oid
    for sub in ("products", "branding", "users"):
        (base / sub).mkdir(parents=True, exist_ok=True)


def delete_key(key: str | None) -> None:
    if not key:
        return
    s = get_settings()
    if s.use_s3_media and key_uses_object_storage(key):
        bucket = (s.aws_s3_media_bucket or "").strip()
        if not bucket:
            return
        try:
            _client().delete_object(Bucket=bucket, Key=key)
        except Exception as e:
            logger.warning("S3 delete_object failed for %s: %s", key, e)
        return
    p = Path(s.upload_dir) / key
    if p.is_file():
        p.unlink(missing_ok=True)
