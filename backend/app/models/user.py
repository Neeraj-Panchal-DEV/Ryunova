from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.organisation import RyunovaUserOrganisation


class RyunovaUser(Base):
    __tablename__ = "ryunova_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(24), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    social_handles: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    pending_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    avatar_s3_key: Mapped[str | None] = mapped_column(String(512))
    is_platform_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    user_admin_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    roles: Mapped[list["RyunovaUserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    organisation_links: Mapped[list["RyunovaUserOrganisation"]] = relationship(
        "RyunovaUserOrganisation",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class RyunovaUserRole(Base):
    __tablename__ = "ryunova_user_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ryunova_users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["RyunovaUser"] = relationship(back_populates="roles")
