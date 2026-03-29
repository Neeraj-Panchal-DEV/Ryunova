#!/usr/bin/env python3
"""One-time migration: legacy media paths -> orgs/<organisation_id>/...

Rewrites keys in PostgreSQL and moves files under upload_dir (local disk only).

Legacy patterns:
  products/<product_id>/...     -> orgs/<org_id>/products/<product_id>/...
  org-logos/<org_id>/...        -> orgs/<org_id>/branding/...
  avatars/<user_id>/...         -> orgs/<org_id>/users/<user_id>/avatars/...
  users/<user_id>/avatars/...   -> orgs/<org_id>/users/<user_id>/avatars/...

Avatar org: first membership (organisation name order), else default org UUID
(see app.constants.DEFAULT_ORGANISATION_ID).

Run from backend/ (same as other scripts):
  cd /opt/apps/app_ryunova/backend   # or repo backend/
  python scripts/migrate_media_paths.py --dry-run
  python scripts/migrate_media_paths.py

Inside Docker (typical production):
  docker exec ryunova_api python scripts/migrate_media_paths.py --dry-run
  docker exec ryunova_api python scripts/migrate_media_paths.py

If USE_S3_MEDIA=true, do not move local files; use --db-only after copying objects in S3 to the new keys,
or temporarily set USE_S3_MEDIA=false and sync. This script aborts when S3 is enabled unless --db-only.

See db/README.md section "Media path migration (one-time)".
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import DEFAULT_ORGANISATION_ID
from app.database import SessionLocal
from app.models.organisation import RyunovaOrganisation, RyunovaUserOrganisation
from app.models.product import RyunovaProductImage, RyunovaProductMaster
from app.models.user import RyunovaUser

_RE_AVATAR_LEGACY = re.compile(r"^avatars/([0-9a-f-]{36})/(.+)$", re.I)
_RE_AVATAR_USERS = re.compile(r"^users/([0-9a-f-]{36})/avatars/(.+)$", re.I)
_RE_ORG_LOGO = re.compile(r"^org-logos/([0-9a-f-]{36})/(.+)$", re.I)


def _upload_root() -> Path:
    return Path(get_settings().upload_dir).resolve()


def _resolve_avatar_org_id(db: Session, user_id: uuid.UUID) -> uuid.UUID:
    oid = db.scalar(
        select(RyunovaOrganisation.id)
        .join(RyunovaUserOrganisation, RyunovaUserOrganisation.organisation_id == RyunovaOrganisation.id)
        .where(RyunovaUserOrganisation.user_id == user_id)
        .order_by(RyunovaOrganisation.name)
        .limit(1)
    )
    return oid or DEFAULT_ORGANISATION_ID


def _move_or_sync_db(
    *,
    root: Path,
    old_key: str,
    new_key: str,
    dry_run: bool,
    db_only: bool,
) -> str | None:
    """Returns None if nothing to do, 'moved' if file moved, 'db' if only DB should be updated."""
    if old_key == new_key:
        return None
    src = root / old_key
    dst = root / new_key
    if db_only:
        if dst.is_file():
            return "db"
        if src.is_file():
            print(f"  warning: --db-only but old path still has file (move or delete first): {src}")
        return None
    if not src.is_file():
        if dst.is_file():
            return "db"
        print(f"  skip (no file at old or new path): {old_key}")
        return None
    if dst.exists():
        print(f"  skip (destination exists): {dst}")
        return None
    if dry_run:
        print(f"  MOVE {src} -> {dst}")
        return "moved"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return "moved"


def migrate_products_fixed(db: Session, root: Path, dry_run: bool, db_only: bool) -> int:
    """Migrate product images: products/... -> orgs/<org>/products/..."""
    n = 0
    imgs = db.scalars(
        select(RyunovaProductImage)
        .join(RyunovaProductMaster, RyunovaProductImage.product_id == RyunovaProductMaster.id)
        .where(
            RyunovaProductImage.s3_key.startswith("products/"),
            ~RyunovaProductImage.s3_key.startswith("orgs/"),
        )
    ).unique()
    for img in imgs:
        p = db.get(RyunovaProductMaster, img.product_id)
        if not p:
            continue
        old_key = img.s3_key
        new_key = f"orgs/{p.organisation_id}/{old_key}"
        action = _move_or_sync_db(root=root, old_key=old_key, new_key=new_key, dry_run=dry_run, db_only=db_only)
        if action == "moved":
            if not dry_run:
                img.s3_key = new_key
            n += 1
            print(f"  product image {img.id}: {old_key} -> {new_key}")
            continue
        if action == "db":
            if not dry_run:
                img.s3_key = new_key
            n += 1
            print(f"  product image (file already at dest) {img.id}: {old_key} -> {new_key}")
            continue
        # file missing at src but dest exists -> align DB
        if (root / new_key).is_file() and old_key != new_key:
            if not dry_run:
                img.s3_key = new_key
            n += 1
            print(f"  product image (align DB only) {img.id}: {old_key} -> {new_key}")
    return n


def migrate_logos(db: Session, root: Path, dry_run: bool, db_only: bool) -> int:
    n = 0
    orgs = db.scalars(
        select(RyunovaOrganisation).where(
            RyunovaOrganisation.logo_s3_key.isnot(None),
            RyunovaOrganisation.logo_s3_key.startswith("org-logos/"),
            ~RyunovaOrganisation.logo_s3_key.startswith("orgs/"),
        )
    ).all()
    for org in orgs:
        old_key = org.logo_s3_key or ""
        m = _RE_ORG_LOGO.match(old_key)
        if not m:
            print(f"  skip unexpected logo key: {old_key}")
            continue
        oid_s, fname = m.group(1), m.group(2)
        new_key = f"orgs/{oid_s}/branding/{fname}"
        action = _move_or_sync_db(root=root, old_key=old_key, new_key=new_key, dry_run=dry_run, db_only=db_only)
        if action == "moved":
            if not dry_run:
                org.logo_s3_key = new_key
            n += 1
            print(f"  org {org.id} logo: {old_key} -> {new_key}")
            continue
        if action == "db":
            if not dry_run:
                org.logo_s3_key = new_key
            n += 1
            print(f"  org {org.id} logo (file at dest): {old_key} -> {new_key}")
            continue
        if (root / new_key).is_file() and old_key != new_key:
            if not dry_run:
                org.logo_s3_key = new_key
            n += 1
            print(f"  org {org.id} logo (align DB): {old_key} -> {new_key}")
    return n


def migrate_avatars(db: Session, root: Path, dry_run: bool, db_only: bool) -> int:
    n = 0
    users = db.scalars(
        select(RyunovaUser).where(
            RyunovaUser.avatar_s3_key.isnot(None),
            ~RyunovaUser.avatar_s3_key.startswith("orgs/"),
        )
    ).all()
    for user in users:
        old_key = user.avatar_s3_key or ""
        new_key: str | None = None
        m1 = _RE_AVATAR_LEGACY.match(old_key)
        m2 = _RE_AVATAR_USERS.match(old_key)
        if m1:
            uid_s, rest = m1.group(1), m1.group(2)
            if uuid.UUID(uid_s) != user.id:
                print(f"  skip avatar user mismatch {user.id}: {old_key}")
                continue
            org_id = _resolve_avatar_org_id(db, user.id)
            new_key = f"orgs/{org_id}/users/{user.id}/avatars/{rest}"
        elif m2:
            uid_s, rest = m2.group(1), m2.group(2)
            if uuid.UUID(uid_s) != user.id:
                print(f"  skip avatar user mismatch {user.id}: {old_key}")
                continue
            org_id = _resolve_avatar_org_id(db, user.id)
            new_key = f"orgs/{org_id}/users/{user.id}/avatars/{rest}"
        else:
            continue

        action = _move_or_sync_db(root=root, old_key=old_key, new_key=new_key, dry_run=dry_run, db_only=db_only)
        if action == "moved":
            if not dry_run:
                user.avatar_s3_key = new_key
            n += 1
            print(f"  user {user.id} avatar: {old_key} -> {new_key}")
            continue
        if action == "db":
            if not dry_run:
                user.avatar_s3_key = new_key
            n += 1
            print(f"  user {user.id} avatar (file at dest): {old_key} -> {new_key}")
            continue
        if (root / new_key).is_file() and old_key != new_key:
            if not dry_run:
                user.avatar_s3_key = new_key
            n += 1
            print(f"  user {user.id} avatar (align DB): {old_key} -> {new_key}")
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy media paths to orgs/<id>/...")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without moving files or committing DB")
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="Only update database keys (use after files already moved or on S3)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.use_s3_media and not args.db_only:
        print(
            "USE_S3_MEDIA=true: refusing to move local files. Copy objects in S3 to the new keys, "
            "then re-run with --db-only, or run this script with USE_S3_MEDIA=false on a host that has the files.",
        )
        sys.exit(1)

    root = _upload_root()
    print(f"upload_dir: {root}")
    print(f"dry_run={args.dry_run} db_only={args.db_only}")

    db: Session = SessionLocal()
    total = 0
    try:
        print("--- product images ---")
        total += migrate_products_fixed(db, root, args.dry_run, args.db_only)
        print("--- organisation logos ---")
        total += migrate_logos(db, root, args.dry_run, args.db_only)
        print("--- user avatars ---")
        total += migrate_avatars(db, root, args.dry_run, args.db_only)

        if args.dry_run:
            print(f"\nDry run complete. Would update ~{total} rows (counts may include duplicates).")
            db.rollback()
        else:
            db.commit()
            print(f"\nDone. Updated rows (approx): {total}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
