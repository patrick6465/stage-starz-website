from __future__ import annotations

from flask import abort, redirect, render_template, request, url_for

from database import get_db
from inventory import ensure_inventory_schema, record_inventory_movement
from services import get_settings, login_required


def register_inventory_routes(app):
    @app.route("/admin/inventory")
    @login_required
    def admin_inventory():
        connection = get_db()
        ensure_inventory_schema(connection)
        settings = get_settings(connection)
        try:
            threshold = max(0, int(settings.get("low_stock_threshold", "5") or 5))
        except ValueError:
            threshold = 5

        products = [dict(row) for row in connection.execute(
            """SELECT id,name,category,stock,active,
                      CASE WHEN stock<=0 THEN 'Out of stock'
                           WHEN stock<=? THEN 'Low stock'
                           ELSE 'Healthy' END AS inventory_status
               FROM products
               ORDER BY stock ASC, category, name""",
            (threshold,),
        ).fetchall()]
        movements = [dict(row) for row in connection.execute(
            """SELECT m.*,p.name AS product_name
               FROM inventory_movements m
               JOIN products p ON p.id=m.product_id
               ORDER BY m.id DESC LIMIT 100"""
        ).fetchall()]
        summary = dict(connection.execute(
            """SELECT COUNT(*) AS products,
                      COALESCE(SUM(stock),0) AS units,
                      COALESCE(SUM(CASE WHEN stock<=0 THEN 1 ELSE 0 END),0) AS out_of_stock,
                      COALESCE(SUM(CASE WHEN stock>0 AND stock<=? THEN 1 ELSE 0 END),0) AS low_stock
               FROM products""",
            (threshold,),
        ).fetchone())
        connection.commit()
        connection.close()
        return render_template(
            "inventory.html",
            products=products,
            movements=movements,
            summary=summary,
            threshold=threshold,
        )

    @app.route("/admin/inventory/<int:product_id>/adjust", methods=["POST"])
    @login_required
    def adjust_inventory(product_id: int):
        try:
            change = int(request.form.get("change_quantity", "0"))
        except ValueError:
            change = 0
        note = request.form.get("note", "").strip()[:250]
        if change == 0:
            return redirect(url_for("admin_inventory"))

        connection = get_db()
        ensure_inventory_schema(connection)
        product = connection.execute(
            "SELECT id,name,stock FROM products WHERE id=? FOR UPDATE", (product_id,)
        ).fetchone()
        if not product:
            connection.rollback()
            connection.close()
            abort(404)

        new_quantity = max(0, int(product["stock"]) + change)
        actual_change = new_quantity - int(product["stock"])
        connection.execute("UPDATE products SET stock=? WHERE id=?", (new_quantity, product_id))
        record_inventory_movement(
            connection,
            product_id,
            actual_change,
            new_quantity,
            "Manual adjustment",
            note=note,
        )
        connection.commit()
        connection.close()
        return redirect(url_for("admin_inventory"))
