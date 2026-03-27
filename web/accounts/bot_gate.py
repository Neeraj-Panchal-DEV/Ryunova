"""Login anti-bot: Cloudflare Turnstile when configured, else session quiz + honeypot."""

from __future__ import annotations

from accounts.human_challenge import (
    HONEYPOT_FIELD,
    discard_human_challenge,
    honeypot_tripped,
    human_challenge_template_context,
    refresh_human_challenge,
    verify_and_consume_human_challenge,
)
from accounts.turnstile import (
    client_ip_for_turnstile,
    is_turnstile_enabled,
    verify_turnstile_token,
)


def verify_login_bot_gate(request) -> bool:
    if is_turnstile_enabled():
        token = (request.POST.get("cf-turnstile-response") or "").strip()
        if not token:
            return False
        return verify_turnstile_token(token, client_ip_for_turnstile(request))
    if not verify_and_consume_human_challenge(request):
        return False
    if honeypot_tripped(request):
        return False
    return True


def refresh_login_bot_challenge(request) -> None:
    """Issue a new fallback quiz when Turnstile is off; no-op when Turnstile handles verification."""
    if not is_turnstile_enabled():
        refresh_human_challenge(request)


def login_form_challenge_context(request) -> dict:
    """Template context for the human quiz partial (empty when Turnstile is active)."""
    if is_turnstile_enabled():
        return {
            "human_question": "",
            "human_options": [],
            "human_honeypot_name": HONEYPOT_FIELD,
        }
    return human_challenge_template_context(request)


def prepare_login_get_page(request) -> dict:
    """Call on GET for password login: fresh quiz or drop quiz for Turnstile."""
    if is_turnstile_enabled():
        discard_human_challenge(request)
    else:
        refresh_human_challenge(request)
    return login_form_challenge_context(request)


def login_gate_fail_message() -> str:
    if is_turnstile_enabled():
        return "Complete the security verification below and try again."
    return (
        "Please answer the “Are you human?” question correctly to continue. The question has been refreshed."
    )
