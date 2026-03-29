from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.dependencies import CurrentUser
from app.models.brand import RyunovaBrand
from app.org_access import OrganisationContextDep, assert_product_in_context
from app.models.category import RyunovaCategory
from app.models.product import ProductCondition, RyunovaProductImage, RyunovaProductMaster
from app.product_sku import create_product_with_allocated_sku
from app.schemas.product import (
    ProductCreate,
    ProductImageFromUrlCreate,
    ProductImageRead,
    ProductImageUpdate,
    ProductListPage,
    ProductRead,
    ProductUpdate,
)
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


def _product_to_read(p: RyunovaProductMaster) -> ProductRead:
    images_out: list[ProductImageRead] = []
    for img in _ordered_product_images(p):
        pr = ProductImageRead.model_validate(img)
        pr.url = _media_url(img.s3_key)
        images_out.append(pr)
    brand_name = p.brand_rel.name if p.brand_rel else None
    data = ProductRead.model_validate(p).model_copy(
        update={
            "images": images_out,
            "brand_name": brand_name,
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
    items = [_product_to_read(p) for p in rows]
    return ProductListPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
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
    return _product_to_read(p)


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
            compare_at_price=body.compare_at_price,
            quantity=body.quantity,
            attributes=body.attributes,
            status=body.status,
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
    return _product_to_read(p)


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
    p.updated_by_user_id = user.id
    db.commit()
    db.refresh(p)
    p = db.scalar(
        select(RyunovaProductMaster)
        .options(*_product_options())
        .where(RyunovaProductMaster.id == product_id)
    )
    assert p
    return _product_to_read(p)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    ctx: OrganisationContextDep,
) -> None:
    p = db.get(RyunovaProductMaster, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    assert_product_in_context(db, ctx, p.organisation_id)
    settings = get_settings()
    upload_root = Path(settings.upload_dir)
    for img in list(p.images):
        path = upload_root / img.s3_key
        if path.is_file():
            path.unlink()
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
    settings = get_settings()
    upload_root = Path(settings.upload_dir)
    safe_name = file.filename or "upload"
    s3_key = f"products/{product_id}/{uuid.uuid4().hex}_{safe_name}"
    dest_dir = upload_root / Path(s3_key).parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_root / s3_key
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
    size = 0
    try:
        with dest_path.open("wb") as out:
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
                out.write(chunk)
    except HTTPException:
        if dest_path.is_file():
            dest_path.unlink(missing_ok=True)
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
    """Download an image from a public URL, verify it is an image, store under upload_dir."""
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

    settings = get_settings()
    upload_root = Path(settings.upload_dir)
    safe_name = build_stored_filename(p.title, content_type)
    s3_key = f"products/{product_id}/{uuid.uuid4().hex}_{safe_name}"
    dest_dir = upload_root / Path(s3_key).parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_root / s3_key
    dest_path.write_bytes(image_bytes)
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
