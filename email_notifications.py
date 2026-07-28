from __future__ import annotations

import html
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage


def ensure_email_schema(connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS email_log (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            email_type TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT NOT NULL DEFAULT ''
        )
    ''')
    connection.execute('CREATE INDEX IF NOT EXISTS idx_email_log_order ON email_log(order_id,id DESC)')


def _order_items(connection, order_id: int):
    return [dict(row) for row in connection.execute(
        'SELECT * FROM order_items WHERE order_id=? ORDER BY id', (order_id,)
    ).fetchall()]


def _order(connection, order_id: int):
    row = connection.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
    if not row:
        return None
    order = dict(row)
    order['items'] = _order_items(connection, order_id)
    return order


def _money(value) -> str:
    return f'${float(value or 0):,.2f}'


def _items_text(order) -> str:
    lines = []
    for item in order['items']:
        options = [f"Size: {item.get('size') or 'N/A'}"]
        if item.get('color'):
            options.append(f"Color: {item['color']}")
        if item.get('requested_name'):
            options.append(f"Name: {item['requested_name']}")
        lines.append(f"- {item['product_name']} x {item['quantity']} ({', '.join(options)}) — {_money(item['line_total'])}")
    return '\n'.join(lines)


def _items_html(order) -> str:
    rows = []
    for item in order['items']:
        options = [f"Size: {html.escape(item.get('size') or 'N/A')}"]
        if item.get('color'):
            options.append(f"Color: {html.escape(item['color'])}")
        if item.get('requested_name'):
            options.append(f"Name: <strong>{html.escape(item['requested_name'])}</strong>")
        rows.append(
            '<tr><td style="padding:10px;border-bottom:1px solid #ddd">'
            f"<strong>{html.escape(item['product_name'])}</strong><br><small>{'<br>'.join(options)}</small></td>"
            f"<td style=\"padding:10px;border-bottom:1px solid #ddd;text-align:center\">{item['quantity']}</td>"
            f"<td style=\"padding:10px;border-bottom:1px solid #ddd;text-align:right\">{_money(item['line_total'])}</td></tr>"
        )
    return ''.join(rows)


def _message(order, store_name: str, kind: str):
    number = order['order_number']
    if kind == 'new_customer':
        subject = f'{store_name} order confirmation — {number}'
        heading = 'Thank you for your order!'
        intro = f"We received your order {number}. Payment status: {order['payment_status']}."
    elif kind == 'new_admin':
        subject = f'New store order — {number}'
        heading = 'A new Stage Starz order was placed'
        intro = f"Customer: {order['customer_name']} ({order['customer_email']})"
    else:
        subject = f'{store_name} order update — {number}'
        heading = f"Order status: {order['status']}"
        intro = f"Your order {number} is now marked {order['status']}. Payment status: {order['payment_status']}."

    fulfillment = 'Studio pickup' if order['fulfillment_method'] == 'pickup' else 'Shipping'
    text = f"{heading}\n\n{intro}\n\nFulfillment: {fulfillment}\n\n{_items_text(order)}\n\nTotal: {_money(order['total'])}\n\nThank you,\n{store_name}"
    body = f'''<!doctype html><html><body style="font-family:Arial,sans-serif;color:#202234;background:#f5f2f8;padding:24px"><div style="max-width:680px;margin:auto;background:white;border-radius:16px;overflow:hidden"><div style="padding:24px;background:linear-gradient(115deg,#4d1f91,#6f35c5,#16a4b8);color:white"><h1 style="margin:0">{html.escape(store_name)}</h1></div><div style="padding:24px"><h2>{html.escape(heading)}</h2><p>{html.escape(intro)}</p><p><strong>Fulfillment:</strong> {html.escape(fulfillment)}</p><table style="width:100%;border-collapse:collapse"><thead><tr><th style="text-align:left;padding:10px">Item</th><th style="padding:10px">Qty</th><th style="text-align:right;padding:10px">Amount</th></tr></thead><tbody>{_items_html(order)}</tbody></table><p style="font-size:20px;text-align:right"><strong>Total: {_money(order['total'])}</strong></p><p>Thank you,<br>{html.escape(store_name)}</p></div></div></body></html>'''
    return subject, text, body


def _log(connection, order_id, recipient, subject, kind, status, error=''):
    ensure_email_schema(connection)
    connection.execute(
        'INSERT INTO email_log (order_id,created_at,recipient,subject,email_type,status,error_message) VALUES (?,?,?,?,?,?,?)',
        (order_id, datetime.now(timezone.utc).isoformat(), recipient, subject, kind, status, error[:500]),
    )


def send_order_email(connection, order_id: int, recipient: str, kind: str, settings: dict[str, str]) -> bool:
    order = _order(connection, order_id)
    if not order or not recipient:
        return False
    store_name = settings.get('store_name') or 'Stage Starz Store'
    subject, text, body = _message(order, store_name, kind)

    host = os.environ.get('SMTP_HOST', '').strip()
    username = os.environ.get('SMTP_USERNAME', '').strip()
    password = os.environ.get('SMTP_PASSWORD', '')
    from_address = os.environ.get('SMTP_FROM_EMAIL', '').strip() or username
    try:
        port = int(os.environ.get('SMTP_PORT', '587'))
    except ValueError:
        port = 587

    if not host or not from_address:
        _log(connection, order_id, recipient, subject, kind, 'Skipped', 'SMTP is not configured.')
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = os.environ.get('SMTP_FROM_NAME', store_name) + f' <{from_address}>'
    msg['To'] = recipient
    msg.set_content(text)
    msg.add_alternative(body, subtype='html')

    try:
        if os.environ.get('SMTP_USE_SSL', '0') == '1':
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.ehlo()
            if os.environ.get('SMTP_USE_TLS', '1') == '1':
                server.starttls()
                server.ehlo()
        if username:
            server.login(username, password)
        server.send_message(msg)
        server.quit()
        _log(connection, order_id, recipient, subject, kind, 'Sent')
        return True
    except Exception as exc:
        _log(connection, order_id, recipient, subject, kind, 'Failed', str(exc))
        return False
