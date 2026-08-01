from __future__ import annotations

import os
import sqlite3
import uuid
from functools import wraps
from pathlib import Path
from typing import Any

from werkzeug.utils import secure_filename

from flask import (
    Flask,
    flash,
    send_from_directory,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "store.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", str(DB_PATH.parent / "uploads")))
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config.update(
    MAX_CONTENT_LENGTH=MAX_IMAGE_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "StageStarz123!")


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
            emoji TEXT NOT NULL DEFAULT '⭐'
        )
        """
    )

    # Safely upgrade existing Railway databases without deleting product data.
    product_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(products)").fetchall()
    }
    if "show_color" not in product_columns:
        cursor.execute(
            "ALTER TABLE products ADD COLUMN show_color INTEGER NOT NULL DEFAULT 1"
        )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    cursor.execute("SELECT COUNT(*) AS count FROM products")
    if cursor.fetchone()["count"] == 0:
        starter_products = [
            (
                "Stage Starz Team Jersey", "Apparel",
                "Moisture-wicking team jersey made for dance, stage, and studio events.",
                32.00, 28.00, 5.00, 14,
                "Youth S,Youth M,Youth L,Adult S,Adult M,Adult L,Adult XL",
                "Black,Purple,Teal", 1, 1, 1, "", "👕"
            ),
            (
                "Signature Dance Jacket", "Apparel",
                "Form-fitting four-way stretch jacket for dancers and team members.",
                55.00, None, 5.00, 9,
                "Youth S,Youth M,Youth L,Adult S,Adult M,Adult L,Adult XL",
                "Black,Purple", 1, 1, 1, "", "🧥"
            ),
            (
                "Stage Starz Duffle Bag", "Bags",
                "Durable dance bag with shoulder strap and room for shoes and apparel.",
                38.00, None, 6.00, 6,
                "One Size", "Black,Purple,Teal", 1, 1, 1, "", "👜"
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO products (
                name, category, description, price, sale_price,
                fulfillment_fee, stock, sizes, colors, show_color,
                allow_name, active, image_url, emoji
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            starter_products,
        )

    defaults = {
        "store_name": "Stardust Ship-it-Shop",
        "order_email": "stagestarzacademy@gmail.com",
        "venmo_username": "@StageStarzDance",
        "name_fee": "10.00",
        "sales_tax_rate": "0.06",
        "customer_shipping_fee": "0.00",
        "allow_customer_shipping": "1",
    }
    for key, value in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )

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
        item["sizes"] = [x.strip() for x in item["sizes"].split(",") if x.strip()]
        item["colors"] = [x.strip() for x in item["colors"].split(",") if x.strip()]
        item["show_color"] = bool(item["show_color"])
        item["allow_name"] = bool(item["allow_name"])
        item["active"] = bool(item["active"])
        products.append(item)
    return products



def allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_uploaded_image(file_storage) -> str:
    if not file_storage or not file_storage.filename:
        return ""
    if not allowed_image(file_storage.filename):
        raise ValueError("Use JPG, JPEG, PNG, WEBP, or GIF images.")
    original = secure_filename(file_storage.filename)
    extension = original.rsplit(".", 1)[1].lower()
    stem = Path(original).stem[:60] or "image"
    filename = f"{stem}-{uuid.uuid4().hex[:10]}.{extension}"
    file_storage.save(UPLOAD_FOLDER / filename)
    return f"/uploads/{filename}"


def delete_uploaded_image(image_url: str) -> None:
    if image_url.startswith("/uploads/"):
        target = UPLOAD_FOLDER / Path(image_url).name
        if target.exists() and target.is_file():
            target.unlink()


@app.errorhandler(413)
def image_too_large(_error):
    flash("The image is too large. Maximum upload size is 10 MB.", "error")
    return redirect(request.referrer or url_for("admin_dashboard"))


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


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/<path:filename>")
def website_file(filename: str):
    """Serve main website pages and shared root-level assets."""
    site_file = BASE_DIR / "site" / filename
    if site_file.exists() and site_file.is_file():
        return send_from_directory(BASE_DIR / "site", filename)

    root_file = BASE_DIR / filename
    if root_file.exists() and root_file.is_file():
        return send_from_directory(BASE_DIR, filename)

    return ("Page not found", 404)


@app.route("/api/products")
def api_products():
    connection = get_db()
    rows = connection.execute(
        "SELECT * FROM products WHERE active = 1 ORDER BY category, name"
    ).fetchall()
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
    products = rows_to_products(rows)
    settings = get_settings()
    return render_template("admin.html", products=products, settings=settings)


@app.route("/admin/media")
@login_required
def media_library():
    files = sorted([{"name": x.name, "url": f"/uploads/{x.name}", "size_kb": round(x.stat().st_size/1024,1)} for x in UPLOAD_FOLDER.iterdir() if x.is_file() and allowed_image(x.name)], key=lambda x: x["name"].lower())
    return render_template("media.html", files=files)


@app.route("/admin/media/upload", methods=["POST"])
@login_required
def media_upload():
    try:
        image_url = save_uploaded_image(request.files.get("image"))
        flash("Image uploaded successfully." if image_url else "Choose an image before uploading.", "success" if image_url else "error")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("media_library"))


@app.route("/admin/media/delete", methods=["POST"])
@login_required
def media_delete():
    image_url = request.form.get("image_url", "")
    connection = get_db()
    in_use = connection.execute("SELECT COUNT(*) AS count FROM products WHERE image_url = ?", (image_url,)).fetchone()["count"]
    connection.close()
    if in_use:
        flash("That image is assigned to a product and cannot be deleted.", "error")
    else:
        delete_uploaded_image(image_url)
        flash("Image deleted.", "success")
    return redirect(url_for("media_library"))


@app.route("/admin/product/save", methods=["POST"])
@login_required
def save_product():
    form = request.form
    product_id = form.get("id", "").strip()
    existing_image_url = form.get("existing_image_url", "").strip()
    image_url = existing_image_url or form.get("image_url", "").strip()
    try:
        uploaded_url = save_uploaded_image(request.files.get("product_image"))
        if uploaded_url:
            image_url = uploaded_url
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("admin_dashboard"))
    if form.get("remove_image") == "on":
        image_url = ""

    values = (
        form.get("name", "").strip(), form.get("category", "").strip(),
        form.get("description", "").strip(), float(form.get("price") or 0),
        float(form["sale_price"]) if form.get("sale_price", "").strip() else None,
        float(form.get("fulfillment_fee") or 0), int(form.get("stock") or 0),
        form.get("sizes", "One Size").strip(), form.get("colors", "Default").strip(),
        1 if form.get("show_color") == "on" else 0,
        1 if form.get("allow_name") == "on" else 0,
        1 if form.get("active") == "on" else 0,
        image_url, form.get("emoji", "⭐").strip() or "⭐",
    )
    connection = get_db()
    if product_id:
        connection.execute("""UPDATE products SET name=?, category=?, description=?, price=?, sale_price=?, fulfillment_fee=?, stock=?, sizes=?, colors=?, show_color=?, allow_name=?, active=?, image_url=?, emoji=? WHERE id=?""", values + (int(product_id),))
    else:
        connection.execute("""INSERT INTO products (name, category, description, price, sale_price, fulfillment_fee, stock, sizes, colors, show_color, allow_name, active, image_url, emoji) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", values)
    connection.commit(); connection.close()
    if existing_image_url and existing_image_url != image_url:
        connection = get_db(); remaining = connection.execute("SELECT COUNT(*) AS count FROM products WHERE image_url = ?", (existing_image_url,)).fetchone()["count"]; connection.close()
        if remaining == 0: delete_uploaded_image(existing_image_url)
    flash("Product saved.", "success")
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
        "store_name",
        "order_email",
        "venmo_username",
        "name_fee",
        "sales_tax_rate",
        "customer_shipping_fee",
        "allow_customer_shipping",
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
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
