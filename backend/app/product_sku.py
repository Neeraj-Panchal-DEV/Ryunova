"""Server-assigned product SKUs: unique per organisation, immutable after create."""
#backend/app/product_sku.py
from __future__ import annotations

import secrets
import string
import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product import RyunovaProductMaster

# Uppercase A–Z only: channel-safe, unambiguous, no digits/symbols.
_SKU_ALPHABET = string.ascii_uppercase
_SKU_LENGTH = 10
_MAX_ATTEMPTS = 48


def generate_product_sku_candidate() -> str:
    """Return one random SKU candidate (not yet checked for uniqueness)."""
    return "".join(secrets.choice(_SKU_ALPHABET) for _ in range(_SKU_LENGTH))


def allocate_unique_sku_for_organisation(db: Session, organisation_id: uuid.UUID) -> str:
    """
    Reserve a SKU that does not exist for this organisation.

    Retries on collision (including rare races on the unique constraint).
    """
    for _ in range(_MAX_ATTEMPTS):
        sku = generate_product_sku_candidate()
        taken = db.scalar(
            select(RyunovaProductMaster.id).where(
                RyunovaProductMaster.organisation_id == organisation_id,
                RyunovaProductMaster.sku == sku,
            )
        )
        if taken is None:
            return sku
    raise RuntimeError("exhausted SKU allocation attempts without finding a free code")


def create_product_with_allocated_sku(
    db: Session,
    *,
    organisation_id: uuid.UUID,
    build_row: Callable[[str], RyunovaProductMaster],
) -> RyunovaProductMaster:
    """
    Insert a product row, retrying SKU generation if the unique constraint races.

    `build_row(sku: str) -> RyunovaProductMaster` must return an unattached ORM instance.
    """
    last_integrity: IntegrityError | None = None
    for _ in range(_MAX_ATTEMPTS):
        sku = allocate_unique_sku_for_organisation(db, organisation_id)
        row = build_row(sku)
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            return row
        except IntegrityError as e:
            last_integrity = e
            db.rollback()
            continue
    if last_integrity is not None:
        raise RuntimeError("could not allocate a unique SKU after repeated collisions") from last_integrity
    raise RuntimeError("could not allocate a unique SKU after repeated collisions")
