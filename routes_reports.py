from __future__ import annotations

from datetime import date, timedelta

from flask import render_template, request

from database import get_db
from services import login_required


def _date_range() -> tuple[str, str, str]:
    today = date.today()
    preset = request.args.get("range", "all")
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()

    if start and end:
        return start, end, "custom"
    if preset == "7":
        return (today - timedelta(days=6)).isoformat(), today.isoformat(), preset
    if preset == "30":
        return (today - timedelta(days=29)).isoformat(), today.isoformat(), preset
    if preset == "90":
        return (today - timedelta(days=89)).isoformat(), today.isoformat(), preset
    if preset == "year":
        return date(today.year, 1, 1).isoformat(), today.isoformat(), preset
    return "0001-01-01", "9999-12-31", "all"


def register_report_routes(app):
    @app.route("/admin/reports")
    @login_required
    def admin_reports():
        start, end, selected_range = _date_range()
        connection = get_db()
        params = (start, end)
        valid_order = "status != 'Cancelled' AND substr(created_at,1,10) BETWEEN ? AND ?"

        summary = dict(connection.execute(
            f"""SELECT
                    COUNT(*) AS total_orders,
                    COALESCE(SUM(total),0) AS gross_sales,
                    COALESCE(SUM(CASE WHEN payment_status='Paid' THEN total ELSE 0 END),0) AS paid_sales,
                    COALESCE(SUM(CASE WHEN payment_status!='Paid' THEN total ELSE 0 END),0) AS unpaid_sales,
                    COALESCE(AVG(total),0) AS average_order,
                    COALESCE(SUM(subtotal),0) AS merchandise_sales,
                    COALESCE(SUM(name_fees),0) AS name_fees,
                    COALESCE(SUM(fulfillment_fees),0) AS fulfillment_fees,
                    COALESCE(SUM(shipping),0) AS shipping,
                    COALESCE(SUM(tax),0) AS tax
                FROM orders WHERE {valid_order}""",
            params,
        ).fetchone())

        daily_sales = [dict(row) for row in connection.execute(
            f"""SELECT substr(created_at,1,10) AS sale_date,
                       COUNT(*) AS orders,
                       ROUND(SUM(total),2) AS sales
                FROM orders WHERE {valid_order}
                GROUP BY substr(created_at,1,10)
                ORDER BY sale_date""",
            params,
        ).fetchall()]

        top_products = [dict(row) for row in connection.execute(
            """SELECT oi.product_name,
                      SUM(oi.quantity) AS units,
                      ROUND(SUM(oi.line_total),2) AS sales
               FROM order_items oi
               JOIN orders o ON o.id=oi.order_id
               WHERE o.status!='Cancelled' AND substr(o.created_at,1,10) BETWEEN ? AND ?
               GROUP BY oi.product_name
               ORDER BY sales DESC, units DESC, oi.product_name
               LIMIT 10""",
            params,
        ).fetchall()]

        top_customers = [dict(row) for row in connection.execute(
            """SELECT COALESCE(c.id,0) AS customer_id,
                      o.customer_name AS name,
                      o.customer_email AS email,
                      COUNT(*) AS orders,
                      ROUND(SUM(o.total),2) AS spending
               FROM orders o
               LEFT JOIN customers c ON c.id=o.customer_id
               WHERE o.status!='Cancelled' AND substr(o.created_at,1,10) BETWEEN ? AND ?
               GROUP BY lower(o.customer_email)
               ORDER BY spending DESC, orders DESC
               LIMIT 10""",
            params,
        ).fetchall()]

        status_breakdown = [dict(row) for row in connection.execute(
            """SELECT status, COUNT(*) AS orders, ROUND(SUM(total),2) AS total
               FROM orders
               WHERE substr(created_at,1,10) BETWEEN ? AND ?
               GROUP BY status ORDER BY orders DESC""",
            params,
        ).fetchall()]

        quantity = connection.execute(
            """SELECT COALESCE(SUM(oi.quantity),0) AS units
               FROM order_items oi JOIN orders o ON o.id=oi.order_id
               WHERE o.status!='Cancelled' AND substr(o.created_at,1,10) BETWEEN ? AND ?""",
            params,
        ).fetchone()["units"]
        summary["units_sold"] = quantity
        connection.close()

        max_daily = max((float(row["sales"] or 0) for row in daily_sales), default=0)
        return render_template(
            "reports.html",
            summary=summary,
            daily_sales=daily_sales,
            top_products=top_products,
            top_customers=top_customers,
            status_breakdown=status_breakdown,
            start=start,
            end=end,
            selected_range=selected_range,
            max_daily=max_daily,
        )
