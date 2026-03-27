"""Shared helpers for PATCH profile (social handles merge)."""

from __future__ import annotations


def merge_social_handles(existing: dict | None, patch: dict[str, str] | None) -> dict[str, str]:
    base = dict(existing) if isinstance(existing, dict) else {}
    if not patch:
        return base
    for k, v in patch.items():
        s = str(v).strip()
        key = str(k).strip()
        if not key:
            continue
        if s:
            base[key] = s
        elif key in base:
            del base[key]
    return base
