"""Secure contact-form email delivery for the public Stage Starz website."""

from __future__ import annotations

import html
import logging
import os
import re
import smtplib
import ssl
import threading
import time
from datetime import datetime, timezone
from email.message import EmailMessage

from flask import redirect, request

from database import get_db
from email_notifications import ensure_email_schema
from zeptomail_sender import is_zeptomail_configured, send_zeptomail

logger = logging.getLogger("stage_starz.contact_email")

DEFAULT_AOL_EMAIL = "stagestarzdance@aol.com"
DEFAULT_CONTACT_EMAIL = "office@stagestarzdance.com"
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


def _log_contact_delivery(recipient: str, subject: str, status: str, detail: str = "") -> None:
    """Record contact-form delivery attempts in the manager Email Delivery Center."""
    connection = None
    try:
        connection = get_db()
        ensure_email_schema(connection)
        connection.execute(
            "INSERT INTO email_log "
            "(order_id,created_at,recipient,subject,email_type,status,error_message) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                None,
                datetime.now(timezone.utc).isoformat(),
                recipient,
                subject,
                "contact_form",
                status,
                (detail or "")[:500],
            ),
        )
        connection.commit()
    except Exception:
        if connection:
            connection.rollback()
        logger.exception("Unable to record contact-form email delivery attempt.")
    finally:
        if connection:
            connection.close()


def _contact_html(full_name: str, sender_email: str, phone: str, message: str) -> str:
    safe_name = html.escape(full_name)
    safe_email = html.escape(sender_email)
    safe_phone = html.escape(phone or "Not provided")
    safe_message = html.escape(message).replace("\n", "<br>")
    return f"""<!doctype html>
<html>
  <body style="margin:0;background:#f5f2f8;font-family:Arial,sans-serif;color:#202234">
    <div style="max-width:680px;margin:24px auto;background:#fff;border-radius:16px;overflow:hidden">
      <div style="padding:22px 24px;background:linear-gradient(115deg,#4d1f91,#6f35c5,#16a4b8);color:#fff">
        <h1 style="margin:0;font-size:24px">New Stage Starz Website Inquiry</h1>
      </div>
      <div style="padding:24px">
        <p><strong>Name:</strong> {safe_name}</p>
        <p><strong>Email:</strong> {safe_email}</p>
        <p><strong>Phone:</strong> {safe_phone}</p>
        <p><strong>Message:</strong></p>
        <div style="padding:16px;border-radius:12px;background:#f7f4fa">{safe_message}</div>
        <p style="margin-top:22px;color:#6d7180;font-size:13px">
          Sent from https://www.stagestarzdance.com/contact.html
        </p>
      </div>
    </div>
  </body>
</html>"""


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

        full_name = " ".join(part for part in (first_name, last_name) if part)
        recipient = (os.getenv("CONTACT_TO_EMAIL") or DEFAULT_CONTACT_EMAIL).strip()
        subject = f"Stage Starz Website Inquiry - {full_name}"

        # Prefer ZeptoMail's HTTPS API on Railway. This avoids outbound SMTP
        # restrictions and sends from the verified stagestarzdance.com domain.
        if is_zeptomail_configured():
            sent, error = send_zeptomail(
                recipient,
                subject,
                html_body=_contact_html(full_name, sender_email, phone, message),
                from_name="Stage Starz Website",
                reply_to=sender_email,
                reply_to_name=full_name,
                client_reference="website-contact",
            )
            if not sent:
                _log_contact_delivery(recipient, subject, "Failed", error)
                logger.error("Unable to send Stage Starz contact email through ZeptoMail: %s", error)
                return _contact_redirect("error")
            _log_contact_delivery(recipient, subject, "Sent", error)
            return _contact_redirect("sent")

        # Temporary fallback while the ZeptoMail token is being added to Railway.
        smtp_user = (os.getenv("AOL_SMTP_USER") or DEFAULT_AOL_EMAIL).strip()
        smtp_password = (os.getenv("AOL_SMTP_APP_PASSWORD") or "").replace(" ", "").strip()
        smtp_host = (os.getenv("AOL_SMTP_HOST") or "smtp.aol.com").strip()
        try:
            smtp_port = int(os.getenv("AOL_SMTP_PORT") or "465")
        except ValueError:
            smtp_port = 465

        if not smtp_password:
            logger.error(
                "Contact email is not configured: ZEPTOMAIL_API_TOKEN and AOL_SMTP_APP_PASSWORD are missing."
            )
            return _contact_redirect("error")

        email_message = EmailMessage()
        email_message["Subject"] = subject
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
        except Exception as exc:
            _log_contact_delivery(recipient, subject, "Failed", f"AOL SMTP fallback: {exc}")
            logger.exception("Unable to send Stage Starz website contact email.")
            return _contact_redirect("error")

        _log_contact_delivery(recipient, subject, "Sent", "AOL SMTP fallback")
        return _contact_redirect("sent")
