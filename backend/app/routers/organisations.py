from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.media_storage import write_bytes as write_media_bytes
from app.database import get_db
from app.dependencies import CurrentUser
from app.media_urls import public_media_url
from app.models.organisation import RyunovaOrganisation, RyunovaUserOrganisation
from app.schemas.auth import OrganisationBrief

router = APIRouter(prefix="/organisations", tags=["organisations"])

_LOGO_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
_MAX_LOGO_BYTES = 5 * 1024 * 1024


def _normalize_content_type(raw: str | None) -> str:
    return (raw or "application/octet-stream").split(";")[0].strip().lower()


def _logo_extension(content_type: str) -> str:
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(content_type, ".bin")


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower().strip())
    s = s.strip("-")
    return s or "organisation"


def _organisation_brief(o: RyunovaOrganisation) -> OrganisationBrief:
    return OrganisationBrief(
        id=o.id,
        name=o.name,
        slug=o.slug,
        description=o.description,
        logo_url=public_media_url(o.logo_s3_key),
    )


def _unique_slug(db: Session, base: str) -> str:
    candidate = base
    n = 2
    while db.scalar(select(RyunovaOrganisation.id).where(RyunovaOrganisation.slug == candidate)):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


@router.get("", response_model=list[OrganisationBrief])
def list_accessible_organisations(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> list[OrganisationBrief]:
    if user.is_platform_user:
        rows = db.scalars(select(RyunovaOrganisation).order_by(RyunovaOrganisation.name)).all()
    else:
        rows = db.scalars(
            select(RyunovaOrganisation)
            .join(RyunovaUserOrganisation, RyunovaUserOrganisation.organisation_id == RyunovaOrganisation.id)
            .where(RyunovaUserOrganisation.user_id == user.id)
            .order_by(RyunovaOrganisation.name)
        ).all()
    return [_organisation_brief(o) for o in rows]


@router.post("", response_model=OrganisationBrief, status_code=status.HTTP_201_CREATED)
async def create_organisation(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    name: Annotated[str, Form()],
    slug: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    logo: UploadFile | None = File(None),
) -> OrganisationBrief:
    if not user.is_platform_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform user access required")
    nm = name.strip()
    if not nm:
        raise HTTPException(status_code=400, detail="name is required")
    base_slug = _slugify((slug or "").strip() or nm)
    unique = _unique_slug(db, base_slug)
    desc = (description or "").strip() or None

    org = RyunovaOrganisation(name=nm, slug=unique, description=desc)
    db.add(org)
    db.flush()

    if logo and logo.filename:
        content_type = _normalize_content_type(logo.content_type)
        if content_type == "image/jpg":
            content_type = "image/jpeg"
        if content_type not in _LOGO_CONTENT_TYPES:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Logo must be JPEG, PNG, GIF, or WebP.",
            )
        ext = _logo_extension(content_type)
        s3_key = f"orgs/{org.id}/branding/{uuid.uuid4().hex}_logo{ext}"
        chunks: list[bytes] = []
        size = 0
        try:
            while True:
                chunk = await logo.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > _MAX_LOGO_BYTES:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Logo too large (max {_MAX_LOGO_BYTES // (1024 * 1024)} MB).",
                    )
                chunks.append(chunk)
        except HTTPException:
            raise
        except Exception:
            db.rollback()
            raise
        data = b"".join(chunks)
        try:
            write_media_bytes(s3_key, data, content_type)
        except Exception:
            db.rollback()
            raise
        org.logo_s3_key = s3_key

    db.commit()
    db.refresh(org)
    return _organisation_brief(org)
