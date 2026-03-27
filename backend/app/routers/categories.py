from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.category import RyunovaCategory
from app.org_access import OrganisationContextDep, assert_category_in_context
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.schemas.taxonomy_actions import TaxonomyReorderBody
from app.taxonomy_display import enrich_category_read

router = APIRouter(prefix="/categories", tags=["categories"])

_SORTABLE = {
    "name": RyunovaCategory.name,
    "slug": RyunovaCategory.slug,
    "sort_order": RyunovaCategory.sort_order,
    "active": RyunovaCategory.active,
    "created_at": RyunovaCategory.created_at,
    "updated_at": RyunovaCategory.updated_at,
    "created_by": RyunovaCategory.created_by_user_id,
    "updated_by": RyunovaCategory.updated_by_user_id,
}


def _category_list_stmt(include_inactive: bool, sort: str, order: str, organisation_id: uuid.UUID | None):
    col = _SORTABLE.get(sort, RyunovaCategory.sort_order)
    primary = desc(col).nulls_last() if order.lower() == "desc" else asc(col).nulls_last()
    stmt = (
        select(RyunovaCategory)
        .options(
            joinedload(RyunovaCategory.parent_category),
            joinedload(RyunovaCategory.created_by_user),
            joinedload(RyunovaCategory.updated_by_user),
        )
        .order_by(primary, asc(RyunovaCategory.name))
    )
    if not include_inactive:
        stmt = stmt.where(RyunovaCategory.active.is_(True))
    if organisation_id is not None:
        stmt = stmt.where(RyunovaCategory.organisation_id == organisation_id)
    return stmt


def _load_category(db: Session, category_id: uuid.UUID) -> RyunovaCategory | None:
    return db.scalar(
        select(RyunovaCategory)
        .options(
            joinedload(RyunovaCategory.parent_category),
            joinedload(RyunovaCategory.created_by_user),
            joinedload(RyunovaCategory.updated_by_user),
        )
        .where(RyunovaCategory.id == category_id)
    )


@router.get("", response_model=list[CategoryRead])
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
    include_inactive: Annotated[bool, Query(description="Include disabled categories")] = False,
    sort: Annotated[str, Query(description="Sort field")] = "sort_order",
    order: Annotated[str, Query(description="asc or desc")] = "asc",
) -> list[CategoryRead]:
    stmt = _category_list_stmt(include_inactive, sort, order, ctx.organisation_id)
    rows = db.scalars(stmt).unique().all()
    return [enrich_category_read(r) for r in rows]


def _list_category_reads(db: Session, *, include_inactive: bool, organisation_id: uuid.UUID | None) -> list[CategoryRead]:
    stmt = _category_list_stmt(include_inactive, "sort_order", "asc", organisation_id)
    rows = db.scalars(stmt).unique().all()
    return [enrich_category_read(r) for r in rows]


@router.post("/reorder", response_model=list[CategoryRead])
def reorder_categories(
    body: TaxonomyReorderBody,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
    include_inactive: Annotated[bool, Query(description="Match list filter (inactive rows)")] = False,
) -> list[CategoryRead]:
    ids = body.ordered_ids
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Duplicate ids in ordered_ids")
    stmt = select(RyunovaCategory).where(RyunovaCategory.id.in_(ids))
    if ctx.organisation_id is not None:
        stmt = stmt.where(RyunovaCategory.organisation_id == ctx.organisation_id)
    if not include_inactive:
        stmt = stmt.where(RyunovaCategory.active.is_(True))
    found = {r.id: r for r in db.scalars(stmt).unique().all()}
    if len(found) != len(ids):
        raise HTTPException(
            status_code=400,
            detail="One or more categories were not found or are not included in the current list",
        )
    for i, uid in enumerate(ids):
        row = found[uid]
        row.sort_order = i
        row.updated_by_user_id = user.id
    db.commit()
    return _list_category_reads(db, include_inactive=include_inactive, organisation_id=ctx.organisation_id)


@router.post("/sort-by-name", response_model=list[CategoryRead])
def sort_categories_by_name(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
    include_inactive: Annotated[bool, Query(description="Include inactive when renumbering")] = False,
) -> list[CategoryRead]:
    stmt = select(RyunovaCategory).options(
        joinedload(RyunovaCategory.parent_category),
        joinedload(RyunovaCategory.created_by_user),
        joinedload(RyunovaCategory.updated_by_user),
    )
    if ctx.organisation_id is not None:
        stmt = stmt.where(RyunovaCategory.organisation_id == ctx.organisation_id)
    if not include_inactive:
        stmt = stmt.where(RyunovaCategory.active.is_(True))
    rows = list(db.scalars(stmt).unique().all())
    rows.sort(key=lambda c: (c.name or "").lower())
    for i, cat in enumerate(rows):
        cat.sort_order = i
        cat.updated_by_user_id = user.id
    db.commit()
    return _list_category_reads(db, include_inactive=include_inactive, organisation_id=ctx.organisation_id)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> CategoryRead:
    oid = ctx.require_organisation_id()
    if body.parent_id:
        parent = db.get(RyunovaCategory, body.parent_id)
        if not parent or parent.organisation_id != oid:
            raise HTTPException(status_code=400, detail="parent_id not found in this organisation")
    next_sort = body.sort_order
    if next_sort is None:
        mx = db.scalar(select(func.max(RyunovaCategory.sort_order)).where(RyunovaCategory.organisation_id == oid))
        next_sort = (int(mx) if mx is not None else -1) + 1
    cat = RyunovaCategory(
        organisation_id=oid,
        name=body.name,
        slug=body.slug,
        description=body.description,
        parent_id=body.parent_id,
        sort_order=next_sort,
        active=body.active,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(cat)
    db.commit()
    cat = _load_category(db, cat.id)
    if not cat:
        raise HTTPException(status_code=500, detail="Failed to load category")
    return enrich_category_read(cat)


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(
    category_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
) -> CategoryRead:
    cat = _load_category(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    assert_category_in_context(ctx, cat.organisation_id)
    return enrich_category_read(cat)


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> CategoryRead:
    cat = db.get(RyunovaCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    assert_category_in_context(ctx, cat.organisation_id)
    data = body.model_dump(exclude_unset=True)
    if "parent_id" in data and data["parent_id"]:
        if data["parent_id"] == category_id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent")
        parent = db.get(RyunovaCategory, data["parent_id"])
        if not parent or parent.organisation_id != cat.organisation_id:
            raise HTTPException(status_code=400, detail="parent_id not found in this organisation")
    for k, v in data.items():
        setattr(cat, k, v)
    cat.updated_by_user_id = user.id
    db.commit()
    cat = _load_category(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return enrich_category_read(cat)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
) -> None:
    cat = db.get(RyunovaCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    assert_category_in_context(ctx, cat.organisation_id)
    db.delete(cat)
    db.commit()
