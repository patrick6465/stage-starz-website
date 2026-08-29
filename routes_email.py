from __future__ import annotations

import os

from flask import redirect, render_template, request, url_for

from database import get_db
from email_notifications import ensure_email_schema, send_order_email
from services import get_settings, login_required
from zeptomail_sender import is_zeptomail_configured


def register_email_routes(app):
    @app.after_request
    def send_automatic_order_emails(response):
        endpoint = request.endpoint or ''
        if response.status_code >= 400 or endpoint not in {'create_order', 'update_order'}:
            return response

        connection = None
        try:
            connection = get_db()
            ensure_email_schema(connection)
            settings = get_settings(connection)

            if endpoint == 'create_order' and response.is_json:
                data = response.get_json(silent=True) or {}
                number = data.get('order_number')
                if number:
                    order = connection.execute(
                        'SELECT id,customer_email FROM orders WHERE order_number=?', (number,)
                    ).fetchone()
                    if order:
                        send_order_email(
                            connection,
                            order['id'],
                            order['customer_email'],
                            'new_customer',
                            settings,
                        )
                        admin_email = settings.get('order_email', '').strip()
                        if admin_email:
                            send_order_email(
                                connection,
                                order['id'],
                                admin_email,
                                'new_admin',
                                settings,
                            )

            elif endpoint == 'update_order':
                order_id = (request.view_args or {}).get('order_id')
                if order_id:
                    order = connection.execute(
                        'SELECT customer_email FROM orders WHERE id=?', (order_id,)
                    ).fetchone()
                    if order:
                        send_order_email(
                            connection,
                            order_id,
                            order['customer_email'],
                            'status_update',
                            settings,
                        )

            connection.commit()
        except Exception:
            if connection:
                connection.rollback()
        finally:
            if connection:
                connection.close()
        return response

    @app.route('/admin/email-log')
    @login_required
    def email_log():
        connection = get_db()
        ensure_email_schema(connection)
        rows = [dict(row) for row in connection.execute("""
            SELECT e.*,o.order_number FROM email_log e
            LEFT JOIN orders o ON o.id=e.order_id
            ORDER BY e.id DESC LIMIT 250
        """).fetchall()]
        smtp_configured = bool(
            os.environ.get('SMTP_HOST')
            and (os.environ.get('SMTP_FROM_EMAIL') or os.environ.get('SMTP_USERNAME'))
        )
        configured = is_zeptomail_configured() or smtp_configured
        provider = (
            'ZeptoMail'
            if is_zeptomail_configured()
            else ('SMTP fallback' if smtp_configured else '')
        )
        connection.commit()
        connection.close()
        return render_template(
            'email_log.html',
            emails=rows,
            configured=configured,
            provider=provider,
        )

    @app.route('/admin/order/<int:order_id>/resend-email', methods=['POST'])
    @login_required
    def resend_order_email(order_id: int):
        connection = get_db()
        settings = get_settings(connection)
        order = connection.execute(
            'SELECT customer_email FROM orders WHERE id=?', (order_id,)
        ).fetchone()
        if order:
            send_order_email(
                connection,
                order_id,
                order['customer_email'],
                'status_update',
                settings,
            )
        connection.commit()
        connection.close()
        return redirect(request.referrer or url_for('email_log'))
