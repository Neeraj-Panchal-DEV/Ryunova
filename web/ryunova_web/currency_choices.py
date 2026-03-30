"""Shared ISO 4217 options for product and organisation currency fields."""

from __future__ import annotations

CURRENCY_CHOICES: list[tuple[str, str]] = [
    ("AUD", "AUD — Australian dollar"),
    ("USD", "USD — US dollar"),
    ("EUR", "EUR — Euro"),
    ("GBP", "GBP — Pound sterling"),
    ("NZD", "NZD — New Zealand dollar"),
    ("CAD", "CAD — Canadian dollar"),
    ("SGD", "SGD — Singapore dollar"),
    ("JPY", "JPY — Japanese yen"),
    ("CNY", "CNY — Chinese yuan"),
    ("INR", "INR — Indian rupee"),
]

_ALLOWED = {c for c, _ in CURRENCY_CHOICES}


def normalize_currency_code(raw: str | None) -> str:
    c = (raw or "").strip().upper()
    return c if c in _ALLOWED else "AUD"
