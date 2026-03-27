import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrganisationBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    organisations: list[OrganisationBrief]
    is_platform_user: bool
    user_admin_access: bool
    is_system_user: bool  # same as is_platform_user; alias for older clients — use is_platform_user
    email_verified: bool


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, max_length=512)


class LoginOtpRequestBody(BaseModel):
    email: EmailStr


class LoginOtpRequestResponse(BaseModel):
    ok: bool = True


class LoginOtpVerifyBody(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class TokenPayload(BaseModel):
    sub: str | None = None
