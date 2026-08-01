from __future__ import annotations

import os
import json
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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS homepage_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
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

    homepage_defaults = {
        "announcement_enabled": "1",
        "announcement_text": "Fall registration is now open!",
        "hero_kicker": "Dance. Grow. Shine.",
        "hero_title": "Where every dancer gets their moment to shine.",
        "hero_subtitle": "Recreational and competitive dance training for ages 3 and up in Temperance, Michigan.",
        "hero_image": "",
        "primary_button_text": "Explore Classes",
        "primary_button_link": "classes.html",
        "secondary_button_text": "Register Now",
        "secondary_button_link": "registration.html",
        "countdown_enabled": "0",
        "countdown_label": "Fall Classes Begin In",
        "countdown_date": "",
    }
    for key, value in homepage_defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO homepage_settings (key, value) VALUES (?, ?)",
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


def get_homepage_settings() -> dict[str, str]:
    connection = get_db()
    rows = connection.execute(
        "SELECT key, value FROM homepage_settings"
    ).fetchall()
    connection.close()
    return {row["key"]: row["value"] for row in rows}


def homepage_runtime_injection(settings: dict[str, str]) -> str:
    payload = json.dumps(settings).replace("</", "<\\/")
    return f"""
<style id="stage-starz-homepage-runtime-styles">
  .ss-countdown {{
    max-width:1180px;margin:24px auto;padding:18px 22px;border-radius:20px;
    color:#fff;text-align:center;
    background:linear-gradient(110deg,#8c3cac,#e91e8c,#20bfc4);
    box-shadow:0 18px 45px rgba(72,28,95,.2)
  }}
  .ss-countdown strong {{font-size:clamp(1.65rem,4vw,3rem);display:block;line-height:1.1}}
  .ss-countdown span {{font-weight:900;letter-spacing:.04em}}
  .ss-admin-link {{
    position:fixed;right:16px;bottom:16px;z-index:9998;
    display:inline-flex;align-items:center;gap:7px;
    padding:9px 13px;border-radius:999px;
    color:#fff!important;background:rgba(12,7,23,.76);
    border:1px solid rgba(255,255,255,.22);
    box-shadow:0 10px 28px rgba(0,0,0,.25);
    backdrop-filter:blur(14px);
    font:800 12px/1 Inter,system-ui,sans-serif;
    text-decoration:none!important;opacity:.72;
    transition:.2s ease
  }}
  .ss-admin-link:hover {{opacity:1;transform:translateY(-2px)}}
  @media(max-width:640px) {{
    .ss-admin-link {{right:10px;bottom:10px;padding:8px 11px}}
  }}
</style>
<script>
(() => {{
  const s = {payload};
  const on = value => value === "1" || value === "true";

  const topbar = document.querySelector(".topbar");
  if (topbar) {{
    if (on(s.announcement_enabled) && s.announcement_text) {{
      topbar.innerHTML = `<span>${{s.announcement_text}}</span>`;
      topbar.style.display = "";
    }} else {{
      topbar.style.display = "none";
    }}
  }}

  const kicker = document.querySelector(".hero .kicker");
  if (kicker && s.hero_kicker) kicker.textContent = s.hero_kicker;

  const title = document.querySelector(".hero h1");
  if (title && s.hero_title) title.textContent = s.hero_title;

  const subtitle = document.querySelector(".hero-copy");
  if (subtitle && s.hero_subtitle) subtitle.textContent = s.hero_subtitle;

  const hero = document.querySelector(".hero");
  if (hero && s.hero_image) {{
    hero.style.backgroundImage =
      `linear-gradient(90deg,rgba(0,0,0,.30),rgba(0,0,0,.90)), url("${{s.hero_image}}")`;
  }}

  const buttons = document.querySelectorAll(".hero .actions a");
  if (buttons[0]) {{
    if (s.primary_button_text) buttons[0].textContent = s.primary_button_text;
    if (s.primary_button_link) buttons[0].href = s.primary_button_link;
  }}
  if (buttons[1]) {{
    if (s.secondary_button_text) buttons[1].textContent = s.secondary_button_text;
    if (s.secondary_button_link) buttons[1].href = s.secondary_button_link;
  }}

  if (!document.querySelector(".ss-admin-link")) {{
    const adminLink = document.createElement("a");
    adminLink.className = "ss-admin-link";
    adminLink.href = "/admin";
    adminLink.setAttribute("aria-label", "Stage Starz administrator login");
    adminLink.innerHTML = "⚙ Admin";
    document.body.appendChild(adminLink);
  }}

  if (on(s.countdown_enabled) && s.countdown_date) {{
    const target = new Date(s.countdown_date + "T00:00:00");
    const panel = document.createElement("section");
    panel.className = "ss-countdown";
    panel.innerHTML = `<span>${{s.countdown_label || "Countdown"}}</span><strong id="ssCountdownValue"></strong>`;
    const heroSection = document.querySelector(".hero");
    if (heroSection) heroSection.insertAdjacentElement("afterend", panel);

    const update = () => {{
      const difference = target.getTime() - Date.now();
      const value = document.getElementById("ssCountdownValue");
      if (!value) return;
      if (difference <= 0) {{
        value.textContent = "Today!";
        return;
      }}
      const days = Math.ceil(difference / 86400000);
      value.textContent = `${{days}} Day${{days === 1 ? "" : "s"}}`;
    }};
    update();
    setInterval(update, 60000);
  }}
}})();
</script>
"""


def log_activity(action: str, detail: str = "") -> None:
    connection = get_db()
    connection.execute(
        "INSERT INTO activity_log (action, detail) VALUES (?, ?)",
        (action, detail),
    )
    connection.commit()
    connection.close()


@app.route("/")
def website_home():
    homepage_path = BASE_DIR / "site" / "index.html"
    if not homepage_path.exists():
        return ("Homepage not found", 404)

    html = homepage_path.read_text(encoding="utf-8")
    injection = homepage_runtime_injection(get_homepage_settings())
    if "</body>" in html:
        html = html.replace("</body>", injection + "\n</body>", 1)
    else:
        html += injection
    return app.response_class(html, mimetype="text/html")


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
    rows = connection.execute(
        "SELECT * FROM products ORDER BY active DESC, category, name"
    ).fetchall()
    connection.close()

    products = rows_to_products(rows)
    active_products = [product for product in products if product["active"]]
    low_stock_products = [
        product for product in active_products
        if 0 < int(product["stock"]) <= 5
    ]
    out_of_stock_products = [
        product for product in active_products
        if int(product["stock"]) <= 0
    ]
    total_units = sum(max(int(product["stock"]), 0) for product in active_products)
    inventory_value = sum(
        max(int(product["stock"]), 0)
        * float(product["sale_price"] if product["sale_price"] is not None else product["price"])
        for product in active_products
    )
    categories = sorted({
        product["category"] for product in active_products if product["category"]
    })
    media_count = sum(
        1 for path in UPLOAD_FOLDER.iterdir()
        if path.is_file() and allowed_image(path.name)
    )

    stats = {
        "active_products": len(active_products),
        "hidden_products": len(products) - len(active_products),
        "low_stock": len(low_stock_products),
        "out_of_stock": len(out_of_stock_products),
        "total_units": total_units,
        "inventory_value": inventory_value,
        "categories": len(categories),
        "media_count": media_count,
    }

    connection = get_db()
    activities = connection.execute(
        "SELECT action, detail, created_at FROM activity_log ORDER BY id DESC LIMIT 8"
    ).fetchall()
    connection.close()

    notifications = []
    if out_of_stock_products:
        notifications.append({
            "level": "danger",
            "title": f"{len(out_of_stock_products)} product(s) out of stock",
            "detail": "Restock or hide these products from the storefront.",
        })
    if low_stock_products:
        notifications.append({
            "level": "warning",
            "title": f"{len(low_stock_products)} low-stock product(s)",
            "detail": "Review inventory before accepting more orders.",
        })
    if media_count == 0:
        notifications.append({
            "level": "info",
            "title": "Media library is empty",
            "detail": "Upload reusable product and website images.",
        })

    return render_template(
        "dashboard.html",
        stats=stats,
        low_stock_products=low_stock_products[:6],
        recent_products=active_products[:6],
        activities=activities,
        notifications=notifications,
        settings=get_settings(),
    )


@app.route("/admin/search")
@login_required
def admin_search():
    query = request.args.get("q", "").strip()
    product_results = []
    page_results = []
    media_results = []

    if query:
        like = f"%{query}%"
        connection = get_db()
        rows = connection.execute(
            """
            SELECT * FROM products
            WHERE name LIKE ? OR category LIKE ? OR description LIKE ?
            ORDER BY active DESC, name
            LIMIT 30
            """,
            (like, like, like),
        ).fetchall()
        connection.close()
        product_results = rows_to_products(rows)

        lower_query = query.lower()
        site_root = BASE_DIR / "site"
        if site_root.exists():
            for path in sorted(site_root.rglob("*.html")):
                title = path.stem.replace("-", " ").replace("_", " ").title()
                if lower_query in title.lower() or lower_query in path.name.lower():
                    page_results.append({
                        "title": title,
                        "url": "/" if path.name == "index.html" else f"/{path.relative_to(site_root).as_posix()}",
                    })
                    if len(page_results) >= 20:
                        break

        for path in sorted(UPLOAD_FOLDER.iterdir()):
            if path.is_file() and allowed_image(path.name) and lower_query in path.name.lower():
                media_results.append({"name": path.name, "url": f"/uploads/{path.name}"})
                if len(media_results) >= 20:
                    break

    return render_template(
        "search.html",
        query=query,
        product_results=product_results,
        page_results=page_results,
        media_results=media_results,
    )


@app.route("/admin/website/homepage")
@login_required
def homepage_editor():
    media_files = sorted(
        [
            {"name": path.name, "url": f"/uploads/{path.name}"}
            for path in UPLOAD_FOLDER.iterdir()
            if path.is_file() and allowed_image(path.name)
        ],
        key=lambda item: item["name"].lower(),
    )
    return render_template(
        "homepage_editor.html",
        homepage=get_homepage_settings(),
        media_files=media_files,
    )


@app.route("/admin/website/homepage/save", methods=["POST"])
@login_required
def save_homepage():
    allowed = {
        "announcement_enabled",
        "announcement_text",
        "hero_kicker",
        "hero_title",
        "hero_subtitle",
        "hero_image",
        "primary_button_text",
        "primary_button_link",
        "secondary_button_text",
        "secondary_button_link",
        "countdown_enabled",
        "countdown_label",
        "countdown_date",
    }

    hero_image = request.form.get("hero_image", "").strip()
    try:
        uploaded = save_uploaded_image(request.files.get("hero_image_upload"))
        if uploaded:
            hero_image = uploaded
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("homepage_editor"))

    values = {
        key: request.form.get(key, "").strip()
        for key in allowed
    }
    values["announcement_enabled"] = (
        "1" if request.form.get("announcement_enabled") == "on" else "0"
    )
    values["countdown_enabled"] = (
        "1" if request.form.get("countdown_enabled") == "on" else "0"
    )
    values["hero_image"] = hero_image

    connection = get_db()
    for key, value in values.items():
        connection.execute(
            """
            INSERT INTO homepage_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )
    connection.commit()
    connection.close()

    log_activity("Homepage updated", "Hero, announcement, buttons, or countdown changed")
    flash("Homepage changes published.", "success")
    return redirect(url_for("homepage_editor"))


@app.route("/admin/store")
@login_required
def store_manager():
    connection = get_db()
    rows = connection.execute(
        "SELECT * FROM products ORDER BY category, name"
    ).fetchall()
    connection.close()
    return render_template(
        "admin.html",
        products=rows_to_products(rows),
        settings=get_settings(),
    )


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
        if image_url:
            log_activity("Image uploaded", Path(image_url).name)
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
        log_activity("Image deleted", Path(image_url).name)
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
    log_activity("Product updated" if product_id else "Product created", form.get("name", "").strip())
    flash("Product saved.", "success")
    return redirect(url_for("store_manager"))


@app.route("/admin/product/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id: int):
    connection = get_db()
    product = connection.execute("SELECT name FROM products WHERE id = ?", (product_id,)).fetchone()
    connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
    connection.commit()
    connection.close()
    log_activity("Product deleted", product["name"] if product else f"Product #{product_id}")
    return redirect(url_for("store_manager"))


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
    log_activity("Store settings updated", "Pricing, payment, or contact settings changed")
    return redirect(url_for("store_manager"))


init_db()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
