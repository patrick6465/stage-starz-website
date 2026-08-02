from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    ALLOWED_IMAGE_EXTENSIONS,
    BASE_DIR,
    DATABASE_URL,
    FLASK_DEBUG,
    FLASK_ENV,
    MAX_IMAGE_BYTES,
    PORT,
    SECRET_KEY,
    SQLITE_DB_PATH,
    UPLOAD_FOLDER,
    USE_POSTGRES,
)
from database import get_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("stage_starz")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    MAX_CONTENT_LENGTH=MAX_IMAGE_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=FLASK_ENV == "production",
)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


ROLE_DEFINITIONS = {
    "owner": {"label":"Owner","description":"Full access to every module.","permissions":{"*"}},
    "office_staff": {"label":"Office Staff","description":"Customers, families, students, orders, content and reports.","permissions":{"dashboard","families","customers","students","orders","website","announcements","media","search","reports"}},
    "teacher": {"label":"Teacher","description":"Student and family access. Classes and attendance come next.","permissions":{"dashboard","families","students","search"}},
    "store_manager": {"label":"Store Manager","description":"Store, inventory, orders, customers, media and reports.","permissions":{"dashboard","store","orders","customers","reports","media","search"}},
}

def current_admin():
    user_id=session.get("admin_user_id")
    if not user_id: return None
    connection=get_db()
    row=connection.execute("SELECT id,username,display_name,email,role,active FROM admin_users WHERE id=?",(int(user_id),)).fetchone()
    connection.close()
    return dict(row) if row else None

def has_permission(permission):
    info=ROLE_DEFINITIONS.get(session.get("admin_role",""))
    return bool(info and ("*" in info["permissions"] or permission in info["permissions"]))

def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args,**kwargs):
            if not session.get("admin_logged_in"): return redirect(url_for("admin_login"))
            if not has_permission(permission):
                flash("You do not have permission to open that module.","error")
                return redirect(url_for("admin_dashboard"))
            return view(*args,**kwargs)
        return wrapped
    return decorator

def rows_to_products(rows: list[Any]) -> list[dict[str, Any]]:
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


@app.context_processor
def inject_access_context():
    return {"has_permission":has_permission,"current_admin_user":current_admin(),"role_definitions":ROLE_DEFINITIONS}

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


MIGRATION_REGISTRY = [
    {
        "key": "001_core_store",
        "title": "Core Store Schema",
        "description": "Products, settings, activity history, and homepage settings.",
        "required_tables": [
            "products", "settings", "activity_log", "homepage_settings"
        ],
        "required_columns": {},
    },
    {
        "key": "002_orders",
        "title": "Orders and Order Items",
        "description": "Persistent customer orders and line items.",
        "required_tables": ["orders", "order_items"],
        "required_columns": {
            "orders": [
                "order_number", "customer_name", "customer_email",
                "total", "status", "created_at"
            ],
        },
    },
    {
        "key": "003_announcements",
        "title": "Announcement Manager",
        "description": "Scheduled homepage announcements and calls to action.",
        "required_tables": ["announcements"],
        "required_columns": {
            "announcements": [
                "title", "message", "priority", "active",
                "start_date", "end_date"
            ],
        },
    },
    {
        "key": "004_postgres_dates",
        "title": "PostgreSQL Date Normalization",
        "description": "Converts operational created_at fields to timestamp types.",
        "required_tables": ["orders", "activity_log", "announcements"],
        "required_columns": {
            "orders": ["created_at"],
            "activity_log": ["created_at"],
            "announcements": ["created_at"],
        },
    },
    {
        "key": "005_customer_crm",
        "title": "Customer CRM",
        "description": "Customer profiles, lifetime value, tags, notes, and timelines.",
        "required_tables": ["customers", "customer_notes"],
        "required_columns": {
            "customers": [
                "name", "email", "phone", "status", "tags", "notes",
                "order_count", "lifetime_value", "last_order_at"
            ],
        },
    },
    {
        "key": "006_family_foundation",
        "title": "Family Foundation",
        "description": "Family households, member links, notes, and combined metrics.",
        "required_tables": ["families", "family_notes"],
        "required_columns": {
            "customers": ["family_id"],
            "families": [
                "family_name", "primary_email", "primary_phone",
                "customer_count", "order_count", "lifetime_value"
            ],
        },
    },
    {
        "key": "007_migration_center",
        "title": "Migration Center",
        "description": "Schema version history, diagnostics, and verification.",
        "required_tables": ["schema_migrations"],
        "required_columns": {
            "schema_migrations": [
                "migration_key", "title", "status", "applied_at"
            ],
        },
    },
    {
        "key": "008_student_foundation",
        "title": "Student Foundation",
        "description": "Student profiles, family links, photos, sizing, status, and notes.",
        "required_tables": ["students", "student_notes"],
        "required_columns": {
            "students": [
                "family_id", "first_name", "last_name", "preferred_name",
                "birth_date", "status", "competition_team", "photo_url",
                "costume_size", "shoe_size", "medical_notes", "tags"
            ],
        },
    },
    {
        "key": "009_roles_permissions",
        "title": "Users, Roles, and Permissions",
        "description": "Administrator accounts, role-based access, and login history.",
        "required_tables": ["admin_users", "admin_login_history"],
        "required_columns": {"admin_users": ["username","display_name","password_hash","role","active","last_login_at"]},
    },
]


def get_database_tables(connection) -> set[str]:
    if connection.backend == "postgresql":
        rows = connection.execute(
            """
            SELECT table_name AS name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
    return {row["name"] for row in rows}


def get_table_columns(connection, table_name: str) -> dict[str, str]:
    if connection.backend == "postgresql":
        rows = connection.execute(
            """
            SELECT column_name AS name, data_type AS type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = ?
            ORDER BY ordinal_position
            """,
            (table_name,),
        ).fetchall()
    else:
        rows = connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    return {
        row["name"]: str(row.get("type", "") if isinstance(row, dict) else row["type"])
        for row in rows
    }


def inspect_migration(connection, migration: dict[str, Any]) -> dict[str, Any]:
    tables = get_database_tables(connection)
    missing_tables = [
        table for table in migration["required_tables"]
        if table not in tables
    ]
    missing_columns = {}

    for table_name, columns in migration["required_columns"].items():
        if table_name not in tables:
            missing_columns[table_name] = list(columns)
            continue
        existing = get_table_columns(connection, table_name)
        absent = [column for column in columns if column not in existing]
        if absent:
            missing_columns[table_name] = absent

    healthy = not missing_tables and not missing_columns
    return {
        **migration,
        "healthy": healthy,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
    }


def record_verified_migrations() -> None:
    """Record verified migrations without altering business data."""
    connection = get_db()
    try:
        for migration in MIGRATION_REGISTRY:
            inspection = inspect_migration(connection, migration)
            if inspection["healthy"]:
                connection.execute(
                    """
                    INSERT INTO schema_migrations (
                        migration_key, title, description,
                        status, execution_ms, details
                    ) VALUES (?, ?, ?, 'applied', 0, ?)
                    ON CONFLICT(migration_key) DO UPDATE SET
                        title=excluded.title,
                        description=excluded.description,
                        status='applied',
                        details=excluded.details
                    """,
                    (
                        migration["key"],
                        migration["title"],
                        migration["description"],
                        "Verified from current database schema",
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        logger.exception("Migration verification recording failed")
    finally:
        connection.close()


def infer_family_name(customer_name: str, email: str) -> str:
    cleaned_name = " ".join((customer_name or "").split())
    if cleaned_name:
        parts = cleaned_name.split()
        if len(parts) >= 2:
            return f"The {parts[-1]} Family"
        return f"{parts[0]} Family"

    email_name = (email or "").split("@", 1)[0].replace(".", " ").replace("_", " ")
    email_name = " ".join(part.capitalize() for part in email_name.split() if part)
    return f"{email_name or 'Stage Starz'} Family"


def refresh_family_metrics(family_id: int) -> None:
    connection = get_db()
    summary = connection.execute(
        """
        SELECT
            COUNT(DISTINCT c.id) AS customer_count,
            COALESCE(SUM(c.order_count), 0) AS order_count,
            COALESCE(SUM(c.lifetime_value), 0) AS lifetime_value,
            MAX(c.last_order_at) AS last_activity_at,
            MAX(c.phone) AS primary_phone,
            MAX(c.email) AS primary_email
        FROM customers c
        WHERE c.family_id = ?
        """,
        (family_id,),
    ).fetchone()

    connection.execute(
        """
        UPDATE families SET
            customer_count=?,
            order_count=?,
            lifetime_value=?,
            last_activity_at=?,
            primary_phone=?,
            primary_email=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (
            int(summary["customer_count"] or 0),
            int(summary["order_count"] or 0),
            float(summary["lifetime_value"] or 0),
            summary["last_activity_at"],
            summary["primary_phone"] or "",
            summary["primary_email"] or "",
            family_id,
        ),
    )
    connection.commit()
    connection.close()


def ensure_family_for_customer(customer_id: int) -> int | None:
    connection = get_db()
    customer = connection.execute(
        """
        SELECT id, name, email, phone, family_id
        FROM customers
        WHERE id = ?
        """,
        (customer_id,),
    ).fetchone()

    if not customer:
        connection.close()
        return None

    if customer["family_id"]:
        family_id = int(customer["family_id"])
        connection.close()
        refresh_family_metrics(family_id)
        return family_id

    email = (customer["email"] or "").strip().lower()
    phone = (customer["phone"] or "").strip()

    family = None
    if email:
        family = connection.execute(
            """
            SELECT id
            FROM families
            WHERE LOWER(primary_email) = ?
            ORDER BY id
            LIMIT 1
            """,
            (email,),
        ).fetchone()

    if not family and phone:
        family = connection.execute(
            """
            SELECT id
            FROM families
            WHERE primary_phone = ?
            ORDER BY id
            LIMIT 1
            """,
            (phone,),
        ).fetchone()

    if family:
        family_id = int(family["id"])
    else:
        insert_sql = """
            INSERT INTO families (
                family_name, primary_email, primary_phone
            ) VALUES (?, ?, ?)
        """
        if connection.backend == "postgresql":
            insert_sql += " RETURNING id"

        cursor = connection.execute(
            insert_sql,
            (
                infer_family_name(customer["name"], customer["email"]),
                email,
                phone,
            ),
        )
        family_id = (
            int(cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(cursor.lastrowid)
        )

    connection.execute(
        "UPDATE customers SET family_id=? WHERE id=?",
        (family_id, customer_id),
    )
    connection.commit()
    connection.close()

    refresh_family_metrics(family_id)
    return family_id


def backfill_families_from_customers() -> None:
    """Assign customers to families without blocking application startup."""
    connection = get_db()
    try:
        customer_rows = connection.execute(
            """
            SELECT id
            FROM customers
            ORDER BY id
            """
        ).fetchall()
    finally:
        connection.close()

    for row in customer_rows:
        try:
            ensure_family_for_customer(int(row["id"]))
        except Exception:
            logger.exception(
                "Family assignment failed for customer %s",
                row["id"],
            )


def backfill_customers_from_orders() -> None:
    """Refresh CRM customers without blocking application startup."""
    connection = get_db()
    try:
        rows = connection.execute(
            """
            SELECT
                LOWER(TRIM(customer_email)) AS email_key,
                MAX(customer_name) AS customer_name,
                MAX(customer_phone) AS customer_phone,
                COUNT(*) AS order_count,
                COALESCE(SUM(total), 0) AS lifetime_value,
                MAX(created_at) AS last_order_at
            FROM orders
            WHERE status != 'Cancelled'
              AND TRIM(customer_email) != ''
            GROUP BY LOWER(TRIM(customer_email))
            """
        ).fetchall()

        for customer in rows:
            connection.execute(
                """
                INSERT INTO customers (
                    name, email, phone, order_count,
                    lifetime_value, last_order_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(email) DO UPDATE SET
                    name=excluded.name,
                    phone=excluded.phone,
                    order_count=excluded.order_count,
                    lifetime_value=excluded.lifetime_value,
                    last_order_at=excluded.last_order_at,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    customer["customer_name"] or "Customer",
                    customer["email_key"],
                    customer["customer_phone"] or "",
                    int(customer["order_count"] or 0),
                    float(customer["lifetime_value"] or 0),
                    customer["last_order_at"],
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        logger.exception("Customer CRM backfill failed")
    finally:
        connection.close()


def sync_customer_from_email(email: str) -> None:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return

    connection = get_db()
    summary = connection.execute(
        """
        SELECT
            MAX(customer_name) AS customer_name,
            MAX(customer_email) AS customer_email,
            MAX(customer_phone) AS customer_phone,
            COUNT(*) AS order_count,
            COALESCE(SUM(total), 0) AS lifetime_value,
            MAX(created_at) AS last_order_at
        FROM orders
        WHERE status != 'Cancelled'
          AND LOWER(TRIM(customer_email)) = ?
        """,
        (normalized_email,),
    ).fetchone()

    if summary and int(summary["order_count"] or 0) > 0:
        connection.execute(
            """
            INSERT INTO customers (
                name, email, phone, order_count,
                lifetime_value, last_order_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(email) DO UPDATE SET
                name=excluded.name,
                phone=excluded.phone,
                order_count=excluded.order_count,
                lifetime_value=excluded.lifetime_value,
                last_order_at=excluded.last_order_at,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                summary["customer_name"] or "Customer",
                normalized_email,
                summary["customer_phone"] or "",
                int(summary["order_count"] or 0),
                float(summary["lifetime_value"] or 0),
                summary["last_order_at"],
            ),
        )
        connection.commit()

    customer = connection.execute(
        "SELECT id, family_id FROM customers WHERE email = ?",
        (normalized_email,),
    ).fetchone()
    connection.close()

    if customer:
        family_id = ensure_family_for_customer(int(customer["id"]))
        if family_id:
            refresh_family_metrics(family_id)


def get_active_announcement() -> dict[str, Any] | None:
    today = date.today().isoformat()
    connection = get_db()
    row = connection.execute(
        """
        SELECT * FROM announcements
        WHERE active = 1
          AND (start_date = '' OR start_date <= ?)
          AND (end_date = '' OR end_date >= ?)
        ORDER BY priority DESC, id DESC
        LIMIT 1
        """,
        (today, today),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def homepage_runtime_injection(settings: dict[str, str], announcement: dict[str, Any] | None = None) -> str:
    payload = json.dumps(settings).replace("</", "<\\/")
    announcement_payload = json.dumps(announcement or {}).replace("</", "<\\/")
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
  const announcement = {announcement_payload};
  const on = value => value === "1" || value === "true";

  const topbar = document.querySelector(".topbar");
  if (topbar) {{
    if (announcement.message) {{
      const action = announcement.button_text && announcement.button_link
        ? ` <a href="${{announcement.button_link}}" style="color:#fff;text-decoration:underline;font-weight:900">${{announcement.button_text}}</a>`
        : "";
      topbar.innerHTML = `<span>${{announcement.message}}${{action}}</span>`;
      topbar.style.display = "";
    }} else if (on(s.announcement_enabled) && s.announcement_text) {{
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


@app.route("/health")
def health_check():
    """Railway liveness check: confirms the web process is accepting requests."""
    return jsonify({
        "status": "ok",
        "service": "stage-starz-website",
    }), 200


@app.route("/ready")
def readiness_check():
    """Readiness diagnostic: verifies the configured database connection."""
    backend = "postgresql" if USE_POSTGRES else "sqlite"
    connection = None
    try:
        connection = get_db()
        connection.execute("SELECT 1 AS ok").fetchone()
        return jsonify({
            "status": "ready",
            "database": "connected",
            "backend": backend,
        }), 200
    except Exception as error:
        logger.exception("Database readiness check failed")
        return jsonify({
            "status": "not_ready",
            "database": "unavailable",
            "backend": backend,
            "error": type(error).__name__,
        }), 503
    finally:
        if connection is not None:
            connection.close()


@app.errorhandler(500)
def internal_server_error(error):
    logger.exception(
        "Unhandled server error on %s %s",
        request.method,
        request.path,
        exc_info=error,
    )
    return (
        render_template(
            "500.html",
            request_id=datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        ),
        500,
    )


@app.route("/")
def website_home():
    homepage_path = BASE_DIR / "site" / "index.html"
    if not homepage_path.exists():
        return ("Homepage not found", 404)

    html = homepage_path.read_text(encoding="utf-8")
    injection = homepage_runtime_injection(
        get_homepage_settings(),
        get_active_announcement(),
    )
    if "</body>" in html:
        html = html.replace("</body>", injection + "\n</body>", 1)
    else:
        html += injection
    return app.response_class(html, mimetype="text/html")


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


@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        username=request.form.get("username","").strip()
        password=request.form.get("password","")
        connection=get_db()
        user=connection.execute("SELECT * FROM admin_users WHERE LOWER(username)=LOWER(?) AND active=1",(username,)).fetchone()
        success=bool(user and user["password_hash"] and check_password_hash(user["password_hash"],password))
        if not success and username==ADMIN_USERNAME and password==ADMIN_PASSWORD:
            user=connection.execute("SELECT * FROM admin_users WHERE username=?",(ADMIN_USERNAME,)).fetchone()
            password_hash=generate_password_hash(ADMIN_PASSWORD)
            if user:
                connection.execute("UPDATE admin_users SET password_hash=?,role='owner',active=1,updated_at=CURRENT_TIMESTAMP WHERE id=?",(password_hash,user["id"]))
                user=connection.execute("SELECT * FROM admin_users WHERE id=?",(user["id"],)).fetchone()
            else:
                sql="INSERT INTO admin_users (username,display_name,password_hash,role,active) VALUES (?,?,?,'owner',1)"
                if connection.backend=="postgresql": sql+=" RETURNING id"
                cur=connection.execute(sql,(ADMIN_USERNAME,"Stage Starz Owner",password_hash))
                uid=cur.fetchone()["id"] if connection.backend=="postgresql" else cur.lastrowid
                user=connection.execute("SELECT * FROM admin_users WHERE id=?",(uid,)).fetchone()
            success=True
        connection.execute("INSERT INTO admin_login_history (admin_user_id,username,success,ip_address,user_agent) VALUES (?,?,?,?,?)",(user["id"] if user else None,username,1 if success else 0,request.headers.get("X-Forwarded-For",request.remote_addr or "")[:200],request.headers.get("User-Agent","")[:500]))
        if success and user:
            connection.execute("UPDATE admin_users SET last_login_at=CURRENT_TIMESTAMP WHERE id=?",(user["id"],))
            connection.commit(); connection.close()
            session.clear()
            session.update(admin_logged_in=True,admin_user_id=int(user["id"]),admin_username=user["username"],admin_display_name=user["display_name"],admin_role=user["role"])
            return redirect(url_for("admin_dashboard"))
        connection.commit(); connection.close()
        flash("Invalid username or password.","error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/system/users")
@permission_required("users")
def admin_users():
    connection=get_db()
    users=connection.execute("SELECT id,username,display_name,email,role,active,last_login_at,created_at FROM admin_users ORDER BY active DESC,display_name").fetchall()
    history=connection.execute("SELECT username,success,ip_address,created_at FROM admin_login_history ORDER BY id DESC LIMIT 20").fetchall()
    connection.close()
    return render_template("admin_users.html",users=[dict(r) for r in users],login_history=[dict(r) for r in history],roles=ROLE_DEFINITIONS,current_user_id=session.get("admin_user_id"))

@app.route("/admin/system/users/save",methods=["POST"])
@permission_required("users")
def save_admin_user():
    f=request.form; uid=f.get("id","").strip(); username=f.get("username","").strip(); name=f.get("display_name","").strip(); email=f.get("email","").strip().lower(); role=f.get("role","office_staff").strip(); password=f.get("password",""); active=1 if f.get("active")=="on" else 0
    if role not in ROLE_DEFINITIONS or not username or not name:
        flash("Valid username, display name, and role are required.","error"); return redirect(url_for("admin_users"))
    c=get_db()
    try:
        if uid:
            vals=[username,name,email,role,active]; sql="UPDATE admin_users SET username=?,display_name=?,email=?,role=?,active=?,updated_at=CURRENT_TIMESTAMP"
            if password: sql+=",password_hash=?"; vals.append(generate_password_hash(password))
            sql+=" WHERE id=?"; vals.append(int(uid)); c.execute(sql,tuple(vals))
        else:
            if not password: flash("A password is required for a new user.","error"); c.close(); return redirect(url_for("admin_users"))
            c.execute("INSERT INTO admin_users (username,display_name,email,password_hash,role,active) VALUES (?,?,?,?,?,?)",(username,name,email,generate_password_hash(password),role,active))
        c.commit()
    except Exception:
        c.rollback(); c.close(); logger.exception("Administrator save failed"); flash("That username may already exist.","error"); return redirect(url_for("admin_users"))
    c.close(); flash("Administrator account saved.","success"); return redirect(url_for("admin_users"))

@app.route("/admin/system/users/<int:user_id>/toggle",methods=["POST"])
@permission_required("users")
def toggle_admin_user(user_id):
    if int(session.get("admin_user_id") or 0)==user_id:
        flash("You cannot deactivate your own account.","error"); return redirect(url_for("admin_users"))
    c=get_db(); u=c.execute("SELECT active FROM admin_users WHERE id=?",(user_id,)).fetchone()
    if u: c.execute("UPDATE admin_users SET active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(0 if u["active"] else 1,user_id)); c.commit()
    c.close(); return redirect(url_for("admin_users"))


@app.route("/admin/system/migrations")
@login_required
def migration_center():
    record_verified_migrations()

    connection = get_db()
    migration_rows = connection.execute(
        """
        SELECT migration_key, title, description, status,
               applied_at, execution_ms, details
        FROM schema_migrations
        ORDER BY migration_key
        """
    ).fetchall()
    applied_map = {
        row["migration_key"]: dict(row)
        for row in migration_rows
    }

    inspections = [
        inspect_migration(connection, migration)
        for migration in MIGRATION_REGISTRY
    ]

    tables = sorted(get_database_tables(connection))
    table_diagnostics = []
    for table_name in tables:
        columns = get_table_columns(connection, table_name)
        try:
            count = connection.execute(
                f"SELECT COUNT(*) AS count FROM {table_name}"
            ).fetchone()["count"]
        except Exception:
            connection.rollback()
            count = "Unavailable"
        table_diagnostics.append({
            "name": table_name,
            "column_count": len(columns),
            "record_count": count,
            "columns": columns,
        })

    backend = connection.backend
    connection.close()

    migrations = []
    for inspection in inspections:
        history = applied_map.get(inspection["key"])
        migrations.append({
            **inspection,
            "recorded": bool(history),
            "history": history,
            "state": (
                "Applied"
                if inspection["healthy"] and history
                else "Verified"
                if inspection["healthy"]
                else "Attention Required"
            ),
        })

    summary = {
        "total": len(migrations),
        "healthy": sum(1 for item in migrations if item["healthy"]),
        "attention": sum(1 for item in migrations if not item["healthy"]),
        "tables": len(tables),
        "backend": backend,
    }

    return render_template(
        "migration_center.html",
        migrations=migrations,
        summary=summary,
        table_diagnostics=table_diagnostics,
    )


@app.route("/admin/system/migrations/verify", methods=["POST"])
@login_required
def verify_migrations():
    record_verified_migrations()
    log_activity(
        "Database migrations verified",
        "Migration Center schema verification completed",
    )
    flash("Migration verification completed.", "success")
    return redirect(url_for("migration_center"))


@app.route("/admin/system/database")
@login_required
def database_status():
    connection = get_db()
    counts = {}
    for table in (
        "products", "orders", "order_items",
        "announcements", "activity_log"
    ):
        try:
            counts[table] = connection.execute(
                f"SELECT COUNT(*) AS count FROM {table}"
            ).fetchone()["count"]
        except Exception:
            counts[table] = "Unavailable"
    backend = connection.backend
    connection.close()

    parsed = urlparse(DATABASE_URL) if DATABASE_URL else None
    details = {
        "backend": backend,
        "host": parsed.hostname if parsed else "Local file",
        "database": parsed.path.lstrip("/") if parsed else str(SQLITE_DB_PATH),
        "port": parsed.port if parsed else "",
        "postgres_configured": USE_POSTGRES,
        "uploads_path": str(UPLOAD_FOLDER),
    }
    return render_template(
        "database_status.html",
        details=details,
        counts=counts,
    )


@app.route("/admin")
@login_required
def admin_dashboard():
    connection = get_db()

    try:
        product_rows = connection.execute(
            "SELECT * FROM products ORDER BY active DESC, category, name"
        ).fetchall()
        products = rows_to_products(product_rows)

        active_products = [
            product for product in products if product["active"]
        ]
        low_stock_products = [
            product for product in active_products
            if 0 < int(product["stock"]) <= 5
        ]
        out_of_stock_products = [
            product for product in active_products
            if int(product["stock"]) <= 0
        ]

        total_units = sum(
            max(int(product["stock"]), 0)
            for product in active_products
        )
        inventory_value = sum(
            max(int(product["stock"]), 0)
            * float(
                product["sale_price"]
                if product["sale_price"] is not None
                else product["price"]
            )
            for product in active_products
        )

        categories = {
            product["category"]
            for product in active_products
            if product["category"]
        }

        # Use Python-calculated date boundaries. These parameterized comparisons
        # work reliably with PostgreSQL timestamps and SQLite text timestamps.
        today_start = datetime.combine(date.today(), datetime.min.time())
        tomorrow_start = today_start + timedelta(days=1)
        month_start = today_start.replace(day=1)
        if month_start.month == 12:
            next_month_start = month_start.replace(
                year=month_start.year + 1,
                month=1,
            )
        else:
            next_month_start = month_start.replace(
                month=month_start.month + 1,
            )

        basic_orders = connection.execute(
            """
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(CASE WHEN status = 'New' THEN 1 ELSE 0 END), 0) AS new_orders,
                COALESCE(SUM(CASE WHEN status = 'Processing' THEN 1 ELSE 0 END), 0) AS processing_orders,
                COALESCE(SUM(CASE WHEN status = 'Ready' THEN 1 ELSE 0 END), 0) AS ready_orders,
                COALESCE(SUM(CASE WHEN status != 'Cancelled' THEN total ELSE 0 END), 0) AS lifetime_revenue
            FROM orders
            """
        ).fetchone()

        sales_today = connection.execute(
            """
            SELECT COALESCE(SUM(total), 0) AS amount
            FROM orders
            WHERE status != 'Cancelled'
              AND created_at::timestamp >= ?
              AND created_at::timestamp < ?
            """,
            (today_start, tomorrow_start),
        ).fetchone()["amount"]

        sales_month = connection.execute(
            """
            SELECT COALESCE(SUM(total), 0) AS amount
            FROM orders
            WHERE status != 'Cancelled'
              AND created_at::timestamp >= ?
              AND created_at::timestamp < ?
            """,
            (month_start, next_month_start),
        ).fetchone()["amount"]

        recent_orders = connection.execute(
            """
            SELECT id, order_number, customer_name, total, status, created_at
            FROM orders
            ORDER BY id DESC
            LIMIT 6
            """
        ).fetchall()

        today_text = date.today().isoformat()
        active_announcements = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM announcements
            WHERE active = 1
              AND (start_date = '' OR start_date <= ?)
              AND (end_date = '' OR end_date >= ?)
            """,
            (today_text, today_text),
        ).fetchone()["count"]

        activities = connection.execute(
            """
            SELECT action, detail, created_at
            FROM activity_log
            ORDER BY id DESC
            LIMIT 7
            """
        ).fetchall()

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    media_count = 0
    try:
        media_count = sum(
            1
            for path in UPLOAD_FOLDER.iterdir()
            if path.is_file() and allowed_image(path.name)
        )
    except OSError:
        media_count = 0

    stats = {
        "active_products": len(active_products),
        "hidden_products": len(products) - len(active_products),
        "low_stock": len(low_stock_products),
        "out_of_stock": len(out_of_stock_products),
        "total_units": total_units,
        "inventory_value": inventory_value,
        "categories": len(categories),
        "media_count": media_count,
        "total_orders": int(basic_orders["total_orders"] or 0),
        "new_orders": int(basic_orders["new_orders"] or 0),
        "processing_orders": int(basic_orders["processing_orders"] or 0),
        "ready_orders": int(basic_orders["ready_orders"] or 0),
        "sales_today": float(sales_today or 0),
        "sales_month": float(sales_month or 0),
        "lifetime_revenue": float(
            basic_orders["lifetime_revenue"] or 0
        ),
        "active_announcements": int(active_announcements or 0),
    }

    notifications = []
    if stats["new_orders"]:
        notifications.append({
            "level": "info",
            "title": f"{stats['new_orders']} new order(s)",
            "detail": "Review new orders in the Orders Dashboard.",
        })
    if stats["ready_orders"]:
        notifications.append({
            "level": "info",
            "title": f"{stats['ready_orders']} order(s) ready",
            "detail": "These orders are waiting for pickup or delivery.",
        })
    if low_stock_products:
        notifications.append({
            "level": "warning",
            "title": f"{len(low_stock_products)} low-stock product(s)",
            "detail": "Review inventory before items sell out.",
        })
    if out_of_stock_products:
        notifications.append({
            "level": "danger",
            "title": f"{len(out_of_stock_products)} out-of-stock product(s)",
            "detail": "Restock or hide unavailable products.",
        })
    if not USE_POSTGRES:
        notifications.insert(0, {
            "level": "danger",
            "title": "PostgreSQL is not connected",
            "detail": "The website is using the SQLite fallback.",
        })

    hour = datetime.now().hour
    greeting = (
        "Good morning"
        if hour < 12
        else "Good afternoon"
        if hour < 18
        else "Good evening"
    )

    return render_template(
        "dashboard.html",
        stats=stats,
        low_stock_products=low_stock_products[:6],
        recent_products=active_products[:6],
        recent_orders=[dict(row) for row in recent_orders],
        activities=[dict(row) for row in activities],
        notifications=notifications,
        settings=get_settings(),
        greeting=greeting,
        database_backend=(
            "PostgreSQL" if USE_POSTGRES else "SQLite fallback"
        ),
    )


@app.route("/admin/search")
@permission_required("search")
def admin_search():
    query = request.args.get("q", "").strip()
    product_results = []
    customer_results = []
    order_results = []
    page_results = []
    media_results = []

    if query:
        like = f"%{query}%"
        lower_like = f"%{query.lower()}%"
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
        product_results = rows_to_products(rows)

        customer_rows = connection.execute(
            """
            SELECT id, name, email, phone, status, order_count, lifetime_value
            FROM customers
            WHERE LOWER(name) LIKE ?
               OR LOWER(email) LIKE ?
               OR LOWER(phone) LIKE ?
               OR LOWER(tags) LIKE ?
            ORDER BY lifetime_value DESC, name
            LIMIT 20
            """,
            (lower_like, lower_like, lower_like, lower_like),
        ).fetchall()
        customer_results = [dict(row) for row in customer_rows]

        order_rows = connection.execute(
            """
            SELECT id, order_number, customer_name, customer_email,
                   status, total, created_at
            FROM orders
            WHERE LOWER(order_number) LIKE ?
               OR LOWER(customer_name) LIKE ?
               OR LOWER(customer_email) LIKE ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (lower_like, lower_like, lower_like),
        ).fetchall()
        order_results = [dict(row) for row in order_rows]
        connection.close()

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
        customer_results=customer_results,
        order_results=order_results,
        page_results=page_results,
        media_results=media_results,
    )


@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    customer = data.get("customer") or {}
    items = data.get("items") or []
    totals = data.get("totals") or {}
    name = str(customer.get("name", "")).strip()
    email = str(customer.get("email", "")).strip()
    payment = str(customer.get("payment_method", "")).strip()
    if not name or not email or not payment:
        return jsonify({"error": "Name, email, and payment method are required."}), 400
    if not items:
        return jsonify({"error": "The cart is empty."}), 400

    connection = get_db()
    next_id = connection.execute("SELECT COALESCE(MAX(id),0)+1 AS next_id FROM orders").fetchone()["next_id"]
    order_number = f"SS-{date.today().strftime('%Y%m%d')}-{int(next_id):04d}"
    insert_sql = """
        INSERT INTO orders (
            order_number, customer_name, customer_email, customer_phone,
            payment_method, fulfillment_method, notes,
            subtotal, name_fees, fulfillment_fees, shipping_fee, tax, total, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'New')
    """
    if connection.backend == "postgresql":
        insert_sql += " RETURNING id"

    cursor = connection.execute(
        insert_sql,
        (
            order_number, name, email, str(customer.get("phone","")).strip(),
            payment, str(customer.get("fulfillment_method","Studio Pickup")).strip(),
            str(customer.get("notes","")).strip(),
            float(totals.get("subtotal") or 0), float(totals.get("name_fees") or 0),
            float(totals.get("fulfillment_fees") or 0), float(totals.get("shipping_fee") or 0),
            float(totals.get("tax") or 0), float(totals.get("total") or 0),
        ),
    )
    order_id = (
        cursor.fetchone()["id"]
        if connection.backend == "postgresql"
        else cursor.lastrowid
    )
    for item in items:
        connection.execute(
            """
            INSERT INTO order_items (
                order_id, product_id, product_name, size, color, requested_name,
                item_price, name_fee, fulfillment_fee, quantity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id, item.get("id"), str(item.get("name","")).strip(),
                str(item.get("size","")).strip(), str(item.get("color","")).strip(),
                str(item.get("requestedName","")).strip(), float(item.get("price") or 0),
                float(item.get("nameFee") or 0), float(item.get("fulfillmentFee") or 0),
                int(item.get("quantity") or 1),
            ),
        )
    connection.commit()
    connection.close()
    sync_customer_from_email(email)
    log_activity("New store order", order_number)
    return jsonify({"ok": True, "order_number": order_number})


@app.route("/admin/students")
@permission_required("students")
def students_dashboard():
    query = request.args.get("q", "").strip()
    selected_status = request.args.get("status", "").strip()
    selected_family = request.args.get("family_id", "").strip()
    sort = request.args.get("sort", "name").strip()

    sort_options = {
        "name": "s.last_name ASC, s.first_name ASC",
        "birthday": "s.birth_date ASC, s.last_name ASC",
        "newest": "s.id DESC",
        "family": "f.family_name ASC NULLS LAST, s.last_name ASC",
    }
    order_by = sort_options.get(sort, sort_options["name"])

    conditions = []
    parameters = []

    if query:
        like = f"%{query.lower()}%"
        conditions.append(
            """
            (
                LOWER(s.first_name) LIKE ?
                OR LOWER(s.last_name) LIKE ?
                OR LOWER(s.preferred_name) LIKE ?
                OR LOWER(s.tags) LIKE ?
                OR LOWER(f.family_name) LIKE ?
            )
            """
        )
        parameters.extend((like, like, like, like, like))

    if selected_status:
        conditions.append("s.status = ?")
        parameters.append(selected_status)

    if selected_family:
        conditions.append("s.family_id = ?")
        parameters.append(int(selected_family))

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    connection = get_db()
    rows = connection.execute(
        f"""
        SELECT
            s.*,
            f.family_name
        FROM students s
        LEFT JOIN families f ON f.id = s.family_id
        {where_clause}
        ORDER BY {order_by}
        """,
        tuple(parameters),
    ).fetchall()

    summary = connection.execute(
        """
        SELECT
            COUNT(*) AS student_count,
            COALESCE(SUM(CASE WHEN status='Active' THEN 1 ELSE 0 END), 0) AS active_count,
            COALESCE(SUM(CASE WHEN status='Trial' THEN 1 ELSE 0 END), 0) AS trial_count,
            COALESCE(SUM(CASE WHEN competition_team=1 THEN 1 ELSE 0 END), 0) AS competition_count
        FROM students
        """
    ).fetchone()

    families = connection.execute(
        """
        SELECT id, family_name
        FROM families
        ORDER BY family_name
        """
    ).fetchall()
    connection.close()

    return render_template(
        "students.html",
        students=[dict(row) for row in rows],
        families=[dict(row) for row in families],
        summary=dict(summary),
        query=query,
        selected_status=selected_status,
        selected_family=selected_family,
        selected_sort=sort,
    )


@app.route("/admin/students/new")
@login_required
def new_student():
    connection = get_db()
    families = connection.execute(
        "SELECT id, family_name FROM families ORDER BY family_name"
    ).fetchall()
    connection.close()

    return render_template(
        "student_form.html",
        student=None,
        families=[dict(row) for row in families],
    )


@app.route("/admin/students/save", methods=["POST"])
@login_required
def save_student():
    form = request.form
    student_id = form.get("id", "").strip()
    existing_photo = form.get("existing_photo_url", "").strip()
    photo_url = existing_photo

    try:
        uploaded_photo = save_uploaded_image(
            request.files.get("student_photo")
        )
        if uploaded_photo:
            photo_url = uploaded_photo
    except ValueError as error:
        flash(str(error), "error")
        return redirect(request.referrer or url_for("students_dashboard"))

    if form.get("remove_photo") == "on":
        photo_url = ""

    family_value = form.get("family_id", "").strip()
    family_id = int(family_value) if family_value else None

    values = (
        family_id,
        form.get("first_name", "").strip(),
        form.get("last_name", "").strip(),
        form.get("preferred_name", "").strip(),
        form.get("birth_date", "").strip(),
        form.get("status", "Active").strip(),
        1 if form.get("competition_team") == "on" else 0,
        photo_url,
        form.get("email", "").strip().lower(),
        form.get("phone", "").strip(),
        form.get("school", "").strip(),
        form.get("grade", "").strip(),
        form.get("leotard_size", "").strip(),
        form.get("costume_size", "").strip(),
        form.get("shoe_size", "").strip(),
        form.get("warmup_size", "").strip(),
        form.get("medical_notes", "").strip(),
        form.get("general_notes", "").strip(),
        form.get("tags", "").strip(),
    )

    connection = get_db()
    if student_id:
        connection.execute(
            """
            UPDATE students SET
                family_id=?, first_name=?, last_name=?,
                preferred_name=?, birth_date=?, status=?,
                competition_team=?, photo_url=?, email=?, phone=?,
                school=?, grade=?, leotard_size=?, costume_size=?,
                shoe_size=?, warmup_size=?, medical_notes=?,
                general_notes=?, tags=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            values + (int(student_id),),
        )
        action = "Student updated"
    else:
        insert_sql = """
            INSERT INTO students (
                family_id, first_name, last_name, preferred_name,
                birth_date, status, competition_team, photo_url,
                email, phone, school, grade, leotard_size,
                costume_size, shoe_size, warmup_size,
                medical_notes, general_notes, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if connection.backend == "postgresql":
            insert_sql += " RETURNING id"

        cursor = connection.execute(insert_sql, values)
        student_id = (
            int(cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(cursor.lastrowid)
        )
        action = "Student created"

    connection.commit()
    connection.close()

    if existing_photo and existing_photo != photo_url:
        delete_uploaded_image(existing_photo)

    display_name = " ".join(
        part for part in (
            form.get("first_name", "").strip(),
            form.get("last_name", "").strip(),
        )
        if part
    )
    log_activity(action, display_name)
    flash("Student profile saved.", "success")
    return redirect(url_for("student_profile", student_id=int(student_id)))


@app.route("/admin/students/<int:student_id>")
@login_required
def student_profile(student_id: int):
    connection = get_db()
    student = connection.execute(
        """
        SELECT s.*, f.family_name
        FROM students s
        LEFT JOIN families f ON f.id = s.family_id
        WHERE s.id=?
        """,
        (student_id,),
    ).fetchone()

    if not student:
        connection.close()
        return ("Student not found", 404)

    notes = connection.execute(
        """
        SELECT id, note, created_at
        FROM student_notes
        WHERE student_id=?
        ORDER BY id DESC
        """,
        (student_id,),
    ).fetchall()

    families = connection.execute(
        "SELECT id, family_name FROM families ORDER BY family_name"
    ).fetchall()
    connection.close()

    student_data = dict(student)
    student_data["competition_team"] = bool(
        student_data["competition_team"]
    )
    student_data["tag_list"] = [
        tag.strip()
        for tag in (student_data.get("tags") or "").split(",")
        if tag.strip()
    ]

    timeline = [
        {
            "title": "Student note",
            "detail": note["note"],
            "created_at": note["created_at"],
        }
        for note in notes
    ]

    return render_template(
        "student_profile.html",
        student=student_data,
        notes=[dict(row) for row in notes],
        timeline=timeline,
        families=[dict(row) for row in families],
    )


@app.route("/admin/students/<int:student_id>/notes", methods=["POST"])
@login_required
def add_student_note(student_id: int):
    note = request.form.get("note", "").strip()
    if note:
        connection = get_db()
        connection.execute(
            "INSERT INTO student_notes (student_id, note) VALUES (?, ?)",
            (student_id, note),
        )
        connection.commit()
        connection.close()
        log_activity("Student note added", f"Student #{student_id}")
    return redirect(url_for("student_profile", student_id=student_id))


@app.route("/admin/students/<int:student_id>/delete", methods=["POST"])
@login_required
def delete_student(student_id: int):
    connection = get_db()
    student = connection.execute(
        "SELECT first_name, last_name, photo_url FROM students WHERE id=?",
        (student_id,),
    ).fetchone()

    connection.execute(
        "DELETE FROM students WHERE id=?",
        (student_id,),
    )
    connection.commit()
    connection.close()

    if student:
        delete_uploaded_image(student["photo_url"] or "")
        log_activity(
            "Student deleted",
            f"{student['first_name']} {student['last_name']}",
        )

    flash("Student deleted.", "success")
    return redirect(url_for("students_dashboard"))


@app.route("/admin/families")
@permission_required("families")
def families_dashboard():
    backfill_customers_from_orders()
    backfill_families_from_customers()

    query = request.args.get("q", "").strip()
    sort = request.args.get("sort", "activity").strip()

    sort_options = {
        "name": "family_name ASC",
        "members": "customer_count DESC, family_name ASC",
        "orders": "order_count DESC, family_name ASC",
        "value": "lifetime_value DESC, family_name ASC",
        "activity": "last_activity_at DESC NULLS LAST, family_name ASC",
    }
    order_by = sort_options.get(sort, sort_options["activity"])

    connection = get_db()
    if query:
        like = f"%{query.lower()}%"
        rows = connection.execute(
            f"""
            SELECT *
            FROM families
            WHERE LOWER(family_name) LIKE ?
               OR LOWER(primary_email) LIKE ?
               OR LOWER(primary_phone) LIKE ?
               OR LOWER(tags) LIKE ?
            ORDER BY {order_by}
            """,
            (like, like, like, like),
        ).fetchall()
    else:
        rows = connection.execute(
            f"SELECT * FROM families ORDER BY {order_by}"
        ).fetchall()

    summary = connection.execute(
        """
        SELECT
            COUNT(*) AS family_count,
            COALESCE(SUM(customer_count), 0) AS customer_count,
            COALESCE(SUM(order_count), 0) AS order_count,
            COALESCE(SUM(lifetime_value), 0) AS lifetime_value
        FROM families
        """
    ).fetchone()
    connection.close()

    return render_template(
        "families.html",
        families=[dict(row) for row in rows],
        summary=dict(summary),
        query=query,
        selected_sort=sort,
    )


@app.route("/admin/families/<int:family_id>")
@login_required
def family_profile(family_id: int):
    refresh_family_metrics(family_id)
    connection = get_db()

    family = connection.execute(
        "SELECT * FROM families WHERE id=?",
        (family_id,),
    ).fetchone()

    if not family:
        connection.close()
        return ("Family not found", 404)

    customers = connection.execute(
        """
        SELECT id, name, email, phone, status, tags,
               order_count, lifetime_value, last_order_at
        FROM customers
        WHERE family_id=?
        ORDER BY name
        """,
        (family_id,),
    ).fetchall()

    orders = connection.execute(
        """
        SELECT DISTINCT o.id, o.order_number, o.customer_name,
               o.status, o.total, o.created_at
        FROM orders o
        JOIN customers c
          ON LOWER(TRIM(c.email)) = LOWER(TRIM(o.customer_email))
        WHERE c.family_id=?
        ORDER BY o.id DESC
        """,
        (family_id,),
    ).fetchall()

    notes = connection.execute(
        """
        SELECT id, note, created_at
        FROM family_notes
        WHERE family_id=?
        ORDER BY id DESC
        """,
        (family_id,),
    ).fetchall()
    connection.close()

    timeline = []
    for order in orders:
        timeline.append({
            "kind": "order",
            "title": f"Order {order['order_number']}",
            "detail": (
                f"{order['customer_name']} · {order['status']} · "
                f"${float(order['total'] or 0):.2f}"
            ),
            "created_at": order["created_at"],
            "url": url_for("order_detail", order_id=order["id"]),
        })

    for note in notes:
        timeline.append({
            "kind": "note",
            "title": "Family note",
            "detail": note["note"],
            "created_at": note["created_at"],
            "url": "",
        })

    timeline.sort(
        key=lambda item: str(item["created_at"] or ""),
        reverse=True,
    )

    return render_template(
        "family_profile.html",
        family=dict(family),
        customers=[dict(row) for row in customers],
        orders=[dict(row) for row in orders],
        notes=[dict(row) for row in notes],
        timeline=timeline,
    )


@app.route("/admin/families/<int:family_id>/save", methods=["POST"])
@login_required
def save_family(family_id: int):
    connection = get_db()
    connection.execute(
        """
        UPDATE families SET
            family_name=?,
            primary_email=?,
            primary_phone=?,
            tags=?,
            notes=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (
            request.form.get("family_name", "").strip(),
            request.form.get("primary_email", "").strip().lower(),
            request.form.get("primary_phone", "").strip(),
            request.form.get("tags", "").strip(),
            request.form.get("notes", "").strip(),
            family_id,
        ),
    )
    connection.commit()
    connection.close()

    log_activity(
        "Family updated",
        request.form.get("family_name", "").strip(),
    )
    flash("Family profile saved.", "success")
    return redirect(url_for("family_profile", family_id=family_id))


@app.route("/admin/families/<int:family_id>/notes", methods=["POST"])
@login_required
def add_family_note(family_id: int):
    note = request.form.get("note", "").strip()
    if note:
        connection = get_db()
        connection.execute(
            "INSERT INTO family_notes (family_id, note) VALUES (?, ?)",
            (family_id, note),
        )
        connection.commit()
        connection.close()
        log_activity("Family note added", f"Family #{family_id}")
    return redirect(url_for("family_profile", family_id=family_id))


@app.route("/admin/customers")
@permission_required("customers")
def customers_dashboard():
    backfill_customers_from_orders()
    query = request.args.get("q", "").strip()
    sort = request.args.get("sort", "last_order").strip()
    selected_tag = request.args.get("tag", "").strip()
    selected_status = request.args.get("status", "").strip()

    sort_options = {
        "name": "name ASC",
        "orders": "order_count DESC, name ASC",
        "lifetime": "lifetime_value DESC, name ASC",
        "last_order": "last_order_at DESC NULLS LAST, name ASC",
    }
    order_by = sort_options.get(sort, sort_options["last_order"])

    conditions = []
    parameters = []

    if query:
        like = f"%{query.lower()}%"
        conditions.append(
            """
            (
                LOWER(name) LIKE ?
                OR LOWER(email) LIKE ?
                OR LOWER(phone) LIKE ?
                OR LOWER(tags) LIKE ?
            )
            """
        )
        parameters.extend((like, like, like, like))

    if selected_tag:
        conditions.append("LOWER(tags) LIKE ?")
        parameters.append(f"%{selected_tag.lower()}%")

    if selected_status:
        conditions.append("status = ?")
        parameters.append(selected_status)

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    connection = get_db()
    rows = connection.execute(
        f"""
        SELECT *
        FROM customers
        {where_clause}
        ORDER BY {order_by}
        """,
        tuple(parameters),
    ).fetchall()

    summary = connection.execute(
        """
        SELECT
            COUNT(*) AS customer_count,
            COALESCE(SUM(order_count), 0) AS total_orders,
            COALESCE(SUM(lifetime_value), 0) AS lifetime_value,
            COALESCE(AVG(lifetime_value), 0) AS average_value
        FROM customers
        """
    ).fetchone()

    tag_rows = connection.execute(
        """
        SELECT tags
        FROM customers
        WHERE TRIM(tags) != ''
        """
    ).fetchall()
    connection.close()

    available_tags = sorted({
        tag.strip()
        for row in tag_rows
        for tag in (row["tags"] or "").split(",")
        if tag.strip()
    })

    return render_template(
        "customers.html",
        customers=[dict(row) for row in rows],
        summary=dict(summary),
        query=query,
        selected_sort=sort,
        selected_tag=selected_tag,
        selected_status=selected_status,
        available_tags=available_tags,
    )


@app.route("/admin/customers/<int:customer_id>")
@login_required
def customer_profile(customer_id: int):
    connection = get_db()
    customer = connection.execute(
        "SELECT * FROM customers WHERE id = ?",
        (customer_id,),
    ).fetchone()

    if not customer:
        connection.close()
        return ("Customer not found", 404)

    orders = connection.execute(
        """
        SELECT id, order_number, status, total, payment_method, created_at
        FROM orders
        WHERE LOWER(TRIM(customer_email)) = ?
        ORDER BY id DESC
        """,
        (customer["email"].strip().lower(),),
    ).fetchall()

    notes = connection.execute(
        """
        SELECT id, note, created_at
        FROM customer_notes
        WHERE customer_id = ?
        ORDER BY id DESC
        """,
        (customer_id,),
    ).fetchall()
    connection.close()

    order_list = [dict(row) for row in orders]
    note_list = [dict(row) for row in notes]

    timeline = []
    for order in order_list:
        timeline.append({
            "kind": "order",
            "title": f"Order {order['order_number']}",
            "detail": (
                f"{order['status']} · {order['payment_method']} · "
                f"${float(order['total'] or 0):.2f}"
            ),
            "created_at": order["created_at"],
            "url": url_for("order_detail", order_id=order["id"]),
        })

    for note in note_list:
        timeline.append({
            "kind": "note",
            "title": "Customer note",
            "detail": note["note"],
            "created_at": note["created_at"],
            "url": "",
        })

    timeline.sort(
        key=lambda item: str(item["created_at"] or ""),
        reverse=True,
    )

    customer_data = dict(customer)
    customer_data["tag_list"] = [
        tag.strip()
        for tag in (customer_data.get("tags") or "").split(",")
        if tag.strip()
    ]

    return render_template(
        "customer_profile.html",
        customer=customer_data,
        orders=order_list,
        notes=note_list,
        timeline=timeline,
    )


@app.route("/admin/customers/<int:customer_id>/save", methods=["POST"])
@login_required
def save_customer(customer_id: int):
    connection = get_db()
    connection.execute(
        """
        UPDATE customers SET
            name=?,
            phone=?,
            status=?,
            tags=?,
            notes=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (
            request.form.get("name", "").strip(),
            request.form.get("phone", "").strip(),
            request.form.get("status", "Active").strip(),
            request.form.get("tags", "").strip(),
            request.form.get("notes", "").strip(),
            customer_id,
        ),
    )
    connection.commit()
    connection.close()
    log_activity("Customer updated", request.form.get("name", "").strip())
    flash("Customer profile saved.", "success")
    return redirect(url_for("customer_profile", customer_id=customer_id))


@app.route("/admin/customers/<int:customer_id>/notes", methods=["POST"])
@login_required
def add_customer_note(customer_id: int):
    note = request.form.get("note", "").strip()
    if note:
        connection = get_db()
        connection.execute(
            "INSERT INTO customer_notes (customer_id, note) VALUES (?, ?)",
            (customer_id, note),
        )
        connection.commit()
        connection.close()
        log_activity("Customer note added", f"Customer #{customer_id}")
    return redirect(url_for("customer_profile", customer_id=customer_id))


@app.route("/admin/orders")
@permission_required("orders")
def orders_dashboard():
    status = request.args.get("status", "").strip()
    connection = get_db()
    rows = connection.execute(
        "SELECT * FROM orders WHERE status = ? ORDER BY id DESC" if status else
        "SELECT * FROM orders ORDER BY id DESC",
        (status,) if status else (),
    ).fetchall()
    summary = connection.execute(
        """
        SELECT COUNT(*) AS total_orders,
        SUM(CASE WHEN status='New' THEN 1 ELSE 0 END) AS new_orders,
        SUM(CASE WHEN status='Processing' THEN 1 ELSE 0 END) AS processing_orders,
        SUM(CASE WHEN status='Ready' THEN 1 ELSE 0 END) AS ready_orders,
        COALESCE(SUM(CASE WHEN status!='Cancelled' THEN total ELSE 0 END),0) AS revenue
        FROM orders
        """
    ).fetchone()
    connection.close()
    return render_template("orders.html", orders=[dict(r) for r in rows], summary=dict(summary), selected_status=status)


@app.route("/admin/orders/<int:order_id>")
@login_required
def order_detail(order_id: int):
    connection = get_db()
    order = connection.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    items = connection.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order_id,)).fetchall()
    connection.close()
    if not order:
        return ("Order not found", 404)
    return render_template("order_detail.html", order=dict(order), items=[dict(i) for i in items])


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id: int):
    allowed = {"New","Processing","Ready","Completed","Cancelled"}
    status = request.form.get("status","").strip()
    if status not in allowed:
        flash("Invalid order status.", "error")
        return redirect(url_for("order_detail", order_id=order_id))
    connection = get_db()
    order = connection.execute("SELECT order_number FROM orders WHERE id=?", (order_id,)).fetchone()
    connection.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    connection.commit()
    connection.close()
    if order:
        order_customer = get_db()
        customer_row = order_customer.execute(
            "SELECT customer_email FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        order_customer.close()
        if customer_row:
            sync_customer_from_email(customer_row["customer_email"])
        log_activity("Order status updated", f"{order['order_number']} → {status}")
    flash("Order status updated.", "success")
    return redirect(url_for("order_detail", order_id=order_id))


@app.route("/admin/reports")
@permission_required("reports")
def reports_dashboard():
    connection = get_db()

    overview = connection.execute(
        """
        SELECT
            COUNT(*) AS total_orders,
            SUM(CASE WHEN status != 'Cancelled' THEN 1 ELSE 0 END) AS valid_orders,
            COALESCE(SUM(CASE WHEN status != 'Cancelled' THEN total ELSE 0 END), 0) AS revenue,
            COALESCE(AVG(CASE WHEN status != 'Cancelled' THEN total END), 0) AS average_order,
            SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed_orders,
            SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_orders
        FROM orders
        """
    ).fetchone()

    recent_sales = connection.execute(
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
        """
    ).fetchall()

    payment_mix = connection.execute(
        """
        SELECT payment_method, COUNT(*) AS orders, COALESCE(SUM(total), 0) AS revenue
        FROM orders
        WHERE status != 'Cancelled'
        GROUP BY payment_method
        ORDER BY orders DESC
        """
    ).fetchall()

    status_mix = connection.execute(
        """
        SELECT status, COUNT(*) AS orders, COALESCE(SUM(total), 0) AS revenue
        FROM orders
        GROUP BY status
        ORDER BY orders DESC
        """
    ).fetchall()

    best_sellers = connection.execute(
        """
        SELECT
            product_name,
            SUM(quantity) AS units,
            COALESCE(SUM((item_price + name_fee + fulfillment_fee) * quantity), 0) AS revenue
        FROM order_items
        GROUP BY product_name
        ORDER BY units DESC, revenue DESC
        LIMIT 10
        """
    ).fetchall()

    product_rows = connection.execute(
        "SELECT * FROM products WHERE active = 1 ORDER BY stock ASC, name"
    ).fetchall()
    connection.close()

    products = rows_to_products(product_rows)
    low_stock = [p for p in products if int(p["stock"]) <= 5]
    inventory_units = sum(max(int(p["stock"]), 0) for p in products)
    inventory_value = sum(
        max(int(p["stock"]), 0)
        * float(p["sale_price"] if p["sale_price"] is not None else p["price"])
        for p in products
    )

    recent_sales = list(reversed([dict(row) for row in recent_sales]))
    max_daily_revenue = max(
        [float(row["revenue"] or 0) for row in recent_sales] or [1]
    )

    return render_template(
        "reports.html",
        overview=dict(overview),
        recent_sales=recent_sales,
        payment_mix=[dict(row) for row in payment_mix],
        status_mix=[dict(row) for row in status_mix],
        best_sellers=[dict(row) for row in best_sellers],
        low_stock=low_stock[:10],
        inventory_units=inventory_units,
        inventory_value=inventory_value,
        max_daily_revenue=max_daily_revenue,
    )


@app.route("/admin/announcements")
@permission_required("announcements")
def announcement_manager():
    connection = get_db()
    rows = connection.execute(
        "SELECT * FROM announcements ORDER BY active DESC, priority DESC, id DESC"
    ).fetchall()
    connection.close()
    return render_template(
        "announcements.html",
        announcements=[dict(row) for row in rows],
        today=date.today().isoformat(),
    )


@app.route("/admin/announcements/save", methods=["POST"])
@login_required
def save_announcement():
    form = request.form
    announcement_id = form.get("id", "").strip()
    values = (
        form.get("title", "").strip(),
        form.get("message", "").strip(),
        form.get("button_text", "").strip(),
        form.get("button_link", "").strip(),
        form.get("start_date", "").strip(),
        form.get("end_date", "").strip(),
        int(form.get("priority") or 0),
        1 if form.get("active") == "on" else 0,
    )
    connection = get_db()
    if announcement_id:
        connection.execute(
            """
            UPDATE announcements SET
                title=?, message=?, button_text=?, button_link=?,
                start_date=?, end_date=?, priority=?, active=?
            WHERE id=?
            """,
            values + (int(announcement_id),),
        )
        action = "Announcement updated"
    else:
        connection.execute(
            """
            INSERT INTO announcements (
                title, message, button_text, button_link,
                start_date, end_date, priority, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        action = "Announcement created"
    connection.commit()
    connection.close()
    log_activity(action, form.get("title", "").strip())
    flash("Announcement saved.", "success")
    return redirect(url_for("announcement_manager"))


@app.route("/admin/announcements/<int:announcement_id>/toggle", methods=["POST"])
@login_required
def toggle_announcement(announcement_id: int):
    connection = get_db()
    row = connection.execute(
        "SELECT title, active FROM announcements WHERE id = ?",
        (announcement_id,),
    ).fetchone()
    if row:
        new_value = 0 if row["active"] else 1
        connection.execute(
            "UPDATE announcements SET active = ? WHERE id = ?",
            (new_value, announcement_id),
        )
        connection.commit()
        log_activity(
            "Announcement activated" if new_value else "Announcement paused",
            row["title"],
        )
    connection.close()
    return redirect(url_for("announcement_manager"))


@app.route("/admin/announcements/<int:announcement_id>/delete", methods=["POST"])
@login_required
def delete_announcement(announcement_id: int):
    connection = get_db()
    row = connection.execute(
        "SELECT title FROM announcements WHERE id = ?",
        (announcement_id,),
    ).fetchone()
    connection.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    connection.commit()
    connection.close()
    log_activity(
        "Announcement deleted",
        row["title"] if row else f"Announcement #{announcement_id}",
    )
    flash("Announcement deleted.", "success")
    return redirect(url_for("announcement_manager"))


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
@permission_required("store")
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
@permission_required("media")
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
        port=PORT,
        debug=FLASK_DEBUG,
    )
