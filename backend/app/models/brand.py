from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RyunovaBrand(Base):
    __tablename__ = "ryunova_brands"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_ryunova_brand_org_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ryunova_organisations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int | None] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ryunova_users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ryunova_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    created_by_user: Mapped["RyunovaUser | None"] = relationship(
        "RyunovaUser",
        foreign_keys=[created_by_user_id],
    )
    updated_by_user: Mapped["RyunovaUser | None"] = relationship(
        "RyunovaUser",
        foreign_keys=[updated_by_user_id],
    )

    products: Mapped[list["RyunovaProductMaster"]] = relationship(
        "RyunovaProductMaster",
        back_populates="brand_rel",
    )
