from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RyunovaOrganisation(Base):
    __tablename__ = "ryunova_organisations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="AUD", server_default="AUD")
    website_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_locality: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address_region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address_postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    address_place_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tax_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    key_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    key_contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    key_contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user_links: Mapped[list["RyunovaUserOrganisation"]] = relationship(
        "RyunovaUserOrganisation", back_populates="organisation"
    )


class RyunovaUserOrganisation(Base):
    __tablename__ = "ryunova_user_organisations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ryunova_users.id", ondelete="CASCADE"), primary_key=True
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ryunova_organisations.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organisation: Mapped["RyunovaOrganisation"] = relationship("RyunovaOrganisation", back_populates="user_links")
    user: Mapped["RyunovaUser"] = relationship("RyunovaUser", back_populates="organisation_links")


class RyunovaEmailVerificationToken(Base):
    __tablename__ = "ryunova_email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ryunova_users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    token_kind: Mapped[str] = mapped_column(String(32), nullable=False, server_default="signup")
    new_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
