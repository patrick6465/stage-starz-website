from __future__ import annotations

import sqlite3

from flask import redirect, render_template, request, session, url_for

from config import ADMIN_PASSWORD, ADMIN_USERNAME, ALLOWED_IMAGE_TYPES, MAX_PRODUCT_IMAGES, ORDER_STATUSES
from database import get_db
from services import build_dashboard, get_settings, login_required, rows_to_products


def register_admin_routes(app):
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        error = ""
        if request.method == "POST":
            if request.form.get("username", "") == ADMIN_USERNAME and request.form.get("password", "") == ADMIN_PASSWORD:
                session["admin_logged_in"] = True
                return redirect(url_for("admin_dashboard"))
            error = "Invalid username or password."
        return render_template("login.html", error=error)

    @app.route("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("admin_login"))

    @app.route("/admin")
    @login_required
    def admin_dashboard():
        connection = get_db()
        rows = connection.execute("SELECT * FROM products ORDER BY category,name").fetchall()
        products = rows_to_products(rows, connection)
        settings = get_settings(connection)
        dashboard = build_dashboard(products, settings)
        connection.close()
        return render_template("admin.html", products=products, settings=settings, dashboard=dashboard, max_product_images=MAX_PRODUCT_IMAGES)

    @app.route("/admin/orders")
    @login_required
    def admin_orders():
        connection = get_db()
        orders = [dict(row) for row in connection.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()]
        for order in orders:
            order["items"] = [dict(row) for row in connection.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)).fetchall()]
        summary_row = connection.execute(
            """SELECT COUNT(*) AS total_orders,
                      COALESCE(SUM(CASE WHEN status NOT IN ('Completed','Cancelled') THEN 1 ELSE 0 END),0) AS open_orders,
                      COALESCE(SUM(CASE WHEN payment_status='Paid' THEN total ELSE 0 END),0) AS paid_revenue,
                      COALESCE(SUM(CASE WHEN payment_status!='Paid' AND status!='Cancelled' THEN total ELSE 0 END),0) AS unpaid_total
               FROM orders"""
        ).fetchone()
        summary = dict(summary_row)
        connection.close()
        return render_template("orders.html", orders=orders, summary=summary, statuses=sorted(ORDER_STATUSES))

    @app.route("/admin/order/<int:order_id>/update", methods=["POST"])
    @login_required
    def update_order(order_id: int):
        status = request.form.get("status", "New")
        status = status if status in ORDER_STATUSES else "New"
        payment_status = "Paid" if request.form.get("payment_status") == "Paid" else "Unpaid"
        connection = get_db()
        connection.execute("UPDATE orders SET status=?,payment_status=? WHERE id=?", (status, payment_status, order_id))
        connection.commit()
        connection.close()
        return redirect(url_for("admin_orders"))

    @app.route("/admin/product/save", methods=["POST"])
    @login_required
    def save_product():
        form = request.form
        product_id = form.get("id", "").strip()
        values = (
            form.get("name", "").strip(), form.get("category", "").strip(), form.get("description", "").strip(),
            float(form.get("price") or 0), float(form["sale_price"]) if form.get("sale_price", "").strip() else None,
            float(form.get("fulfillment_fee") or 0), int(form.get("stock") or 0), form.get("sizes", "One Size").strip(),
            form.get("colors", "Default").strip(), 1 if form.get("show_color") == "on" else 0,
            1 if form.get("allow_name") == "on" else 0, 1 if form.get("active") == "on" else 0,
            form.get("image_url", "").strip(), form.get("emoji", "⭐").strip() or "⭐",
        )
        connection = get_db()
        if product_id:
            connection.execute("UPDATE products SET name=?,category=?,description=?,price=?,sale_price=?,fulfillment_fee=?,stock=?,sizes=?,colors=?,show_color=?,allow_name=?,active=?,image_url=?,emoji=? WHERE id=?", values + (int(product_id),))
            saved_id = int(product_id)
        else:
            cursor = connection.execute("INSERT INTO products (name,category,description,price,sale_price,fulfillment_fee,stock,sizes,colors,show_color,allow_name,active,image_url,emoji) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            saved_id = int(cursor.lastrowid)

        existing = connection.execute("SELECT id FROM product_images WHERE product_id=?", (saved_id,)).fetchall()
        existing_ids = {row["id"] for row in existing}
        remove_ids = {int(x) for x in form.getlist("remove_image") if x.isdigit()} & existing_ids
        for image_id in remove_ids:
            connection.execute("DELETE FROM product_images WHERE id=? AND product_id=?", (image_id, saved_id))
        for image_id in existing_ids - remove_ids:
            try:
                order = max(0, int(form.get(f"image_order_{image_id}", "0")))
            except ValueError:
                order = 0
            connection.execute("UPDATE product_images SET sort_order=? WHERE id=? AND product_id=?", (order, image_id, saved_id))

        remaining_count = connection.execute("SELECT COUNT(*) AS count FROM product_images WHERE product_id=?", (saved_id,)).fetchone()["count"]
        uploads = [file for file in request.files.getlist("image_uploads") if file and file.filename]
        if remaining_count + len(uploads) > MAX_PRODUCT_IMAGES:
            connection.rollback()
            connection.close()
            return (f"Each product may have up to {MAX_PRODUCT_IMAGES} uploaded images.", 400)
        next_order = connection.execute("SELECT COALESCE(MAX(sort_order),-1)+1 AS next_order FROM product_images WHERE product_id=?", (saved_id,)).fetchone()["next_order"]
        for upload in uploads:
            if upload.mimetype not in ALLOWED_IMAGE_TYPES:
                connection.rollback()
                connection.close()
                return ("Unsupported image type. Please upload JPG, PNG, WebP, or GIF.", 400)
            image_bytes = upload.read()
            if image_bytes:
                connection.execute("INSERT INTO product_images (product_id,image_data,image_mime,sort_order,is_primary) VALUES (?,?,?,?,0)", (saved_id, sqlite3.Binary(image_bytes), upload.mimetype, next_order))
                next_order += 1

        primary_raw = form.get("primary_image", "")
        primary_id = int(primary_raw) if primary_raw.isdigit() else None
        valid_ids = {row["id"] for row in connection.execute("SELECT id FROM product_images WHERE product_id=?", (saved_id,)).fetchall()}
        if primary_id not in valid_ids:
            primary_id = min(valid_ids) if valid_ids else None
        connection.execute("UPDATE product_images SET is_primary=0 WHERE product_id=?", (saved_id,))
        if primary_id:
            connection.execute("UPDATE product_images SET is_primary=1 WHERE id=? AND product_id=?", (primary_id, saved_id))
        connection.execute("UPDATE products SET image_data=NULL,image_mime='' WHERE id=?", (saved_id,))
        connection.commit()
        connection.close()
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/product/<int:product_id>/delete", methods=["POST"])
    @login_required
    def delete_product(product_id: int):
        connection = get_db()
        connection.execute("DELETE FROM product_images WHERE product_id=?", (product_id,))
        connection.execute("DELETE FROM products WHERE id=?", (product_id,))
        connection.commit()
        connection.close()
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/settings/save", methods=["POST"])
    @login_required
    def save_settings():
        allowed = {"store_name", "order_email", "venmo_username", "name_fee", "name_max_chars", "name_instructions", "sales_tax_rate", "shipping_mode", "shipping_rate", "free_shipping_threshold", "allow_customer_shipping", "customer_shipping_fee", "low_stock_threshold"}
        connection = get_db()
        for key in allowed:
            value = request.form.get(key, "")
            if key == "allow_customer_shipping":
                value = "1" if request.form.get(key) == "on" else "0"
            connection.execute("INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        connection.commit()
        connection.close()
        return redirect(url_for("admin_dashboard"))
