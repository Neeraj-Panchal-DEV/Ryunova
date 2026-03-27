from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.organisation import RyunovaEmailVerificationToken, RyunovaOrganisation, RyunovaUserOrganisation
from app.models.user import RyunovaUser
from app.org_access import user_has_org_membership
from app.profile_patch import merge_social_handles
from app.public_codes import allocate_public_code
from app.routers.auth import _user_to_read
from app.schemas.user import UserRead
from app.schemas.admin_user import (
    AdminUserPatchBody,
    AdminUserProfilePatch,
    InviteUserBody,
    InviteUserResponse,
    OrganisationMemberUser,
    ResendInviteBody,
)
from app.security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_platform_user(user: RyunovaUser) -> None:
    if not user.is_platform_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform user access required")


def _parse_org_header(raw: str | None) -> uuid.UUID | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def _can_view_org_member_list(actor: RyunovaUser, organisation_id: uuid.UUID, db: Session) -> bool:
    if actor.is_platform_user:
        return True
    if actor.user_admin_access and user_has_org_membership(db, actor, organisation_id):
        return True
    return False


def _can_manage_user_profile(
    actor: RyunovaUser, target: RyunovaUser, db: Session, org_id: uuid.UUID | None
) -> bool:
    if actor.id == target.id:
        return True
    if actor.is_platform_user:
        return True
    if actor.user_admin_access and org_id is not None:
        return user_has_org_membership(db, actor, org_id) and user_has_org_membership(db, target, org_id)
    return False


@router.get("/organisations/{organisation_id}/users", response_model=list[OrganisationMemberUser])
def list_organisation_users(
    organisation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
) -> list[OrganisationMemberUser]:
    """Platform users or organisation user-admins (for their org): members linked to the organisation."""
    org = db.get(RyunovaOrganisation, organisation_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    if not _can_view_org_member_list(actor, organisation_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to list members for this organisation")
    stmt = (
        select(RyunovaUser)
        .join(RyunovaUserOrganisation, RyunovaUserOrganisation.user_id == RyunovaUser.id)
        .where(RyunovaUserOrganisation.organisation_id == organisation_id)
        .order_by(RyunovaUser.email)
    )
    users = list(db.scalars(stmt).all())
    return [
        OrganisationMemberUser(
            id=u.id,
            public_code=u.public_code,
            email=u.email,
            display_name=u.display_name,
            is_platform_user=u.is_platform_user,
            user_admin_access=u.user_admin_access,
            email_verified=bool(u.email_verified_at),
        )
        for u in users
    ]


def _require_invite_permission(actor: RyunovaUser, organisation_id: uuid.UUID, db: Session) -> None:
    if actor.is_platform_user:
        return
    if actor.user_admin_access and user_has_org_membership(db, actor, organisation_id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Platform user or organisation user-admin access required for this organisation.",
    )


@router.post("/users/invite", response_model=InviteUserResponse)
def invite_user(
    body: InviteUserBody,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
) -> InviteUserResponse:
    _require_invite_permission(actor, body.organisation_id, db)
    org = db.get(RyunovaOrganisation, body.organisation_id)
    if not org:
        raise HTTPException(status_code=400, detail="organisation_id not found")
    email = body.email.lower().strip()
    existing = db.scalar(select(RyunovaUser).where(RyunovaUser.email == email))
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    temp_pw = secrets.token_urlsafe(14)
    verify_plain = secrets.token_urlsafe(32)
    verify_hash = hashlib.sha256(verify_plain.encode("utf-8")).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(days=7)

    u = RyunovaUser(
        public_code=allocate_public_code(db),
        email=email,
        display_name=(body.display_name or "").strip() or None,
        password_hash=hash_password(temp_pw),
        email_verified_at=None,
        is_platform_user=False,
        user_admin_access=False,
        is_active=True,
    )
    db.add(u)
    db.flush()
    db.add(RyunovaUserOrganisation(user_id=u.id, organisation_id=body.organisation_id))
    db.add(
        RyunovaEmailVerificationToken(
            user_id=u.id,
            token_hash=verify_hash,
            expires_at=expires,
        )
    )
    db.commit()
    db.refresh(u)
    return InviteUserResponse(
        user_id=u.id,
        email=u.email,
        temporary_password=temp_pw,
        verification_token=verify_plain,
    )


def _user_member_of_org(db: Session, user_id: uuid.UUID, organisation_id: uuid.UUID) -> bool:
    row = db.scalar(
        select(RyunovaUserOrganisation.user_id).where(
            RyunovaUserOrganisation.user_id == user_id,
            RyunovaUserOrganisation.organisation_id == organisation_id,
        )
    )
    return row is not None


@router.post("/users/{user_id}/resend-invite", response_model=InviteUserResponse)
def resend_invite(
    user_id: uuid.UUID,
    body: ResendInviteBody,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
) -> InviteUserResponse:
    """New verification link and temporary password for a member who has not verified yet."""
    _require_invite_permission(actor, body.organisation_id, db)
    org = db.get(RyunovaOrganisation, body.organisation_id)
    if not org:
        raise HTTPException(status_code=400, detail="organisation_id not found")
    target = db.get(RyunovaUser, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not _user_member_of_org(db, target.id, body.organisation_id):
        raise HTTPException(status_code=400, detail="User is not a member of this organisation")
    if target.email_verified_at is not None:
        raise HTTPException(status_code=400, detail="This user has already verified their email")
    if target.is_platform_user:
        raise HTTPException(status_code=400, detail="Cannot resend invite for platform users this way")

    temp_pw = secrets.token_urlsafe(14)
    verify_plain = secrets.token_urlsafe(32)
    verify_hash = hashlib.sha256(verify_plain.encode("utf-8")).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(days=7)

    db.execute(
        delete(RyunovaEmailVerificationToken).where(
            RyunovaEmailVerificationToken.user_id == target.id,
            RyunovaEmailVerificationToken.used_at.is_(None),
        )
    )
    target.password_hash = hash_password(temp_pw)
    db.add(
        RyunovaEmailVerificationToken(
            user_id=target.id,
            token_hash=verify_hash,
            expires_at=expires,
        )
    )
    db.commit()
    db.refresh(target)
    return InviteUserResponse(
        user_id=target.id,
        email=target.email,
        temporary_password=temp_pw,
        verification_token=verify_plain,
    )


@router.patch("/users/{user_id}", response_model=dict)
def admin_patch_user(
    user_id: uuid.UUID,
    body: AdminUserPatchBody,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
) -> dict:
    _require_platform_user(actor)
    target = db.get(RyunovaUser, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if body.is_platform_user is None and body.user_admin_access is None:
        return {
            "ok": True,
            "id": str(target.id),
            "is_platform_user": target.is_platform_user,
            "user_admin_access": target.user_admin_access,
            "is_system_user": target.is_platform_user,  # same flag; alias for older clients
        }
    if body.is_platform_user is False and target.is_platform_user:
        cnt = int(
            db.scalar(select(func.count()).select_from(RyunovaUser).where(RyunovaUser.is_platform_user.is_(True))) or 0
        )
        if cnt <= 1:
            raise HTTPException(
                status_code=400,
                detail="At least one platform user must remain.",
            )
    if body.is_platform_user is not None:
        target.is_platform_user = bool(body.is_platform_user)
    if body.user_admin_access is not None:
        target.user_admin_access = bool(body.user_admin_access)
    db.commit()
    return {
        "ok": True,
        "id": str(target.id),
        "is_platform_user": target.is_platform_user,
        "user_admin_access": target.user_admin_access,
        "is_system_user": target.is_platform_user,  # same flag; alias for older clients
    }


@router.get("/users/{user_id}/profile", response_model=UserRead)
def get_admin_user_profile(
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
    x_organisation_id: Annotated[str | None, Header(alias="X-Organisation-Id")] = None,
) -> UserRead:
    target = db.get(RyunovaUser, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    org_id = _parse_org_header(x_organisation_id)
    if not _can_manage_user_profile(actor, target, db, org_id):
        raise HTTPException(status_code=403, detail="Not allowed to view this profile")
    return _user_to_read(target)


@router.patch("/users/{user_id}/profile", response_model=UserRead)
def patch_admin_user_profile(
    user_id: uuid.UUID,
    body: AdminUserProfilePatch,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
    x_organisation_id: Annotated[str | None, Header(alias="X-Organisation-Id")] = None,
) -> UserRead:
    target = db.get(RyunovaUser, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    org_id = _parse_org_header(x_organisation_id)
    if not _can_manage_user_profile(actor, target, db, org_id):
        raise HTTPException(status_code=403, detail="Not allowed to update this profile")
    data = body.model_dump(exclude_unset=True)
    if actor.id == target.id and data.get("email"):
        raise HTTPException(
            status_code=400,
            detail="Use the profile email change request to change your own email.",
        )
    if "email" in data and data["email"] is not None:
        new_em = str(data["email"]).lower().strip()
        taken = db.scalar(select(RyunovaUser.id).where(RyunovaUser.email == new_em, RyunovaUser.id != target.id))
        if taken:
            raise HTTPException(status_code=400, detail="That email is already registered")
        target.email = new_em
        target.pending_email = None
        del data["email"]
    if "social_handles" in data:
        target.social_handles = merge_social_handles(target.social_handles, data.pop("social_handles"))
    for key in ("display_name", "first_name", "last_name", "date_of_birth", "phone_e164", "job_title"):
        if key in data:
            setattr(target, key, data[key])
    db.commit()
    db.refresh(target)
    return _user_to_read(target)
