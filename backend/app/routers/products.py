from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.brand import RyunovaBrand
from app.media_storage import delete_key as delete_media_key, write_bytes as write_media_bytes
from app.org_access import OrganisationContextDep, assert_product_in_context
from app.models.category import RyunovaCategory
from app.models.listing_channel import RyunovaListingChannel, RyunovaProductChannelListing
from app.models.product import ProductCondition, RyunovaProductImage, RyunovaProductMaster
from app.models.product_comment import RyunovaProductComment
from app.models.user import RyunovaUser
from app.product_sku import create_product_with_allocated_sku
from app.schemas.listing_channel import (
    BulkSetListingReadinessBody,
    BulkSetMarketplaceFlagsBody,
    ProductMarketplaceListingRead,
    ProductMarketplaceListingsPatch,
)
from app.schemas.product import (
    ProductCommentCreate,
    ProductCommentRead,
    ProductCreate,
    ProductImageFromUrlCreate,
    ProductImageRead,
    ProductImageUpdate,
    ProductListPage,
    ProductRead,
    ProductUpdate,
    ScrapePreviewRequest,
    ScrapePreviewResponse,
)
from app.services.listing_scrape import scrape_ebay, scrape_shopify
from app.taxonomy_display import product_audit_labels
from app.media_urls import public_media_url
from app.utils.image_url_import import build_stored_filename, download_image_bytes

ALLOWED_PRODUCT_PAGE_SIZES = frozenset({10, 20, 50, 100})
DEFAULT_PRODUCT_PAGE_SIZE = 20

# Allowed uploads for product media (content-type after normalisation).
_ALLOWED_MEDIA_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "video/mp4",
        "video/webm",
        "video/quicktime",
    }
)
_MAX_IMAGE_BYTES = 25 * 1024 * 1024
_MAX_VIDEO_BYTES = 150 * 1024 * 1024

router = APIRouter(prefix="/products", tags=["products"])

LOCAL_BUCKET = "local"


def _media_url(s3_key: str) -> str:
    """Same rules as avatars (S3 base vs API public URL)."""
    return public_media_url(s3_key) or ""


def _normalize_content_type(raw: str | None) -> str:
    return (raw or "application/octet-stream").split(";")[0].strip().lower()


def _media_type_from_content_type(content_type: str) -> str:
    ct = _normalize_content_type(content_type)
    if ct == "image/jpg":
        ct = "image/jpeg"
    if ct.startswith("video/"):
        return "video"
    return "image"


def _max_bytes_for_media(media_type: str) -> int:
    return _MAX_VIDEO_BYTES if media_type == "video" else _MAX_IMAGE_BYTES


def _ordered_product_images(p: RyunovaProductMaster) -> list[RyunovaProductImage]:
    """Cover first, then gallery order (sort_order, created_at)."""
    return sorted(
        p.images,
        key=lambda i: (0 if i.is_cover else 1, i.sort_order, i.created_at),
    )


def _author_display_name(u: RyunovaUser | None) -> str:
    if not u:
        return "User"
    if u.display_name and str(u.display_name).strip():
        return str(u.display_name).strip()
    return u.email.split("@")[0]


def _comment_counts_for_products(db: Session, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not product_ids:
        return {}
    stmt = (
        select(RyunovaProductComment.product_id, func.count())
        .where(RyunovaProductComment.product_id.in_(product_ids))
        .group_by(RyunovaProductComment.product_id)
    )
    return {pid: int(n) for pid, n in db.execute(stmt).all()}


def _active_channels(db: Session) -> list[RyunovaListingChannel]:
    return list(
        db.scalars(
            select(RyunovaListingChannel)
            .where(RyunovaListingChannel.active.is_(True))
            .order_by(RyunovaListingChannel.sort_order, RyunovaListingChannel.name)
        ).all()
    )


def _pcl_by_product(
    db: Session, product_ids: list[uuid.UUID]
) -> dict[tuple[uuid.UUID, uuid.UUID], RyunovaProductChannelListing]:
    if not product_ids:
        return {}
    rows = db.scalars(
        select(RyunovaProductChannelListing).where(RyunovaProductChannelListing.product_id.in_(product_ids))
    ).all()
    return {(r.product_id, r.channel_id): r for r in rows}


def _product_to_read(
    p: RyunovaProductMaster,
    *,
    comment_count: int = 0,
    channels: list[RyunovaListingChannel] | None = None,
    pcl_map: dict[tuple[uuid.UUID, uuid.UUID], RyunovaProductChannelListing] | None = None,
) -> ProductRead:
    images_out: list[ProductImageRead] = []
    for img in _ordered_product_images(p):
        pr = ProductImageRead.model_validate(img)
        pr.url = _media_url(img.s3_key)
        images_out.append(pr)
    brand_name = p.brand_rel.name if p.brand_rel else None
    ch_list: list[ProductMarketplaceListingRead] = []
    if channels is not None and pcl_map is not None:
        for ch in channels:
            row = pcl_map.get((p.id, ch.id))
            ch_list.append(
                ProductMarketplaceListingRead(
                    marketplace_id=ch.id,
                    code=ch.code,
                    name=ch.name,
                    enabled=row.enabled if row else False,
                    last_refreshed_at=row.last_refreshed_at if row else None,
                    posted_at=row.posted_at if row else None,
                )
            )
    data = ProductRead.model_validate(p).model_copy(
        update={
            "images": images_out,
            "brand_name": brand_name,
            "comment_count": comment_count,
            "marketplace_listings": ch_list,
            **product_audit_labels(p),
        }
    )
    return data


def _product_options():
    return (
        selectinload(RyunovaProductMaster.images),
        selectinload(RyunovaProductMaster.brand_rel),
        selectinload(RyunovaProductMaster.created_by_user),
        selectinload(RyunovaProductMaster.updated_by_user),
    )


def _product_list_where(
    *,
    include_inactive: bool,
    q: str | None,
    status_filter: str | None,
    listing_readiness_filter: str | None,
    organisation_id: uuid.UUID | None,
) -> list:
    conditions: list = []
    if not include_inactive:
        conditions.append(RyunovaProductMaster.active.is_(True))
    if q:
        like = f"%{q}%"
        conditions.append(or_(RyunovaProductMaster.title.ilike(like), RyunovaProductMaster.sku.ilike(like)))
    if status_filter:
        conditions.append(RyunovaProductMaster.status == status_filter)
    if listing_readiness_filter:
        conditions.append(RyunovaProductMaster.listing_readiness == listing_readiness_filter)
    if organisation_id is not None:
        conditions.append(RyunovaProductMaster.organisation_id == organisation_id)
    return conditions


def _ensure_brand_category_in_org(
    db: Session,
    organisation_id: uuid.UUID,
    brand_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
) -> None:
    if brand_id:
        br = db.get(RyunovaBrand, brand_id)
        if not br or br.organisation_id != organisation_id:
            raise HTTPException(status_code=400, detail="brand_id not found in this organisation")
    if category_id:
        c = db.get(RyunovaCategory, category_id)
        if not c or c.organisation_id != organisation_id:
            raise HTTPException(status_code=400, detail="category_id not found in this organisation")


@router.get("", response_model=ProductListPage)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
    q: str | None = None,
    status_filter: str | None = None,
    listing_readiness_filter: str | None = None,
    include_inactive: Annotated[bool, Query(description="Include disabled products (active=false)")] = False,
    page: Annotated[int, Query(ge=1, description="1-based page index")] = 1,
    page_size: Annotated[
        int,
        Query(description="Rows per page (allowed: 10, 20, 50, 100)"),
    ] = DEFAULT_PRODUCT_PAGE_SIZE,
) -> ProductListPage:
    if page_size not in ALLOWED_PRODUCT_PAGE_SIZES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"page_size must be one of: {', '.join(str(x) for x in sorted(ALLOWED_PRODUCT_PAGE_SIZES))}",
        )
    conditions = _product_list_where(
        include_inactive=include_inactive,
        q=q,
        status_filter=status_filter,
        listing_readiness_filter=listing_readiness_filter,
        organisation_id=ctx.organisation_id,
    )
    count_stmt = select(func.count()).select_from(RyunovaProductMaster)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = int(db.scalar(count_stmt) or 0)

    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page = min(page, total_pages) if total else 1

    offset = (page - 1) * page_size
    stmt = (
        select(RyunovaProductMaster)
        .options(*_product_options())
        .order_by(RyunovaProductMaster.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if conditions:
        stmt = stmt.where(*conditions)
    rows = db.scalars(stmt).unique().all()
    ids = [p.id for p in rows]
    counts = _comment_counts_for_products(db, ids)
    channels = _active_channels(db)
    pcl_map = _pcl_by_product(db, ids)
    items = [
        _product_to_read(p, comment_count=counts.get(p.id, 0), channels=channels, pcl_map=pcl_map) for p in rows
    ]
    return ProductListPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/scrape-preview", response_model=ScrapePreviewResponse)
def scrape_preview(
    body: ScrapePreviewRequest,
    ctx: OrganisationContextDep,
) -> ScrapePreviewResponse:
    ctx.require_organisation_id()
    url = str(body.url)
    try:
        if body.source == "shopify":
            raw = scrape_shopify(url)
        else:
            raw = scrape_ebay(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e!s}") from e
    return ScrapePreviewResponse(**raw)


@router.post("/bulk-listing-readiness", status_code=status.HTTP_200_OK)
def bulk_set_listing_readiness(
    body: BulkSetListingReadinessBody,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> dict[str, int]:
    """Set listing readiness (draft / ready_to_post) on many products. Clears marketplace flags when set to draft."""
    oid = ctx.require_organisation_id()
    n = 0
    for pid in body.product_ids:
        p = db.get(RyunovaProductMaster, pid)
        if not p or p.organisation_id != oid:
            continue
        p.listing_readiness = body.listing_readiness
        p.updated_by_user_id = user.id
        if body.listing_readiness == "draft":
            db.execute(
                update(RyunovaProductChannelListing)
                .where(RyunovaProductChannelListing.product_id == pid)
                .values(enabled=False)
            )
        n += 1
    db.commit()
    return {"updated": n}


@router.post("/bulk-marketplace-flags", status_code=status.HTTP_200_OK)
def bulk_set_marketplace_flags(
    body: BulkSetMarketplaceFlagsBody,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> dict[str, int]:
    """Enable or disable one marketplace for many products (only products in ready_to_post)."""
    oid = ctx.require_organisation_id()
    ch = db.get(RyunovaListingChannel, body.marketplace_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    now = datetime.now(timezone.utc)
    n = 0
    for pid in body.product_ids:
        p = db.get(RyunovaProductMaster, pid)
        if not p or p.organisation_id != oid:
            continue
        if p.listing_readiness != "ready_to_post":
            continue
        if body.enabled and not ch.active:
            raise HTTPException(status_code=400, detail=f"Marketplace {ch.code} is inactive")
        row = db.scalar(
            select(RyunovaProductChannelListing).where(
                RyunovaProductChannelListing.product_id == pid,
                RyunovaProductChannelListing.channel_id == body.marketplace_id,
            )
        )
        if row:
            row.enabled = body.enabled
            if body.enabled:
                row.posted_at = row.posted_at or now
                row.last_refreshed_at = now
            else:
                row.last_refreshed_at = None
        else:
            db.add(
                RyunovaProductChannelListing(
                    product_id=pid,
                    channel_id=body.marketplace_id,
                    enabled=body.enabled,
                    posted_at=now if body.enabled else None,
                    last_refreshed_at=now if body.enabled else None,
                )
            )
        p.updated_by_user_id = user.id
        n += 1
    db.commit()
    return {"updated": n}


@router.get("/{product_id}/comments", response_model=list[ProductCommentRead])
def list_product_comments(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
) -> list[ProductCommentRead]:
    p = db.scalar(select(RyunovaProductMaster).where(RyunovaProductMaster.id == product_id))
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)
    stmt = (
        select(RyunovaProductComment, RyunovaUser)
        .join(RyunovaUser, RyunovaProductComment.user_id == RyunovaUser.id)
        .where(RyunovaProductComment.product_id == product_id)
        .order_by(RyunovaProductComment.created_at.desc())
    )
    out: list[ProductCommentRead] = []
    for row in db.execute(stmt).all():
        c, u = row
        out.append(
            ProductCommentRead(
                id=c.id,
                product_id=c.product_id,
                body=c.body,
                created_at=c.created_at,
                author_display_name=_author_display_name(u),
            )
        )
    return out


@router.post(
    "/{product_id}/comments",
    response_model=ProductCommentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_product_comment(
    product_id: uuid.UUID,
    body: ProductCommentCreate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> ProductCommentRead:
    p = db.scalar(select(RyunovaProductMaster).where(RyunovaProductMaster.id == product_id))
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)
    c = RyunovaProductComment(
        product_id=product_id,
        organisation_id=p.organisation_id,
        user_id=user.id,
        body=body.body,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    u = db.get(RyunovaUser, user.id)
    return ProductCommentRead(
        id=c.id,
        product_id=c.product_id,
        body=c.body,
        created_at=c.created_at,
        author_display_name=_author_display_name(u),
    )


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
) -> ProductRead:
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(*_product_options())
        .where(RyunovaProductMaster.id == product_id)
    )
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)
    counts = _comment_counts_for_products(db, [product_id])
    channels = _active_channels(db)
    pcl_map = _pcl_by_product(db, [product_id])
    return _product_to_read(p, comment_count=counts.get(product_id, 0), channels=channels, pcl_map=pcl_map)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> ProductRead:
    oid = ctx.require_organisation_id()
    _ensure_brand_category_in_org(db, oid, body.brand_id, body.category_id)

    def _row(sku: str) -> RyunovaProductMaster:
        return RyunovaProductMaster(
            organisation_id=oid,
            sku=sku,
            title=body.title,
            description=body.description,
            condition=body.condition,
            brand_id=body.brand_id,
            model=body.model,
            category_id=body.category_id,
            colour=body.colour,
            length_cm=body.length_cm,
            width_cm=body.width_cm,
            depth_cm=body.depth_cm,
            base_price=body.base_price,
            currency_code=body.currency_code,
            compare_at_price=body.compare_at_price,
            quantity=body.quantity,
            attributes=body.attributes,
            status=body.status,
            listing_readiness=body.listing_readiness,
            active=body.active,
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
        )

    try:
        p = create_product_with_allocated_sku(db, organisation_id=oid, build_row=_row)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not allocate a unique product code; try again.",
        ) from None
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(*_product_options())
        .where(RyunovaProductMaster.id == p.id)
    )
    assert p
    counts = _comment_counts_for_products(db, [p.id])
    channels = _active_channels(db)
    pcl_map = _pcl_by_product(db, [p.id])
    return _product_to_read(p, comment_count=counts.get(p.id, 0), channels=channels, pcl_map=pcl_map)


@router.patch("/{product_id}/marketplace-listings", response_model=ProductRead)
def patch_product_marketplace_listings(
    product_id: uuid.UUID,
    body: ProductMarketplaceListingsPatch,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> ProductRead:
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(*_product_options())
        .where(RyunovaProductMaster.id == product_id)
    )
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)
    if p.listing_readiness != "ready_to_post" and any(it.enabled for it in body.items):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set listing readiness to Ready to post before enabling marketplace flags.",
        )
    now = datetime.now(timezone.utc)
    for it in body.items:
        ch = db.get(RyunovaListingChannel, it.marketplace_id)
        if not ch:
            raise HTTPException(status_code=400, detail=f"Unknown marketplace {it.marketplace_id}")
        if it.enabled and not ch.active:
            raise HTTPException(status_code=400, detail=f"Marketplace {ch.code} is inactive")
        row = db.scalar(
            select(RyunovaProductChannelListing).where(
                RyunovaProductChannelListing.product_id == product_id,
                RyunovaProductChannelListing.channel_id == it.marketplace_id,
            )
        )
        if row:
            row.enabled = it.enabled
            if it.mark_refreshed and it.enabled:
                row.last_refreshed_at = now
            elif it.enabled:
                row.posted_at = row.posted_at or now
                row.last_refreshed_at = now
            else:
                row.last_refreshed_at = None
        else:
            db.add(
                RyunovaProductChannelListing(
                    product_id=product_id,
                    channel_id=it.marketplace_id,
                    enabled=it.enabled,
                    posted_at=now if it.enabled else None,
                    last_refreshed_at=now if it.enabled else None,
                )
            )
    p.updated_by_user_id = user.id
    db.commit()
    db.refresh(p)
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(*_product_options())
        .where(RyunovaProductMaster.id == product_id)
    )
    assert p
    counts = _comment_counts_for_products(db, [product_id])
    channels = _active_channels(db)
    pcl_map = _pcl_by_product(db, [product_id])
    return _product_to_read(p, comment_count=counts.get(product_id, 0), channels=channels, pcl_map=pcl_map)


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> ProductRead:
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(*_product_options())
        .where(RyunovaProductMaster.id == product_id)
    )
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)
    data = body.model_dump(exclude_unset=True)
    new_brand = p.brand_id
    new_cat = p.category_id
    if "brand_id" in data:
        new_brand = data["brand_id"]
    if "category_id" in data:
        new_cat = data["category_id"]
    _ensure_brand_category_in_org(db, p.organisation_id, new_brand, new_cat)
    for k, v in data.items():
        setattr(p, k, v)
    if data.get("listing_readiness") == "draft":
        db.execute(
            update(RyunovaProductChannelListing)
            .where(RyunovaProductChannelListing.product_id == product_id)
            .values(enabled=False)
        )
    p.updated_by_user_id = user.id
    db.commit()
    db.refresh(p)
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(*_product_options())
        .where(RyunovaProductMaster.id == product_id)
    )
    assert p
    counts = _comment_counts_for_products(db, [product_id])
    channels = _active_channels(db)
    pcl_map = _pcl_by_product(db, [product_id])
    return _product_to_read(p, comment_count=counts.get(product_id, 0), channels=channels, pcl_map=pcl_map)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
) -> None:
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(selectinload(RyunovaProductMaster.images))
        .where(RyunovaProductMaster.id == product_id)
    )
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)
    for img in list(p.images):
        delete_media_key(img.s3_key)
    db.delete(p)
    db.commit()


def _parse_cover_form(raw: str | None) -> bool:
    if raw is None:
        return False
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _ensure_product_has_cover(db: Session, product_id: uuid.UUID) -> None:
    imgs = list(db.scalars(select(RyunovaProductImage).where(RyunovaProductImage.product_id == product_id)).all())
    if not imgs or any(i.is_cover for i in imgs):
        return
    pick = min(imgs, key=lambda x: (x.sort_order, x.created_at))
    pick.is_cover = True
    db.commit()


@router.post("/{product_id}/images", response_model=ProductImageRead, status_code=status.HTTP_201_CREATED)
async def upload_product_image(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
    file: UploadFile = File(...),
    is_cover: Annotated[str, Form()] = "false",
) -> ProductImageRead:
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(selectinload(RyunovaProductMaster.images))
        .where(RyunovaProductMaster.id == product_id)
    )
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)
    safe_name = file.filename or "upload"
    s3_key = f"orgs/{p.organisation_id}/products/{product_id}/{uuid.uuid4().hex}_{safe_name}"
    content_type = _normalize_content_type(file.content_type)
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    if content_type not in _ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Use images (JPEG, PNG, GIF, WebP) or video (MP4, WebM, QuickTime).",
        )
    media_type = _media_type_from_content_type(content_type)
    max_bytes = _max_bytes_for_media(media_type)
    chunks: list[bytes] = []
    size = 0
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large (max {max_bytes // (1024 * 1024)} MB for {media_type}s).",
                )
            chunks.append(chunk)
    except HTTPException:
        raise
    data = b"".join(chunks)
    try:
        write_media_bytes(s3_key, data, content_type)
    except Exception:
        delete_media_key(s3_key)
        raise

    want_cover = _parse_cover_form(is_cover)
    max_sort = max((i.sort_order for i in p.images), default=-1)
    p.updated_by_user_id = user.id

    if want_cover:
        for i in p.images:
            i.is_cover = False

    img = RyunovaProductImage(
        product_id=product_id,
        sort_order=max_sort + 1,
        media_type=media_type,
        is_cover=want_cover,
        s3_bucket=LOCAL_BUCKET,
        s3_key=s3_key,
        filename=safe_name,
        content_type=content_type,
        size_bytes=size,
    )
    db.add(img)
    db.commit()
    _ensure_product_has_cover(db, product_id)
    db.refresh(img)
    pr = ProductImageRead.model_validate(img)
    pr.url = _media_url(img.s3_key)
    return pr


@router.post(
    "/{product_id}/images/from-url",
    response_model=ProductImageRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_product_image_from_url(
    product_id: uuid.UUID,
    body: ProductImageFromUrlCreate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> ProductImageRead:
    """Download an image from a public URL, verify it is an image, store via media_storage."""
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(selectinload(RyunovaProductMaster.images))
        .where(RyunovaProductMaster.id == product_id)
    )
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)

    raw_url = body.url.strip()
    try:
        image_bytes, _final_url, content_type = await download_image_bytes(raw_url, _MAX_IMAGE_BYTES)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not download URL: {e!s}",
        ) from e

    safe_name = build_stored_filename(p.title, content_type)
    s3_key = f"orgs/{p.organisation_id}/products/{product_id}/{uuid.uuid4().hex}_{safe_name}"
    try:
        write_media_bytes(s3_key, image_bytes, content_type)
    except Exception:
        delete_media_key(s3_key)
        raise
    size = len(image_bytes)

    want_cover = body.is_cover
    max_sort = max((i.sort_order for i in p.images), default=-1)
    p.updated_by_user_id = user.id

    if want_cover:
        for i in p.images:
            i.is_cover = False

    img = RyunovaProductImage(
        product_id=product_id,
        sort_order=max_sort + 1,
        media_type="image",
        is_cover=want_cover,
        s3_bucket=LOCAL_BUCKET,
        s3_key=s3_key,
        filename=safe_name,
        content_type=content_type,
        size_bytes=size,
    )
    db.add(img)
    db.commit()
    _ensure_product_has_cover(db, product_id)
    db.refresh(img)
    pr = ProductImageRead.model_validate(img)
    pr.url = _media_url(img.s3_key)
    return pr


@router.patch("/{product_id}/images/{image_id}", response_model=ProductImageRead)
def patch_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    body: ProductImageUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    ctx: OrganisationContextDep,
) -> ProductImageRead:
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(selectinload(RyunovaProductMaster.images))
        .where(RyunovaProductMaster.id == product_id)
    )
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)
    img = next((i for i in p.images if i.id == image_id), None)
    if not img:
        raise HTTPException(status_code=404, detail="Media not found")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    if data.get("is_cover") is True:
        for i in p.images:
            i.is_cover = i.id == image_id
        p.updated_by_user_id = user.id
    elif data.get("is_cover") is False:
        if img.is_cover:
            img.is_cover = False
            others = [i for i in p.images if i.id != image_id]
            if others:
                pick = min(others, key=lambda x: (x.sort_order, x.created_at))
                pick.is_cover = True
            else:
                img.is_cover = True
            p.updated_by_user_id = user.id
    db.commit()
    db.refresh(img)
    pr = ProductImageRead.model_validate(img)
    pr.url = _media_url(img.s3_key)
    return pr
