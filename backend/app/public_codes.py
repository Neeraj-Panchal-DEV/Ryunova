"""Allocate immutable public_code values for ryunova_users (10 alphanumeric characters)."""
#backend/app/public_codes.py
from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import RyunovaUser

# Uppercase letters + digits (36 symbols); 36^10 possibilities per attempt.
_ALPHANUM = string.ascii_uppercase + string.digits
_PUBLIC_CODE_LEN = 10


def allocate_public_code(db: Session) -> str:
    for _ in range(256):
        code = "".join(secrets.choice(_ALPHANUM) for _ in range(_PUBLIC_CODE_LEN))
        taken = db.scalar(select(RyunovaUser.id).where(RyunovaUser.public_code == code))
        if not taken:
            return code
    raise RuntimeError("Could not allocate a unique public_code")
