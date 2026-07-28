from __future__ import annotations

from flask import jsonify, redirect, render_template, request, url_for

from database import get_db
from email_notifications import ensure_email_schema, send_order_email
from services import get_settings, login_required


def register_email_routes(app):
    @app.after_request
    def send_automatic_order_emails(response):
        if response.status_code >= 400:
            return response
        try:
            endpoint = request.endpoint or ''
            connection = get_db()
            ensure_email_schema(connection)
            settings = get_settings(connection)

            if endpoint == 'create_order' and response.is_json:
                data = response.get_json(silent=True) or {}
                number = data.get('order_number')
                if number:
                    order = connection.execute('SELECT id,customer_email FROM orders WHERE order_number=?', (number,)).fetchone()
                    if order:
                        send_order_email(connection, order['id'], order['customer_email'], 'new_customer', settings)
                        admin_email = settings.get('order_email', '').strip()
                        if admin_email:
                            send_order_email(connection, order['id'], admin_email, 'new_admin', settings)

            elif endpoint == 'update_order':
                order_id = (request.view_args or {}).get('order_id')
                if order_id:
                    order = connection.execute('SELECT customer_email FROM orders WHERE id=?', (order_id,)).fetchone()
                    if order:
                        send_order_email(connection, order_id, order['customer_email'], 'status_update', settings)

            connection.commit()
            connection.close()
        except Exception:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        return response

    @app.route('/admin/email-log')
    @login_required
    def email_log():
        connection = get_db()
        ensure_email_schema(connection)
        rows = [dict(row) for row in connection.execute('''
            SELECT e.*,o.order_number FROM email_log e
            LEFT JOIN orders o ON o.id=e.order_id
            ORDER BY e.id DESC LIMIT 250
        ''').fetchall()]
        configured = bool(__import__('os').environ.get('SMTP_HOST') and (__import__('os').environ.get('SMTP_FROM_EMAIL') or __import__('os').environ.get('SMTP_USERNAME')))
        connection.commit()
        connection.close()
        return render_template('email_log.html', emails=rows, configured=configured)

    @app.route('/admin/order/<int:order_id>/resend-email', methods=['POST'])
    @login_required
    def resend_order_email(order_id: int):
        connection = get_db()
        settings = get_settings(connection)
        order = connection.execute('SELECT customer_email FROM orders WHERE id=?', (order_id,)).fetchone()
        if order:
            send_order_email(connection, order_id, order['customer_email'], 'status_update', settings)
        connection.commit()
        connection.close()
        return redirect(request.referrer or url_for('email_log'))
