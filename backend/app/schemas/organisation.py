import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganisationRead(BaseModel):
    """Full organisation record for settings UI."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None
    currency_code: str = "AUD"
    website_url: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    address_locality: str | None = None
    address_region: str | None = None
    address_postal_code: str | None = None
    address_country: str | None = None
    address_place_id: str | None = None
    tax_identifier: str | None = None
    key_contact_name: str | None = None
    key_contact_email: str | None = None
    key_contact_phone: str | None = None


class OrganisationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    website_url: str | None = Field(None, max_length=512)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    address_locality: str | None = Field(None, max_length=128)
    address_region: str | None = Field(None, max_length=128)
    address_postal_code: str | None = Field(None, max_length=32)
    address_country: str | None = Field(None, min_length=2, max_length=2)
    address_place_id: str | None = Field(None, max_length=256)
    tax_identifier: str | None = Field(None, max_length=64)
    key_contact_name: str | None = Field(None, max_length=255)
    key_contact_email: str | None = Field(None, max_length=255)
    key_contact_phone: str | None = Field(None, max_length=64)

    @field_validator(
        "currency_code",
        "address_country",
        mode="before",
    )
    @classmethod
    def _upper_trim(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        return s.upper()
