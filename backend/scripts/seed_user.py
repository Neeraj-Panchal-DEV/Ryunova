#!/usr/bin/env python3
"""Create initial admin user. Run from backend/: python scripts/seed_user.py"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import RyunovaUser, RyunovaUserRole
from app.public_codes import allocate_public_code
from app.security import hash_password


def main() -> None:
    # Use a normal domain; .local is rejected by EmailStr / email-validator (reserved for mDNS).
    email = (sys.argv[1] if len(sys.argv) > 1 else "admin@example.com").lower().strip()
    password = sys.argv[2] if len(sys.argv) > 2 else "admin123"
    display = sys.argv[3] if len(sys.argv) > 3 else "Admin"

    db: Session = SessionLocal()
    try:
        existing = db.scalar(select(RyunovaUser).where(RyunovaUser.email == email))
        if existing:
            print(f"User already exists: {email}")
            return
        user = RyunovaUser(
            id=uuid.uuid4(),
            public_code=allocate_public_code(db),
            email=email,
            display_name=display,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(RyunovaUserRole(user_id=user.id, role="admin"))
        db.commit()
        print(f"Created user {email} with role admin (password: {password})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
