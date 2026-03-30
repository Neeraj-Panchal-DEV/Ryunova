from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.brand import RyunovaBrand
    from app.models.listing_channel import RyunovaProductChannelListing
    from app.models.user import RyunovaUser


class ProductCondition(str, enum.Enum):
    new = "new"
    used = "used"
    refurbished = "refurbished"


class RyunovaProductMaster(Base):
    __tablename__ = "ryunova_product_master"
    __table_args__ = (UniqueConstraint("organisation_id", "sku", name="uq_ryunova_product_org_sku"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ryunova_organisations.id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    condition: Mapped[ProductCondition] = mapped_column(
        "condition",
        SAEnum(
            ProductCondition,
            name="ryunova_product_condition",
            native_enum=True,
            create_constraint=False,
            schema="ryunova",
        ),
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ryunova_brands.id", ondelete="SET NULL"))
    model: Mapped[str | None] = mapped_column(String(255))
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ryunova_categories.id", ondelete="SET NULL"))
    colour: Mapped[str | None] = mapped_column(String(255))
    length_cm: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    width_cm: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    depth_cm: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD", server_default="AUD")
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    listing_readiness: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )  # draft | ready_to_post (channel flags only when ready_to_post)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ryunova_users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ryunova_users.id", ondelete="SET NULL"), nullable=True
    )

    brand_rel: Mapped[RyunovaBrand | None] = relationship(back_populates="products")
    created_by_user: Mapped["RyunovaUser | None"] = relationship(
        "RyunovaUser",
        foreign_keys=[created_by_user_id],
    )
    updated_by_user: Mapped["RyunovaUser | None"] = relationship(
        "RyunovaUser",
        foreign_keys=[updated_by_user_id],
    )
    images: Mapped[list["RyunovaProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="RyunovaProductImage.sort_order",
    )
    channel_listings: Mapped[list["RyunovaProductChannelListing"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )


class RyunovaProductImage(Base):
    __tablename__ = "ryunova_product_image"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ryunova_product_master.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False, default="image")
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(128))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped["RyunovaProductMaster"] = relationship(back_populates="images")
