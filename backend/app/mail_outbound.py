"""Send transactional email from the API (sign-in codes). Uses same SMTP env vars as Django when set."""
#backend/app/mail_outbound.py
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_login_code_email(*, to_email: str, code: str) -> None:
    settings = get_settings()
    subject = "Your RyuNova sign-in code"
    login_url = settings.site_url.rstrip("/") + "/accounts/login/"
    text = (
        f"Your sign-in code is: {code}\n\n"
        f"It expires in 15 minutes. If you did not request this, ignore this email.\n\n"
        f"Sign in: {login_url}\n"
    )
    html = f"""<!DOCTYPE html><html><body style="font-family:system-ui,sans-serif;line-height:1.5;color:#111;">
<p>Your sign-in code is:</p>
<p style="font-size:1.5rem;font-weight:700;letter-spacing:0.2em;">{code}</p>
<p>It expires in <strong>15 minutes</strong>. If you did not request this, you can ignore this email.</p>
<p><a href="{login_url}">Open sign-in</a></p>
</body></html>"""

    from_addr = settings.from_email_address
    from_header = formataddr((settings.email_host_user_name, from_addr))

    if not settings.smtp_configured:
        logger.warning(
            "SMTP not configured (EMAIL_HOST_USER/PASSWORD); login code for %s not emailed. Code (dev only): %s",
            to_email,
            code,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if settings.email_use_ssl:
            with smtplib.SMTP_SSL(settings.email_host, settings.email_port, timeout=25) as smtp:
                smtp.login(settings.email_host_user, settings.email_host_password)
                smtp.sendmail(from_addr, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(settings.email_host, settings.email_port, timeout=25) as smtp:
                if settings.email_use_tls:
                    smtp.starttls()
                smtp.login(settings.email_host_user, settings.email_host_password)
                smtp.sendmail(from_addr, [to_email], msg.as_string())
    except OSError as e:
        logger.exception("SMTP send failed for login code to %s: %s", to_email, e)
        raise


def send_email_change_verification_email(*, to_email: str, verify_url: str) -> None:
    settings = get_settings()
    subject = "Confirm your new email — RyuNova"
    text = (
        f"You requested to change your RyuNova account email.\n\n"
        f"Open this link to confirm (expires in 48 hours):\n{verify_url}\n\n"
        f"If you did not request this, ignore this email.\n"
    )
    html = f"""<!DOCTYPE html><html><body style="font-family:system-ui,sans-serif;line-height:1.5;color:#111;">
<p>You requested to change your <strong>RyuNova</strong> account email.</p>
<p><a href="{verify_url}">Confirm new email address</a></p>
<p>This link expires in <strong>48 hours</strong>. If you did not request this change, you can ignore this email.</p>
</body></html>"""

    from_addr = settings.from_email_address
    from_header = formataddr((settings.email_host_user_name, from_addr))

    if not settings.smtp_configured:
        logger.warning(
            "SMTP not configured; email change link for %s not sent. Dev link: %s",
            to_email,
            verify_url,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if settings.email_use_ssl:
            with smtplib.SMTP_SSL(settings.email_host, settings.email_port, timeout=25) as smtp:
                smtp.login(settings.email_host_user, settings.email_host_password)
                smtp.sendmail(from_addr, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(settings.email_host, settings.email_port, timeout=25) as smtp:
                if settings.email_use_tls:
                    smtp.starttls()
                smtp.login(settings.email_host_user, settings.email_host_password)
                smtp.sendmail(from_addr, [to_email], msg.as_string())
    except OSError as e:
        logger.exception("SMTP send failed for email change to %s: %s", to_email, e)
        raise
