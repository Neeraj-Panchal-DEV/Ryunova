"""Persist uploaded media to local disk or S3 (see USE_S3_MEDIA + key prefixes orgs/ and users/)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_s3_client: Any = None


def key_uses_object_storage(key: str) -> bool:
    """Keys under orgs/ or users/ can be stored in S3 when USE_S3_MEDIA is true."""
    return bool(key) and (key.startswith("orgs/") or key.startswith("users/"))


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
