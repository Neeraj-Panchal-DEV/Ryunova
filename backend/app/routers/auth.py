from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.mail_outbound import send_email_change_verification_email, send_login_code_email
from app.profile_patch import merge_social_handles
from app.media_storage import delete_key as delete_media_key, write_bytes as write_media_bytes
from app.media_urls import public_media_url
from app.dependencies import CurrentUser
from app.models.login_code import RyunovaLoginCode
from app.models.organisation import RyunovaEmailVerificationToken, RyunovaOrganisation, RyunovaUserOrganisation
from app.models.user import RyunovaUser
from app.schemas.auth import (
    LoginOtpRequestBody,
    LoginOtpRequestResponse,
    LoginOtpVerifyBody,
    LoginRequest,
    LoginResponse,
    OrganisationBrief,
    VerifyEmailRequest,
)
from app.schemas.user import EmailChangeRequestBody, PasswordChangeBody, UserMeUpdate, UserRead
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)

_AVATAR_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
_MAX_AVATAR_BYTES = 5 * 1024 * 1024


def _normalize_content_type(raw: str | None) -> str:
    return (raw or "application/octet-stream").split(";")[0].strip().lower()


def _avatar_extension(content_type: str) -> str:
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(content_type, ".bin")


def _organisation_brief(o: RyunovaOrganisation) -> OrganisationBrief:
    return OrganisationBrief(
        id=o.id,
        name=o.name,
        slug=o.slug,
        description=o.description,
        logo_url=public_media_url(o.logo_s3_key),
    )


def _login_response_for_user(db: Session, user: RyunovaUser) -> LoginResponse:
    token = create_access_token(subject=str(user.id), extra_claims={"email": user.email})
    if user.is_platform_user:
        org_rows = list(db.scalars(select(RyunovaOrganisation).order_by(RyunovaOrganisation.name)).all())
    else:
        org_rows = list(
            db.scalars(
                select(RyunovaOrganisation)
                .join(RyunovaUserOrganisation, RyunovaUserOrganisation.organisation_id == RyunovaOrganisation.id)
                .where(RyunovaUserOrganisation.user_id == user.id)
                .order_by(RyunovaOrganisation.name)
            ).all()
        )
    orgs = [_organisation_brief(o) for o in org_rows]
    return LoginResponse(
        access_token=token,
        organisations=orgs,
        is_platform_user=user.is_platform_user,
        user_admin_access=user.user_admin_access,
        is_system_user=user.is_platform_user,
        email_verified=True,
    )


def _user_to_read(user: RyunovaUser) -> UserRead:
    roles = [r.role for r in user.roles]
    avatar_url = public_media_url(user.avatar_s3_key) if user.avatar_s3_key else None
    sh = user.social_handles if isinstance(user.social_handles, dict) else {}
    return UserRead(
        id=user.id,
        public_code=user.public_code,
        email=user.email,
        display_name=user.display_name,
        first_name=user.first_name,
        last_name=user.last_name,
        date_of_birth=user.date_of_birth,
        phone_e164=user.phone_e164,
        job_title=user.job_title,
        social_handles=sh,
        pending_email=user.pending_email,
        is_active=user.is_active,
        roles=roles,
        avatar_url=avatar_url,
        has_password=bool(user.password_hash),
        is_platform_user=user.is_platform_user,
        user_admin_access=user.user_admin_access,
        is_system_user=user.is_platform_user,  # same flag; alias for older clients
        email_verified=bool(user.email_verified_at),
    )


def _delete_avatar_file(key: str | None) -> None:
    delete_media_key(key)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> LoginResponse:
    user = db.scalar(select(RyunovaUser).where(RyunovaUser.email == body.email.lower().strip()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    if not user.email_verified_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email using the link we sent you before signing in.",
        )
    return _login_response_for_user(db, user)


@router.post("/login-otp/request", response_model=LoginOtpRequestResponse)
def request_login_otp(body: LoginOtpRequestBody, db: Annotated[Session, Depends(get_db)]) -> LoginOtpRequestResponse:
    """Send a 6-digit code to the email if the account exists and can sign in with password."""
    email = body.email.lower().strip()
    user = db.scalar(select(RyunovaUser).where(RyunovaUser.email == email))
    if not user or not user.is_active or not user.email_verified_at or not user.password_hash:
        return LoginOtpRequestResponse()

    last = db.scalars(
        select(RyunovaLoginCode)
        .where(RyunovaLoginCode.user_id == user.id)
        .order_by(RyunovaLoginCode.created_at.desc())
        .limit(1)
    ).first()
    if last is not None and last.created_at is not None:
        created = last.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - created).total_seconds() < 60:
            return LoginOtpRequestResponse()

    db.execute(
        delete(RyunovaLoginCode).where(
            RyunovaLoginCode.user_id == user.id,
            RyunovaLoginCode.used_at.is_(None),
        )
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    row = RyunovaLoginCode(user_id=user.id, code_hash=code_hash, expires_at=expires)
    db.add(row)
    try:
        send_login_code_email(to_email=user.email, code=code)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("login-otp: could not send email for %s", email)
    return LoginOtpRequestResponse()


@router.post("/login-otp/verify", response_model=LoginResponse)
def verify_login_otp(body: LoginOtpVerifyBody, db: Annotated[Session, Depends(get_db)]) -> LoginResponse:
    email = body.email.lower().strip()
    user = db.scalar(select(RyunovaUser).where(RyunovaUser.email == email))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code or email")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    if not user.email_verified_at or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code or email")

    th = hashlib.sha256(body.code.encode("utf-8")).hexdigest()
    row = db.scalar(
        select(RyunovaLoginCode).where(
            RyunovaLoginCode.user_id == user.id,
            RyunovaLoginCode.code_hash == th,
            RyunovaLoginCode.used_at.is_(None),
        )
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code or email")
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code expired")

    row.used_at = datetime.now(timezone.utc)
    db.commit()
    return _login_response_for_user(db, user)


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(body: VerifyEmailRequest, db: Annotated[Session, Depends(get_db)]) -> None:
    th = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    row = db.scalar(select(RyunovaEmailVerificationToken).where(RyunovaEmailVerificationToken.token_hash == th))
    if not row or row.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already used verification link")
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification link has expired")
    u = db.get(RyunovaUser, row.user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    kind = (getattr(row, "token_kind", None) or "signup").lower()
    now = datetime.now(timezone.utc)
    if kind == "email_change":
        new_em = (row.new_email or "").lower().strip()
        if not new_em:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email change token")
        taken = db.scalar(select(RyunovaUser.id).where(RyunovaUser.email == new_em, RyunovaUser.id != u.id))
        if taken:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That email is already in use")
        u.email = new_em
        u.pending_email = None
        row.used_at = now
        db.commit()
        return
    u.email_verified_at = now
    row.used_at = now
    db.commit()


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return _user_to_read(user)


@router.patch("/me", response_model=UserRead)
def update_me(
    body: UserMeUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> UserRead:
    data = body.model_dump(exclude_unset=True)
    if "social_handles" in data:
        user.social_handles = merge_social_handles(user.social_handles, data.pop("social_handles"))
    for key, val in data.items():
        setattr(user, key, val)
    db.commit()
    db.refresh(user)
    return _user_to_read(user)


@router.post("/me/request-email-change", status_code=status.HTTP_204_NO_CONTENT)
def request_email_change(
    body: EmailChangeRequestBody,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> None:
    new_em = body.new_email.lower().strip()
    if new_em == user.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That is already your email address")
    taken = db.scalar(select(RyunovaUser.id).where(RyunovaUser.email == new_em))
    if taken:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That email is already registered")
    db.execute(
        delete(RyunovaEmailVerificationToken).where(
            RyunovaEmailVerificationToken.user_id == user.id,
            RyunovaEmailVerificationToken.token_kind == "email_change",
            RyunovaEmailVerificationToken.used_at.is_(None),
        )
    )
    verify_plain = secrets.token_urlsafe(32)
    verify_hash = hashlib.sha256(verify_plain.encode("utf-8")).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(hours=48)
    db.add(
        RyunovaEmailVerificationToken(
            user_id=user.id,
            token_hash=verify_hash,
            expires_at=expires,
            token_kind="email_change",
            new_email=new_em,
        )
    )
    user.pending_email = new_em
    db.commit()
    settings = get_settings()
    verify_path = settings.site_url.rstrip("/") + "/accounts/verify-email/?token=" + verify_plain
    try:
        send_email_change_verification_email(to_email=new_em, verify_url=verify_path)
    except Exception:
        logger.exception("email change: could not send verification to %s", new_em)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send verification email. Try again later or contact support.",
        )


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: PasswordChangeBody,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> None:
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has no password set; sign-in may use another method.",
        )
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()


@router.post("/me/avatar", response_model=UserRead)
async def upload_avatar(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    file: UploadFile = File(...),
) -> UserRead:
    content_type = _normalize_content_type(file.content_type)
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    if content_type not in _AVATAR_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Use JPEG, PNG, GIF, or WebP.",
        )
    ext = _avatar_extension(content_type)
    s3_key = f"users/{user.id}/avatars/{uuid.uuid4().hex}_avatar{ext}"
    chunks: list[bytes] = []
    size = 0
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > _MAX_AVATAR_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Avatar too large (max {_MAX_AVATAR_BYTES // (1024 * 1024)} MB).",
                )
            chunks.append(chunk)
    except HTTPException:
        raise
    data = b"".join(chunks)
    try:
        write_media_bytes(s3_key, data, content_type)
    except Exception:
        delete_media_key(s3_key)
        raise

    old_key = user.avatar_s3_key
    user.avatar_s3_key = s3_key
    db.commit()
    _delete_avatar_file(old_key)
    db.refresh(user)
    return _user_to_read(user)
