import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _blank_str_none(v: object) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    public_code: str
    email: EmailStr
    display_name: str | None
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    phone_e164: str | None = None
    job_title: str | None = None
    social_handles: dict[str, Any] = Field(default_factory=dict)
    pending_email: str | None = None
    is_active: bool
    roles: list[str] = []
    avatar_url: str | None = None
    has_password: bool = False
    is_platform_user: bool = False
    user_admin_access: bool = False
    is_system_user: bool = False
    email_verified: bool = False


class UserMeUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    date_of_birth: date | None = None
    phone_e164: str | None = Field(None, max_length=24)
    job_title: str | None = Field(None, max_length=255)
    social_handles: dict[str, str] | None = None

    @field_validator("display_name", "first_name", "last_name", "phone_e164", "job_title", mode="before")
    @classmethod
    def _blanks(cls, v: object) -> str | None:
        return _blank_str_none(v)


class EmailChangeRequestBody(BaseModel):
    new_email: EmailStr


class PasswordChangeBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)
