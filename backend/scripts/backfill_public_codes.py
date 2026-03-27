#!/usr/bin/env python3
"""Reassign every user's public_code to a new 10-character A–Z0–9 value. Run from backend/: python scripts/backfill_public_codes.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import RyunovaUser
from app.public_codes import allocate_public_code


def main() -> None:
    db: Session = SessionLocal()
    try:
        users = list(db.scalars(select(RyunovaUser)).all())
        for u in users:
            u.public_code = allocate_public_code(db)
            db.flush()
        db.commit()
        print(f"Updated public_code for {len(users)} user(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
