"""Secure contact-form email delivery for the public Stage Starz website."""

from __future__ import annotations

import logging
import os
import re
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

from flask import redirect, request

logger = logging.getLogger("stage_starz.contact_email")

DEFAULT_AOL_EMAIL = "stagestarzdance@aol.com"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_RATE_WINDOW_SECONDS = 10 * 60
_RATE_MAX_SUBMISSIONS = 5
_rate_lock = threading.Lock()
_rate_events: dict[str, list[float]] = {}


def _one_line(value: str, limit: int) -> str:
    value = (value or "").replace("\r", " ").replace("\n", " ")
    return " ".join(value.split())[:limit]


def _client_key() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    return request.remote_addr or "unknown"


def _rate_limited(client_key: str) -> bool:
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW_SECONDS
    with _rate_lock:
        recent = [stamp for stamp in _rate_events.get(client_key, []) if stamp >= cutoff]
        if len(recent) >= _RATE_MAX_SUBMISSIONS:
            _rate_events[client_key] = recent
            return True
        recent.append(now)
        _rate_events[client_key] = recent
        return False


def _contact_redirect(status: str):
    return redirect(f"/contact.html?contact={status}#contact-form", code=303)


def register_contact_email(app) -> None:
    if "stage_starz_contact_submit" in app.view_functions:
        return

    @app.post("/contact/submit", endpoint="stage_starz_contact_submit")
    def stage_starz_contact_submit():
        # Bots commonly fill hidden honeypot fields. Silently accept those
        # submissions so they do not learn how the spam protection works.
        if (request.form.get("company_website") or "").strip():
            return _contact_redirect("sent")

        client_key = _client_key()
        if _rate_limited(client_key):
            return _contact_redirect("rate")

        first_name = _one_line(request.form.get("first_name", ""), 80)
        last_name = _one_line(request.form.get("last_name", ""), 80)
        sender_email = _one_line(request.form.get("email", ""), 254).lower()
        phone = _one_line(request.form.get("phone", ""), 60)
        message = (request.form.get("message", "") or "").strip()[:5000]

        if not first_name or not sender_email or not message or not EMAIL_RE.match(sender_email):
            return _contact_redirect("invalid")

        smtp_user = (os.getenv("AOL_SMTP_USER") or DEFAULT_AOL_EMAIL).strip()
        smtp_password = (os.getenv("AOL_SMTP_APP_PASSWORD") or "").replace(" ", "").strip()
        recipient = (os.getenv("CONTACT_TO_EMAIL") or DEFAULT_AOL_EMAIL).strip()
        smtp_host = (os.getenv("AOL_SMTP_HOST") or "smtp.aol.com").strip()
        try:
            smtp_port = int(os.getenv("AOL_SMTP_PORT") or "465")
        except ValueError:
            smtp_port = 465

        if not smtp_password:
            logger.error("Contact email is not configured: AOL_SMTP_APP_PASSWORD is missing.")
            return _contact_redirect("error")

        full_name = " ".join(part for part in (first_name, last_name) if part)
        email_message = EmailMessage()
        email_message["Subject"] = f"Stage Starz Website Inquiry - {full_name}"
        email_message["From"] = smtp_user
        email_message["To"] = recipient
        email_message["Reply-To"] = sender_email
        email_message.set_content(
            "\n".join(
                [
                    "New message from the Stage Starz website contact form",
                    "",
                    f"Name: {full_name}",
                    f"Email: {sender_email}",
                    f"Phone: {phone or 'Not provided'}",
                    "",
                    "Message:",
                    message,
                    "",
                    "Website: https://www.stagestarzdance.com/contact.html",
                ]
            )
        )

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                smtp_host,
                smtp_port,
                context=context,
                timeout=20,
            ) as smtp:
                smtp.login(smtp_user, smtp_password)
                smtp.send_message(email_message)
        except Exception:
            logger.exception("Unable to send Stage Starz website contact email.")
            return _contact_redirect("error")

        return _contact_redirect("sent")
