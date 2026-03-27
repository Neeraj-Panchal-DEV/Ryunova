from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.brand import RyunovaBrand
from app.org_access import OrganisationContextDep, assert_brand_in_context
from app.schemas.brand import BrandCreate, BrandRead, BrandUpdate
from app.schemas.taxonomy_actions import TaxonomyReorderBody
from app.taxonomy_display import enrich_brand_read

router = APIRouter(prefix="/brands", tags=["brands"])

_SORTABLE = {
    "name": RyunovaBrand.name,
    "slug": RyunovaBrand.slug,
    "sort_order": RyunovaBrand.sort_order,
    "active": RyunovaBrand.active,
    "created_at": RyunovaBrand.created_at,
    "updated_at": RyunovaBrand.updated_at,
    "created_by": RyunovaBrand.created_by_user_id,
    "updated_by": RyunovaBrand.updated_by_user_id,
}


def _brand_list_stmt(include_inactive: bool, sort: str, order: str, organisation_id: uuid.UUID | None):
    col = _SORTABLE.get(sort, RyunovaBrand.sort_order)
    primary = desc(col).nulls_last() if order.lower() == "desc" else asc(col).nulls_last()
    stmt = (
        select(RyunovaBrand)
        .options(
            joinedload(RyunovaBrand.created_by_user),
            joinedload(RyunovaBrand.updated_by_user),
        )
        .order_by(primary, asc(RyunovaBrand.name))
    )
    if not include_inactive:
        stmt = stmt.where(RyunovaBrand.active.is_(True))
    if organisation_id is not None:
        stmt = stmt.where(RyunovaBrand.organisation_id == organisation_id)
    return stmt


def _load_brand(db: Session, brand_id: uuid.UUID) -> RyunovaBrand | None:
    return db.scalar(
        select(RyunovaBrand)
        .options(
            joinedload(RyunovaBrand.created_by_user),
            joinedload(RyunovaBrand.updated_by_user),
        )
        .where(RyunovaBrand.id == brand_id)
    )


@router.get("", response_model=list[BrandRead])
def list_brands(
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
    include_inactive: Annotated[bool, Query(description="Include disabled brands")] = False,
    sort: Annotated[str, Query(description="Sort field")] = "sort_order",
    order: Annotated[str, Query(description="asc or desc")] = "asc",
) -> list[BrandRead]:
    stmt = _brand_list_stmt(include_inactive, sort, order, ctx.organisation_id)
    rows = db.scalars(stmt).unique().all()
    return [enrich_brand_read(r) for r in rows]


def _list_brand_reads(db: Session, *, include_inactive: bool, organisation_id: uuid.UUID | None) -> list[BrandRead]:
    stmt = _brand_list_stmt(include_inactive, "sort_order", "asc", organisation_id)
    rows = db.scalars(stmt).unique().all()
    return [enrich_brand_read(r) for r in rows]


@router.post("/reorder", response_model=list[BrandRead])
def reorder_brands(
    body: TaxonomyReorderBody,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
    include_inactive: Annotated[bool, Query(description="Match list filter (inactive rows)")] = False,
) -> list[BrandRead]:
    ids = body.ordered_ids
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Duplicate ids in ordered_ids")
    stmt = select(RyunovaBrand).where(RyunovaBrand.id.in_(ids))
    if ctx.organisation_id is not None:
        stmt = stmt.where(RyunovaBrand.organisation_id == ctx.organisation_id)
    if not include_inactive:
        stmt = stmt.where(RyunovaBrand.active.is_(True))
    found = {r.id: r for r in db.scalars(stmt).unique().all()}
    if len(found) != len(ids):
        raise HTTPException(
            status_code=400,
            detail="One or more brands were not found or are not included in the current list",
        )
    for i, uid in enumerate(ids):
        row = found[uid]
        row.sort_order = i
        row.updated_by_user_id = user.id
    db.commit()
    return _list_brand_reads(db, include_inactive=include_inactive, organisation_id=ctx.organisation_id)


@router.post("/sort-by-name", response_model=list[BrandRead])
def sort_brands_by_name(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
    include_inactive: Annotated[bool, Query(description="Include inactive when renumbering")] = False,
) -> list[BrandRead]:
    stmt = select(RyunovaBrand).options(
        joinedload(RyunovaBrand.created_by_user),
        joinedload(RyunovaBrand.updated_by_user),
    )
    if ctx.organisation_id is not None:
        stmt = stmt.where(RyunovaBrand.organisation_id == ctx.organisation_id)
    if not include_inactive:
        stmt = stmt.where(RyunovaBrand.active.is_(True))
    rows = list(db.scalars(stmt).unique().all())
    rows.sort(key=lambda b: (b.name or "").lower())
    for i, brand in enumerate(rows):
        brand.sort_order = i
        brand.updated_by_user_id = user.id
    db.commit()
    return _list_brand_reads(db, include_inactive=include_inactive, organisation_id=ctx.organisation_id)


@router.post("", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
def create_brand(
    body: BrandCreate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> BrandRead:
    oid = ctx.require_organisation_id()
    existing = db.scalar(
        select(RyunovaBrand).where(
            RyunovaBrand.name == body.name.strip(),
            RyunovaBrand.organisation_id == oid,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="A brand with this name already exists in this organisation")
    next_sort = body.sort_order
    if next_sort is None:
        mx = db.scalar(select(func.max(RyunovaBrand.sort_order)).where(RyunovaBrand.organisation_id == oid))
        next_sort = (int(mx) if mx is not None else -1) + 1
    b = RyunovaBrand(
        organisation_id=oid,
        name=body.name.strip(),
        slug=body.slug,
        description=body.description,
        sort_order=next_sort,
        active=body.active,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(b)
    db.commit()
    b = _load_brand(db, b.id)
    if not b:
        raise HTTPException(status_code=500, detail="Failed to load brand")
    return enrich_brand_read(b)


@router.get("/{brand_id}", response_model=BrandRead)
def get_brand(
    brand_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
) -> BrandRead:
    b = _load_brand(db, brand_id)
    if not b:
        raise HTTPException(status_code=404, detail="Brand not found")
    assert_brand_in_context(ctx, b.organisation_id)
    return enrich_brand_read(b)


@router.patch("/{brand_id}", response_model=BrandRead)
def update_brand(
    brand_id: uuid.UUID,
    body: BrandUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> BrandRead:
    b = db.get(RyunovaBrand, brand_id)
    if not b:
        raise HTTPException(status_code=404, detail="Brand not found")
    assert_brand_in_context(ctx, b.organisation_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        other = db.scalar(
            select(RyunovaBrand).where(
                RyunovaBrand.name == data["name"].strip(),
                RyunovaBrand.organisation_id == b.organisation_id,
                RyunovaBrand.id != brand_id,
            )
        )
        if other:
            raise HTTPException(status_code=400, detail="A brand with this name already exists")
        data["name"] = data["name"].strip()
    for k, v in data.items():
        setattr(b, k, v)
    b.updated_by_user_id = user.id
    db.commit()
    b = _load_brand(db, brand_id)
    if not b:
        raise HTTPException(status_code=404, detail="Brand not found")
    return enrich_brand_read(b)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(
    brand_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
) -> None:
    b = db.get(RyunovaBrand, brand_id)
    if not b:
        raise HTTPException(status_code=404, detail="Brand not found")
    assert_brand_in_context(ctx, b.organisation_id)
    db.delete(b)
    db.commit()
