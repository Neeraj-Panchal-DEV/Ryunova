from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.listing_channel import RyunovaListingChannel
from app.schemas.listing_channel import MarketplaceRead, MarketplaceUpdate

router = APIRouter(prefix="/marketplaces", tags=["marketplaces"])


@router.get("", response_model=list[MarketplaceRead])
def list_marketplaces(
    db: Annotated[Session, Depends(get_db)],
    _user: CurrentUser,
    include_inactive: bool = False,
) -> list[MarketplaceRead]:
    """List all marketplace / e-commerce integrations (global configuration)."""
    stmt = select(RyunovaListingChannel).order_by(RyunovaListingChannel.sort_order, RyunovaListingChannel.name)
    if not include_inactive:
        stmt = stmt.where(RyunovaListingChannel.active.is_(True))
    rows = db.scalars(stmt).all()
    return [MarketplaceRead.model_validate(r) for r in rows]


@router.get("/{marketplace_id}", response_model=MarketplaceRead)
def get_marketplace(
    marketplace_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _user: CurrentUser,
) -> MarketplaceRead:
    ch = db.get(RyunovaListingChannel, marketplace_id)
    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marketplace not found")
    return MarketplaceRead.model_validate(ch)


@router.patch("/{marketplace_id}", response_model=MarketplaceRead)
def update_marketplace(
    marketplace_id: uuid.UUID,
    body: MarketplaceUpdate,
    db: Annotated[Session, Depends(get_db)],
    _user: CurrentUser,
) -> MarketplaceRead:
    """Update marketplace metadata and integration requirements (JSON)."""
    ch = db.get(RyunovaListingChannel, marketplace_id)
    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marketplace not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(ch, k, v)
    db.commit()
    db.refresh(ch)
    return MarketplaceRead.model_validate(ch)
