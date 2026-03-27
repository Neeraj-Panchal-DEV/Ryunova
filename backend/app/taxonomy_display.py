"""Shared helpers for category/brand/product API responses (audit labels, parent name)."""

from app.models.brand import RyunovaBrand
from app.models.category import RyunovaCategory
from app.models.product import RyunovaProductMaster
from app.models.user import RyunovaUser
from app.schemas.brand import BrandRead
from app.schemas.category import CategoryRead


def user_audit_label(user: RyunovaUser | None) -> str | None:
    """Human-readable audit label; does not expose email (use display_name only)."""
    if user is None:
        return None
    dn = (user.display_name or "").strip()
    return dn or None


def enrich_category_read(cat: RyunovaCategory) -> CategoryRead:
    base = CategoryRead.model_validate(cat)
    return base.model_copy(
        update={
            "created_by_label": user_audit_label(cat.created_by_user),
            "updated_by_label": user_audit_label(cat.updated_by_user),
            "parent_name": cat.parent_category.name if cat.parent_category else None,
        }
    )


def enrich_brand_read(b: RyunovaBrand) -> BrandRead:
    base = BrandRead.model_validate(b)
    return base.model_copy(
        update={
            "created_by_label": user_audit_label(b.created_by_user),
            "updated_by_label": user_audit_label(b.updated_by_user),
        }
    )


def product_audit_labels(p: RyunovaProductMaster) -> dict[str, str | None]:
    """For ProductRead.model_copy(update=...)."""
    return {
        "created_by_label": user_audit_label(p.created_by_user),
        "updated_by_label": user_audit_label(p.updated_by_user),
    }
