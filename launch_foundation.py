from __future__ import annotations

import html
import os
from datetime import datetime, timezone

from flask import flash, redirect, render_template, request

from database import get_db
from email_notifications import ensure_email_schema
from zeptomail_sender import is_zeptomail_configured, send_zeptomail

DEFAULT_CONTACT_EMAIL = "office@stagestarzdance.com"


def ensure_website_inquiry_schema() -> None:
    connection = get_db()
    id_column = (
        "SERIAL PRIMARY KEY"
        if getattr(connection, "backend", "sqlite") == "postgresql"
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS website_inquiries (
            id {id_column},
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            interest TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New',
            source_page TEXT NOT NULL DEFAULT 'contact',
            admin_notes TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()


def _log_contact_delivery(recipient: str, subject: str, status: str, detail: str = "") -> None:
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
    finally:
        if connection:
            connection.close()


def _contact_email_html(
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    interest: str,
    message: str,
) -> str:
    full_name = " ".join(part for part in (first_name, last_name) if part)
    return f"""<!doctype html>
<html><body style="font-family:Arial,sans-serif;color:#202234;background:#f5f2f8;padding:24px">
<div style="max-width:680px;margin:auto;background:#fff;border-radius:16px;overflow:hidden">
<div style="padding:24px;background:linear-gradient(115deg,#4d1f91,#6f35c5,#16a4b8);color:#fff">
<h1 style="margin:0">New Stage Starz Website Inquiry</h1></div>
<div style="padding:24px">
<p><strong>Name:</strong> {html.escape(full_name)}</p>
<p><strong>Email:</strong> {html.escape(email)}</p>
<p><strong>Phone:</strong> {html.escape(phone or "Not provided")}</p>
<p><strong>Interested In:</strong> {html.escape(interest or "Not specified")}</p>
<p><strong>Message:</strong></p>
<div style="padding:16px;border-radius:12px;background:#f7f4fa">{html.escape(message).replace(chr(10), "<br>")}</div>
<p style="margin-top:22px;color:#6d7180;font-size:13px">Sent from https://www.stagestarzdance.com/contact.html</p>
</div></div></body></html>"""


def register_launch_foundation(app, permission_required, log_activity=None) -> None:
    """Register launch-readiness routes without modifying the main application module."""
    ensure_website_inquiry_schema()

    @app.route("/index.html")
    @app.route("/index-new.html")
    @app.route("/START-HERE.html")
    def launch_legacy_home_redirect():
        return redirect("/", code=301)

    @app.route("/contact/submit", methods=["POST"])
    def launch_contact_submit():
        # Honeypot: bots commonly fill every field; real visitors never see this one.
        if request.form.get("website", "").strip():
            return redirect("/contact.html?sent=1#contact-form", code=303)

        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        interest = request.form.get("interest", "").strip()
        message = request.form.get("message", "").strip()

        if not first_name or not email or not message:
            return redirect("/contact.html?error=required#contact-form", code=303)
        if "@" not in email or len(email) > 254:
            return redirect("/contact.html?error=email#contact-form", code=303)

        connection = get_db()
        connection.execute(
            """
            INSERT INTO website_inquiries (
                first_name,last_name,email,phone,
                interest,message,status,source_page
            ) VALUES (?,?,?,?,?,?,'New','contact')
            """,
            (
                first_name[:100],
                last_name[:100],
                email[:254],
                phone[:60],
                interest[:120],
                message[:5000],
            ),
        )
        connection.commit()
        connection.close()

        if log_activity:
            try:
                log_activity(
                    "Website inquiry received",
                    f"{first_name} {last_name}".strip() + f" · {email}",
                )
            except Exception:
                app.logger.exception("Could not write website inquiry activity log")

        recipient = (os.environ.get("CONTACT_TO_EMAIL") or DEFAULT_CONTACT_EMAIL).strip()
        subject = f"Stage Starz Website Inquiry - {' '.join(part for part in (first_name, last_name) if part)}"

        if not is_zeptomail_configured():
            detail = "ZeptoMail is not configured in Railway."
            _log_contact_delivery(recipient, subject, "Failed", detail)
            app.logger.error(detail)
            return redirect("/contact.html?error=send#contact-form", code=303)

        sent, detail = send_zeptomail(
            recipient,
            subject,
            html_body=_contact_email_html(
                first_name,
                last_name,
                email,
                phone,
                interest,
                message,
            ),
            from_name="Stage Starz Website",
            reply_to=email,
            reply_to_name=" ".join(part for part in (first_name, last_name) if part),
            client_reference="website-contact",
        )
        _log_contact_delivery(
            recipient,
            subject,
            "Sent" if sent else "Failed",
            detail,
        )
        if not sent:
            app.logger.error("ZeptoMail contact delivery failed: %s", detail)
            return redirect("/contact.html?error=send#contact-form", code=303)

        return redirect("/contact.html?sent=1#contact-form", code=303)

    @app.route("/admin/website/inquiries")
    @permission_required("website")
    def launch_website_inquiries():
        connection = get_db()
        inquiries = connection.execute(
            """
            SELECT *
            FROM website_inquiries
            ORDER BY
                CASE status
                    WHEN 'New' THEN 0
                    WHEN 'Contacted' THEN 1
                    WHEN 'Closed' THEN 2
                    ELSE 3
                END,
                created_at DESC,
                id DESC
            """
        ).fetchall()
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status='New' THEN 1 ELSE 0 END) AS new_count,
                SUM(CASE WHEN status='Contacted' THEN 1 ELSE 0 END) AS contacted_count,
                SUM(CASE WHEN status='Closed' THEN 1 ELSE 0 END) AS closed_count
            FROM website_inquiries
            """
        ).fetchone()
        connection.close()
        return render_template(
            "website_inquiries.html",
            inquiries=[dict(row) for row in inquiries],
            summary=dict(summary),
        )

    @app.route("/admin/website/inquiries/<int:inquiry_id>/update", methods=["POST"])
    @permission_required("website")
    def launch_update_website_inquiry(inquiry_id: int):
        status = request.form.get("status", "New").strip()
        if status not in {"New", "Contacted", "Closed"}:
            status = "New"

        connection = get_db()
        inquiry = connection.execute(
            "SELECT id FROM website_inquiries WHERE id=?",
            (inquiry_id,),
        ).fetchone()
        if not inquiry:
            connection.close()
            return ("Inquiry not found", 404)

        connection.execute(
            """
            UPDATE website_inquiries SET
                status=?,
                admin_notes=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                status,
                request.form.get("admin_notes", "").strip()[:5000],
                inquiry_id,
            ),
        )
        connection.commit()
        connection.close()
        flash("Website inquiry updated.", "success")
        return redirect("/admin/website/inquiries")
