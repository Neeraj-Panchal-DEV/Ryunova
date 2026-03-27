"""Lightweight human verification for login flows (session-backed multiple choice).

Not a replacement for reCAPTCHA Turnstile against determined attackers; reduces
drive-by scripted credential stuffing and OTP spam.
"""

from __future__ import annotations

import random
import secrets
import time
from typing import Any

SESSION_KEY = "login_human_challenge"
TTL_SECONDS = 900  # 15 minutes

# Honeypot field must stay empty (hidden from users).
HONEYPOT_FIELD = "contact_url"


def _now() -> float:
    return time.time()


def _option_tokens(n: int) -> list[str]:
    return [secrets.token_urlsafe(12) for _ in range(n)]


def _build_challenge() -> dict[str, Any]:
    generators = (
        _challenge_math_add,
        _challenge_math_sub,
        _challenge_days_week,
        _challenge_mammal,
        _challenge_browser,
        _challenge_ocean,
        _challenge_vowel,
        _challenge_shape_sides,
    )
    return random.choice(generators)()


def _challenge_math_add() -> dict[str, Any]:
    a, b = random.randint(3, 14), random.randint(3, 14)
    correct = a + b
    wrong_pool = set()
    for _ in range(80):
        if len(wrong_pool) >= 3:
            break
        delta = random.randint(-8, 8)
        if delta == 0:
            continue
        w = correct + delta
        if w > 0 and w != correct:
            wrong_pool.add(w)
    while len(wrong_pool) < 3:
        w = correct + 17 + len(wrong_pool)
        if w != correct:
            wrong_pool.add(w)
    texts = [correct, *wrong_pool]
    random.shuffle(texts)
    return _pack("What is the sum?", [str(x) for x in texts], str(correct))


def _challenge_math_sub() -> dict[str, Any]:
    a = random.randint(10, 24)
    b = random.randint(2, min(9, a - 2))
    correct = a - b
    wrong_pool = set()
    for _ in range(80):
        if len(wrong_pool) >= 3:
            break
        delta = random.randint(-6, 6)
        if delta == 0:
            continue
        w = correct + delta
        if w >= 0 and w != correct:
            wrong_pool.add(w)
    while len(wrong_pool) < 3:
        w = correct + 20 + len(wrong_pool)
        if w != correct:
            wrong_pool.add(w)
    texts = [correct, *wrong_pool]
    random.shuffle(texts)
    return _pack(f"What is {a} − {b}?", [str(x) for x in texts], str(correct))


def _challenge_days_week() -> dict[str, Any]:
    labels = [("7", True), ("5", False), ("10", False), ("12", False)]
    random.shuffle(labels)
    return _pack("How many days are in one week?", [x[0] for x in labels], next(t for t, ok in labels if ok))


def _challenge_mammal() -> dict[str, Any]:
    pool = [
        ("Dog", True),
        ("Oak tree", False),
        ("Granite", False),
        ("Diesel fuel", False),
        ("Salmon", True),
        ("Smartphone", False),
    ]
    correct_items = [x for x in pool if x[1]]
    wrong_items = [x for x in pool if not x[1]]
    c = random.choice(correct_items)
    wrong = random.sample(wrong_items, 3)
    opts = [c[0]] + [w[0] for w in wrong]
    random.shuffle(opts)
    return _pack("Which of these is a mammal?", opts, c[0])


def _challenge_browser() -> dict[str, Any]:
    pool = [
        ("Web browser", True),
        ("Refrigerator", False),
        ("Invoice total", False),
        ("Ethernet cable", False),
    ]
    random.shuffle(pool)
    return _pack("Which item is used to view websites?", [x[0] for x in pool], next(t for t, ok in pool if ok))


def _challenge_ocean() -> dict[str, Any]:
    pool = [
        ("Pacific Ocean", True),
        ("Atlantic spreadsheet", False),
        ("Mediterranean desk", False),
        ("Arctic algorithm", False),
    ]
    random.shuffle(pool)
    return _pack("Which is a real ocean?", [x[0] for x in pool], next(t for t, ok in pool if ok))


def _challenge_vowel() -> dict[str, Any]:
    pool = [("A", True), ("B", False), ("K", False), ("T", False)]
    random.shuffle(pool)
    return _pack("Which letter is a vowel in English?", [x[0] for x in pool], next(t for t, ok in pool if ok))


def _challenge_shape_sides() -> dict[str, Any]:
    pool = [
        ("Triangle (3)", True),
        ("Circle (0 corners)", False),
        ("Line (1)", False),
        ("Point (0)", False),
    ]
    random.shuffle(pool)
    return _pack("Which shape has exactly three straight sides?", [x[0] for x in pool], next(t for t, ok in pool if ok))


def _pack(question: str, labels: list[str], correct_label: str) -> dict[str, Any]:
    tokens = _option_tokens(len(labels))
    correct_token = ""
    options: list[dict[str, str]] = []
    for tok, lab in zip(tokens, labels, strict=True):
        options.append({"id": tok, "label": lab})
        if lab == correct_label:
            correct_token = tok
    assert correct_token
    return {
        "question": question,
        "options": options,
        "correct": correct_token,
        "exp": _now() + TTL_SECONDS,
    }


def refresh_human_challenge(request) -> None:
    """Replace any existing challenge with a new one (call on GET and after failed POST)."""
    request.session[SESSION_KEY] = _build_challenge()
    request.session.modified = True


def discard_human_challenge(request) -> None:
    """Remove session quiz (e.g. when using Cloudflare Turnstile instead)."""
    request.session.pop(SESSION_KEY, None)
    request.session.modified = True


def human_challenge_template_context(request) -> dict[str, Any]:
    """Context for templates; ensures a challenge exists."""
    if SESSION_KEY not in request.session:
        refresh_human_challenge(request)
    raw = request.session.get(SESSION_KEY) or {}
    return {
        "human_question": raw.get("question", ""),
        "human_options": raw.get("options", []),
        "human_honeypot_name": HONEYPOT_FIELD,
    }


def verify_and_consume_human_challenge(request) -> bool:
    """
    Validate POSTed choice against session. Always removes session challenge
    (success or failure) so the next response must show a new one.
    """
    data = request.session.pop(SESSION_KEY, None)
    posted = (request.POST.get("human_verification") or "").strip()
    if not isinstance(data, dict) or not posted:
        return False
    exp = data.get("exp")
    if not isinstance(exp, (int, float)) or _now() > exp:
        return False
    correct = data.get("correct")
    if not isinstance(correct, str):
        return False
    return secrets.compare_digest(posted, correct)


def honeypot_tripped(request) -> bool:
    return bool((request.POST.get(HONEYPOT_FIELD) or "").strip())
