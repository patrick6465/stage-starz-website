from __future__ import annotations

import os
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "store.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "StageStarz123!")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            price REAL NOT NULL DEFAULT 0,
            sale_price REAL,
            fulfillment_fee REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            sizes TEXT NOT NULL DEFAULT 'One Size',
            colors TEXT NOT NULL DEFAULT 'Default',
            show_color INTEGER NOT NULL DEFAULT 1,
            allow_name INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            image_url TEXT NOT NULL DEFAULT '',
            emoji TEXT NOT NULL DEFAULT '⭐',
            image_data BLOB,
            image_mime TEXT NOT NULL DEFAULT ''
        )
        """
    )
    product_columns = {row["name"] for row in cursor.execute("PRAGMA table_info(products)").fetchall()}
    upgrades = {
        "show_color": "ALTER TABLE products ADD COLUMN show_color INTEGER NOT NULL DEFAULT 1",
        "image_data": "ALTER TABLE products ADD COLUMN image_data BLOB",
        "image_mime": "ALTER TABLE products ADD COLUMN image_mime TEXT NOT NULL DEFAULT ''",
    }
    for column, statement in upgrades.items():
        if column not in product_columns:
            cursor.execute(statement)

    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    cursor.execute("SELECT COUNT(*) AS count FROM products")
    if cursor.fetchone()["count"] == 0:
        starter_products = [
            ("Stage Starz Team Jersey", "Apparel", "Moisture-wicking team jersey made for dance, stage, and studio events.", 32.00, 28.00, 5.00, 14, "Youth S,Youth M,Youth L,Adult S,Adult M,Adult L,Adult XL", "Black,Purple,Teal", 1, 1, 1, "", "👕"),
            ("Signature Dance Jacket", "Apparel", "Form-fitting four-way stretch jacket for dancers and team members.", 55.00, None, 5.00, 9, "Youth S,Youth M,Youth L,Adult S,Adult M,Adult L,Adult XL", "Black,Purple", 1, 1, 1, "", "🧥"),
            ("Stage Starz Duffle Bag", "Bags", "Durable dance bag with shoulder strap and room for shoes and apparel.", 38.00, None, 6.00, 6, "One Size", "Black,Purple,Teal", 1, 1, 1, "", "👜"),
        ]
        cursor.executemany(
            """
            INSERT INTO products (
                name, category, description, price, sale_price, fulfillment_fee,
                stock, sizes, colors, show_color, allow_name, active, image_url, emoji
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            starter_products,
        )

    defaults = {
        "store_name": "Stardust Ship-it-Shop",
        "order_email": "stagestarzacademy@gmail.com",
        "venmo_username": "@StageStarzDance",
        "name_fee": "10.00",
        "name_max_chars": "20",
        "name_instructions": "Enter the name exactly as you want it printed.",
        "sales_tax_rate": "0.06",
        "shipping_mode": "per_item",
        "shipping_rate": "5.00",
        "free_shipping_threshold": "100.00",
        "allow_customer_shipping": "1",
        "customer_shipping_fee": "0.00",
    }
    for key, value in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    connection.commit()
    connection.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def rows_to_products(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    products = []
    for row in rows:
        item = dict(row)
        image_data = item.pop("image_data", None)
        item.pop("image_mime", None)
        item["external_image_url"] = item.get("image_url", "")
        item["has_uploaded_image"] = bool(image_data)
        if image_data:
            item["image_url"] = url_for("product_image", product_id=item["id"])
        item["sizes"] = [x.strip() for x in item["sizes"].split(",") if x.strip()]
        item["colors"] = [x.strip() for x in item["colors"].split(",") if x.strip()]
        item["show_color"] = bool(item["show_color"])
        item["allow_name"] = bool(item["allow_name"])
        item["active"] = bool(item["active"])
        products.append(item)
    return products


def get_settings() -> dict[str, str]:
    connection = get_db()
    rows = connection.execute("SELECT key, value FROM settings").fetchall()
    connection.close()
    return {row["key"]: row["value"] for row in rows}


@app.route("/")
def website_home():
    return send_from_directory(BASE_DIR / "site", "index.html")


@app.route("/health")
def health_check():
    return jsonify({"status": "ok"})


@app.route("/store")
def storefront():
    return render_template("store.html")


@app.route("/product-image/<int:product_id>")
def product_image(product_id: int):
    connection = get_db()
    row = connection.execute("SELECT image_data, image_mime FROM products WHERE id = ?", (product_id,)).fetchone()
    connection.close()
    if not row or not row["image_data"]:
        abort(404)
    return Response(row["image_data"], mimetype=row["image_mime"] or "application/octet-stream", headers={"Cache-Control": "public, max-age=3600"})


@app.route("/<path:filename>")
def website_file(filename: str):
    requested = BASE_DIR / "site" / filename
    if requested.exists() and requested.is_file():
        return send_from_directory(BASE_DIR / "site", filename)
    return ("Page not found", 404)


@app.route("/api/products")
def api_products():
    connection = get_db()
    rows = connection.execute("SELECT * FROM products WHERE active = 1 ORDER BY category, name").fetchall()
    connection.close()
    return jsonify(rows_to_products(rows))


@app.route("/api/settings")
def api_settings():
    return jsonify(get_settings())


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
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
    rows = connection.execute("SELECT * FROM products ORDER BY category, name").fetchall()
    connection.close()
    return render_template("admin.html", products=rows_to_products(rows), settings=get_settings())


@app.route("/admin/product/save", methods=["POST"])
@login_required
def save_product():
    form = request.form
    product_id = form.get("id", "").strip()
    values = (
        form.get("name", "").strip(),
        form.get("category", "").strip(),
        form.get("description", "").strip(),
        float(form.get("price") or 0),
        float(form["sale_price"]) if form.get("sale_price", "").strip() else None,
        float(form.get("fulfillment_fee") or 0),
        int(form.get("stock") or 0),
        form.get("sizes", "One Size").strip(),
        form.get("colors", "Default").strip(),
        1 if form.get("show_color") == "on" else 0,
        1 if form.get("allow_name") == "on" else 0,
        1 if form.get("active") == "on" else 0,
        form.get("image_url", "").strip(),
        form.get("emoji", "⭐").strip() or "⭐",
    )
    connection = get_db()
    if product_id:
        connection.execute(
            """
            UPDATE products SET name=?, category=?, description=?, price=?, sale_price=?,
                fulfillment_fee=?, stock=?, sizes=?, colors=?, show_color=?, allow_name=?,
                active=?, image_url=?, emoji=? WHERE id=?
            """,
            values + (int(product_id),),
        )
        saved_id = int(product_id)
    else:
        cursor = connection.execute(
            """
            INSERT INTO products (
                name, category, description, price, sale_price, fulfillment_fee,
                stock, sizes, colors, show_color, allow_name, active, image_url, emoji
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        saved_id = int(cursor.lastrowid)

    upload = request.files.get("image_upload")
    if form.get("remove_uploaded_image") == "1":
        connection.execute("UPDATE products SET image_data = NULL, image_mime = '' WHERE id = ?", (saved_id,))
    elif upload and upload.filename:
        if upload.mimetype not in ALLOWED_IMAGE_TYPES:
            connection.close()
            return ("Unsupported image type. Please upload JPG, PNG, WebP, or GIF.", 400)
        image_bytes = upload.read()
        if not image_bytes:
            connection.close()
            return ("The uploaded image was empty.", 400)
        connection.execute(
            "UPDATE products SET image_data = ?, image_mime = ? WHERE id = ?",
            (sqlite3.Binary(image_bytes), upload.mimetype, saved_id),
        )

    connection.commit()
    connection.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/product/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id: int):
    connection = get_db()
    connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
    connection.commit()
    connection.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/settings/save", methods=["POST"])
@login_required
def save_settings():
    allowed = {
        "store_name", "order_email", "venmo_username", "name_fee",
        "name_max_chars", "name_instructions", "sales_tax_rate",
        "shipping_mode", "shipping_rate", "free_shipping_threshold",
        "allow_customer_shipping", "customer_shipping_fee",
    }
    connection = get_db()
    for key in allowed:
        value = request.form.get(key, "")
        if key == "allow_customer_shipping":
            value = "1" if request.form.get(key) == "on" else "0"
        connection.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )
    connection.commit()
    connection.close()
    return redirect(url_for("admin_dashboard"))


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
