"""Multi-tenant organisation context from X-Organisation-Id + membership rules."""
#backend/app/org_access.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.organisation import RyunovaOrganisation, RyunovaUserOrganisation
from app.models.user import RyunovaUser


@dataclass
class OrganisationContext:
    """organisation_id None only when a platform user omits X-Organisation-Id (read-all mode)."""

    user: RyunovaUser
    organisation_id: uuid.UUID | None

    @property
    def read_all_organisations(self) -> bool:
        return self.organisation_id is None and self.user.is_platform_user

    def require_organisation_id(self) -> uuid.UUID:
        """Writes (create/update) need a tenant scope; platform all-org mode is read-only."""
        if self.organisation_id is not None:
            return self.organisation_id
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Catalog changes require a scoped organisation. "
                "Use the organisation switcher to pick one organisation, then try again."
            ),
        )


def user_has_org_membership(db: Session, user: RyunovaUser, organisation_id: uuid.UUID) -> bool:
    if user.is_platform_user:
        return True
    row = db.scalar(
        select(RyunovaUserOrganisation.user_id).where(
            RyunovaUserOrganisation.user_id == user.id,
            RyunovaUserOrganisation.organisation_id == organisation_id,
        )
    )
    return row is not None


def _parse_org_header(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = raw.strip()
    return s or None


def get_organisation_context(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    x_organisation_id: Annotated[str | None, Header(alias="X-Organisation-Id")] = None,
) -> OrganisationContext:
    raw = _parse_org_header(x_organisation_id)
    if user.is_platform_user:
        if raw is None or raw.lower() == "all":
            return OrganisationContext(user=user, organisation_id=None)
        try:
            oid = uuid.UUID(raw)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Organisation-Id") from e
        org = db.get(RyunovaOrganisation, oid)
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
        return OrganisationContext(user=user, organisation_id=oid)

    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organisation-Id is required",
        )
    try:
        oid = uuid.UUID(raw)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Organisation-Id") from e
    if not user_has_org_membership(db, user, oid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organisation")
    return OrganisationContext(user=user, organisation_id=oid)


OrganisationContextDep = Annotated[OrganisationContext, Depends(get_organisation_context)]


def assert_product_in_context(db: Session, ctx: OrganisationContext, product_org_id: uuid.UUID) -> None:
    if ctx.read_all_organisations:
        return
    if ctx.organisation_id != product_org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")


def assert_brand_in_context(ctx: OrganisationContext, brand_org_id: uuid.UUID) -> None:
    if ctx.read_all_organisations:
        return
    if ctx.organisation_id != brand_org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")


def assert_category_in_context(ctx: OrganisationContext, category_org_id: uuid.UUID) -> None:
    if ctx.read_all_organisations:
        return
    if ctx.organisation_id != category_org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
