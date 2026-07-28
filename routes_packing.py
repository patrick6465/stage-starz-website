from __future__ import annotations

from flask import abort, render_template

from database import get_db
from services import get_settings, login_required


def _load_order(connection, order_id: int):
    row = connection.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        return None
    order = dict(row)
    order["items"] = [
        dict(item)
        for item in connection.execute(
            "SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order_id,)
        ).fetchall()
    ]
    return order


def register_packing_routes(app):
    @app.route("/admin/packing-slips")
    @login_required
    def packing_slips():
        connection = get_db()
        orders = [
            dict(row)
            for row in connection.execute(
                """SELECT id,order_number,created_at,customer_name,
                          fulfillment_method,status,payment_status
                   FROM orders
                   WHERE status!='Cancelled'
                   ORDER BY id DESC"""
            ).fetchall()
        ]
        connection.close()
        return render_template("packing_slips.html", orders=orders)

    @app.route("/admin/order/<int:order_id>/packing-slip")
    @login_required
    def packing_slip(order_id: int):
        connection = get_db()
        order = _load_order(connection, order_id)
        settings = get_settings(connection)
        connection.close()
        if not order:
            abort(404)
        return render_template("packing_slip.html", order=order, settings=settings)
