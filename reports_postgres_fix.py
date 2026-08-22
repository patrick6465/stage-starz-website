"""PostgreSQL-safe replacement for the Store & Orders reports dashboard."""

from __future__ import annotations

from flask import render_template

from database import get_db


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def register_reports_postgres_fix(app, permission_required):
    """Replace the legacy reports view with normalized, backend-safe data."""

    @permission_required("reports")
    def reports_dashboard_postgres_safe():
        connection = get_db()
        try:
            overview_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_orders,
                    COALESCE(SUM(CASE WHEN status != 'Cancelled' THEN 1 ELSE 0 END), 0) AS valid_orders,
                    COALESCE(SUM(CASE WHEN status != 'Cancelled' THEN total ELSE 0 END), 0) AS revenue,
                    COALESCE(AVG(CASE WHEN status != 'Cancelled' THEN total END), 0) AS average_order,
                    COALESCE(SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END), 0) AS completed_orders,
                    COALESCE(SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END), 0) AS cancelled_orders
                FROM orders
                """
            ).fetchone()
            raw_overview = dict(overview_row or {})
            overview = {
                "total_orders": _as_int(raw_overview.get("total_orders")),
                "valid_orders": _as_int(raw_overview.get("valid_orders")),
                "revenue": _as_float(raw_overview.get("revenue")),
                "average_order": _as_float(raw_overview.get("average_order")),
                "completed_orders": _as_int(raw_overview.get("completed_orders")),
                "cancelled_orders": _as_int(raw_overview.get("cancelled_orders")),
            }

            recent_rows = connection.execute(
                """
                SELECT
                    DATE(created_at) AS order_date,
                    COUNT(*) AS orders,
                    COALESCE(SUM(total), 0) AS revenue
                FROM orders
                WHERE status != 'Cancelled'
                GROUP BY DATE(created_at)
                ORDER BY order_date DESC
                LIMIT 14
                """
            ).fetchall()
            recent_sales = []
            for row in reversed(recent_rows):
                item = dict(row)
                recent_sales.append({
                    "order_date": str(item.get("order_date") or ""),
                    "orders": _as_int(item.get("orders")),
                    "revenue": _as_float(item.get("revenue")),
                })

            payment_rows = connection.execute(
                """
                SELECT
                    COALESCE(NULLIF(payment_method, ''), 'Unknown') AS payment_method,
                    COUNT(*) AS orders,
                    COALESCE(SUM(total), 0) AS revenue
                FROM orders
                WHERE status != 'Cancelled'
                GROUP BY payment_method
                ORDER BY orders DESC
                """
            ).fetchall()
            payment_mix = [
                {
                    "payment_method": dict(row).get("payment_method") or "Unknown",
                    "orders": _as_int(dict(row).get("orders")),
                    "revenue": _as_float(dict(row).get("revenue")),
                }
                for row in payment_rows
            ]

            status_rows = connection.execute(
                """
                SELECT
                    COALESCE(NULLIF(status, ''), 'Unknown') AS status,
                    COUNT(*) AS orders,
                    COALESCE(SUM(total), 0) AS revenue
                FROM orders
                GROUP BY status
                ORDER BY orders DESC
                """
            ).fetchall()
            status_mix = [
                {
                    "status": dict(row).get("status") or "Unknown",
                    "orders": _as_int(dict(row).get("orders")),
                    "revenue": _as_float(dict(row).get("revenue")),
                }
                for row in status_rows
            ]

            seller_rows = connection.execute(
                """
                SELECT
                    oi.product_name,
                    COALESCE(SUM(oi.quantity), 0) AS units,
                    COALESCE(
                        SUM(
                            (
                                COALESCE(oi.item_price, 0)
                                + COALESCE(oi.name_fee, 0)
                                + COALESCE(oi.fulfillment_fee, 0)
                            ) * COALESCE(oi.quantity, 0)
                        ),
                        0
                    ) AS revenue
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE o.status != 'Cancelled'
                GROUP BY oi.product_name
                ORDER BY units DESC, revenue DESC
                LIMIT 10
                """
            ).fetchall()
            best_sellers = [
                {
                    "product_name": dict(row).get("product_name") or "Unknown product",
                    "units": _as_int(dict(row).get("units")),
                    "revenue": _as_float(dict(row).get("revenue")),
                }
                for row in seller_rows
            ]

            product_rows = connection.execute(
                """
                SELECT name, category, stock, price, sale_price
                FROM products
                WHERE active = 1
                ORDER BY stock ASC, name
                """
            ).fetchall()
            products = [dict(row) for row in product_rows]
            low_stock = [
                {
                    "name": product.get("name") or "Unnamed product",
                    "category": product.get("category") or "",
                    "stock": _as_int(product.get("stock")),
                }
                for product in products
                if _as_int(product.get("stock")) <= 5
            ]
            inventory_units = sum(max(_as_int(product.get("stock")), 0) for product in products)
            inventory_value = sum(
                max(_as_int(product.get("stock")), 0)
                * _as_float(
                    product.get("sale_price")
                    if product.get("sale_price") is not None
                    else product.get("price")
                )
                for product in products
            )

            max_daily_revenue = max(
                [item["revenue"] for item in recent_sales] or [1.0]
            )
            if max_daily_revenue <= 0:
                max_daily_revenue = 1.0

            return render_template(
                "reports.html",
                overview=overview,
                recent_sales=recent_sales,
                payment_mix=payment_mix,
                status_mix=status_mix,
                best_sellers=best_sellers,
                low_stock=low_stock[:10],
                inventory_units=inventory_units,
                inventory_value=float(inventory_value),
                max_daily_revenue=float(max_daily_revenue),
            )
        finally:
            connection.close()

    # The URL rule already exists in app.py. Replacing its endpoint callable keeps
    # every existing link intact while routing requests through the safe handler.
    app.view_functions["reports_dashboard"] = reports_dashboard_postgres_safe
