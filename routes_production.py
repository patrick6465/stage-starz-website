from __future__ import annotations

from datetime import datetime, timezone

from flask import abort, redirect, render_template, request, url_for

from database import get_db
from email_notifications import send_order_email
from services import get_settings, login_required

PRODUCTION_STAGES = [
    "New",
    "Waiting to Order",
    "Ordered from Manufacturer",
    "Received at Studio",
    "Ready for Pickup",
    "Completed",
]


def ensure_production_schema(connection) -> None:
    connection.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS production_status TEXT NOT NULL DEFAULT 'New'")
    connection.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS production_updated_at TEXT NOT NULL DEFAULT ''")
    connection.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS production_batch TEXT NOT NULL DEFAULT ''")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS production_history (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            old_status TEXT NOT NULL DEFAULT '',
            new_status TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT ''
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_production_history_order ON production_history(order_id,id DESC)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_production_status ON orders(production_status,id DESC)")


def _set_stage(connection, order_ids: list[int], stage: str, note: str = "") -> list[int]:
    if stage not in PRODUCTION_STAGES or not order_ids:
        return []
    changed: list[int] = []
    now = datetime.now(timezone.utc).isoformat()
    marks = ",".join("?" for _ in order_ids)
    rows = connection.execute(
        f"SELECT id,production_status FROM orders WHERE id IN ({marks}) FOR UPDATE", order_ids
    ).fetchall()
    for row in rows:
        old = row["production_status"] or "New"
        if old == stage:
            continue
        connection.execute(
            "UPDATE orders SET production_status=?,production_updated_at=? WHERE id=?",
            (stage, now, row["id"]),
        )
        connection.execute(
            "INSERT INTO production_history(order_id,created_at,old_status,new_status,note) VALUES (?,?,?,?,?)",
            (row["id"], now, old, stage, note[:250]),
        )
        if stage == "Completed":
            connection.execute("UPDATE orders SET status='Completed' WHERE id=?", (row["id"],))
        elif stage == "Ready for Pickup":
            connection.execute("UPDATE orders SET status='Ready' WHERE id=? AND status!='Cancelled'", (row["id"],))
        changed.append(int(row["id"]))
    return changed


def register_production_routes(app):
    @app.route("/admin/production")
    @login_required
    def production_center():
        query = request.args.get("q", "").strip()
        stage = request.args.get("stage", "").strip()
        connection = get_db()
        ensure_production_schema(connection)
        params: list[object] = []
        filters = ["o.status!='Cancelled'"]
        if stage in PRODUCTION_STAGES:
            filters.append("o.production_status=?")
            params.append(stage)
        if query:
            filters.append("(o.customer_name ILIKE ? OR o.customer_email ILIKE ? OR o.order_number ILIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like])
        where = " AND ".join(filters)
        orders = [dict(row) for row in connection.execute(
            f"""SELECT o.*,COALESCE(SUM(i.quantity),0) AS item_count,
                       COALESCE(SUM(CASE WHEN trim(i.requested_name)!='' THEN i.quantity ELSE 0 END),0) AS personalized_count
                FROM orders o LEFT JOIN order_items i ON i.order_id=o.id
                WHERE {where}
                GROUP BY o.id ORDER BY o.id DESC""",
            params,
        ).fetchall()]
        counts = {row["production_status"]: int(row["count"]) for row in connection.execute(
            "SELECT production_status,COUNT(*) AS count FROM orders WHERE status!='Cancelled' GROUP BY production_status"
        ).fetchall()}
        totals = dict(connection.execute("""
            SELECT COALESCE(SUM(i.quantity),0) AS waiting_items,
                   COALESCE(SUM(CASE WHEN o.production_status='Ready for Pickup' THEN 1 ELSE 0 END),0) AS ready_orders,
                   COALESCE(SUM(CASE WHEN o.production_status='Completed' AND left(o.production_updated_at,10)=to_char(CURRENT_DATE,'YYYY-MM-DD') THEN 1 ELSE 0 END),0) AS completed_today
            FROM orders o LEFT JOIN order_items i ON i.order_id=o.id
            WHERE o.status!='Cancelled' AND o.production_status='Waiting to Order'
        """).fetchone())
        connection.commit()
        connection.close()
        return render_template("production.html", orders=orders, stages=PRODUCTION_STAGES, counts=counts, totals=totals, query=query, selected_stage=stage)

    @app.route("/admin/production/update", methods=["POST"])
    @login_required
    def production_update():
        ids = [int(value) for value in request.form.getlist("order_id") if value.isdigit()]
        stage = request.form.get("production_status", "")
        note = request.form.get("note", "").strip()
        connection = get_db()
        ensure_production_schema(connection)
        changed = _set_stage(connection, ids, stage, note)
        settings = get_settings(connection)
        if stage == "Ready for Pickup":
            for order_id in changed:
                order = connection.execute("SELECT customer_email FROM orders WHERE id=?", (order_id,)).fetchone()
                if order and order["customer_email"]:
                    send_order_email(connection, order_id, order["customer_email"], "status_update", settings)
        connection.commit()
        connection.close()
        return redirect(request.referrer or url_for("production_center"))

    @app.route("/admin/production/order/<int:order_id>/update", methods=["POST"])
    @login_required
    def production_order_update(order_id: int):
        connection = get_db()
        ensure_production_schema(connection)
        exists = connection.execute("SELECT id FROM orders WHERE id=?", (order_id,)).fetchone()
        if not exists:
            connection.close()
            abort(404)
        stage = request.form.get("production_status", "")
        changed = _set_stage(connection, [order_id], stage, request.form.get("note", "").strip())
        if changed and stage == "Ready for Pickup":
            settings = get_settings(connection)
            order = connection.execute("SELECT customer_email FROM orders WHERE id=?", (order_id,)).fetchone()
            if order and order["customer_email"]:
                send_order_email(connection, order_id, order["customer_email"], "status_update", settings)
        connection.commit()
        connection.close()
        return redirect(request.referrer or url_for("production_center"))

    @app.route("/admin/production/manufacturer-sheet")
    @login_required
    def manufacturer_sheet():
        stage = request.args.get("stage", "Waiting to Order")
        if stage not in PRODUCTION_STAGES:
            stage = "Waiting to Order"
        connection = get_db()
        ensure_production_schema(connection)
        items = [dict(row) for row in connection.execute("""
            SELECT i.product_name,i.size,i.color,SUM(i.quantity) AS quantity
            FROM order_items i JOIN orders o ON o.id=i.order_id
            WHERE o.status!='Cancelled' AND o.production_status=?
            GROUP BY i.product_name,i.size,i.color
            ORDER BY i.product_name,i.size,i.color
        """, (stage,)).fetchall()]
        names = [dict(row) for row in connection.execute("""
            SELECT o.order_number,o.customer_name,i.product_name,i.size,i.color,i.requested_name,i.quantity
            FROM order_items i JOIN orders o ON o.id=i.order_id
            WHERE o.status!='Cancelled' AND o.production_status=? AND trim(i.requested_name)!=''
            ORDER BY i.product_name,i.requested_name
        """, (stage,)).fetchall()]
        settings = get_settings(connection)
        connection.close()
        return render_template("manufacturer_sheet.html", items=items, names=names, stage=stage, settings=settings, generated_at=datetime.now().strftime("%B %d, %Y"))
