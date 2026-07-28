from __future__ import annotations

from flask import redirect, render_template, request, url_for

from database import get_db
from routes_production import ensure_production_schema
from services import get_settings, login_required


def register_menu_routes(app):
    @app.before_request
    def redirect_admin_dashboard_to_menu():
        if request.endpoint == "admin_dashboard":
            return redirect(url_for("admin_menu"))
        return None

    @app.route("/admin/menu")
    @login_required
    def admin_menu():
        connection = get_db()
        ensure_production_schema(connection)
        settings = get_settings(connection)
        try:
            low_stock_threshold = max(0, int(settings.get("low_stock_threshold", "5") or 5))
        except ValueError:
            low_stock_threshold = 5

        today = dict(connection.execute(
            """
            SELECT COUNT(*) AS orders,
                   COALESCE(SUM(total), 0) AS sales
            FROM orders
            WHERE status != 'Cancelled'
              AND left(created_at, 10) = to_char(CURRENT_DATE, 'YYYY-MM-DD')
            """
        ).fetchone())

        production_counts = {
            row["production_status"]: int(row["count"])
            for row in connection.execute(
                """
                SELECT production_status, COUNT(*) AS count
                FROM orders
                WHERE status != 'Cancelled'
                GROUP BY production_status
                """
            ).fetchall()
        }

        waiting_orders = production_counts.get("New", 0) + production_counts.get("Waiting to Order", 0)
        in_production = (
            production_counts.get("Ordered from Manufacturer", 0)
            + production_counts.get("Received at Studio", 0)
        )
        ready_for_pickup = production_counts.get("Ready for Pickup", 0)

        inventory_alerts = int(connection.execute(
            "SELECT COUNT(*) AS count FROM products WHERE active = 1 AND stock <= ?",
            (low_stock_threshold,),
        ).fetchone()["count"])

        recent_orders = [dict(row) for row in connection.execute(
            """
            SELECT id, order_number, customer_name, total, status,
                   production_status, created_at
            FROM orders
            WHERE status != 'Cancelled'
            ORDER BY id DESC
            LIMIT 8
            """
        ).fetchall()]

        low_stock_products = [dict(row) for row in connection.execute(
            """
            SELECT id, name, stock
            FROM products
            WHERE active = 1 AND stock <= ?
            ORDER BY stock ASC, name ASC
            LIMIT 8
            """,
            (low_stock_threshold,),
        ).fetchall()]

        connection.commit()
        connection.close()

        metrics = {
            "today_sales": float(today.get("sales") or 0),
            "today_orders": int(today.get("orders") or 0),
            "waiting_orders": waiting_orders,
            "in_production": in_production,
            "ready_for_pickup": ready_for_pickup,
            "inventory_alerts": inventory_alerts,
        }
        return render_template(
            "admin_menu.html",
            metrics=metrics,
            recent_orders=recent_orders,
            low_stock_products=low_stock_products,
            low_stock_threshold=low_stock_threshold,
        )

    @app.route("/admin/products")
    @login_required
    def admin_products():
        return app.view_functions["admin_dashboard"]()
