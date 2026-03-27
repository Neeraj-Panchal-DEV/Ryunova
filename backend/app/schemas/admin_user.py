import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ResendInviteBody(BaseModel):
    organisation_id: uuid.UUID


class InviteUserBody(BaseModel):
    email: EmailStr
    organisation_id: uuid.UUID
    display_name: str | None = Field(None, max_length=255)


class InviteUserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    temporary_password: str
    verification_token: str


class AdminUserPatchBody(BaseModel):
    is_platform_user: bool | None = None
    user_admin_access: bool | None = None


def _blank_str_none(v: object) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


class AdminUserProfilePatch(BaseModel):
    """Platform or org user-admin may update another member in a shared organisation."""

    display_name: str | None = Field(None, max_length=255)
    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    date_of_birth: date | None = None
    phone_e164: str | None = Field(None, max_length=24)
    job_title: str | None = Field(None, max_length=255)
    social_handles: dict[str, str] | None = None
    email: EmailStr | None = None

    @field_validator("display_name", "first_name", "last_name", "phone_e164", "job_title", mode="before")
    @classmethod
    def _blanks(cls, v: object) -> str | None:
        return _blank_str_none(v)


class OrganisationMemberUser(BaseModel):
    """User row for admin list of members in one organisation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    public_code: str
    email: str
    display_name: str | None = None
    is_platform_user: bool = False
    user_admin_access: bool = False
    email_verified: bool = False
