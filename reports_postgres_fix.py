"""PostgreSQL-safe replacement for the Store & Orders reports dashboard."""

from __future__ import annotations

from flask import render_template, render_template_string

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

    def query_one(label: str, sql: str):
        connection = get_db()
        try:
            row = connection.execute(sql).fetchone()
            return dict(row or {})
        except Exception:
            app.logger.exception("Reports query failed: %s", label)
            return {}
        finally:
            connection.close()

    def query_all(label: str, sql: str):
        connection = get_db()
        try:
            return [dict(row) for row in connection.execute(sql).fetchall()]
        except Exception:
            app.logger.exception("Reports query failed: %s", label)
            return []
        finally:
            connection.close()

    @permission_required("reports")
    def reports_dashboard_postgres_safe():
        raw_overview = query_one(
            "overview",
            """
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(CASE WHEN status != 'Cancelled' THEN 1 ELSE 0 END), 0) AS valid_orders,
                COALESCE(SUM(CASE WHEN status != 'Cancelled' THEN total ELSE 0 END), 0) AS revenue,
                COALESCE(AVG(CASE WHEN status != 'Cancelled' THEN total END), 0) AS average_order,
                COALESCE(SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END), 0) AS completed_orders,
                COALESCE(SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END), 0) AS cancelled_orders
            FROM orders
            """,
        )
        overview = {
            "total_orders": _as_int(raw_overview.get("total_orders")),
            "valid_orders": _as_int(raw_overview.get("valid_orders")),
            "revenue": _as_float(raw_overview.get("revenue")),
            "average_order": _as_float(raw_overview.get("average_order")),
            "completed_orders": _as_int(raw_overview.get("completed_orders")),
            "cancelled_orders": _as_int(raw_overview.get("cancelled_orders")),
        }

        recent_rows = query_all(
            "recent sales",
            """
            SELECT
                CAST(created_at AS DATE) AS order_date,
                COUNT(*) AS orders,
                COALESCE(SUM(total), 0) AS revenue
            FROM orders
            WHERE status != 'Cancelled'
            GROUP BY CAST(created_at AS DATE)
            ORDER BY order_date DESC
            LIMIT 14
            """,
        )
        recent_sales = []
        for row in reversed(recent_rows):
            date_text = str(row.get("order_date") or "")
            recent_sales.append({
                "order_date": date_text,
                "date_label": date_text[5:] if len(date_text) >= 10 else date_text,
                "orders": _as_int(row.get("orders")),
                "revenue": _as_float(row.get("revenue")),
                "bar_height": 3,
            })

        payment_rows = query_all(
            "payment mix",
            """
            SELECT
                COALESCE(NULLIF(payment_method, ''), 'Unknown') AS payment_method,
                COUNT(*) AS orders,
                COALESCE(SUM(total), 0) AS revenue
            FROM orders
            WHERE status != 'Cancelled'
            GROUP BY payment_method
            ORDER BY orders DESC
            """,
        )
        payment_mix = [
            {
                "payment_method": row.get("payment_method") or "Unknown",
                "orders": _as_int(row.get("orders")),
                "revenue": _as_float(row.get("revenue")),
            }
            for row in payment_rows
        ]

        status_rows = query_all(
            "status mix",
            """
            SELECT
                COALESCE(NULLIF(status, ''), 'Unknown') AS status,
                COUNT(*) AS orders,
                COALESCE(SUM(total), 0) AS revenue
            FROM orders
            GROUP BY status
            ORDER BY orders DESC
            """,
        )
        status_mix = [
            {
                "status": row.get("status") or "Unknown",
                "orders": _as_int(row.get("orders")),
                "revenue": _as_float(row.get("revenue")),
            }
            for row in status_rows
        ]

        # Prefer full line-item revenue. Some older live databases may not yet
        # contain every fee column, so fall back to the universally available
        # product_name + quantity fields used by packing slips.
        seller_rows = query_all(
            "best sellers with revenue",
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
            """,
        )
        if not seller_rows:
            seller_rows = query_all(
                "best sellers fallback",
                """
                SELECT
                    product_name,
                    COALESCE(SUM(quantity), 0) AS units,
                    0 AS revenue
                FROM order_items
                GROUP BY product_name
                ORDER BY units DESC, product_name
                LIMIT 10
                """,
            )

        best_sellers = [
            {
                "product_name": row.get("product_name") or "Unknown product",
                "units": _as_int(row.get("units")),
                "revenue": _as_float(row.get("revenue")),
            }
            for row in seller_rows
        ]

        products = query_all(
            "inventory",
            """
            SELECT name, category, stock, price, sale_price
            FROM products
            WHERE active = 1
            ORDER BY stock ASC, name
            """,
        )
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

        max_daily_revenue = max([item["revenue"] for item in recent_sales] or [1.0])
        if max_daily_revenue <= 0:
            max_daily_revenue = 1.0
        for item in recent_sales:
            item["bar_height"] = max(3, round(item["revenue"] / max_daily_revenue * 190))

        context = dict(
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

        try:
            return render_template("reports.html", **context)
        except Exception:
            app.logger.exception("Reports template failed; serving safe fallback")
            return render_template_string(
                """
                <!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
                <title>Store Reports | Stage Starz</title>
                <style>body{font-family:system-ui;background:#0c0717;color:#fff;margin:0;padding:24px}.wrap{max-width:900px;margin:auto}.cards{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.card{background:#17102a;border:1px solid #38294a;border-radius:18px;padding:18px}.big{font-size:2rem;font-weight:900}.muted{color:#b8adca}table{width:100%;border-collapse:collapse;margin-top:12px}td,th{padding:10px;border-bottom:1px solid #38294a;text-align:left}@media(max-width:600px){.cards{grid-template-columns:1fr}}</style>
                </head><body><main class="wrap"><h1>📊 Store Reports</h1><p class="muted">Reports are available. A display component was bypassed safely.</p>
                <div class="cards"><div class="card"><div class="big">${{ '%.2f'|format(overview.revenue) }}</div><div class="muted">Revenue</div></div><div class="card"><div class="big">{{ overview.valid_orders }}</div><div class="muted">Orders</div></div><div class="card"><div class="big">${{ '%.2f'|format(overview.average_order) }}</div><div class="muted">Average order</div></div><div class="card"><div class="big">{{ inventory_units }}</div><div class="muted">Inventory units</div></div></div>
                <div class="card" style="margin-top:12px"><h2>Best-Selling Products</h2><table><tr><th>Product</th><th>Units</th><th>Revenue</th></tr>{% for p in best_sellers %}<tr><td>{{ p.product_name }}</td><td>{{ p.units }}</td><td>${{ '%.2f'|format(p.revenue) }}</td></tr>{% else %}<tr><td colspan="3">No sales data yet.</td></tr>{% endfor %}</table></div>
                </main></body></html>
                """,
                **context,
            )

    app.view_functions["reports_dashboard"] = reports_dashboard_postgres_safe
