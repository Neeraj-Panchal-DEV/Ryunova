"""Transactional email for user invites — HTML layout matches dragon-latrobe_fintext verify_email template."""

from __future__ import annotations

import logging
from datetime import date

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

INVITE_TEMPLATE = "accounts/emails/invite_user.html"

logger = logging.getLogger(__name__)


def email_delivery_is_console_only() -> bool:
    """
    True when Django uses the console backend: messages are printed to the server process stdout/stderr,
    not delivered to the recipient's inbox. Happens when EMAIL_HOST_USER / EMAIL_HOST_PASSWORD are unset
    unless EMAIL_BACKEND is overridden to SMTP explicitly.
    """
    backend = (getattr(settings, "EMAIL_BACKEND", "") or "").lower()
    return "console" in backend


def build_invite_email(
    *,
    recipient_email: str,
    organisation_name: str,
    verify_url: str,
    temporary_password: str,
    display_name: str | None,
    reminder: bool = False,
) -> tuple[str, str, str]:
    """Returns (subject, text_body, html_body)."""
    greeting_name = (display_name or "").strip() or recipient_email.split("@")[0]
    subject = (
        f"Reminder: complete your RyuNova invitation — {organisation_name}"
        if reminder
        else f"You're invited to RyuNova Platform — {organisation_name}"
    )

    site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8001").rstrip("/")
    login_url = f"{site_url}/accounts/login/"
    logo_url = getattr(settings, "EMAIL_LOGO_URL", "") or None

    html = render_to_string(
        INVITE_TEMPLATE,
        {
            "logo_url": logo_url,
            "site_url": site_url,
            "login_url": login_url,
            "verify_link": verify_url,
            "organisation_name": organisation_name,
            "greeting_name": greeting_name,
            "temporary_password": temporary_password,
            "copyright_year": date.today().year,
            "reminder": reminder,
        },
    )

    open_para = (
        f"This is a reminder to finish setting up your account for {organisation_name} on RyuNova Platform (Dragon and Peaches)."
        if reminder
        else f"You've been invited to {organisation_name} on RyuNova Platform (Dragon and Peaches)."
    )
    text = f"""Hello {greeting_name},

{open_para}

Next steps:
1. Verify your email (required before sign-in):
   {verify_url}
2. Sign in at: {login_url}
   Use your email and this temporary password, then change your password under Profile:
   {temporary_password}
3. Update your display name and photo under Profile.

If you did not expect this invitation, you can ignore this email.

— Dragon and Peaches Pty Ltd · RyuNova Platform
"""

    return subject, text, html


def _format_from_header() -> str:
    """Fintext-style: \"Display Name\" <address@domain>."""
    addr = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
    name = getattr(settings, "EMAIL_HOST_USER_NAME", "") or "RyuNova Platform"
    if not addr:
        addr = "noreply@localhost"
    return f'"{name}" <{addr}>'


def send_user_invite_email(
    *,
    to_email: str,
    organisation_name: str,
    verify_url: str,
    temporary_password: str,
    display_name: str | None,
    reminder: bool = False,
) -> None:
    subject, text_body, html_body = build_invite_email(
        recipient_email=to_email,
        organisation_name=organisation_name,
        verify_url=verify_url,
        temporary_password=temporary_password,
        display_name=display_name,
        reminder=reminder,
    )
    from_header = _format_from_header()
    msg = EmailMultiAlternatives(subject, text_body, from_header, [to_email])
    msg.attach_alternative(html_body, "text/html")
    if email_delivery_is_console_only():
        logger.warning(
            "Invite for %s: using console email backend—message will not reach an inbox; "
            "see web/.env EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, docs/EMAIL_SETTINGS.md",
            to_email,
        )
    else:
        logger.info("Sending invite email to %s via %s", to_email, settings.EMAIL_BACKEND)
    msg.send(fail_silently=False)
