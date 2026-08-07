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
    Response,
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
import qrcode
from qrcode.image.svg import SvgPathImage

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
    "office_staff": {"label":"Office Staff","description":"Customers, families, students, classes, attendance, billing, recitals, workflows, orders, content and reports.","permissions":{"dashboard","families","customers","students","classes","teachers","attendance","billing","costumes","competitions","recitals","ticketing","notifications","workflow","orders","website","announcements","media","search","reports"}},
    "teacher": {"label":"Teacher","description":"View assigned classes, take attendance, and access rosters, students, families, and search.","permissions":{"dashboard","families","students","classes","attendance","search"}},
    "store_manager": {"label":"Store Manager","description":"Store, inventory, orders, customers, notifications, media and reports.","permissions":{"dashboard","store","orders","customers","ticketing","notifications","workflow","reports","media","search"}},
}

def current_admin():
    user_id=session.get("admin_user_id")
    if not user_id: return None
    connection=get_db()
    row=connection.execute("SELECT id,username,display_name,email,role,active FROM admin_users WHERE id=?",(int(user_id),)).fetchone()
    connection.close()
    return dict(row) if row else None

def admin_greeting_name(admin_user=None):
    user = admin_user or current_admin()
    if not user:
        return "Administrator"
    display_name = (user.get("display_name") or "").strip()
    username = (user.get("username") or "").strip()
    generic_names = {
        "administrator", "admin", "manager", "owner", "office staff",
        "office manager", "store manager", "teacher", "staff",
        "stage starz owner",
    }
    if display_name.lower() in generic_names and username:
        return username.replace("_", " ").replace(".", " ").title()
    return display_name or username.replace("_", " ").replace(".", " ").title() or "Administrator"


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
    admin_user = current_admin()
    return {
        "has_permission": has_permission,
        "current_admin_user": admin_user,
        "current_admin_greeting_name": admin_greeting_name(admin_user),
        "role_definitions": ROLE_DEFINITIONS,
    }

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
    {
        "key": "010_class_management",
        "title": "Class Management",
        "description": "Teachers, class schedules, rooms, capacity, and student enrollment.",
        "required_tables": ["teachers", "classes", "class_enrollments"],
        "required_columns": {
            "classes": [
                "name", "teacher_id", "room", "day_of_week",
                "start_time", "end_time", "capacity", "active"
            ],
            "class_enrollments": [
                "class_id", "student_id", "status", "enrolled_at"
            ],
        },
    },
    {
        "key": "011_attendance_center",
        "title": "Attendance Center",
        "description": "Class sessions, attendance statuses, notes, and reporting.",
        "required_tables": ["class_sessions", "attendance_records"],
        "required_columns": {
            "class_sessions": [
                "class_id", "session_date", "status",
                "topic", "teacher_notes", "created_by"
            ],
            "attendance_records": [
                "session_id", "student_id", "status",
                "minutes_late", "note", "marked_by"
            ],
        },
    },
    {
        "key": "012_billing_tuition",
        "title": "Billing and Tuition Center",
        "description": "Family charges, payments, balances, receipts, due dates, and audit history.",
        "required_tables": ["billing_charges", "billing_payments"],
        "required_columns": {
            "billing_charges": [
                "family_id", "student_id", "charge_type",
                "description", "amount", "due_date", "status"
            ],
            "billing_payments": [
                "family_id", "amount", "payment_method",
                "payment_date", "status", "received_by"
            ],
        },
    },
    {
        "key": "013_workflow_engine",
        "title": "Workflow and Notification Engine",
        "description": "Events, workflow rules, queued tasks, dashboard notifications, and delivery history.",
        "required_tables": [
            "workflow_events", "workflow_rules",
            "workflow_tasks", "notifications"
        ],
        "required_columns": {
            "workflow_events": [
                "event_type", "source_module", "title",
                "details", "severity", "created_at"
            ],
            "workflow_rules": [
                "name", "event_type", "action_type",
                "title_template", "active"
            ],
            "workflow_tasks": [
                "task_type", "status", "title",
                "scheduled_for", "attempts"
            ],
            "notifications": [
                "admin_user_id", "title", "message",
                "severity", "read_at", "dismissed_at"
            ],
        },
    },
    {
        "key": "014_recital_center",
        "title": "Recital Management Center",
        "description": "Productions, shows, performance lineups, class assignments, music tracking, and rehearsals.",
        "required_tables": [
            "recital_productions", "recital_shows",
            "recital_performances", "recital_rehearsals"
        ],
        "required_columns": {
            "recital_productions": [
                "name", "season", "venue", "status", "ticket_status"
            ],
            "recital_shows": [
                "production_id", "name", "show_date",
                "start_time", "status"
            ],
            "recital_performances": [
                "show_id", "class_id", "title",
                "performance_order", "music_status", "status"
            ],
            "recital_rehearsals": [
                "production_id", "show_id", "title",
                "rehearsal_date", "status"
            ],
        },
    },
    {
        "key": "015_costume_management",
        "title": "Costume Management Center",
        "description": "Costume catalog, vendors, class and student assignments, fulfillment, billing, and recital links.",
        "required_tables": ["costume_vendors","costumes","costume_class_assignments","student_costume_assignments"],
        "required_columns": {
            "costumes": ["vendor_id","name","style_number","color","charge_amount","order_status"],
            "student_costume_assignments": ["costume_id","student_id","costume_size","assignment_status","alteration_status","pickup_status","billing_charge_id"],
        },
    },
    {
        "key": "016_competition_management",
        "title": "Competition Management Center",
        "description": "Competition events, routines, dancers, fees, deadlines, music, travel, and awards.",
        "required_tables": ["competitions","competition_routines","competition_dancers","competition_awards"],
        "required_columns": {
            "competitions": ["name","venue","start_date","end_date","registration_deadline","status"],
            "competition_routines": ["competition_id","title","class_id","music_status","entry_status","entry_fee"],
            "competition_dancers": ["routine_id","student_id","registration_status","waiver_status","travel_status","costume_ready"],
            "competition_awards": ["routine_id","award_name","placement","score"],
        },
    },
    {
        "key": "017_ticketing_center",
        "title": "Reserved Seating and Ticketing Center",
        "description": "Venue layouts, assigned seating, ticket orders, printable tickets, billing, and door check-in.",
        "required_tables": [
            "ticket_venues", "ticket_sections", "ticket_seats",
            "ticket_show_settings", "ticket_orders", "tickets",
            "ticket_holds", "ticket_hold_seats", "ticket_row_layouts", "ticket_venue_layouts", "ticket_section_layouts", "ticket_venue_objects", "ticket_venue_presets", "ticket_canvas_settings"
        ],
        "required_columns": {
            "ticket_venues": ["name","address","active"],
            "ticket_sections": ["venue_id","name","sort_order"],
            "ticket_seats": ["section_id","row_label","seat_number","seat_label","seat_type","active"],
            "ticket_show_settings": ["recital_show_id","venue_id","default_price","sales_status"],
            "ticket_orders": ["recital_show_id","family_id","purchaser_name","order_status","payment_status","total_amount"],
            "tickets": ["order_id","recital_show_id","seat_id","ticket_code","price","status","checked_in_at"],
            "ticket_holds": ["recital_show_id","family_id","held_for_name","notes","expires_at","status","converted_order_id"],
            "ticket_hold_seats": ["hold_id","recital_show_id","seat_id"],
            "ticket_row_layouts": ["section_id","row_label","extra_space_after","seat_direction","notes"],
            "ticket_venue_layouts": ["venue_id","booth_enabled","booth_label","booth_position"],
            "ticket_section_layouts": ["section_id","orientation","placement","x_pos","y_pos","width_px","height_px","rotation_deg","z_index"],
            "ticket_venue_objects": ["venue_id","object_type","label","placement","sort_order","x_pos","y_pos","width_px","height_px","rotation_deg","z_index","shape","active"],
            "ticket_venue_presets": ["venue_id","preset_key","applied_at"],
            "ticket_canvas_settings": ["venue_id","canvas_width","canvas_height","background_label"],
        },
    },
    {
        "key": "018_public_ticket_sales",
        "title": "Public Reserved Ticket Sales Portal",
        "description": "Public show listings, temporary seat locks, checkout, ticket confirmation, and family billing.",
        "required_tables": ["public_ticket_settings","ticket_checkout_sessions","ticket_checkout_seats"],
        "required_columns": {
            "public_ticket_settings": ["recital_show_id","public_slug","public_enabled","sales_open_at","sales_close_at","max_tickets_per_order","hold_minutes"],
            "ticket_checkout_sessions": ["checkout_token","recital_show_id","status","expires_at","converted_order_id"],
            "ticket_checkout_seats": ["checkout_session_id","recital_show_id","seat_id"],
        },
    },
    {
        "key": "019_digital_ticket_delivery_checkin",
        "title": "Digital Ticket Delivery and Door Check-In",
        "description": "QR mobile tickets, camera-assisted door check-in, duplicate warnings, lookup, re-entry, and attendance tracking.",
        "required_tables": ["ticket_delivery_settings","ticket_checkin_events"],
        "required_columns": {
            "ticket_delivery_settings": ["recital_show_id","mobile_tickets_enabled","checkin_enabled","allow_reentry","reentry_limit","door_notes","delivery_message"],
            "ticket_checkin_events": ["ticket_id","recital_show_id","action","method","staff_user_id","notes","created_at"],
        },
    },
    {
        "key": "020_email_notification_center",
        "title": "Email and Notification Center",
        "description": "Templates, campaigns, recipient groups, message queue, scheduling, and delivery history.",
        "required_tables": [
            "notification_templates",
            "notification_campaigns",
            "notification_recipients",
            "notification_delivery_log"
        ],
        "required_columns": {
            "notification_templates": [
                "name","category","subject","body_text","active"
            ],
            "notification_campaigns": [
                "name","template_id","category","subject","body_text",
                "recipient_scope","scheduled_for","status"
            ],
            "notification_recipients": [
                "campaign_id","family_id","student_id","recipient_name",
                "recipient_email","source_type","source_reference",
                "status","last_error"
            ],
            "notification_delivery_log": [
                "campaign_id","recipient_id","channel","provider",
                "provider_message_id","status","error_message","sent_at"
            ],
        },
    },
    {
        "key": "021_parent_portal",
        "title": "Parent Portal",
        "description": "Secure family login, student schedules, attendance, billing, costumes, recitals, tickets, notifications, documents, and profile self-service.",
        "required_tables": [
            "parent_portal_accounts",
            "parent_portal_activity",
            "parent_portal_message_reads",
            "parent_portal_documents"
        ],
        "required_columns": {
            "parent_portal_accounts": [
                "family_id","email","password_hash","display_name",
                "active","must_change_password","last_login_at"
            ],
            "parent_portal_activity": [
                "account_id","family_id","action","details","created_at"
            ],
            "parent_portal_message_reads": [
                "account_id","campaign_id","read_at"
            ],
            "parent_portal_documents": [
                "family_id","title","category","description",
                "document_url","active"
            ],
        },
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


def generate_ticket_code() -> str:
    import secrets
    return "SS-" + secrets.token_hex(5).upper()



def cleanup_public_checkout_locks(connection, show_id=None):
    if show_id:
        rows=connection.execute("SELECT id FROM ticket_checkout_sessions WHERE recital_show_id=? AND status='Active' AND expires_at<=CURRENT_TIMESTAMP",(show_id,)).fetchall()
    else:
        rows=connection.execute("SELECT id FROM ticket_checkout_sessions WHERE status='Active' AND expires_at<=CURRENT_TIMESTAMP").fetchall()
    for row in rows:
        connection.execute("DELETE FROM ticket_checkout_seats WHERE checkout_session_id=?",(row["id"],))
        connection.execute("UPDATE ticket_checkout_sessions SET status='Expired',updated_at=CURRENT_TIMESTAMP WHERE id=?",(row["id"],))


def make_public_slug(value):
    import re
    return re.sub(r"[^a-z0-9]+","-",value.lower()).strip("-") or uuid.uuid4().hex[:10]


def get_public_show(connection, slug):
    return connection.execute("""SELECT rs.id AS show_id,rs.name,rs.show_date,rs.start_time,rp.name AS production_name,
        tss.venue_id,tss.default_price,tss.sales_status,tv.name AS venue_name,tv.address AS venue_address,pts.*
        FROM public_ticket_settings pts JOIN recital_shows rs ON rs.id=pts.recital_show_id
        JOIN recital_productions rp ON rp.id=rs.production_id
        JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id
        LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id WHERE pts.public_slug=?""",(slug,)).fetchone()


def public_sales_open(show):
    if not show or not int(show["public_enabled"] or 0) or show["sales_status"]!="On Sale": return False
    now=datetime.utcnow()
    def parse(v):
        if not v:return None
        if isinstance(v,datetime): return v
        try:return datetime.fromisoformat(str(v).replace("Z","+00:00")).replace(tzinfo=None)
        except ValueError:return None
    start,end=parse(show["sales_open_at"]),parse(show["sales_close_at"])
    return not (start and now<start) and not (end and now>end)


@app.route("/admin/ticketing/shows/<int:show_id>/public-settings",methods=["POST"])
@permission_required("ticketing")
def save_public_ticket_settings(show_id):
    c=get_db(); show=c.execute("SELECT rs.name,rp.name AS production_name FROM recital_shows rs JOIN recital_productions rp ON rp.id=rs.production_id WHERE rs.id=?",(show_id,)).fetchone()
    if not show:c.close();return ("Show not found",404)
    existing=c.execute("SELECT public_slug FROM public_ticket_settings WHERE recital_show_id=?",(show_id,)).fetchone()
    slug=make_public_slug(request.form.get("public_slug","").strip() or (existing["public_slug"] if existing else "") or f"{show['production_name']}-{show['name']}-{show_id}")
    c.execute("""INSERT INTO public_ticket_settings(recital_show_id,public_slug,public_enabled,sales_open_at,sales_close_at,max_tickets_per_order,hold_minutes,allow_pay_at_studio,allow_family_billing,public_title,public_description,accessibility_notes,terms_text)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(recital_show_id) DO UPDATE SET public_slug=excluded.public_slug,public_enabled=excluded.public_enabled,sales_open_at=excluded.sales_open_at,sales_close_at=excluded.sales_close_at,max_tickets_per_order=excluded.max_tickets_per_order,hold_minutes=excluded.hold_minutes,allow_pay_at_studio=excluded.allow_pay_at_studio,allow_family_billing=excluded.allow_family_billing,public_title=excluded.public_title,public_description=excluded.public_description,accessibility_notes=excluded.accessibility_notes,terms_text=excluded.terms_text,updated_at=CURRENT_TIMESTAMP""",
      (show_id,slug,1 if request.form.get("public_enabled")=="on" else 0,request.form.get("sales_open_at","").strip() or None,request.form.get("sales_close_at","").strip() or None,max(1,min(int(request.form.get("max_tickets_per_order","12") or 12),50)),max(5,min(int(request.form.get("hold_minutes","10") or 10),60)),1 if request.form.get("allow_pay_at_studio")=="on" else 0,1 if request.form.get("allow_family_billing")=="on" else 0,request.form.get("public_title","").strip(),request.form.get("public_description","").strip(),request.form.get("accessibility_notes","").strip(),request.form.get("terms_text","").strip()))
    c.commit();c.close();flash("Public ticket sales settings saved.","success");return redirect(url_for("ticket_show",show_id=show_id))


@app.route("/tickets")
def public_ticket_portal():
    c=get_db();cleanup_public_checkout_locks(c)
    rows=c.execute("""SELECT pts.public_slug,pts.public_title,pts.public_description,rs.name,rs.show_date,rs.start_time,rp.name AS production_name,tv.name AS venue_name,tss.sales_status,
      COUNT(DISTINCT ts.id) AS total_seats,COUNT(DISTINCT CASE WHEN tk.status='Valid' THEN tk.id END) AS sold_seats
      FROM public_ticket_settings pts JOIN recital_shows rs ON rs.id=pts.recital_show_id JOIN recital_productions rp ON rp.id=rs.production_id
      JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id
      LEFT JOIN ticket_sections sec ON sec.venue_id=tss.venue_id LEFT JOIN ticket_seats ts ON ts.section_id=sec.id AND ts.active=1
      LEFT JOIN tickets tk ON tk.recital_show_id=rs.id AND tk.seat_id=ts.id AND tk.status='Valid'
      WHERE pts.public_enabled=1 GROUP BY pts.public_slug,pts.public_title,pts.public_description,rs.name,rs.show_date,rs.start_time,rp.name,tv.name,tss.sales_status ORDER BY rs.show_date,rs.start_time""").fetchall()
    c.commit();c.close();return render_template("public_ticket_portal.html",shows=[dict(r) for r in rows])


@app.route("/tickets/<slug>")
def public_ticket_show(slug):
    c=get_db();show=get_public_show(c,slug)
    if not show:c.close();return ("Ticket event not found",404)
    cleanup_public_checkout_locks(c,int(show["show_id"]))
    canvas=c.execute("SELECT * FROM ticket_canvas_settings WHERE venue_id=?",(show["venue_id"],)).fetchone()
    objects=c.execute("SELECT * FROM ticket_venue_objects WHERE venue_id=? AND active=1 ORDER BY z_index,sort_order,id",(show["venue_id"],)).fetchall()
    seats=c.execute("""SELECT ts.id,ts.row_label,ts.seat_number,ts.seat_type,sec.id AS section_id,sec.name AS section_name,
      COALESCE(trl.extra_space_after,0) AS extra_space_after,COALESCE(trl.seat_direction,'Low Left') AS seat_direction,
      COALESCE(tsl.orientation,'Horizontal') AS section_orientation,COALESCE(tsl.x_pos,400) AS section_x_pos,COALESCE(tsl.y_pos,250) AS section_y_pos,
      COALESCE(tsl.width_px,600) AS section_width_px,COALESCE(tsl.height_px,220) AS section_height_px,COALESCE(tsl.rotation_deg,0) AS section_rotation_deg,COALESCE(tsl.z_index,10) AS section_z_index,
      tk.id AS ticket_id,ths.hold_id,tcs.checkout_session_id FROM ticket_seats ts JOIN ticket_sections sec ON sec.id=ts.section_id
      LEFT JOIN ticket_row_layouts trl ON trl.section_id=ts.section_id AND trl.row_label=ts.row_label LEFT JOIN ticket_section_layouts tsl ON tsl.section_id=ts.section_id
      LEFT JOIN tickets tk ON tk.seat_id=ts.id AND tk.recital_show_id=? AND tk.status='Valid'
      LEFT JOIN ticket_hold_seats ths ON ths.seat_id=ts.id AND ths.recital_show_id=?
      LEFT JOIN ticket_checkout_seats tcs ON tcs.seat_id=ts.id AND tcs.recital_show_id=?
      WHERE sec.venue_id=? AND ts.active=1 ORDER BY sec.sort_order,sec.name,ts.row_label,ts.seat_number""",(show["show_id"],show["show_id"],show["show_id"],show["venue_id"])).fetchall()
    grouped={}
    for r in seats:
        item=dict(r);grouped.setdefault((item["section_id"],item["section_name"]),{}).setdefault(item["row_label"],[]).append(item)
    c.commit();c.close();return render_template("public_ticket_show.html",show=dict(show),grouped_seats=grouped,canvas=dict(canvas) if canvas else {"canvas_width":1400,"canvas_height":1100},objects=[dict(r) for r in objects],sales_open=public_sales_open(show))


@app.route("/tickets/<slug>/checkout",methods=["POST"])
def public_ticket_checkout_start(slug):
    c=get_db();show=get_public_show(c,slug)
    if not show or not public_sales_open(show):c.close();flash("Public ticket sales are not open.","error");return redirect(url_for("public_ticket_show",slug=slug))
    cleanup_public_checkout_locks(c,int(show["show_id"]))
    seats=[int(v) for v in request.form.getlist("seat_id") if v.isdigit()]
    if not seats or len(seats)>int(show["max_tickets_per_order"] or 12):c.close();flash("Select an allowed number of seats.","error");return redirect(url_for("public_ticket_show",slug=slug))
    ph=','.join('?' for _ in seats);params=tuple([show["show_id"]]+seats)
    checks=[c.execute(f"SELECT seat_id FROM tickets WHERE recital_show_id=? AND status='Valid' AND seat_id IN ({ph})",params).fetchall(),c.execute(f"SELECT seat_id FROM ticket_hold_seats WHERE recital_show_id=? AND seat_id IN ({ph})",params).fetchall(),c.execute(f"SELECT seat_id FROM ticket_checkout_seats WHERE recital_show_id=? AND seat_id IN ({ph})",params).fetchall()]
    if any(checks):c.close();flash("One or more selected seats are unavailable.","error");return redirect(url_for("public_ticket_show",slug=slug))
    token=uuid.uuid4().hex;expires=datetime.utcnow()+timedelta(minutes=int(show["hold_minutes"] or 10));sql="INSERT INTO ticket_checkout_sessions(checkout_token,recital_show_id,status,expires_at) VALUES (?,?,'Active',?)"+(" RETURNING id" if c.backend=="postgresql" else "")
    cur=c.execute(sql,(token,show["show_id"],expires));cid=int(cur.fetchone()["id"]) if c.backend=="postgresql" else int(cur.lastrowid)
    for seat in seats:c.execute("INSERT INTO ticket_checkout_seats(checkout_session_id,recital_show_id,seat_id) VALUES (?,?,?)",(cid,show["show_id"],seat))
    c.commit();c.close();return redirect(url_for("public_ticket_checkout",token=token))


@app.route("/tickets/checkout/<token>")
def public_ticket_checkout(token):
    c=get_db();cleanup_public_checkout_locks(c)
    co=c.execute("""SELECT tcs.*,rs.name AS show_name,rs.show_date,rs.start_time,rp.name AS production_name,tv.name AS venue_name,tv.address AS venue_address,tss.default_price,pts.allow_pay_at_studio,pts.allow_family_billing,pts.terms_text
      FROM ticket_checkout_sessions tcs JOIN recital_shows rs ON rs.id=tcs.recital_show_id JOIN recital_productions rp ON rp.id=rs.production_id JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id JOIN public_ticket_settings pts ON pts.recital_show_id=rs.id LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id WHERE tcs.checkout_token=?""",(token,)).fetchone()
    if not co:c.close();return ("Checkout not found",404)
    seats=c.execute("""SELECT ts.id,ts.row_label,ts.seat_number,ts.seat_type,sec.name AS section_name FROM ticket_checkout_seats tcs JOIN ticket_seats ts ON ts.id=tcs.seat_id JOIN ticket_sections sec ON sec.id=ts.section_id WHERE tcs.checkout_session_id=? ORDER BY sec.sort_order,sec.name,ts.row_label,ts.seat_number""",(co["id"],)).fetchall()
    fam=c.execute("SELECT id,family_name FROM families ORDER BY family_name").fetchall();c.commit();c.close();return render_template("public_ticket_checkout.html",checkout=dict(co),seats=[dict(r) for r in seats],families=[dict(r) for r in fam])


@app.route("/tickets/checkout/<token>/complete",methods=["POST"])
def public_ticket_checkout_complete(token):
    c=get_db();cleanup_public_checkout_locks(c)
    co=c.execute("""SELECT tcs.*,pts.allow_pay_at_studio,pts.allow_family_billing,tss.default_price,rs.name AS show_name FROM ticket_checkout_sessions tcs JOIN public_ticket_settings pts ON pts.recital_show_id=tcs.recital_show_id JOIN ticket_show_settings tss ON tss.recital_show_id=tcs.recital_show_id JOIN recital_shows rs ON rs.id=tcs.recital_show_id WHERE tcs.checkout_token=?""",(token,)).fetchone()
    if not co or co["status"]!="Active":c.close();return ("Checkout expired",410)
    seats=[int(r["seat_id"]) for r in c.execute("SELECT seat_id FROM ticket_checkout_seats WHERE checkout_session_id=?",(co["id"],)).fetchall()]
    name=request.form.get("purchaser_name","").strip();email=request.form.get("purchaser_email","").strip();phone=request.form.get("purchaser_phone","").strip();method=request.form.get("payment_method","Pay at Studio").strip();fv=request.form.get("family_id","").strip();family_id=int(fv) if fv else None
    if not name or not email:c.close();flash("Name and email are required.","error");return redirect(url_for("public_ticket_checkout",token=token))
    if method=="Family Billing" and (not family_id or not int(co["allow_family_billing"] or 0)):c.close();flash("Choose a family account.","error");return redirect(url_for("public_ticket_checkout",token=token))
    price=float(co["default_price"] or 0);total=price*len(seats);sql="INSERT INTO ticket_orders(recital_show_id,family_id,purchaser_name,purchaser_email,purchaser_phone,order_status,payment_status,total_amount,notes,created_by) VALUES (?,?,?,?,?,'Confirmed','Due',?,?,NULL)"+(" RETURNING id" if c.backend=="postgresql" else "")
    cur=c.execute(sql,(co["recital_show_id"],family_id,name,email,phone,total,f"Public portal · {method}"));oid=int(cur.fetchone()["id"]) if c.backend=="postgresql" else int(cur.lastrowid)
    for seat in seats:
        code=generate_ticket_code()
        while c.execute("SELECT id FROM tickets WHERE ticket_code=?",(code,)).fetchone():code=generate_ticket_code()
        c.execute("INSERT INTO tickets(order_id,recital_show_id,seat_id,ticket_code,price,status) VALUES (?,?,?,?,?,'Valid')",(oid,co["recital_show_id"],seat,code,price))
    if method=="Family Billing" and family_id and total>0:
        sql2="INSERT INTO billing_charges(family_id,charge_type,description,amount,due_date,status,reference,created_by) VALUES (?,'Other',?,?,?,'Open',?,NULL)"+(" RETURNING id" if c.backend=="postgresql" else "")
        cur2=c.execute(sql2,(family_id,f"Reserved tickets - {co['show_name']}",total,request.form.get("due_date","").strip(),f"Public ticket order #{oid}"));bid=int(cur2.fetchone()["id"]) if c.backend=="postgresql" else int(cur2.lastrowid);c.execute("UPDATE ticket_orders SET billing_charge_id=? WHERE id=?",(bid,oid))
    c.execute("UPDATE ticket_checkout_sessions SET family_id=?,purchaser_name=?,purchaser_email=?,purchaser_phone=?,status='Converted',converted_order_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(family_id,name,email,phone,oid,co["id"]));c.execute("DELETE FROM ticket_checkout_seats WHERE checkout_session_id=?",(co["id"],));c.commit();c.close()
    event_id=create_workflow_event("public_ticket_order_created","ticketing","Public reserved ticket order created",f"Order #{oid} · {len(seats)} seats · ${total:.2f}","success",str(oid));evaluate_workflow_rules(event_id)
    return redirect(url_for("public_ticket_order",order_id=oid))


@app.route("/tickets/order/<int:order_id>")
def public_ticket_order(order_id):
    c=get_db();order=c.execute("""SELECT tor.*,rs.name AS show_name,rs.show_date,rs.start_time,rp.name AS production_name,tv.name AS venue_name,tv.address AS venue_address FROM ticket_orders tor JOIN recital_shows rs ON rs.id=tor.recital_show_id JOIN recital_productions rp ON rp.id=rs.production_id LEFT JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id WHERE tor.id=?""",(order_id,)).fetchone()
    if not order:c.close();return ("Order not found",404)
    tickets=c.execute("""SELECT tk.*,ts.row_label,ts.seat_number,ts.seat_type,sec.name AS section_name FROM tickets tk JOIN ticket_seats ts ON ts.id=tk.seat_id JOIN ticket_sections sec ON sec.id=ts.section_id WHERE tk.order_id=? ORDER BY sec.sort_order,sec.name,ts.row_label,ts.seat_number""",(order_id,)).fetchall();c.close();return render_template("public_ticket_order.html",order=dict(order),tickets=[dict(r) for r in tickets])


def digital_ticket_token(ticket_id, ticket_code):
    return f"{int(ticket_id)}-{ticket_code}"


def ticket_from_digital_token(connection, token):
    if "-" not in token:
        return None
    ticket_id_text, ticket_code = token.split("-", 1)
    if not ticket_id_text.isdigit():
        return None
    return connection.execute(
        """SELECT tk.*,tor.purchaser_name,tor.purchaser_email,tor.purchaser_phone,
                  rs.name AS show_name,rs.show_date,rs.start_time,rp.name AS production_name,
                  tv.name AS venue_name,tv.address AS venue_address,
                  ts.row_label,ts.seat_number,ts.seat_label,ts.seat_type,sec.name AS section_name,
                  COALESCE(tds.mobile_tickets_enabled,1) AS mobile_tickets_enabled,
                  COALESCE(tds.checkin_enabled,1) AS checkin_enabled,
                  COALESCE(tds.allow_reentry,0) AS allow_reentry,
                  COALESCE(tds.reentry_limit,1) AS reentry_limit,
                  COALESCE(tds.delivery_message,'') AS delivery_message
           FROM tickets tk JOIN ticket_orders tor ON tor.id=tk.order_id
           JOIN recital_shows rs ON rs.id=tk.recital_show_id
           JOIN recital_productions rp ON rp.id=rs.production_id
           JOIN ticket_seats ts ON ts.id=tk.seat_id JOIN ticket_sections sec ON sec.id=ts.section_id
           LEFT JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id
           LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id
           LEFT JOIN ticket_delivery_settings tds ON tds.recital_show_id=rs.id
           WHERE tk.id=? AND tk.ticket_code=?""",
        (int(ticket_id_text), ticket_code),
    ).fetchone()


def perform_door_checkin(connection, ticket, method="Manual", notes=""):
    if ticket["status"] != "Valid":
        return False, "This ticket is not valid."
    if not int(ticket["checkin_enabled"] or 0):
        return False, "Door check-in is disabled for this performance."
    count = connection.execute(
        "SELECT COUNT(*) AS count FROM ticket_checkin_events WHERE ticket_id=? AND action='Check In'",
        (ticket["id"],),
    ).fetchone()["count"]
    count = int(count or 0)
    if ticket["checked_in_at"] and not int(ticket["allow_reentry"] or 0):
        return False, "DUPLICATE ENTRY: this ticket was already checked in."
    if ticket["checked_in_at"] and count >= int(ticket["reentry_limit"] or 1) + 1:
        return False, "This ticket has reached its re-entry limit."
    connection.execute(
        "UPDATE tickets SET checked_in_at=CURRENT_TIMESTAMP,checked_in_by=? WHERE id=?",
        (int(session.get("admin_user_id") or 0) or None,ticket["id"]),
    )
    connection.execute(
        """INSERT INTO ticket_checkin_events(ticket_id,recital_show_id,action,method,staff_user_id,notes)
           VALUES (?,?,'Check In',?,?,?)""",
        (ticket["id"],ticket["recital_show_id"],method,int(session.get("admin_user_id") or 0) or None,notes),
    )
    return True, "Ticket checked in."


@app.route("/admin/ticketing/shows/<int:show_id>/delivery-settings",methods=["POST"])
@permission_required("ticketing")
def save_ticket_delivery_settings(show_id):
    c=get_db()
    c.execute("""INSERT INTO ticket_delivery_settings(recital_show_id,mobile_tickets_enabled,checkin_enabled,allow_reentry,reentry_limit,door_notes,delivery_message)
      VALUES(?,?,?,?,?,?,?) ON CONFLICT(recital_show_id) DO UPDATE SET mobile_tickets_enabled=excluded.mobile_tickets_enabled,
      checkin_enabled=excluded.checkin_enabled,allow_reentry=excluded.allow_reentry,reentry_limit=excluded.reentry_limit,
      door_notes=excluded.door_notes,delivery_message=excluded.delivery_message,updated_at=CURRENT_TIMESTAMP""",
      (show_id,1 if request.form.get("mobile_tickets_enabled")=="on" else 0,1 if request.form.get("checkin_enabled")=="on" else 0,
       1 if request.form.get("allow_reentry")=="on" else 0,max(1,min(int(request.form.get("reentry_limit","1") or 1),10)),
       request.form.get("door_notes","").strip(),request.form.get("delivery_message","").strip()))
    c.commit();c.close();flash("Digital ticket settings saved.","success");return redirect(url_for("ticket_show",show_id=show_id))


@app.route("/admin/ticketing/shows/<int:show_id>/checkin")
@permission_required("ticketing")
def ticket_checkin_center(show_id):
    q=request.args.get("q","").strip();c=get_db()
    show=c.execute("""SELECT rs.id,rs.name,rs.show_date,rs.start_time,rp.name AS production_name,tv.name AS venue_name,
      COALESCE(tds.checkin_enabled,1) AS checkin_enabled,COALESCE(tds.allow_reentry,0) AS allow_reentry,
      COALESCE(tds.reentry_limit,1) AS reentry_limit,COALESCE(tds.door_notes,'') AS door_notes
      FROM recital_shows rs JOIN recital_productions rp ON rp.id=rs.production_id
      LEFT JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id
      LEFT JOIN ticket_delivery_settings tds ON tds.recital_show_id=rs.id WHERE rs.id=?""",(show_id,)).fetchone()
    if not show:c.close();return ("Show not found",404)
    summary=c.execute("""SELECT COUNT(*) AS valid_tickets,
      SUM(CASE WHEN checked_in_at IS NOT NULL THEN 1 ELSE 0 END) AS checked_in,
      SUM(CASE WHEN checked_in_at IS NULL THEN 1 ELSE 0 END) AS not_arrived
      FROM tickets WHERE recital_show_id=? AND status='Valid'""",(show_id,)).fetchone()
    where="";params=[show_id]
    if q:
        where=" AND (tk.ticket_code LIKE ? OR tor.purchaser_name LIKE ? OR tor.purchaser_email LIKE ? OR tor.purchaser_phone LIKE ? OR CAST(tor.id AS TEXT) LIKE ?)"
        like=f"%{q}%";params += [like]*5
    tickets=c.execute("""SELECT tk.id,tk.ticket_code,tk.checked_in_at,tor.id AS order_id,tor.purchaser_name,tor.purchaser_email,tor.purchaser_phone,
      ts.row_label,ts.seat_number,ts.seat_type,sec.name AS section_name,
      (SELECT COUNT(*) FROM ticket_checkin_events e WHERE e.ticket_id=tk.id AND e.action='Check In') AS checkin_count
      FROM tickets tk JOIN ticket_orders tor ON tor.id=tk.order_id JOIN ticket_seats ts ON ts.id=tk.seat_id JOIN ticket_sections sec ON sec.id=ts.section_id
      WHERE tk.recital_show_id=? AND tk.status='Valid'"""+where+" ORDER BY tk.checked_in_at IS NOT NULL,tor.purchaser_name,sec.sort_order,ts.row_label,ts.seat_number LIMIT 150",tuple(params)).fetchall()
    c.close();return render_template("ticket_checkin_center.html",show=dict(show),summary=dict(summary),tickets=[dict(r) for r in tickets],query=q)


@app.route("/admin/ticketing/tickets/<int:ticket_id>/door-checkin",methods=["POST"])
@permission_required("ticketing")
def door_checkin_ticket(ticket_id):
    c=get_db();ticket=c.execute("""SELECT tk.*,COALESCE(tds.checkin_enabled,1) AS checkin_enabled,COALESCE(tds.allow_reentry,0) AS allow_reentry,
      COALESCE(tds.reentry_limit,1) AS reentry_limit FROM tickets tk LEFT JOIN ticket_delivery_settings tds ON tds.recital_show_id=tk.recital_show_id WHERE tk.id=?""",(ticket_id,)).fetchone()
    if not ticket:c.close();return ("Ticket not found",404)
    ok,msg=perform_door_checkin(c,ticket,request.form.get("method","Manual"),request.form.get("notes","").strip())
    if ok:c.commit()
    c.close();flash(msg,"success" if ok else "error");return redirect(url_for("ticket_checkin_center",show_id=ticket["recital_show_id"]))


@app.route("/admin/ticketing/tickets/<int:ticket_id>/undo-checkin",methods=["POST"])
@permission_required("ticketing")
def undo_door_checkin(ticket_id):
    c=get_db();ticket=c.execute("SELECT recital_show_id FROM tickets WHERE id=?",(ticket_id,)).fetchone()
    if not ticket:c.close();return ("Ticket not found",404)
    c.execute("UPDATE tickets SET checked_in_at=NULL,checked_in_by=NULL WHERE id=?",(ticket_id,))
    c.execute("INSERT INTO ticket_checkin_events(ticket_id,recital_show_id,action,method,staff_user_id,notes) VALUES (?,?,'Undo','Manual',?,?)",
      (ticket_id,ticket["recital_show_id"],int(session.get("admin_user_id") or 0) or None,request.form.get("notes","").strip()))
    c.commit();c.close();flash("Check-in undone.","success");return redirect(url_for("ticket_checkin_center",show_id=ticket["recital_show_id"]))


@app.route("/admin/ticketing/scan/<token>",methods=["POST"])
@permission_required("ticketing")
def scan_digital_ticket(token):
    c=get_db();ticket=ticket_from_digital_token(c,token)
    if not ticket:c.close();return jsonify({"ok":False,"message":"Ticket not found."}),404
    ok,msg=perform_door_checkin(c,ticket,"Camera QR")
    if ok:c.commit()
    fresh=c.execute("SELECT checked_in_at FROM tickets WHERE id=?",(ticket["id"],)).fetchone();c.close()
    return jsonify({"ok":ok,"message":msg,"show_id":ticket["recital_show_id"],"purchaser":ticket["purchaser_name"],"section":ticket["section_name"],"row":ticket["row_label"],"seat":ticket["seat_number"],"checked_in_at":fresh["checked_in_at"] if fresh else None}),200 if ok else 409


@app.route("/ticket/<token>")
def mobile_ticket(token):
    c=get_db();ticket=ticket_from_digital_token(c,token)
    if not ticket:c.close();return ("Ticket not found",404)
    c.close()
    if not int(ticket["mobile_tickets_enabled"] or 0):return ("Mobile tickets are disabled for this performance.",403)
    return render_template("mobile_ticket.html",ticket=dict(ticket),token=token)


@app.route("/ticket/<token>/qr.svg")
def mobile_ticket_qr(token):
    c=get_db();ticket=ticket_from_digital_token(c,token);c.close()
    if not ticket:return ("Ticket not found",404)
    qr=qrcode.QRCode(version=None,box_size=8,border=3);qr.add_data(f"STAGESTARZ:{token}");qr.make(fit=True)
    image=qr.make_image(image_factory=SvgPathImage);from io import BytesIO
    stream=BytesIO();image.save(stream);return Response(stream.getvalue(),mimetype="image/svg+xml",headers={"Cache-Control":"private, max-age=3600"})


def notification_scope_recipients(connection, scope):
    rows = []

    if scope == "All Families":
        data = connection.execute(
            """
            SELECT
                id AS family_id,
                family_name AS recipient_name,
                primary_email AS recipient_email,
                primary_phone AS recipient_phone
            FROM families
            WHERE COALESCE(primary_email,'')!=''
            ORDER BY family_name
            """
        ).fetchall()
        for row in data:
            rows.append({
                "family_id": row["family_id"],
                "student_id": None,
                "recipient_name": row["recipient_name"],
                "recipient_email": row["recipient_email"],
                "recipient_phone": row["recipient_phone"],
                "source_type": "Family",
                "source_reference": str(row["family_id"]),
            })

    elif scope == "Active Students":
        data = connection.execute(
            """
            SELECT
                s.id AS student_id,
                s.first_name,
                s.last_name,
                f.id AS family_id,
                f.family_name,
                f.primary_email,
                f.primary_phone
            FROM students s
            LEFT JOIN families f ON f.id=s.family_id
            WHERE COALESCE(s.active,1)=1
              AND COALESCE(f.primary_email,'')!=''
            ORDER BY s.last_name,s.first_name
            """
        ).fetchall()
        for row in data:
            rows.append({
                "family_id": row["family_id"],
                "student_id": row["student_id"],
                "recipient_name": f"{row['first_name']} {row['last_name']}".strip(),
                "recipient_email": row["primary_email"],
                "recipient_phone": row["primary_phone"],
                "source_type": "Student",
                "source_reference": str(row["student_id"]),
            })

    elif scope == "Open Billing":
        data = connection.execute(
            """
            SELECT DISTINCT
                f.id AS family_id,
                f.family_name AS recipient_name,
                f.primary_email AS recipient_email,
                f.primary_phone AS recipient_phone
            FROM billing_charges bc
            JOIN families f ON f.id=bc.family_id
            WHERE bc.status='Open'
              AND COALESCE(f.primary_email,'')!=''
            ORDER BY f.family_name
            """
        ).fetchall()
        for row in data:
            rows.append({
                "family_id": row["family_id"],
                "student_id": None,
                "recipient_name": row["recipient_name"],
                "recipient_email": row["recipient_email"],
                "recipient_phone": row["recipient_phone"],
                "source_type": "Billing",
                "source_reference": str(row["family_id"]),
            })

    elif scope == "Ticket Purchasers":
        data = connection.execute(
            """
            SELECT DISTINCT
                tor.family_id,
                tor.purchaser_name AS recipient_name,
                tor.purchaser_email AS recipient_email,
                tor.purchaser_phone AS recipient_phone,
                tor.id AS order_id
            FROM ticket_orders tor
            WHERE COALESCE(tor.purchaser_email,'')!=''
              AND tor.order_status!='Voided'
            ORDER BY tor.purchaser_name
            """
        ).fetchall()
        for row in data:
            rows.append({
                "family_id": row["family_id"],
                "student_id": None,
                "recipient_name": row["recipient_name"],
                "recipient_email": row["recipient_email"],
                "recipient_phone": row["recipient_phone"],
                "source_type": "Ticket Order",
                "source_reference": str(row["order_id"]),
            })

    elif scope == "Competition Families":
        data = connection.execute(
            """
            SELECT DISTINCT
                f.id AS family_id,
                f.family_name AS recipient_name,
                f.primary_email AS recipient_email,
                f.primary_phone AS recipient_phone
            FROM competition_dancers cd
            JOIN students s ON s.id=cd.student_id
            JOIN families f ON f.id=s.family_id
            WHERE COALESCE(f.primary_email,'')!=''
            ORDER BY f.family_name
            """
        ).fetchall()
        for row in data:
            rows.append({
                "family_id": row["family_id"],
                "student_id": None,
                "recipient_name": row["recipient_name"],
                "recipient_email": row["recipient_email"],
                "recipient_phone": row["recipient_phone"],
                "source_type": "Competition",
                "source_reference": str(row["family_id"]),
            })

    elif scope == "Recital Families":
        data = connection.execute(
            """
            SELECT DISTINCT
                f.id AS family_id,
                f.family_name AS recipient_name,
                f.primary_email AS recipient_email,
                f.primary_phone AS recipient_phone
            FROM recital_cast rc
            JOIN students s ON s.id=rc.student_id
            JOIN families f ON f.id=s.family_id
            WHERE COALESCE(f.primary_email,'')!=''
            ORDER BY f.family_name
            """
        ).fetchall()
        for row in data:
            rows.append({
                "family_id": row["family_id"],
                "student_id": None,
                "recipient_name": row["recipient_name"],
                "recipient_email": row["recipient_email"],
                "recipient_phone": row["recipient_phone"],
                "source_type": "Recital",
                "source_reference": str(row["family_id"]),
            })

    return rows


def parent_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("parent_account_id") or not session.get("parent_family_id"):
            return redirect(url_for("parent_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def current_parent_account(connection):
    account_id = session.get("parent_account_id")
    family_id = session.get("parent_family_id")
    if not account_id or not family_id:
        return None
    return connection.execute(
        """
        SELECT
            ppa.*,
            f.family_name,
            f.primary_email,
            f.primary_phone
        FROM parent_portal_accounts ppa
        JOIN families f ON f.id=ppa.family_id
        WHERE ppa.id=? AND ppa.family_id=? AND ppa.active=1
        """,
        (account_id, family_id),
    ).fetchone()


def log_parent_activity(connection, family_id, action, details=""):
    connection.execute(
        """
        INSERT INTO parent_portal_activity (
            account_id,family_id,action,details
        ) VALUES (?,?,?,?)
        """,
        (
            int(session.get("parent_account_id") or 0) or None,
            family_id,
            action,
            details,
        ),
    )


def parent_family_students(connection, family_id):
    return connection.execute(
        """
        SELECT *
        FROM students
        WHERE family_id=?
          AND status!='Archived'
        ORDER BY last_name,first_name
        """,
        (family_id,),
    ).fetchall()


@app.route("/parent/login", methods=["GET","POST"])
def parent_login():
    if session.get("parent_account_id") and session.get("parent_family_id"):
        return redirect(url_for("parent_dashboard"))

    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")

        connection = get_db()
        account = connection.execute(
            """
            SELECT *
            FROM parent_portal_accounts
            WHERE LOWER(email)=LOWER(?)
            """,
            (email,),
        ).fetchone()

        if not account or not int(account["active"] or 0) or not check_password_hash(account["password_hash"], password):
            connection.close()
            flash("The email or password was not recognized.","error")
            return render_template("parent_login.html",email=email)

        session["parent_account_id"] = int(account["id"])
        session["parent_family_id"] = int(account["family_id"])
        session["parent_display_name"] = account["display_name"] or ""

        connection.execute(
            """
            UPDATE parent_portal_accounts SET
                last_login_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (account["id"],),
        )
        log_parent_activity(
            connection,
            int(account["family_id"]),
            "Parent login",
            f"Account #{account['id']}",
        )
        connection.commit()
        connection.close()

        if int(account["must_change_password"] or 0):
            return redirect(url_for("parent_profile",change_password="1"))

        next_url = request.args.get("next","").strip()
        if next_url.startswith("/parent/"):
            return redirect(next_url)
        return redirect(url_for("parent_dashboard"))

    return render_template("parent_login.html",email="")


@app.route("/parent/logout")
def parent_logout():
    family_id = session.get("parent_family_id")
    if family_id:
        connection = get_db()
        log_parent_activity(connection,int(family_id),"Parent logout")
        connection.commit()
        connection.close()

    for key in ["parent_account_id","parent_family_id","parent_display_name"]:
        session.pop(key,None)

    return redirect(url_for("parent_login"))


@app.route("/parent")
@parent_login_required
def parent_dashboard():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        session.pop("parent_account_id",None)
        session.pop("parent_family_id",None)
        return redirect(url_for("parent_login"))

    family_id = int(account["family_id"])
    students = parent_family_students(connection,family_id)
    billing = get_family_billing_summary(connection,family_id)

    class_count = connection.execute(
        """
        SELECT COUNT(DISTINCT ce.class_id) AS count
        FROM class_enrollments ce
        JOIN students s ON s.id=ce.student_id
        WHERE s.family_id=? AND ce.status='Active'
        """,
        (family_id,),
    ).fetchone()

    attendance = connection.execute(
        """
        SELECT
            COUNT(ar.id) AS total,
            SUM(CASE WHEN ar.status='Present' THEN 1 ELSE 0 END) AS present,
            SUM(CASE WHEN ar.status='Absent' THEN 1 ELSE 0 END) AS absent,
            SUM(CASE WHEN ar.status='Late' THEN 1 ELSE 0 END) AS late
        FROM attendance_records ar
        JOIN students s ON s.id=ar.student_id
        WHERE s.family_id=?
        """,
        (family_id,),
    ).fetchone()

    ticket_summary = connection.execute(
        """
        SELECT
            COUNT(DISTINCT tor.id) AS order_count,
            COUNT(tk.id) AS ticket_count
        FROM ticket_orders tor
        LEFT JOIN tickets tk
          ON tk.order_id=tor.id
         AND tk.status='Valid'
        WHERE tor.family_id=?
           OR LOWER(COALESCE(tor.purchaser_email,''))=LOWER(?)
        """,
        (family_id,account["primary_email"] or account["email"]),
    ).fetchone()

    unread_messages = connection.execute(
        """
        SELECT COUNT(DISTINCT nc.id) AS count
        FROM notification_campaigns nc
        JOIN notification_recipients nr ON nr.campaign_id=nc.id
        LEFT JOIN parent_portal_message_reads ppmr
          ON ppmr.campaign_id=nc.id
         AND ppmr.account_id=?
        WHERE nr.family_id=?
          AND nc.status IN ('Queued','Completed')
          AND ppmr.id IS NULL
        """,
        (account["id"],family_id),
    ).fetchone()

    recent_activity = connection.execute(
        """
        SELECT *
        FROM parent_portal_activity
        WHERE family_id=?
        ORDER BY id DESC
        LIMIT 8
        """,
        (family_id,),
    ).fetchall()

    connection.close()

    return render_template(
        "parent_dashboard.html",
        account=dict(account),
        students=[dict(row) for row in students],
        billing=billing,
        class_count=int(class_count["count"] or 0),
        attendance=dict(attendance),
        ticket_summary=dict(ticket_summary),
        unread_messages=int(unread_messages["count"] or 0),
        recent_activity=[dict(row) for row in recent_activity],
    )


@app.route("/parent/students")
@parent_login_required
def parent_students():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    students = parent_family_students(connection,int(account["family_id"]))
    connection.close()

    return render_template(
        "parent_students.html",
        account=dict(account),
        students=[dict(row) for row in students],
    )


@app.route("/parent/students/<int:student_id>")
@parent_login_required
def parent_student_profile(student_id):
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    student = connection.execute(
        """
        SELECT *
        FROM students
        WHERE id=? AND family_id=?
        """,
        (student_id,account["family_id"]),
    ).fetchone()

    if not student:
        connection.close()
        return ("Student not found",404)

    classes = connection.execute(
        """
        SELECT
            c.id,c.name,c.category,c.level,
            c.day_of_week,c.start_time,c.end_time,
            c.room,c.season,
            t.first_name AS teacher_first_name,
            t.last_name AS teacher_last_name
        FROM class_enrollments ce
        JOIN classes c ON c.id=ce.class_id
        LEFT JOIN teachers t ON t.id=c.teacher_id
        WHERE ce.student_id=?
          AND ce.status='Active'
        ORDER BY c.day_of_week,c.start_time,c.name
        """,
        (student_id,),
    ).fetchall()

    attendance = connection.execute(
        """
        SELECT
            cs.session_date,
            c.name AS class_name,
            ar.status,ar.minutes_late,ar.note
        FROM attendance_records ar
        JOIN class_sessions cs ON cs.id=ar.session_id
        JOIN classes c ON c.id=cs.class_id
        WHERE ar.student_id=?
        ORDER BY cs.session_date DESC, c.name
        LIMIT 50
        """,
        (student_id,),
    ).fetchall()

    costumes = connection.execute(
        """
        SELECT
            sca.*,
            co.name AS costume_name,
            co.color,co.season,co.category,
            co.order_status,co.expected_date,
            c.name AS class_name
        FROM student_costume_assignments sca
        JOIN costumes co ON co.id=sca.costume_id
        LEFT JOIN classes c ON c.id=sca.class_id
        WHERE sca.student_id=?
        ORDER BY co.season DESC,co.name
        """,
        (student_id,),
    ).fetchall()

    recitals = connection.execute(
        """
        SELECT DISTINCT
            rp.title AS routine_title,
            rp.performance_order,
            rp.music_title,
            rp.costume_notes,
            rs.name AS show_name,
            rs.show_date,
            rs.start_time,
            prod.name AS production_name,
            c.name AS class_name
        FROM class_enrollments ce
        JOIN classes c ON c.id=ce.class_id
        JOIN recital_performances rp ON rp.class_id=c.id
        JOIN recital_shows rs ON rs.id=rp.show_id
        JOIN recital_productions prod ON prod.id=rs.production_id
        WHERE ce.student_id=?
          AND ce.status='Active'
        ORDER BY rs.show_date,rp.performance_order,rp.title
        """,
        (student_id,),
    ).fetchall()

    connection.close()

    return render_template(
        "parent_student_profile.html",
        account=dict(account),
        student=dict(student),
        classes=[dict(row) for row in classes],
        attendance=[dict(row) for row in attendance],
        costumes=[dict(row) for row in costumes],
        recitals=[dict(row) for row in recitals],
    )


@app.route("/parent/schedule")
@parent_login_required
def parent_schedule():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    rows = connection.execute(
        """
        SELECT
            s.id AS student_id,
            s.first_name,s.last_name,s.preferred_name,
            c.id AS class_id,c.name AS class_name,
            c.category,c.level,c.day_of_week,
            c.start_time,c.end_time,c.room,c.season,
            t.first_name AS teacher_first_name,
            t.last_name AS teacher_last_name
        FROM students s
        JOIN class_enrollments ce ON ce.student_id=s.id
        JOIN classes c ON c.id=ce.class_id
        LEFT JOIN teachers t ON t.id=c.teacher_id
        WHERE s.family_id=?
          AND ce.status='Active'
        ORDER BY
          CASE c.day_of_week
            WHEN 'Monday' THEN 1
            WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3
            WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5
            WHEN 'Saturday' THEN 6
            WHEN 'Sunday' THEN 7
            ELSE 8
          END,
          c.start_time,c.name
        """,
        (account["family_id"],),
    ).fetchall()

    connection.close()
    return render_template(
        "parent_schedule.html",
        account=dict(account),
        schedule=[dict(row) for row in rows],
    )


@app.route("/parent/attendance")
@parent_login_required
def parent_attendance():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    rows = connection.execute(
        """
        SELECT
            s.first_name,s.last_name,s.preferred_name,
            cs.session_date,
            c.name AS class_name,
            ar.status,ar.minutes_late,ar.note
        FROM attendance_records ar
        JOIN students s ON s.id=ar.student_id
        JOIN class_sessions cs ON cs.id=ar.session_id
        JOIN classes c ON c.id=cs.class_id
        WHERE s.family_id=?
        ORDER BY cs.session_date DESC,s.last_name,s.first_name,c.name
        LIMIT 300
        """,
        (account["family_id"],),
    ).fetchall()

    connection.close()
    return render_template(
        "parent_attendance.html",
        account=dict(account),
        attendance=[dict(row) for row in rows],
    )


@app.route("/parent/billing")
@parent_login_required
def parent_billing():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    family_id = int(account["family_id"])
    summary = get_family_billing_summary(connection,family_id)

    charges = connection.execute(
        """
        SELECT
            bc.*,
            s.first_name,s.last_name
        FROM billing_charges bc
        LEFT JOIN students s ON s.id=bc.student_id
        WHERE bc.family_id=?
        ORDER BY bc.id DESC
        LIMIT 200
        """,
        (family_id,),
    ).fetchall()

    payments = connection.execute(
        """
        SELECT *
        FROM billing_payments
        WHERE family_id=?
        ORDER BY payment_date DESC,id DESC
        LIMIT 200
        """,
        (family_id,),
    ).fetchall()

    connection.close()

    return render_template(
        "parent_billing.html",
        account=dict(account),
        summary=summary,
        charges=[dict(row) for row in charges],
        payments=[dict(row) for row in payments],
    )


@app.route("/parent/costumes")
@parent_login_required
def parent_costumes():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    rows = connection.execute(
        """
        SELECT
            s.first_name,s.last_name,s.preferred_name,
            sca.costume_size,sca.tights_size,sca.shoe_size,
            sca.accessories,sca.assignment_status,
            sca.alteration_status,sca.pickup_status,
            co.name AS costume_name,co.color,
            co.season,co.category,co.order_status,
            co.expected_date,
            c.name AS class_name
        FROM student_costume_assignments sca
        JOIN students s ON s.id=sca.student_id
        JOIN costumes co ON co.id=sca.costume_id
        LEFT JOIN classes c ON c.id=sca.class_id
        WHERE s.family_id=?
        ORDER BY s.last_name,s.first_name,co.season DESC,co.name
        """,
        (account["family_id"],),
    ).fetchall()

    connection.close()
    return render_template(
        "parent_costumes.html",
        account=dict(account),
        costumes=[dict(row) for row in rows],
    )


@app.route("/parent/recitals")
@parent_login_required
def parent_recitals():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    rows = connection.execute(
        """
        SELECT DISTINCT
            s.id AS student_id,
            s.first_name,s.last_name,s.preferred_name,
            rp.title AS routine_title,
            rp.performance_order,
            rp.music_title,rp.costume_notes,
            rs.name AS show_name,
            rs.show_date,rs.start_time,rs.doors_open_time,
            prod.name AS production_name,
            prod.venue,
            c.name AS class_name
        FROM students s
        JOIN class_enrollments ce ON ce.student_id=s.id
        JOIN classes c ON c.id=ce.class_id
        JOIN recital_performances rp ON rp.class_id=c.id
        JOIN recital_shows rs ON rs.id=rp.show_id
        JOIN recital_productions prod ON prod.id=rs.production_id
        WHERE s.family_id=?
          AND ce.status='Active'
        ORDER BY rs.show_date,rp.performance_order,s.last_name,s.first_name
        """,
        (account["family_id"],),
    ).fetchall()

    rehearsals = connection.execute(
        """
        SELECT DISTINCT
            rr.title,rr.rehearsal_date,rr.start_time,
            rr.end_time,rr.location,rr.notes,
            rp.name AS production_name
        FROM recital_rehearsals rr
        JOIN recital_productions rp ON rp.id=rr.production_id
        JOIN recital_shows rs ON rs.production_id=rp.id
        JOIN recital_performances perf ON perf.show_id=rs.id
        JOIN class_enrollments ce ON ce.class_id=perf.class_id
        JOIN students s ON s.id=ce.student_id
        WHERE s.family_id=?
          AND ce.status='Active'
        ORDER BY rr.rehearsal_date,rr.start_time
        """,
        (account["family_id"],),
    ).fetchall()

    connection.close()
    return render_template(
        "parent_recitals.html",
        account=dict(account),
        recitals=[dict(row) for row in rows],
        rehearsals=[dict(row) for row in rehearsals],
    )


@app.route("/parent/tickets")
@parent_login_required
def parent_tickets():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    orders = connection.execute(
        """
        SELECT
            tor.*,
            rs.name AS show_name,
            rs.show_date,rs.start_time,
            rp.name AS production_name,
            tv.name AS venue_name,
            COUNT(tk.id) AS ticket_count
        FROM ticket_orders tor
        JOIN recital_shows rs ON rs.id=tor.recital_show_id
        JOIN recital_productions rp ON rp.id=rs.production_id
        LEFT JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id
        LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id
        LEFT JOIN tickets tk ON tk.order_id=tor.id AND tk.status='Valid'
        WHERE tor.family_id=?
           OR LOWER(COALESCE(tor.purchaser_email,''))=LOWER(?)
        GROUP BY
            tor.id,tor.recital_show_id,tor.family_id,
            tor.purchaser_name,tor.purchaser_email,tor.purchaser_phone,
            tor.order_status,tor.payment_status,tor.total_amount,
            tor.notes,tor.created_by,tor.created_at,
            tor.billing_charge_id,
            rs.name,rs.show_date,rs.start_time,rp.name,tv.name
        ORDER BY tor.id DESC
        """,
        (account["family_id"],account["primary_email"] or account["email"]),
    ).fetchall()

    tickets = connection.execute(
        """
        SELECT
            tk.id,tk.order_id,tk.ticket_code,tk.status,tk.checked_in_at,
            ts.row_label,ts.seat_number,ts.seat_type,
            sec.name AS section_name
        FROM tickets tk
        JOIN ticket_orders tor ON tor.id=tk.order_id
        JOIN ticket_seats ts ON ts.id=tk.seat_id
        JOIN ticket_sections sec ON sec.id=ts.section_id
        WHERE (
            tor.family_id=?
            OR LOWER(COALESCE(tor.purchaser_email,''))=LOWER(?)
        )
          AND tk.status='Valid'
        ORDER BY tk.order_id DESC,sec.sort_order,ts.row_label,ts.seat_number
        """,
        (account["family_id"],account["primary_email"] or account["email"]),
    ).fetchall()

    connection.close()

    grouped_tickets = {}
    for ticket in tickets:
        grouped_tickets.setdefault(int(ticket["order_id"]),[]).append(dict(ticket))

    return render_template(
        "parent_tickets.html",
        account=dict(account),
        orders=[dict(row) for row in orders],
        grouped_tickets=grouped_tickets,
    )


@app.route("/parent/messages")
@parent_login_required
def parent_messages():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    messages = connection.execute(
        """
        SELECT DISTINCT
            nc.id,nc.name,nc.category,nc.subject,nc.body_text,
            nc.status,nc.created_at,
            ppmr.read_at
        FROM notification_campaigns nc
        JOIN notification_recipients nr ON nr.campaign_id=nc.id
        LEFT JOIN parent_portal_message_reads ppmr
          ON ppmr.campaign_id=nc.id
         AND ppmr.account_id=?
        WHERE nr.family_id=?
          AND nc.status IN ('Queued','Completed')
        ORDER BY nc.id DESC
        """,
        (account["id"],account["family_id"]),
    ).fetchall()

    connection.close()
    return render_template(
        "parent_messages.html",
        account=dict(account),
        messages=[dict(row) for row in messages],
    )


@app.route("/parent/messages/<int:campaign_id>")
@parent_login_required
def parent_message(campaign_id):
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    message = connection.execute(
        """
        SELECT DISTINCT nc.*
        FROM notification_campaigns nc
        JOIN notification_recipients nr ON nr.campaign_id=nc.id
        WHERE nc.id=?
          AND nr.family_id=?
          AND nc.status IN ('Queued','Completed')
        """,
        (campaign_id,account["family_id"]),
    ).fetchone()

    if not message:
        connection.close()
        return ("Message not found",404)

    connection.execute(
        """
        INSERT INTO parent_portal_message_reads (
            account_id,campaign_id
        ) VALUES (?,?)
        ON CONFLICT(account_id,campaign_id) DO UPDATE SET
            read_at=CURRENT_TIMESTAMP
        """,
        (account["id"],campaign_id),
    )
    log_parent_activity(
        connection,
        int(account["family_id"]),
        "Message viewed",
        message["subject"] or message["name"],
    )
    connection.commit()
    connection.close()

    return render_template(
        "parent_message.html",
        account=dict(account),
        message=dict(message),
    )


@app.route("/parent/documents")
@parent_login_required
def parent_documents():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    documents = connection.execute(
        """
        SELECT *
        FROM parent_portal_documents
        WHERE active=1
          AND (family_id IS NULL OR family_id=?)
        ORDER BY category,title,id DESC
        """,
        (account["family_id"],),
    ).fetchall()

    connection.close()
    return render_template(
        "parent_documents.html",
        account=dict(account),
        documents=[dict(row) for row in documents],
    )


@app.route("/parent/profile", methods=["GET","POST"])
@parent_login_required
def parent_profile():
    connection = get_db()
    account = current_parent_account(connection)
    if not account:
        connection.close()
        return redirect(url_for("parent_logout"))

    if request.method=="POST":
        action = request.form.get("action","profile")

        if action=="password":
            current_password = request.form.get("current_password","")
            new_password = request.form.get("new_password","")
            confirm_password = request.form.get("confirm_password","")

            if not check_password_hash(account["password_hash"],current_password):
                connection.close()
                flash("Current password is incorrect.","error")
                return redirect(url_for("parent_profile"))

            if len(new_password)<8:
                connection.close()
                flash("New password must be at least 8 characters.","error")
                return redirect(url_for("parent_profile"))

            if new_password!=confirm_password:
                connection.close()
                flash("New passwords do not match.","error")
                return redirect(url_for("parent_profile"))

            connection.execute(
                """
                UPDATE parent_portal_accounts SET
                    password_hash=?,
                    must_change_password=0,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (generate_password_hash(new_password),account["id"]),
            )
            log_parent_activity(
                connection,
                int(account["family_id"]),
                "Password changed",
            )
            connection.commit()
            connection.close()
            flash("Password updated.","success")
            return redirect(url_for("parent_profile"))

        primary_email = request.form.get("primary_email","").strip().lower()
        primary_phone = request.form.get("primary_phone","").strip()
        display_name = request.form.get("display_name","").strip()

        connection.execute(
            """
            UPDATE families SET
                primary_email=?,
                primary_phone=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (primary_email,primary_phone,account["family_id"]),
        )
        connection.execute(
            """
            UPDATE parent_portal_accounts SET
                email=?,
                display_name=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (primary_email,display_name,account["id"]),
        )
        log_parent_activity(
            connection,
            int(account["family_id"]),
            "Parent profile updated",
            primary_email,
        )
        connection.commit()
        connection.close()

        session["parent_display_name"] = display_name
        flash("Family contact information updated.","success")
        return redirect(url_for("parent_profile"))

    connection.close()
    return render_template(
        "parent_profile.html",
        account=dict(account),
    )


@app.route("/admin/parent-portal")
@login_required
def parent_portal_admin():
    connection = get_db()

    accounts = connection.execute(
        """
        SELECT
            ppa.*,
            f.family_name,
            f.primary_email,
            f.primary_phone,
            COUNT(DISTINCT s.id) AS student_count
        FROM parent_portal_accounts ppa
        JOIN families f ON f.id=ppa.family_id
        LEFT JOIN students s ON s.family_id=f.id
        GROUP BY
            ppa.id,ppa.family_id,ppa.email,ppa.password_hash,
            ppa.display_name,ppa.active,ppa.must_change_password,
            ppa.last_login_at,ppa.created_at,ppa.updated_at,
            f.family_name,f.primary_email,f.primary_phone
        ORDER BY f.family_name
        """
    ).fetchall()

    families = connection.execute(
        """
        SELECT
            f.id,f.family_name,f.primary_email,f.primary_phone,
            COUNT(s.id) AS student_count
        FROM families f
        LEFT JOIN students s ON s.family_id=f.id
        LEFT JOIN parent_portal_accounts ppa ON ppa.family_id=f.id
        WHERE ppa.id IS NULL
        GROUP BY f.id,f.family_name,f.primary_email,f.primary_phone
        ORDER BY f.family_name
        """
    ).fetchall()

    documents = connection.execute(
        """
        SELECT
            ppd.*,
            f.family_name
        FROM parent_portal_documents ppd
        LEFT JOIN families f ON f.id=ppd.family_id
        ORDER BY ppd.id DESC
        LIMIT 100
        """
    ).fetchall()

    connection.close()

    return render_template(
        "parent_portal_admin.html",
        accounts=[dict(row) for row in accounts],
        families=[dict(row) for row in families],
        documents=[dict(row) for row in documents],
    )


@app.route("/admin/parent-portal/accounts/create", methods=["POST"])
@login_required
def create_parent_portal_account():
    family_id = int(request.form.get("family_id","0") or 0)
    password = request.form.get("password","")
    display_name = request.form.get("display_name","").strip()

    if len(password)<8:
        flash("Temporary password must be at least 8 characters.","error")
        return redirect(url_for("parent_portal_admin"))

    connection = get_db()
    family = connection.execute(
        "SELECT * FROM families WHERE id=?",
        (family_id,),
    ).fetchone()

    if not family:
        connection.close()
        flash("Family not found.","error")
        return redirect(url_for("parent_portal_admin"))

    email = request.form.get("email","").strip().lower() or str(family["primary_email"] or "").strip().lower()
    if not email:
        connection.close()
        flash("A family email is required.","error")
        return redirect(url_for("parent_portal_admin"))

    try:
        connection.execute(
            """
            INSERT INTO parent_portal_accounts (
                family_id,email,password_hash,display_name,
                active,must_change_password
            ) VALUES (?,?,?,?,1,1)
            """,
            (
                family_id,
                email,
                generate_password_hash(password),
                display_name,
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        connection.close()
        flash("A parent portal account already exists for this family or email.","error")
        return redirect(url_for("parent_portal_admin"))

    connection.close()
    flash("Parent portal account created. The parent will be required to change the temporary password.","success")
    return redirect(url_for("parent_portal_admin"))


@app.route("/admin/parent-portal/accounts/<int:account_id>/update", methods=["POST"])
@login_required
def update_parent_portal_account(account_id):
    connection = get_db()
    account = connection.execute(
        "SELECT * FROM parent_portal_accounts WHERE id=?",
        (account_id,),
    ).fetchone()

    if not account:
        connection.close()
        return ("Parent account not found",404)

    active = 1 if request.form.get("active")=="on" else 0
    display_name = request.form.get("display_name","").strip()
    connection.execute(
        """
        UPDATE parent_portal_accounts SET
            active=?,
            display_name=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (active,display_name,account_id),
    )

    new_password = request.form.get("new_password","")
    if new_password:
        if len(new_password)<8:
            connection.close()
            flash("New temporary password must be at least 8 characters.","error")
            return redirect(url_for("parent_portal_admin"))

        connection.execute(
            """
            UPDATE parent_portal_accounts SET
                password_hash=?,
                must_change_password=1,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (generate_password_hash(new_password),account_id),
        )

    connection.commit()
    connection.close()
    flash("Parent portal account updated.","success")
    return redirect(url_for("parent_portal_admin"))


@app.route("/admin/parent-portal/documents/save", methods=["POST"])
@login_required
def save_parent_portal_document():
    family_value = request.form.get("family_id","").strip()
    family_id = int(family_value) if family_value else None

    connection = get_db()
    connection.execute(
        """
        INSERT INTO parent_portal_documents (
            family_id,title,category,description,
            document_url,active,created_by
        ) VALUES (?,?,?,?,?,1,?)
        """,
        (
            family_id,
            request.form.get("title","").strip(),
            request.form.get("category","General").strip(),
            request.form.get("description","").strip(),
            request.form.get("document_url","").strip(),
            int(session.get("admin_user_id") or 0) or None,
        ),
    )
    connection.commit()
    connection.close()

    flash("Parent portal document added.","success")
    return redirect(url_for("parent_portal_admin"))


@app.route("/admin/parent-portal/documents/<int:document_id>/delete", methods=["POST"])
@login_required
def delete_parent_portal_document(document_id):
    connection = get_db()
    connection.execute(
        "DELETE FROM parent_portal_documents WHERE id=?",
        (document_id,),
    )
    connection.commit()
    connection.close()
    flash("Parent portal document removed.","success")
    return redirect(url_for("parent_portal_admin"))


@app.route("/admin/notifications")
@permission_required("notifications")
def notification_center():
    connection = get_db()

    templates = connection.execute(
        """
        SELECT *
        FROM notification_templates
        ORDER BY active DESC,category,name
        """
    ).fetchall()

    campaigns = connection.execute(
        """
        SELECT
            nc.*,
            nt.name AS template_name,
            COUNT(nr.id) AS recipient_count,
            SUM(CASE WHEN nr.status='Sent' THEN 1 ELSE 0 END) AS sent_count,
            SUM(CASE WHEN nr.status='Failed' THEN 1 ELSE 0 END) AS failed_count
        FROM notification_campaigns nc
        LEFT JOIN notification_templates nt ON nt.id=nc.template_id
        LEFT JOIN notification_recipients nr ON nr.campaign_id=nc.id
        GROUP BY
            nc.id,nc.name,nc.template_id,nc.category,
            nc.subject,nc.body_text,nc.recipient_scope,
            nc.scheduled_for,nc.status,nc.created_by,
            nc.created_at,nc.updated_at,nt.name
        ORDER BY nc.id DESC
        LIMIT 100
        """
    ).fetchall()

    summary = connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM notification_templates WHERE active=1) AS active_templates,
            (SELECT COUNT(*) FROM notification_campaigns WHERE status='Draft') AS draft_campaigns,
            (SELECT COUNT(*) FROM notification_recipients WHERE status='Queued') AS queued_recipients,
            (SELECT COUNT(*) FROM notification_recipients WHERE status='Failed') AS failed_recipients
        """
    ).fetchone()

    connection.close()

    return render_template(
        "notification_center.html",
        templates=[dict(row) for row in templates],
        campaigns=[dict(row) for row in campaigns],
        summary=dict(summary),
    )


@app.route("/admin/notifications/templates/save", methods=["POST"])
@permission_required("notifications")
def save_notification_template():
    template_id = request.form.get("id","").strip()
    values = (
        request.form.get("name","").strip(),
        request.form.get("category","General").strip(),
        request.form.get("subject","").strip(),
        request.form.get("body_text","").strip(),
        1 if request.form.get("active")=="on" else 0,
    )

    connection = get_db()

    if template_id:
        connection.execute(
            """
            UPDATE notification_templates SET
                name=?,category=?,subject=?,body_text=?,active=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            values + (int(template_id),),
        )
        saved_id = int(template_id)
    else:
        sql = """
            INSERT INTO notification_templates (
                name,category,subject,body_text,
                active,created_by
            ) VALUES (?,?,?,?,?,?)
        """
        if connection.backend=="postgresql":
            sql += " RETURNING id"
        cursor = connection.execute(
            sql,
            values + (int(session.get("admin_user_id") or 0) or None,),
        )
        saved_id = (
            int(cursor.fetchone()["id"])
            if connection.backend=="postgresql"
            else int(cursor.lastrowid)
        )

    connection.commit()
    connection.close()
    flash("Notification template saved.","success")
    return redirect(url_for("notification_template",template_id=saved_id))


@app.route("/admin/notifications/templates/<int:template_id>")
@permission_required("notifications")
def notification_template(template_id):
    connection = get_db()
    template = connection.execute(
        "SELECT * FROM notification_templates WHERE id=?",
        (template_id,),
    ).fetchone()
    connection.close()

    if not template:
        return ("Template not found",404)

    return render_template(
        "notification_template.html",
        template=dict(template),
    )


@app.route("/admin/notifications/campaigns/create", methods=["POST"])
@permission_required("notifications")
def create_notification_campaign():
    template_value = request.form.get("template_id","").strip()
    template_id = int(template_value) if template_value else None
    scope = request.form.get("recipient_scope","Manual").strip()

    connection = get_db()
    template = None
    if template_id:
        template = connection.execute(
            "SELECT * FROM notification_templates WHERE id=?",
            (template_id,),
        ).fetchone()

    subject = request.form.get("subject","").strip()
    body_text = request.form.get("body_text","").strip()
    category = request.form.get("category","General").strip()

    if template:
        if not subject:
            subject = template["subject"]
        if not body_text:
            body_text = template["body_text"]
        if category=="General":
            category = template["category"]

    sql = """
        INSERT INTO notification_campaigns (
            name,template_id,category,subject,body_text,
            recipient_scope,scheduled_for,status,created_by
        ) VALUES (?,?,?,?,?,?,?,'Draft',?)
    """
    if connection.backend=="postgresql":
        sql += " RETURNING id"

    cursor = connection.execute(
        sql,
        (
            request.form.get("name","").strip(),
            template_id,
            category,
            subject,
            body_text,
            scope,
            request.form.get("scheduled_for","").strip() or None,
            int(session.get("admin_user_id") or 0) or None,
        ),
    )
    campaign_id = (
        int(cursor.fetchone()["id"])
        if connection.backend=="postgresql"
        else int(cursor.lastrowid)
    )

    if scope!="Manual":
        for recipient in notification_scope_recipients(connection,scope):
            connection.execute(
                """
                INSERT INTO notification_recipients (
                    campaign_id,family_id,student_id,
                    recipient_name,recipient_email,recipient_phone,
                    source_type,source_reference,status
                ) VALUES (?,?,?,?,?,?,?,?,'Queued')
                """,
                (
                    campaign_id,
                    recipient["family_id"],
                    recipient["student_id"],
                    recipient["recipient_name"],
                    recipient["recipient_email"],
                    recipient["recipient_phone"],
                    recipient["source_type"],
                    recipient["source_reference"],
                ),
            )

    connection.commit()
    connection.close()

    flash("Notification campaign created.","success")
    return redirect(url_for("notification_campaign",campaign_id=campaign_id))


@app.route("/admin/notifications/campaigns/<int:campaign_id>")
@permission_required("notifications")
def notification_campaign(campaign_id):
    connection = get_db()

    campaign = connection.execute(
        """
        SELECT nc.*,nt.name AS template_name
        FROM notification_campaigns nc
        LEFT JOIN notification_templates nt ON nt.id=nc.template_id
        WHERE nc.id=?
        """,
        (campaign_id,),
    ).fetchone()

    if not campaign:
        connection.close()
        return ("Campaign not found",404)

    recipients = connection.execute(
        """
        SELECT *
        FROM notification_recipients
        WHERE campaign_id=?
        ORDER BY recipient_name,recipient_email,id
        """,
        (campaign_id,),
    ).fetchall()

    log_rows = connection.execute(
        """
        SELECT
            ndl.*,
            nr.recipient_name,
            nr.recipient_email
        FROM notification_delivery_log ndl
        JOIN notification_recipients nr ON nr.id=ndl.recipient_id
        WHERE ndl.campaign_id=?
        ORDER BY ndl.id DESC
        LIMIT 200
        """,
        (campaign_id,),
    ).fetchall()

    families = connection.execute(
        """
        SELECT id,family_name,primary_email,primary_phone
        FROM families
        WHERE COALESCE(primary_email,'')!=''
        ORDER BY family_name
        """
    ).fetchall()

    connection.close()

    return render_template(
        "notification_campaign.html",
        campaign=dict(campaign),
        recipients=[dict(row) for row in recipients],
        delivery_log=[dict(row) for row in log_rows],
        families=[dict(row) for row in families],
    )


@app.route("/admin/notifications/campaigns/<int:campaign_id>/update", methods=["POST"])
@permission_required("notifications")
def update_notification_campaign(campaign_id):
    connection = get_db()
    connection.execute(
        """
        UPDATE notification_campaigns SET
            name=?,category=?,subject=?,body_text=?,
            scheduled_for=?,updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (
            request.form.get("name","").strip(),
            request.form.get("category","General").strip(),
            request.form.get("subject","").strip(),
            request.form.get("body_text","").strip(),
            request.form.get("scheduled_for","").strip() or None,
            campaign_id,
        ),
    )
    connection.commit()
    connection.close()
    flash("Campaign updated.","success")
    return redirect(url_for("notification_campaign",campaign_id=campaign_id))


@app.route("/admin/notifications/campaigns/<int:campaign_id>/recipients/add", methods=["POST"])
@permission_required("notifications")
def add_notification_recipient(campaign_id):
    connection = get_db()

    family_value = request.form.get("family_id","").strip()
    family_id = int(family_value) if family_value else None

    recipient_name = request.form.get("recipient_name","").strip()
    recipient_email = request.form.get("recipient_email","").strip()
    recipient_phone = request.form.get("recipient_phone","").strip()

    if family_id and (not recipient_name or not recipient_email):
        family = connection.execute(
            """
            SELECT family_name,primary_email,primary_phone
            FROM families
            WHERE id=?
            """,
            (family_id,),
        ).fetchone()
        if family:
            recipient_name = recipient_name or family["family_name"]
            recipient_email = recipient_email or family["primary_email"]
            recipient_phone = recipient_phone or family["primary_phone"]

    if not recipient_email:
        connection.close()
        flash("Recipient email is required.","error")
        return redirect(url_for("notification_campaign",campaign_id=campaign_id))

    connection.execute(
        """
        INSERT INTO notification_recipients (
            campaign_id,family_id,recipient_name,
            recipient_email,recipient_phone,
            source_type,source_reference,status
        ) VALUES (?,?,?,?,?,'Manual','','Queued')
        """,
        (
            campaign_id,
            family_id,
            recipient_name,
            recipient_email,
            recipient_phone,
        ),
    )
    connection.commit()
    connection.close()

    flash("Recipient added.","success")
    return redirect(url_for("notification_campaign",campaign_id=campaign_id))


@app.route("/admin/notifications/recipients/<int:recipient_id>/remove", methods=["POST"])
@permission_required("notifications")
def remove_notification_recipient(recipient_id):
    connection = get_db()
    recipient = connection.execute(
        "SELECT campaign_id FROM notification_recipients WHERE id=?",
        (recipient_id,),
    ).fetchone()

    if not recipient:
        connection.close()
        return ("Recipient not found",404)

    campaign_id = int(recipient["campaign_id"])
    connection.execute(
        "DELETE FROM notification_recipients WHERE id=?",
        (recipient_id,),
    )
    connection.commit()
    connection.close()

    flash("Recipient removed.","success")
    return redirect(url_for("notification_campaign",campaign_id=campaign_id))


@app.route("/admin/notifications/campaigns/<int:campaign_id>/queue", methods=["POST"])
@permission_required("notifications")
def queue_notification_campaign(campaign_id):
    connection = get_db()

    campaign = connection.execute(
        "SELECT * FROM notification_campaigns WHERE id=?",
        (campaign_id,),
    ).fetchone()

    if not campaign:
        connection.close()
        return ("Campaign not found",404)

    recipients = connection.execute(
        """
        SELECT *
        FROM notification_recipients
        WHERE campaign_id=?
          AND COALESCE(recipient_email,'')!=''
        """,
        (campaign_id,),
    ).fetchall()

    if not recipients:
        connection.close()
        flash("Add at least one recipient before queueing the campaign.","error")
        return redirect(url_for("notification_campaign",campaign_id=campaign_id))

    for recipient in recipients:
        existing = connection.execute(
            """
            SELECT id
            FROM notification_delivery_log
            WHERE campaign_id=? AND recipient_id=?
              AND status IN ('Queued','Sent')
            """,
            (campaign_id,recipient["id"]),
        ).fetchone()

        if not existing:
            connection.execute(
                """
                INSERT INTO notification_delivery_log (
                    campaign_id,recipient_id,channel,
                    provider,status
                ) VALUES (?,?,'Email','Internal Queue','Queued')
                """,
                (campaign_id,recipient["id"]),
            )

        connection.execute(
            """
            UPDATE notification_recipients SET
                status='Queued',
                last_error='',
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (recipient["id"],),
        )

    connection.execute(
        """
        UPDATE notification_campaigns SET
            status='Queued',
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (campaign_id,),
    )

    connection.commit()
    connection.close()

    event_id = create_workflow_event(
        "notification_campaign_queued",
        "notifications",
        "Notification campaign queued",
        f"Campaign #{campaign_id} · {len(recipients)} recipient(s)",
        "info",
        str(campaign_id),
    )
    evaluate_workflow_rules(event_id)

    flash("Campaign queued in the internal notification engine.","success")
    return redirect(url_for("notification_campaign",campaign_id=campaign_id))


@app.route("/admin/notifications/delivery/<int:delivery_id>/mark-sent", methods=["POST"])
@permission_required("notifications")
def mark_notification_sent(delivery_id):
    connection = get_db()

    delivery = connection.execute(
        """
        SELECT campaign_id,recipient_id
        FROM notification_delivery_log
        WHERE id=?
        """,
        (delivery_id,),
    ).fetchone()

    if not delivery:
        connection.close()
        return ("Delivery record not found",404)

    connection.execute(
        """
        UPDATE notification_delivery_log SET
            status='Sent',
            sent_at=CURRENT_TIMESTAMP,
            error_message=''
        WHERE id=?
        """,
        (delivery_id,),
    )
    connection.execute(
        """
        UPDATE notification_recipients SET
            status='Sent',
            last_error='',
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (delivery["recipient_id"],),
    )

    remaining = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM notification_recipients
        WHERE campaign_id=? AND status!='Sent'
        """,
        (delivery["campaign_id"],),
    ).fetchone()

    if int(remaining["count"] or 0)==0:
        connection.execute(
            """
            UPDATE notification_campaigns SET
                status='Completed',
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (delivery["campaign_id"],),
        )

    connection.commit()
    campaign_id = int(delivery["campaign_id"])
    connection.close()

    flash("Delivery marked sent.","success")
    return redirect(url_for("notification_campaign",campaign_id=campaign_id))


@app.route("/admin/notifications/delivery/<int:delivery_id>/mark-failed", methods=["POST"])
@permission_required("notifications")
def mark_notification_failed(delivery_id):
    connection = get_db()

    delivery = connection.execute(
        """
        SELECT campaign_id,recipient_id
        FROM notification_delivery_log
        WHERE id=?
        """,
        (delivery_id,),
    ).fetchone()

    if not delivery:
        connection.close()
        return ("Delivery record not found",404)

    error_message = request.form.get("error_message","").strip() or "Delivery failed"

    connection.execute(
        """
        UPDATE notification_delivery_log SET
            status='Failed',
            error_message=?
        WHERE id=?
        """,
        (error_message,delivery_id),
    )
    connection.execute(
        """
        UPDATE notification_recipients SET
            status='Failed',
            last_error=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (error_message,delivery["recipient_id"]),
    )

    connection.commit()
    campaign_id = int(delivery["campaign_id"])
    connection.close()

    flash("Delivery marked failed.","success")
    return redirect(url_for("notification_campaign",campaign_id=campaign_id))


@app.route("/admin/ticketing")
@permission_required("ticketing")
def ticketing_center():
    connection = get_db()
    shows = connection.execute(
        """
        SELECT
            rs.id,
            rs.name,
            rs.show_date,
            rs.start_time,
            rp.name AS production_name,
            tss.venue_id,
            tss.default_price,
            tss.sales_status,
            tv.name AS venue_name,
            COUNT(DISTINCT ts.id) AS seat_count,
            COUNT(DISTINCT CASE WHEN tk.status='Valid' THEN tk.id END) AS sold_count,
            COALESCE(SUM(CASE WHEN tk.status='Valid' THEN tk.price ELSE 0 END),0) AS ticket_revenue
        FROM recital_shows rs
        JOIN recital_productions rp ON rp.id=rs.production_id
        LEFT JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id
        LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id
        LEFT JOIN ticket_sections sec ON sec.venue_id=tss.venue_id
        LEFT JOIN ticket_seats ts ON ts.section_id=sec.id AND ts.active=1
        LEFT JOIN tickets tk ON tk.recital_show_id=rs.id AND tk.seat_id=ts.id
        GROUP BY
            rs.id,rs.name,rs.show_date,rs.start_time,
            rp.name,tss.venue_id,tss.default_price,
            tss.sales_status,tv.name
        ORDER BY rs.show_date,rs.start_time,rs.id
        """
    ).fetchall()

    venues = connection.execute(
        """
        SELECT
            tv.*,
            COUNT(DISTINCT sec.id) AS section_count,
            COUNT(DISTINCT ts.id) AS seat_count
        FROM ticket_venues tv
        LEFT JOIN ticket_sections sec ON sec.venue_id=tv.id
        LEFT JOIN ticket_seats ts ON ts.section_id=sec.id AND ts.active=1
        GROUP BY
            tv.id,tv.name,tv.address,tv.notes,tv.active,
            tv.created_at,tv.updated_at
        ORDER BY tv.active DESC,tv.name
        """
    ).fetchall()

    summary = connection.execute(
        """
        SELECT
            COALESCE((SELECT COUNT(*) FROM tickets WHERE status='Valid'),0) AS tickets_sold,
            COALESCE((SELECT SUM(price) FROM tickets WHERE status='Valid'),0) AS revenue,
            COALESCE((SELECT COUNT(*) FROM tickets WHERE checked_in_at IS NOT NULL AND status='Valid'),0) AS checked_in,
            COALESCE((SELECT COUNT(*) FROM ticket_holds WHERE status='Active'),0) AS held_orders
        """
    ).fetchone()
    connection.close()

    return render_template(
        "ticketing_center.html",
        shows=[dict(row) for row in shows],
        venues=[dict(row) for row in venues],
        summary=dict(summary),
    )


@app.route("/admin/ticketing/venues/save", methods=["POST"])
@permission_required("ticketing")
def save_ticket_venue():
    venue_id = request.form.get("id", "").strip()
    values = (
        request.form.get("name", "").strip(),
        request.form.get("address", "").strip(),
        request.form.get("notes", "").strip(),
        1 if request.form.get("active") == "on" else 0,
    )
    connection = get_db()
    if venue_id:
        connection.execute(
            """
            UPDATE ticket_venues SET
                name=?,address=?,notes=?,active=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            values + (int(venue_id),),
        )
        saved_id = int(venue_id)
    else:
        sql = """
            INSERT INTO ticket_venues (
                name,address,notes,active
            ) VALUES (?,?,?,?)
        """
        if connection.backend == "postgresql":
            sql += " RETURNING id"
        cursor = connection.execute(sql, values)
        saved_id = (
            int(cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(cursor.lastrowid)
        )
    connection.commit()
    connection.close()
    flash("Venue saved.", "success")
    return redirect(url_for("ticket_venue", venue_id=saved_id))


@app.route("/admin/ticketing/venues/<int:venue_id>")
@permission_required("ticketing")
def ticket_venue(venue_id: int):
    connection = get_db()
    venue = connection.execute(
        """
        SELECT tv.*,
          COALESCE((SELECT COUNT(*) FROM ticket_show_settings tss WHERE tss.venue_id=tv.id),0) AS assigned_show_count,
          COALESCE((SELECT COUNT(*) FROM tickets tk JOIN ticket_seats ts ON ts.id=tk.seat_id JOIN ticket_sections sec ON sec.id=ts.section_id WHERE sec.venue_id=tv.id),0) AS issued_ticket_count,
          COALESCE(tvl.booth_enabled,0) AS booth_enabled,
          COALESCE(tvl.booth_label,'CREW BOOTH') AS booth_label,
          COALESCE(tvl.booth_position,'Rear Center') AS booth_position
        FROM ticket_venues tv LEFT JOIN ticket_venue_layouts tvl ON tvl.venue_id=tv.id WHERE tv.id=?
        """,
        (venue_id,),
    ).fetchone()
    if not venue:
        connection.close()
        return ("Venue not found", 404)

    sections = connection.execute(
        """
        SELECT sec.*, COUNT(ts.id) AS seat_count,
               COALESCE(tsl.orientation,'Horizontal') AS orientation,
               COALESCE(tsl.placement,'Center') AS placement,
               COALESCE(tsl.x_pos,400) AS x_pos,
               COALESCE(tsl.y_pos,250) AS y_pos,
               COALESCE(tsl.width_px,600) AS width_px,
               COALESCE(tsl.height_px,220) AS height_px,
               COALESCE(tsl.rotation_deg,0) AS rotation_deg,
               COALESCE(tsl.z_index,10) AS z_index
        FROM ticket_sections sec
        LEFT JOIN ticket_seats ts ON ts.section_id=sec.id AND ts.active=1
        LEFT JOIN ticket_section_layouts tsl ON tsl.section_id=sec.id
        WHERE sec.venue_id=?
        GROUP BY sec.id,sec.venue_id,sec.name,sec.sort_order,sec.notes,sec.created_at,tsl.orientation,tsl.placement,tsl.x_pos,tsl.y_pos,tsl.width_px,tsl.height_px,tsl.rotation_deg,tsl.z_index
        ORDER BY sec.sort_order,sec.name
        """,
        (venue_id,),
    ).fetchall()

    seats = connection.execute(
        """
        SELECT ts.*,sec.name AS section_name,sec.sort_order,
               COALESCE(trl.extra_space_after,0) AS extra_space_after,
               COALESCE(trl.seat_direction,'Low Left') AS seat_direction,
               COALESCE(trl.notes,'') AS row_layout_notes,
               COALESCE(tsl.orientation,'Horizontal') AS section_orientation,
               COALESCE(tsl.placement,'Center') AS section_placement
        FROM ticket_seats ts
        JOIN ticket_sections sec ON sec.id=ts.section_id
        LEFT JOIN ticket_row_layouts trl
          ON trl.section_id=ts.section_id
         AND trl.row_label=ts.row_label
        LEFT JOIN ticket_section_layouts tsl ON tsl.section_id=ts.section_id
        WHERE sec.venue_id=?
        ORDER BY sec.sort_order,sec.name,ts.row_label,ts.seat_number
        """,
        (venue_id,),
    ).fetchall()
    canvas = connection.execute(
        "SELECT * FROM ticket_canvas_settings WHERE venue_id=?",
        (venue_id,),
    ).fetchone()
    if not canvas:
        canvas = {"venue_id":venue_id,"canvas_width":1400,"canvas_height":1100,"background_label":""}
    venue_objects = connection.execute(
        """
        SELECT *
        FROM ticket_venue_objects
        WHERE venue_id=? AND active=1
        ORDER BY sort_order,id
        """,
        (venue_id,),
    ).fetchall()
    connection.close()

    grouped_seats = {}
    row_layouts = {}
    for row in seats:
        item = dict(row)
        key = (item["section_id"], item["section_name"])
        grouped_seats.setdefault(key, {}).setdefault(item["row_label"], []).append(item)
        row_layouts[(item["section_id"],item["row_label"])] = {
            "extra_space_after": int(item["extra_space_after"] or 0),
            "seat_direction": item["seat_direction"] or "Low Left",
            "notes": item["row_layout_notes"] or "",
        }

    return render_template(
        "ticket_venue.html",
        venue=dict(venue),
        sections=[dict(row) for row in sections],
        grouped_seats=grouped_seats,
        row_layouts=row_layouts,
        venue_objects=[dict(row) for row in venue_objects],
        canvas=dict(canvas),
    )


@app.route("/admin/ticketing/venues/<int:venue_id>/sections/generate", methods=["POST"])
@permission_required("ticketing")
def generate_ticket_section(venue_id: int):
    section_name = request.form.get("name", "").strip()
    row_label = request.form.get("row_label", "A").strip().upper()
    first_seat = int(request.form.get("first_seat", "1") or 1)
    last_seat = int(request.form.get("last_seat", "1") or 1)
    seat_type = request.form.get("seat_type", "Standard").strip()
    sort_order = int(request.form.get("sort_order", "0") or 0)
    notes = request.form.get("notes", "").strip()

    if not section_name:
        flash("Section name is required.", "error")
        return redirect(url_for("ticket_venue", venue_id=venue_id))

    if not row_label:
        flash("Row label is required.", "error")
        return redirect(url_for("ticket_venue", venue_id=venue_id))

    step = 1 if last_seat >= first_seat else -1
    seat_numbers = list(range(first_seat, last_seat + step, step))

    if len(seat_numbers) > 500:
        flash("A single row cannot contain more than 500 seats.", "error")
        return redirect(url_for("ticket_venue", venue_id=venue_id))

    connection = get_db()

    section = connection.execute(
        """
        SELECT id
        FROM ticket_sections
        WHERE venue_id=? AND LOWER(name)=LOWER(?)
        """,
        (venue_id, section_name),
    ).fetchone()

    if section:
        section_id = int(section["id"])
        connection.execute(
            """
            UPDATE ticket_sections SET
                sort_order=?,
                notes=CASE WHEN ?!='' THEN ? ELSE notes END
            WHERE id=?
            """,
            (sort_order, notes, notes, section_id),
        )
    else:
        section_sql = """
            INSERT INTO ticket_sections (
                venue_id,name,sort_order,notes
            ) VALUES (?,?,?,?)
        """
        if connection.backend == "postgresql":
            section_sql += " RETURNING id"

        cursor = connection.execute(
            section_sql,
            (venue_id, section_name, sort_order, notes),
        )
        section_id = (
            int(cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(cursor.lastrowid)
        )

    existing_rows = connection.execute(
        """
        SELECT seat_number
        FROM ticket_seats
        WHERE section_id=? AND row_label=?
        """,
        (section_id, row_label),
    ).fetchall()
    existing_numbers = {
        int(existing_row["seat_number"])
        for existing_row in existing_rows
    }

    created = 0
    skipped = 0

    for seat_number in seat_numbers:
        if seat_number in existing_numbers:
            skipped += 1
            continue

        connection.execute(
            """
            INSERT INTO ticket_seats (
                section_id,row_label,seat_number,
                seat_label,seat_type,active
            ) VALUES (?,?,?,?,?,1)
            """,
            (
                section_id,
                row_label,
                seat_number,
                f"{row_label}-{seat_number}",
                seat_type,
            ),
        )
        created += 1

    connection.commit()
    connection.close()

    message = (
        f"Row {row_label} added with {created} seat(s), "
        f"numbered {first_seat} through {last_seat}."
    )
    if skipped:
        message += f" {skipped} duplicate seat number(s) were skipped."

    flash(message, "success")
    return redirect(url_for("ticket_venue", venue_id=venue_id))



def venue_has_ticket_history(connection, venue_id: int) -> bool:
    row = connection.execute("""SELECT COUNT(*) AS count FROM tickets tk JOIN ticket_seats ts ON ts.id=tk.seat_id JOIN ticket_sections sec ON sec.id=ts.section_id WHERE sec.venue_id=?""",(venue_id,)).fetchone()
    return int(row["count"] or 0)>0

@app.route("/admin/ticketing/venues/<int:venue_id>/delete",methods=["POST"])
@permission_required("ticketing")
def delete_ticket_venue(venue_id):
    c=get_db()
    if venue_has_ticket_history(c,venue_id):
        c.close(); flash("This venue has ticket history and cannot be deleted. Mark it inactive instead.","error"); return redirect(url_for("ticket_venue",venue_id=venue_id))
    used=c.execute("SELECT COUNT(*) AS count FROM ticket_show_settings WHERE venue_id=?",(venue_id,)).fetchone()
    if int(used["count"] or 0)>0:
        c.close(); flash("Remove this venue from recital shows before deleting it.","error"); return redirect(url_for("ticket_venue",venue_id=venue_id))
    c.execute("DELETE FROM ticket_venues WHERE id=?",(venue_id,)); c.commit(); c.close(); flash("Unfinished venue deleted.","success"); return redirect(url_for("ticketing_center"))

@app.route("/admin/ticketing/venues/<int:venue_id>/reset",methods=["POST"])
@permission_required("ticketing")
def reset_ticket_venue_chart(venue_id):
    c=get_db()
    if venue_has_ticket_history(c,venue_id): c.close(); flash("Chart is locked because tickets exist.","error"); return redirect(url_for("ticket_venue",venue_id=venue_id))
    c.execute("DELETE FROM ticket_sections WHERE venue_id=?",(venue_id,)); c.commit(); c.close(); flash("Unfinished seating chart reset.","success"); return redirect(url_for("ticket_venue",venue_id=venue_id))

@app.route("/admin/ticketing/sections/<int:section_id>/update",methods=["POST"])
@permission_required("ticketing")
def update_ticket_section(section_id):
    c=get_db(); sec=c.execute("SELECT venue_id FROM ticket_sections WHERE id=?",(section_id,)).fetchone()
    if not sec: c.close(); return ("Section not found",404)
    venue_id=int(sec["venue_id"])
    if venue_has_ticket_history(c,venue_id): c.close(); flash("Layout is locked because tickets exist.","error"); return redirect(url_for("ticket_venue",venue_id=venue_id))
    c.execute("UPDATE ticket_sections SET name=?,sort_order=?,notes=? WHERE id=?",(request.form.get("name","").strip(),int(request.form.get("sort_order","0") or 0),request.form.get("notes","").strip(),section_id)); c.commit(); c.close(); flash("Section updated.","success"); return redirect(url_for("ticket_venue",venue_id=venue_id))

@app.route("/admin/ticketing/sections/<int:section_id>/delete",methods=["POST"])
@permission_required("ticketing")
def delete_ticket_section(section_id):
    c=get_db(); sec=c.execute("SELECT venue_id FROM ticket_sections WHERE id=?",(section_id,)).fetchone()
    if not sec: c.close(); return ("Section not found",404)
    venue_id=int(sec["venue_id"])
    if venue_has_ticket_history(c,venue_id): c.close(); flash("Layout is locked because tickets exist.","error"); return redirect(url_for("ticket_venue",venue_id=venue_id))
    c.execute("DELETE FROM ticket_sections WHERE id=?",(section_id,)); c.commit(); c.close(); flash("Section deleted.","success"); return redirect(url_for("ticket_venue",venue_id=venue_id))

def insert_ticket_section(connection, venue_id, name, sort_order, notes=""):
    sql = """
        INSERT INTO ticket_sections (
            venue_id,name,sort_order,notes
        ) VALUES (?,?,?,?)
    """
    if connection.backend == "postgresql":
        sql += " RETURNING id"
    cursor = connection.execute(sql, (venue_id, name, sort_order, notes))
    return (
        int(cursor.fetchone()["id"])
        if connection.backend == "postgresql"
        else int(cursor.lastrowid)
    )


def add_ticket_row(
    connection,
    section_id,
    row_label,
    first_seat,
    last_seat,
    seat_type="Standard",
    seat_direction="Low Right",
    extra_space_after=0,
    row_notes="",
):
    step = 1 if last_seat >= first_seat else -1
    for seat_number in range(first_seat, last_seat + step, step):
        connection.execute(
            """
            INSERT INTO ticket_seats (
                section_id,row_label,seat_number,
                seat_label,seat_type,active
            ) VALUES (?,?,?,?,?,1)
            ON CONFLICT(section_id,row_label,seat_number) DO NOTHING
            """,
            (
                section_id,
                row_label,
                seat_number,
                f"{row_label}-{seat_number}",
                seat_type,
            ),
        )

    connection.execute(
        """
        INSERT INTO ticket_row_layouts (
            section_id,row_label,extra_space_after,
            seat_direction,notes
        ) VALUES (?,?,?,?,?)
        ON CONFLICT(section_id,row_label) DO UPDATE SET
            extra_space_after=excluded.extra_space_after,
            seat_direction=excluded.seat_direction,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            section_id,
            row_label,
            extra_space_after,
            seat_direction,
            row_notes,
        ),
    )


def configure_ticket_section_layout(
    connection, section_id, orientation="Horizontal", placement="Center",
    x_pos=400, y_pos=250, width_px=600, height_px=220,
    rotation_deg=0, z_index=10,
):
    connection.execute(
        """
        INSERT INTO ticket_section_layouts (
            section_id,orientation,placement,x_pos,y_pos,width_px,height_px,rotation_deg,z_index
        ) VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(section_id) DO UPDATE SET
            orientation=excluded.orientation,placement=excluded.placement,
            x_pos=excluded.x_pos,y_pos=excluded.y_pos,width_px=excluded.width_px,
            height_px=excluded.height_px,rotation_deg=excluded.rotation_deg,
            z_index=excluded.z_index,updated_at=CURRENT_TIMESTAMP
        """,
        (section_id,orientation,placement,x_pos,y_pos,width_px,height_px,rotation_deg,z_index),
    )


@app.route("/admin/ticketing/venues/<int:venue_id>/presets/meyer", methods=["POST"])
@permission_required("ticketing")
def apply_meyer_theater_preset(venue_id):
    connection = get_db()

    if venue_has_ticket_history(connection, venue_id):
        connection.close()
        flash(
            "The Meyer Theater preset cannot be applied after tickets exist.",
            "error",
        )
        return redirect(url_for("ticket_venue", venue_id=venue_id))

    existing_sections = connection.execute(
        "SELECT COUNT(*) AS count FROM ticket_sections WHERE venue_id=?",
        (venue_id,),
    ).fetchone()
    if int(existing_sections["count"] or 0) > 0:
        connection.close()
        flash(
            "Reset the unfinished seating chart before applying the Meyer Theater preset.",
            "error",
        )
        return redirect(url_for("ticket_venue", venue_id=venue_id))

    connection.execute(
        """
        INSERT INTO ticket_canvas_settings (venue_id,canvas_width,canvas_height,background_label)
        VALUES (?,1400,1100,'MEYER THEATER')
        ON CONFLICT(venue_id) DO UPDATE SET canvas_width=1400,canvas_height=1100,
        background_label='MEYER THEATER',updated_at=CURRENT_TIMESTAMP
        """,
        (venue_id,),
    )

    connection.execute(
        """
        INSERT INTO ticket_venue_layouts (
            venue_id,booth_enabled,booth_label,booth_position
        ) VALUES (?,1,'THEATER CREW BOOTH','Rear Center')
        ON CONFLICT(venue_id) DO UPDATE SET
            booth_enabled=1,
            booth_label='THEATER CREW BOOTH',
            booth_position='Rear Center',
            updated_at=CURRENT_TIMESTAMP
        """,
        (venue_id,),
    )

    upper_orchestra = insert_ticket_section(
        connection,
        venue_id,
        "Upper Orchestra",
        10,
        "Meyer Theater Rows F through R.",
    )
    configure_ticket_section_layout(
        connection,
        upper_orchestra,
        "Horizontal",
        "Center",
        185,
        120,
        1030,
        430,
        0,
        10,
    )

    upper_rows = [
        ("F", 101, 132, 0),
        ("G", 101, 131, 0),
        ("H", 101, 132, 18),
        ("J", 101, 131, 0),
        ("K", 101, 131, 0),
        ("L", 101, 131, 0),
        ("M", 101, 132, 0),
        ("N", 101, 132, 0),
        ("O", 101, 132, 0),
        ("P", 101, 131, 0),
        ("Q", 101, 131, 0),
        ("R", 101, 131, 0),
    ]
    for row_label, first_seat, last_seat, gap in upper_rows:
        add_ticket_row(
            connection,
            upper_orchestra,
            row_label,
            first_seat,
            last_seat,
            "Standard",
            "Low Right",
            gap,
            "Meyer Theater upper orchestra row.",
        )

    row_x = insert_ticket_section(
        connection,
        venue_id,
        "Row X Accessible and Soft Seating",
        20,
        "One soft seat on each end with numbered seats 101 through 130.",
    )
    configure_ticket_section_layout(
        connection,
        row_x,
        "Horizontal",
        "Center",
        115,
        560,
        1170,
        125,
        0,
        20,
    )

    # Row X contains one soft-seat position on each end
    # with thirty numbered seats, 101 through 130, between them.
    row_x_positions = [
        (100, "Soft Seating", "X-SOFT-LEFT"),
    ]
    row_x_positions.extend(
        (seat_number, "Standard", f"X-{seat_number}")
        for seat_number in range(101, 131)
    )
    row_x_positions.append(
        (131, "Soft Seating", "X-SOFT-RIGHT")
    )

    for seat_number, seat_type, seat_label in row_x_positions:
        connection.execute(
            """
            INSERT INTO ticket_seats (
                section_id,row_label,seat_number,
                seat_label,seat_type,active
            ) VALUES (?,'X',?,?,?,1)
            """,
            (row_x, seat_number, seat_label, seat_type),
        )

    connection.execute(
        """
        INSERT INTO ticket_row_layouts (
            section_id,row_label,extra_space_after,
            seat_direction,notes
        ) VALUES (?,'X',18,'Low Left',?)
        """,
        (
            row_x,
            "Soft seat, numbered seats 101 through 130, soft seat.",
        ),
    )

    lower_orchestra = insert_ticket_section(
        connection,
        venue_id,
        "Lower Orchestra",
        30,
        "Meyer Theater Rows A through E.",
    )
    configure_ticket_section_layout(
        connection,
        lower_orchestra,
        "Horizontal",
        "Center",
        315,
        720,
        770,
        235,
        0,
        10,
    )

    lower_rows = [
        ("E", 101, 125, 0),
        ("D", 101, 124, 0),
        ("C", 101, 123, 0),
        ("B", 101, 122, 0),
        ("A", 101, 121, 0),
    ]
    for row_label, first_seat, last_seat, gap in lower_rows:
        add_ticket_row(
            connection,
            lower_orchestra,
            row_label,
            first_seat,
            last_seat,
            "Standard",
            "Low Right",
            gap,
            "Meyer Theater lower orchestra row.",
        )

    vip_left = insert_ticket_section(
        connection,
        venue_id,
        "Upper VIP Left",
        30,
        "Vertical VIP seating beside round guest tables.",
    )
    configure_ticket_section_layout(connection, vip_left, "Vertical", "Left", 35, 160, 125, 510, 0, 12)
    add_ticket_row(
        connection,
        vip_left,
        "VL",
        101,
        114,
        "VIP",
        "Low Left",
        0,
        "Upper-deck VIP starter range.",
    )

    vip_right = insert_ticket_section(
        connection,
        venue_id,
        "Upper VIP Right",
        40,
        "Vertical VIP seating beside round guest tables.",
    )
    configure_ticket_section_layout(connection, vip_right, "Vertical", "Right", 1240, 160, 125, 510, 0, 12)
    add_ticket_row(
        connection,
        vip_right,
        "VR",
        115,
        128,
        "VIP",
        "Low Right",
        0,
        "Upper-deck VIP starter range.",
    )

    vip_rear = insert_ticket_section(
        connection,
        venue_id,
        "Upper VIP Rear",
        50,
        "Small horizontal VIP group beside the crew booth.",
    )
    configure_ticket_section_layout(connection, vip_rear, "Horizontal", "Center", 560, 790, 280, 90, 0, 16)
    add_ticket_row(
        connection,
        vip_rear,
        "V",
        129,
        132,
        "VIP",
        "Low Left",
        18,
        "Rear VIP seating beside the crew booth.",
    )

    objects = [
        ("Stage","STAGE","Front Center",5,320,990,760,55,0,40,"Rectangle"),
        ("Crew Booth","THEATER CREW BOOTH","Rear Center",50,540,20,320,80,0,35,"Rectangle"),
        ("Label","ROW X — ACCESSIBLE & SOFT SEATING","Center",60,330,545,740,28,0,25,"Label"),
    ]
    for object_type,label,placement,sort_order,x_pos,y_pos,width_px,height_px,rotation_deg,z_index,shape in objects:
        connection.execute(
            """
            INSERT INTO ticket_venue_objects (
                venue_id,object_type,label,placement,sort_order,x_pos,y_pos,
                width_px,height_px,rotation_deg,z_index,shape,width_units,height_units,notes,active
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,2,1,'Meyer coordinate preset object',1)
            """,
            (venue_id,object_type,label,placement,sort_order,x_pos,y_pos,width_px,height_px,rotation_deg,z_index,shape),
        )


    connection.execute(
        """
        INSERT INTO ticket_venue_presets (
            venue_id,preset_key,applied_by
        ) VALUES (?,'meyer_theater_v1',?)
        ON CONFLICT(venue_id,preset_key) DO NOTHING
        """,
        (
            venue_id,
            int(session.get("admin_user_id") or 0) or None,
        ),
    )

    connection.commit()
    connection.close()

    event_id = create_workflow_event(
        "ticket_venue_preset_applied",
        "ticketing",
        "Meyer Theater seating preset applied",
        f"Venue #{venue_id}",
        "success",
        str(venue_id),
    )
    evaluate_workflow_rules(event_id)

    flash(
        "Meyer Theater preset created. Review and adjust the editable seat ranges before selling tickets.",
        "success",
    )
    return redirect(url_for("ticket_venue", venue_id=venue_id))


@app.route("/admin/ticketing/venues/<int:venue_id>/canvas/position", methods=["POST"])
@permission_required("ticketing")
def save_ticket_canvas_position(venue_id):
    connection = get_db()

    if venue_has_ticket_history(connection, venue_id):
        connection.close()
        return jsonify({
            "ok": False,
            "message": "The venue layout is locked because ticket history exists.",
        }), 409

    payload = request.get_json(silent=True) or {}
    item_type = str(payload.get("item_type", "")).strip().lower()
    item_id = int(payload.get("item_id", 0) or 0)
    x_pos = int(round(float(payload.get("x_pos", 0) or 0)))
    y_pos = int(round(float(payload.get("y_pos", 0) or 0)))

    canvas = connection.execute(
        """
        SELECT canvas_width,canvas_height
        FROM ticket_canvas_settings
        WHERE venue_id=?
        """,
        (venue_id,),
    ).fetchone()

    canvas_width = int(canvas["canvas_width"] or 1400) if canvas else 1400
    canvas_height = int(canvas["canvas_height"] or 1100) if canvas else 1100

    if item_type == "section":
        item = connection.execute(
            """
            SELECT
                sec.id,
                COALESCE(tsl.width_px,600) AS width_px,
                COALESCE(tsl.height_px,220) AS height_px
            FROM ticket_sections sec
            LEFT JOIN ticket_section_layouts tsl ON tsl.section_id=sec.id
            WHERE sec.id=? AND sec.venue_id=?
            """,
            (item_id, venue_id),
        ).fetchone()

        if not item:
            connection.close()
            return jsonify({"ok": False, "message": "Section not found."}), 404

        max_x = max(0, canvas_width - int(item["width_px"] or 600))
        max_y = max(0, canvas_height - int(item["height_px"] or 220))
        x_pos = max(0, min(x_pos, max_x))
        y_pos = max(0, min(y_pos, max_y))

        connection.execute(
            """
            INSERT INTO ticket_section_layouts (
                section_id,x_pos,y_pos
            ) VALUES (?,?,?)
            ON CONFLICT(section_id) DO UPDATE SET
                x_pos=excluded.x_pos,
                y_pos=excluded.y_pos,
                updated_at=CURRENT_TIMESTAMP
            """,
            (item_id, x_pos, y_pos),
        )

    elif item_type == "object":
        item = connection.execute(
            """
            SELECT id,width_px,height_px
            FROM ticket_venue_objects
            WHERE id=? AND venue_id=?
            """,
            (item_id, venue_id),
        ).fetchone()

        if not item:
            connection.close()
            return jsonify({"ok": False, "message": "Theater object not found."}), 404

        max_x = max(0, canvas_width - int(item["width_px"] or 180))
        max_y = max(0, canvas_height - int(item["height_px"] or 90))
        x_pos = max(0, min(x_pos, max_x))
        y_pos = max(0, min(y_pos, max_y))

        connection.execute(
            """
            UPDATE ticket_venue_objects SET
                x_pos=?,
                y_pos=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND venue_id=?
            """,
            (x_pos, y_pos, item_id, venue_id),
        )

    else:
        connection.close()
        return jsonify({
            "ok": False,
            "message": "Unsupported canvas item type.",
        }), 400

    connection.commit()
    connection.close()

    return jsonify({
        "ok": True,
        "item_type": item_type,
        "item_id": item_id,
        "x_pos": x_pos,
        "y_pos": y_pos,
    })


@app.route("/admin/ticketing/venues/<int:venue_id>/canvas", methods=["POST"])
@permission_required("ticketing")
def update_ticket_canvas(venue_id):
    connection=get_db()
    if venue_has_ticket_history(connection,venue_id):
        connection.close(); flash("Canvas is locked because tickets exist.","error")
        return redirect(url_for("ticket_venue",venue_id=venue_id))
    connection.execute(
        """INSERT INTO ticket_canvas_settings(venue_id,canvas_width,canvas_height,background_label)
           VALUES(?,?,?,?) ON CONFLICT(venue_id) DO UPDATE SET
           canvas_width=excluded.canvas_width,canvas_height=excluded.canvas_height,
           background_label=excluded.background_label,updated_at=CURRENT_TIMESTAMP""",
        (venue_id,max(700,min(int(request.form.get("canvas_width","1400") or 1400),3000)),
         max(700,min(int(request.form.get("canvas_height","1100") or 1100),3000)),
         request.form.get("background_label","").strip())
    )
    connection.commit(); connection.close(); flash("Canvas updated.","success")
    return redirect(url_for("ticket_venue",venue_id=venue_id))


@app.route("/admin/ticketing/venues/<int:venue_id>/objects/save", methods=["POST"])
@permission_required("ticketing")
def save_ticket_venue_object(venue_id):
    connection=get_db()
    if venue_has_ticket_history(connection,venue_id):
        connection.close(); flash("Venue objects are locked because tickets exist.","error")
        return redirect(url_for("ticket_venue",venue_id=venue_id))
    object_id=request.form.get("id","").strip()
    values=(request.form.get("object_type","Label").strip(),request.form.get("label","").strip(),
        request.form.get("placement","Center").strip(),int(request.form.get("sort_order","0") or 0),
        int(request.form.get("x_pos","500") or 500),int(request.form.get("y_pos","800") or 800),
        max(30,int(request.form.get("width_px","180") or 180)),max(20,int(request.form.get("height_px","90") or 90)),
        int(request.form.get("rotation_deg","0") or 0),int(request.form.get("z_index","20") or 20),
        request.form.get("shape","Rectangle").strip(),max(1,int(request.form.get("width_units","2") or 2)),
        max(1,int(request.form.get("height_units","1") or 1)),request.form.get("notes","").strip(),
        1 if request.form.get("active")=="on" else 0)
    if object_id:
        connection.execute("""UPDATE ticket_venue_objects SET object_type=?,label=?,placement=?,sort_order=?,
            x_pos=?,y_pos=?,width_px=?,height_px=?,rotation_deg=?,z_index=?,shape=?,width_units=?,height_units=?,notes=?,active=?,updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND venue_id=?""",values+(int(object_id),venue_id))
    else:
        connection.execute("""INSERT INTO ticket_venue_objects(venue_id,object_type,label,placement,sort_order,x_pos,y_pos,width_px,height_px,rotation_deg,z_index,shape,width_units,height_units,notes,active)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(venue_id,)+values)
    connection.commit(); connection.close(); flash("Theater object saved.","success")
    return redirect(url_for("ticket_venue",venue_id=venue_id))


@app.route("/admin/ticketing/venues/<int:venue_id>/objects/<int:object_id>/delete", methods=["POST"])
@permission_required("ticketing")
def delete_ticket_venue_object(venue_id, object_id):
    connection = get_db()
    if venue_has_ticket_history(connection, venue_id):
        connection.close()
        flash("Venue objects are locked because tickets have been issued.", "error")
        return redirect(url_for("ticket_venue", venue_id=venue_id))

    connection.execute(
        "DELETE FROM ticket_venue_objects WHERE id=? AND venue_id=?",
        (object_id, venue_id),
    )
    connection.commit()
    connection.close()
    flash("Theater object deleted.", "success")
    return redirect(url_for("ticket_venue", venue_id=venue_id))


@app.route("/admin/ticketing/venues/<int:venue_id>/layout",methods=["POST"])
@permission_required("ticketing")
def update_ticket_venue_layout(venue_id):
    c=get_db()
    if venue_has_ticket_history(c,venue_id): c.close(); flash("Venue layout is locked because tickets exist.","error"); return redirect(url_for("ticket_venue",venue_id=venue_id))
    c.execute("""INSERT INTO ticket_venue_layouts(venue_id,booth_enabled,booth_label,booth_position) VALUES(?,?,?,?)
      ON CONFLICT(venue_id) DO UPDATE SET booth_enabled=excluded.booth_enabled,booth_label=excluded.booth_label,booth_position=excluded.booth_position,updated_at=CURRENT_TIMESTAMP""",
      (venue_id,1 if request.form.get("booth_enabled")=="on" else 0,request.form.get("booth_label","CREW BOOTH").strip() or "CREW BOOTH",request.form.get("booth_position","Rear Center").strip()))
    c.commit(); c.close(); flash("Theater objects updated.","success"); return redirect(url_for("ticket_venue",venue_id=venue_id))

@app.route("/admin/ticketing/sections/<int:section_id>/layout",methods=["POST"])
@permission_required("ticketing")
def update_ticket_section_layout(section_id):
    c=get_db(); sec=c.execute("SELECT venue_id FROM ticket_sections WHERE id=?",(section_id,)).fetchone()
    if not sec: c.close(); return ("Section not found",404)
    venue_id=int(sec["venue_id"])
    if venue_has_ticket_history(c,venue_id): c.close(); flash("Section layout is locked because tickets exist.","error"); return redirect(url_for("ticket_venue",venue_id=venue_id))
    c.execute("""INSERT INTO ticket_section_layouts(section_id,orientation,placement,x_pos,y_pos,width_px,height_px,rotation_deg,z_index)
      VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(section_id) DO UPDATE SET orientation=excluded.orientation,placement=excluded.placement,
      x_pos=excluded.x_pos,y_pos=excluded.y_pos,width_px=excluded.width_px,height_px=excluded.height_px,
      rotation_deg=excluded.rotation_deg,z_index=excluded.z_index,updated_at=CURRENT_TIMESTAMP""",
      (section_id,request.form.get("orientation","Horizontal").strip(),request.form.get("placement","Center").strip(),
       int(request.form.get("x_pos","400") or 400),int(request.form.get("y_pos","250") or 250),
       max(80,int(request.form.get("width_px","600") or 600)),max(60,int(request.form.get("height_px","220") or 220)),
       int(request.form.get("rotation_deg","0") or 0),int(request.form.get("z_index","10") or 10)))
    c.commit(); c.close(); flash("Section position updated.","success"); return redirect(url_for("ticket_venue",venue_id=venue_id))


@app.route("/admin/ticketing/sections/<int:section_id>/rows/<row_label>/layout",methods=["POST"])
@permission_required("ticketing")
def update_ticket_row_layout(section_id,row_label):
    connection=get_db()
    section=connection.execute("SELECT venue_id FROM ticket_sections WHERE id=?",(section_id,)).fetchone()
    if not section:
        connection.close()
        return ("Section not found",404)
    venue_id=int(section["venue_id"])
    if venue_has_ticket_history(connection,venue_id):
        connection.close()
        flash("Row layout is locked because tickets have been issued.","error")
        return redirect(url_for("ticket_venue",venue_id=venue_id))
    spacing=max(0,min(int(request.form.get("extra_space_after","0") or 0),200))
    connection.execute(
        """INSERT INTO ticket_row_layouts(section_id,row_label,extra_space_after,seat_direction,notes)
           VALUES(?,?,?,?,?)
           ON CONFLICT(section_id,row_label) DO UPDATE SET
           extra_space_after=excluded.extra_space_after,
           seat_direction=excluded.seat_direction,
           notes=excluded.notes,
           updated_at=CURRENT_TIMESTAMP""",
        (section_id,row_label.upper(),spacing,request.form.get("seat_direction","Low Left").strip(),request.form.get("notes","").strip())
    )
    connection.commit()
    connection.close()
    flash(f"Row {row_label.upper()} spacing updated.","success")
    return redirect(url_for("ticket_venue",venue_id=venue_id))


@app.route("/admin/ticketing/seats/<int:seat_id>/update",methods=["POST"])
@permission_required("ticketing")
def update_ticket_seat(seat_id):
    c=get_db(); seat=c.execute("SELECT sec.venue_id FROM ticket_seats ts JOIN ticket_sections sec ON sec.id=ts.section_id WHERE ts.id=?",(seat_id,)).fetchone()
    if not seat: c.close(); return ("Seat not found",404)
    venue_id=int(seat["venue_id"])
    if venue_has_ticket_history(c,venue_id): c.close(); flash("Layout is locked because tickets exist.","error"); return redirect(url_for("ticket_venue",venue_id=venue_id))
    row=request.form.get("row_label","").strip().upper(); num=int(request.form.get("seat_number","0") or 0)
    c.execute("UPDATE ticket_seats SET row_label=?,seat_number=?,seat_label=?,seat_type=?,active=? WHERE id=?",(row,num,request.form.get("seat_label","").strip() or f"{row}-{num}",request.form.get("seat_type","Standard").strip(),1 if request.form.get("active")=="on" else 0,seat_id)); c.commit(); c.close(); flash("Seat updated.","success"); return redirect(url_for("ticket_venue",venue_id=venue_id))

@app.route("/admin/ticketing/seats/<int:seat_id>/delete",methods=["POST"])
@permission_required("ticketing")
def delete_ticket_seat(seat_id):
    c=get_db(); seat=c.execute("SELECT sec.venue_id FROM ticket_seats ts JOIN ticket_sections sec ON sec.id=ts.section_id WHERE ts.id=?",(seat_id,)).fetchone()
    if not seat: c.close(); return ("Seat not found",404)
    venue_id=int(seat["venue_id"])
    if venue_has_ticket_history(c,venue_id): c.close(); flash("Layout is locked because tickets exist.","error"); return redirect(url_for("ticket_venue",venue_id=venue_id))
    c.execute("DELETE FROM ticket_seats WHERE id=?",(seat_id,)); c.commit(); c.close(); flash("Seat deleted.","success"); return redirect(url_for("ticket_venue",venue_id=venue_id))

@app.route("/admin/ticketing/shows/<int:show_id>/holds",methods=["POST"])
@permission_required("ticketing")
def create_ticket_hold(show_id):
    seats=[int(v) for v in request.form.getlist("seat_id") if v.isdigit()]
    if not seats: flash("Select at least one seat to hold.","error"); return redirect(url_for("ticket_show",show_id=show_id))
    c=get_db(); marks=','.join('?' for _ in seats)
    if c.execute(f"SELECT seat_id FROM tickets WHERE recital_show_id=? AND status='Valid' AND seat_id IN ({marks})",tuple([show_id]+seats)).fetchall() or c.execute(f"SELECT seat_id FROM ticket_hold_seats WHERE recital_show_id=? AND seat_id IN ({marks})",tuple([show_id]+seats)).fetchall():
        c.close(); flash("One or more seats are no longer available.","error"); return redirect(url_for("ticket_show",show_id=show_id))
    family=request.form.get("family_id","").strip(); sql="INSERT INTO ticket_holds (recital_show_id,family_id,held_for_name,email,phone,reason,notes,expires_at,status,created_by) VALUES (?,?,?,?,?,?,?,?,'Active',?)"
    if c.backend=='postgresql': sql+=' RETURNING id'
    cur=c.execute(sql,(show_id,int(family) if family else None,request.form.get("held_for_name","").strip(),request.form.get("email","").strip(),request.form.get("phone","").strip(),request.form.get("reason","").strip(),request.form.get("notes","").strip(),request.form.get("expires_at","").strip() or None,int(session.get("admin_user_id") or 0) or None))
    hold_id=int(cur.fetchone()["id"]) if c.backend=='postgresql' else int(cur.lastrowid)
    for seat_id in seats: c.execute("INSERT INTO ticket_hold_seats (hold_id,recital_show_id,seat_id) VALUES (?,?,?)",(hold_id,show_id,seat_id))
    c.commit(); c.close(); event_id=create_workflow_event("ticket_hold_created","ticketing","Seats placed on hold",f"Hold #{hold_id} · {len(seats)} seats","warning",str(hold_id)); evaluate_workflow_rules(event_id); flash("Seats placed on hold.","success"); return redirect(url_for("ticket_hold",hold_id=hold_id))

@app.route("/admin/ticketing/holds/<int:hold_id>")
@permission_required("ticketing")
def ticket_hold(hold_id):
    c=get_db(); hold=c.execute("""SELECT th.*,rs.name AS show_name,rs.show_date,rs.start_time,rp.name AS production_name,f.family_name FROM ticket_holds th JOIN recital_shows rs ON rs.id=th.recital_show_id JOIN recital_productions rp ON rp.id=rs.production_id LEFT JOIN families f ON f.id=th.family_id WHERE th.id=?""",(hold_id,)).fetchone()
    if not hold: c.close(); return ("Hold not found",404)
    seats=c.execute("""SELECT ts.id,ts.row_label,ts.seat_number,ts.seat_type,sec.name AS section_name FROM ticket_hold_seats hs JOIN ticket_seats ts ON ts.id=hs.seat_id JOIN ticket_sections sec ON sec.id=ts.section_id WHERE hs.hold_id=? ORDER BY sec.sort_order,sec.name,ts.row_label,ts.seat_number""",(hold_id,)).fetchall(); c.close(); return render_template("ticket_hold.html",hold=dict(hold),seats=[dict(r) for r in seats])

@app.route("/admin/ticketing/holds/<int:hold_id>/update",methods=["POST"])
@permission_required("ticketing")
def update_ticket_hold(hold_id):
    c=get_db(); hold=c.execute("SELECT status FROM ticket_holds WHERE id=?",(hold_id,)).fetchone()
    if not hold: c.close(); return ("Hold not found",404)
    if hold["status"]!='Active': c.close(); flash("Only active holds can be edited.","error"); return redirect(url_for("ticket_hold",hold_id=hold_id))
    c.execute("UPDATE ticket_holds SET held_for_name=?,email=?,phone=?,reason=?,notes=?,expires_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(request.form.get("held_for_name","").strip(),request.form.get("email","").strip(),request.form.get("phone","").strip(),request.form.get("reason","").strip(),request.form.get("notes","").strip(),request.form.get("expires_at","").strip() or None,hold_id)); c.commit(); c.close(); flash("Hold updated.","success"); return redirect(url_for("ticket_hold",hold_id=hold_id))

@app.route("/admin/ticketing/holds/<int:hold_id>/release",methods=["POST"])
@permission_required("ticketing")
def release_ticket_hold(hold_id):
    c=get_db(); hold=c.execute("SELECT recital_show_id,status FROM ticket_holds WHERE id=?",(hold_id,)).fetchone()
    if not hold: c.close(); return ("Hold not found",404)
    if hold["status"]=='Active': c.execute("UPDATE ticket_holds SET status='Released',released_at=CURRENT_TIMESTAMP,released_by=?,release_reason=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(int(session.get("admin_user_id") or 0) or None,request.form.get("release_reason","").strip(),hold_id)); c.execute("DELETE FROM ticket_hold_seats WHERE hold_id=?",(hold_id,)); c.commit()
    show_id=int(hold["recital_show_id"]); c.close(); event_id=create_workflow_event("ticket_hold_released","ticketing","Seat hold released",f"Hold #{hold_id}","info",str(hold_id)); evaluate_workflow_rules(event_id); flash("Hold released.","success"); return redirect(url_for("ticket_show",show_id=show_id))

@app.route("/admin/ticketing/holds/<int:hold_id>/convert",methods=["POST"])
@permission_required("ticketing")
def convert_ticket_hold(hold_id):
    c=get_db(); hold=c.execute("SELECT * FROM ticket_holds WHERE id=?",(hold_id,)).fetchone()
    if not hold: c.close(); return ("Hold not found",404)
    if hold["status"]!='Active': c.close(); flash("Only active holds can be converted.","error"); return redirect(url_for("ticket_hold",hold_id=hold_id))
    seats=[int(r["seat_id"]) for r in c.execute("SELECT seat_id FROM ticket_hold_seats WHERE hold_id=?",(hold_id,)).fetchall()]
    setting=c.execute("SELECT default_price FROM ticket_show_settings WHERE recital_show_id=?",(hold["recital_show_id"],)).fetchone(); default=float(setting["default_price"] or 0) if setting else 0
    pay=request.form.get("payment_status","Due").strip(); price=0 if pay=='Complimentary' else float(request.form.get("price_each",str(default)) or default); total=price*len(seats)
    sql="INSERT INTO ticket_orders (recital_show_id,family_id,purchaser_name,purchaser_email,purchaser_phone,order_status,payment_status,total_amount,notes,created_by) VALUES (?,?,?,?,?,?,?,?,?,?)"
    if c.backend=='postgresql': sql+=' RETURNING id'
    cur=c.execute(sql,(hold["recital_show_id"],hold["family_id"],hold["held_for_name"],hold["email"],hold["phone"],request.form.get("order_status","Confirmed").strip(),pay,total,hold["notes"],int(session.get("admin_user_id") or 0) or None)); order_id=int(cur.fetchone()["id"]) if c.backend=='postgresql' else int(cur.lastrowid)
    for seat_id in seats:
        code=generate_ticket_code()
        while c.execute("SELECT id FROM tickets WHERE ticket_code=?",(code,)).fetchone(): code=generate_ticket_code()
        c.execute("INSERT INTO tickets (order_id,recital_show_id,seat_id,ticket_code,price,status) VALUES (?,?,?,?,?,'Valid')",(order_id,hold["recital_show_id"],seat_id,code,price))
    c.execute("UPDATE ticket_holds SET status='Converted',converted_order_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(order_id,hold_id)); c.execute("DELETE FROM ticket_hold_seats WHERE hold_id=?",(hold_id,)); c.commit(); c.close(); event_id=create_workflow_event("ticket_hold_converted","ticketing","Seat hold converted",f"Hold #{hold_id} to Order #{order_id}","success",str(order_id)); evaluate_workflow_rules(event_id); flash("Hold converted to order.","success"); return redirect(url_for("ticket_order",order_id=order_id))

@app.route("/admin/ticketing/shows/<int:show_id>/settings", methods=["POST"])
@permission_required("ticketing")
def save_ticket_show_settings(show_id: int):
    connection = get_db()
    connection.execute(
        """
        INSERT INTO ticket_show_settings (
            recital_show_id,venue_id,default_price,
            sales_status,notes
        ) VALUES (?,?,?,?,?)
        ON CONFLICT(recital_show_id) DO UPDATE SET
            venue_id=excluded.venue_id,
            default_price=excluded.default_price,
            sales_status=excluded.sales_status,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            show_id,
            int(request.form.get("venue_id", "0") or 0),
            float(request.form.get("default_price", "0") or 0),
            request.form.get("sales_status", "Not On Sale").strip(),
            request.form.get("notes", "").strip(),
        ),
    )
    connection.commit()
    connection.close()

    event_id = create_workflow_event(
        "ticket_sales_settings_updated",
        "ticketing",
        "Ticket sales settings updated",
        f"Recital show #{show_id}",
        "info",
        str(show_id),
    )
    evaluate_workflow_rules(event_id)

    flash("Ticket settings saved.", "success")
    return redirect(url_for("ticket_show", show_id=show_id))


@app.route("/admin/ticketing/shows/<int:show_id>")
@permission_required("ticketing")
def ticket_show(show_id: int):
    connection = get_db()
    show = connection.execute(
        """
        SELECT
            rs.*,
            rp.name AS production_name,
            tss.venue_id,
            tss.default_price,
            tss.sales_status,
            tss.notes AS ticket_notes,
            tv.name AS venue_name,
            COALESCE(tvl.booth_enabled,0) AS booth_enabled,
            COALESCE(tvl.booth_label,'CREW BOOTH') AS booth_label,
            COALESCE(tvl.booth_position,'Rear Center') AS booth_position
        FROM recital_shows rs
        JOIN recital_productions rp ON rp.id=rs.production_id
        LEFT JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id
        LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id
        LEFT JOIN ticket_venue_layouts tvl ON tvl.venue_id=tv.id
        WHERE rs.id=?
        """,
        (show_id,),
    ).fetchone()
    if not show:
        connection.close()
        return ("Show not found", 404)

    venues = connection.execute(
        "SELECT id,name FROM ticket_venues WHERE active=1 ORDER BY name"
    ).fetchall()
    families = connection.execute(
        "SELECT id,family_name,primary_email,primary_phone FROM families ORDER BY family_name"
    ).fetchall()

    seats = []
    if show["venue_id"]:
        seats = connection.execute(
            """
            SELECT
                ts.id,ts.row_label,ts.seat_number,
                ts.seat_label,ts.seat_type,
                sec.id AS section_id,
                sec.name AS section_name,
                sec.sort_order,
                COALESCE(trl.extra_space_after,0) AS extra_space_after,
                COALESCE(trl.seat_direction,'Low Left') AS seat_direction,
                COALESCE(tsl.orientation,'Horizontal') AS section_orientation,
                COALESCE(tsl.placement,'Center') AS section_placement,
                COALESCE(tsl.x_pos,400) AS section_x_pos,COALESCE(tsl.y_pos,250) AS section_y_pos,
                COALESCE(tsl.width_px,600) AS section_width_px,COALESCE(tsl.height_px,220) AS section_height_px,
                COALESCE(tsl.rotation_deg,0) AS section_rotation_deg,COALESCE(tsl.z_index,10) AS section_z_index,
                tk.id AS ticket_id,
                tk.status AS ticket_status,
                tk.checked_in_at,
                tor.id AS order_id,
                tor.order_status,
                tor.purchaser_name,
                ths.hold_id,
                th.held_for_name,
                th.notes AS hold_notes,
                th.expires_at AS hold_expires_at
            FROM ticket_seats ts
            JOIN ticket_sections sec ON sec.id=ts.section_id
            LEFT JOIN ticket_row_layouts trl ON trl.section_id=ts.section_id AND trl.row_label=ts.row_label
            LEFT JOIN ticket_section_layouts tsl ON tsl.section_id=ts.section_id
            LEFT JOIN tickets tk
              ON tk.seat_id=ts.id
             AND tk.recital_show_id=?
             AND tk.status='Valid'
            LEFT JOIN ticket_orders tor ON tor.id=tk.order_id
            LEFT JOIN ticket_hold_seats ths ON ths.seat_id=ts.id AND ths.recital_show_id=?
            LEFT JOIN ticket_holds th ON th.id=ths.hold_id AND th.status='Active'
            WHERE sec.venue_id=?
              AND ts.active=1
            ORDER BY sec.sort_order,sec.name,ts.row_label,ts.seat_number
            """,
            (show_id, show_id, show["venue_id"]),
        ).fetchall()

    show_canvas=None; show_objects=[]
    if show["venue_id"]:
        show_canvas=connection.execute("SELECT * FROM ticket_canvas_settings WHERE venue_id=?",(show["venue_id"],)).fetchone()
        show_objects=connection.execute("SELECT * FROM ticket_venue_objects WHERE venue_id=? AND active=1 ORDER BY z_index,sort_order,id",(show["venue_id"],)).fetchall()

    holds = connection.execute(
        """
        SELECT th.*,f.family_name,COUNT(ths.id) AS seat_count
        FROM ticket_holds th
        LEFT JOIN families f ON f.id=th.family_id
        LEFT JOIN ticket_hold_seats ths ON ths.hold_id=th.id
        WHERE th.recital_show_id=? AND th.status='Active'
        GROUP BY th.id,th.recital_show_id,th.family_id,th.held_for_name,th.email,th.phone,th.reason,th.notes,th.expires_at,th.status,th.created_by,th.created_at,th.updated_at,th.released_at,th.released_by,th.release_reason,th.converted_order_id,f.family_name
        ORDER BY th.id DESC
        """,(show_id,)
    ).fetchall()

    orders = connection.execute(
        """
        SELECT
            tor.*,
            f.family_name,
            COUNT(tk.id) AS ticket_count
        FROM ticket_orders tor
        LEFT JOIN families f ON f.id=tor.family_id
        LEFT JOIN tickets tk ON tk.order_id=tor.id AND tk.status='Valid'
        WHERE tor.recital_show_id=?
          AND tor.order_status!='Voided'
        GROUP BY
            tor.id,tor.recital_show_id,tor.family_id,
            tor.purchaser_name,tor.purchaser_email,
            tor.purchaser_phone,tor.order_status,
            tor.payment_status,tor.total_amount,
            tor.billing_charge_id,tor.notes,
            tor.created_by,tor.created_at,
            tor.voided_at,tor.voided_by,tor.void_reason,
            f.family_name
        ORDER BY tor.id DESC
        """,
        (show_id,),
    ).fetchall()
    delivery_settings=connection.execute("SELECT * FROM ticket_delivery_settings WHERE recital_show_id=?",(show_id,)).fetchone()
    public_settings=connection.execute("SELECT * FROM public_ticket_settings WHERE recital_show_id=?",(show_id,)).fetchone()
    connection.close()

    grouped_seats = {}
    for row in seats:
        item = dict(row)
        key = (item["section_id"], item["section_name"])
        grouped_seats.setdefault(key, {}).setdefault(item["row_label"], []).append(item)

    return render_template(
        "ticket_show.html",
        show=dict(show),
        venues=[dict(row) for row in venues],
        families=[dict(row) for row in families],
        grouped_seats=grouped_seats,
        orders=[dict(row) for row in orders],
        holds=[dict(row) for row in holds],
        show_canvas=dict(show_canvas) if show_canvas else {"canvas_width":1400,"canvas_height":1100,"background_label":""},
        show_objects=[dict(row) for row in show_objects],
        public_settings=dict(public_settings) if public_settings else {},
        delivery_settings=dict(delivery_settings) if delivery_settings else {},
    )


@app.route("/admin/ticketing/shows/<int:show_id>/orders", methods=["POST"])
@permission_required("ticketing")
def create_ticket_order(show_id: int):
    selected_seats = [
        int(value)
        for value in request.form.getlist("seat_id")
        if value.isdigit()
    ]
    if not selected_seats:
        flash("Select at least one available reserved seat.", "error")
        return redirect(url_for("ticket_show", show_id=show_id))

    family_value = request.form.get("family_id", "").strip()
    family_id = int(family_value) if family_value else None
    purchaser_name = request.form.get("purchaser_name", "").strip()
    order_status = request.form.get("order_status", "Confirmed").strip()
    payment_status = request.form.get("payment_status", "Due").strip()

    connection = get_db()
    setting = connection.execute(
        """
        SELECT default_price
        FROM ticket_show_settings
        WHERE recital_show_id=?
        """,
        (show_id,),
    ).fetchone()
    default_price = float(setting["default_price"] or 0) if setting else 0

    placeholders = ",".join("?" for _ in selected_seats)
    unavailable = connection.execute(
        f"""
        SELECT seat_id
        FROM tickets
        WHERE recital_show_id=?
          AND status='Valid'
          AND seat_id IN ({placeholders})
        """,
        tuple([show_id] + selected_seats),
    ).fetchall()
    if unavailable:
        connection.close()
        flash("One or more selected seats were just taken. Reload and select again.", "error")
        return redirect(url_for("ticket_show", show_id=show_id))

    price_each = 0 if payment_status == "Complimentary" else float(
        request.form.get("price_each", str(default_price)) or default_price
    )
    total_amount = price_each * len(selected_seats)

    order_sql = """
        INSERT INTO ticket_orders (
            recital_show_id,family_id,purchaser_name,
            purchaser_email,purchaser_phone,
            order_status,payment_status,total_amount,
            notes,created_by
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
    """
    if connection.backend == "postgresql":
        order_sql += " RETURNING id"

    cursor = connection.execute(
        order_sql,
        (
            show_id,
            family_id,
            purchaser_name,
            request.form.get("purchaser_email", "").strip(),
            request.form.get("purchaser_phone", "").strip(),
            order_status,
            payment_status,
            total_amount,
            request.form.get("notes", "").strip(),
            int(session.get("admin_user_id") or 0) or None,
        ),
    )
    order_id = (
        int(cursor.fetchone()["id"])
        if connection.backend == "postgresql"
        else int(cursor.lastrowid)
    )

    for seat_id in selected_seats:
        code = generate_ticket_code()
        while connection.execute(
            "SELECT id FROM tickets WHERE ticket_code=?",
            (code,),
        ).fetchone():
            code = generate_ticket_code()

        connection.execute(
            """
            INSERT INTO tickets (
                order_id,recital_show_id,seat_id,
                ticket_code,price,status
            ) VALUES (?,?,?,?,?,'Valid')
            """,
            (order_id, show_id, seat_id, code, price_each),
        )

    billing_charge_id = None
    if (
        request.form.get("create_billing_charge") == "on"
        and family_id
        and total_amount > 0
        and payment_status == "Due"
    ):
        show_record = connection.execute(
            "SELECT name,show_date FROM recital_shows WHERE id=?",
            (show_id,),
        ).fetchone()

        charge_sql = """
            INSERT INTO billing_charges (
                family_id,charge_type,description,
                amount,due_date,status,reference,created_by
            ) VALUES (?,'Other',?,?,?,'Open',?,?)
        """
        if connection.backend == "postgresql":
            charge_sql += " RETURNING id"

        charge_cursor = connection.execute(
            charge_sql,
            (
                family_id,
                f"Reserved tickets - {show_record['name']}",
                total_amount,
                request.form.get("due_date", "").strip(),
                f"Ticket order #{order_id}",
                int(session.get("admin_user_id") or 0) or None,
            ),
        )
        billing_charge_id = (
            int(charge_cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(charge_cursor.lastrowid)
        )
        connection.execute(
            "UPDATE ticket_orders SET billing_charge_id=? WHERE id=?",
            (billing_charge_id, order_id),
        )

    connection.commit()
    connection.close()

    event_id = create_workflow_event(
        "ticket_order_created",
        "ticketing",
        "Reserved ticket order created",
        f"Order #{order_id} · {len(selected_seats)} seat(s) · ${total_amount:.2f}",
        "success",
        str(order_id),
    )
    evaluate_workflow_rules(event_id)

    flash("Reserved ticket order created.", "success")
    return redirect(url_for("ticket_order", order_id=order_id))


@app.route("/admin/ticketing/orders/<int:order_id>")
@permission_required("ticketing")
def ticket_order(order_id: int):
    connection = get_db()
    order = connection.execute(
        """
        SELECT
            tor.*,
            rs.name AS show_name,
            rs.show_date,
            rs.start_time,
            rp.name AS production_name,
            tv.name AS venue_name,
            tv.address AS venue_address,
            f.family_name
        FROM ticket_orders tor
        JOIN recital_shows rs ON rs.id=tor.recital_show_id
        JOIN recital_productions rp ON rp.id=rs.production_id
        LEFT JOIN ticket_show_settings tss ON tss.recital_show_id=rs.id
        LEFT JOIN ticket_venues tv ON tv.id=tss.venue_id
        LEFT JOIN families f ON f.id=tor.family_id
        WHERE tor.id=?
        """,
        (order_id,),
    ).fetchone()
    if not order:
        connection.close()
        return ("Ticket order not found", 404)

    tickets = connection.execute(
        """
        SELECT
            tk.*,
            ts.row_label,
            ts.seat_number,
            ts.seat_label,
            ts.seat_type,
            sec.name AS section_name
        FROM tickets tk
        JOIN ticket_seats ts ON ts.id=tk.seat_id
        JOIN ticket_sections sec ON sec.id=ts.section_id
        WHERE tk.order_id=?
        ORDER BY sec.sort_order,sec.name,ts.row_label,ts.seat_number
        """,
        (order_id,),
    ).fetchall()
    connection.close()

    return render_template(
        "ticket_order.html",
        order=dict(order),
        tickets=[dict(row) for row in tickets],
    )


@app.route("/admin/ticketing/tickets/<int:ticket_id>/check-in", methods=["POST"])
@permission_required("ticketing")
def check_in_ticket(ticket_id: int):
    connection = get_db()
    ticket = connection.execute(
        "SELECT order_id,status,checked_in_at FROM tickets WHERE id=?",
        (ticket_id,),
    ).fetchone()
    if not ticket:
        connection.close()
        return ("Ticket not found", 404)

    if ticket["status"] != "Valid":
        connection.close()
        flash("This ticket is not valid.", "error")
        return redirect(url_for("ticket_order", order_id=ticket["order_id"]))

    if ticket["checked_in_at"]:
        connection.close()
        flash("This ticket was already checked in.", "error")
        return redirect(url_for("ticket_order", order_id=ticket["order_id"]))

    connection.execute(
        """
        UPDATE tickets SET
            checked_in_at=CURRENT_TIMESTAMP,
            checked_in_by=?
        WHERE id=?
        """,
        (
            int(session.get("admin_user_id") or 0) or None,
            ticket_id,
        ),
    )
    connection.commit()
    order_id = int(ticket["order_id"])
    connection.close()

    flash("Guest checked in.", "success")
    return redirect(url_for("ticket_order", order_id=order_id))


@app.route("/admin/ticketing/orders/<int:order_id>/void", methods=["POST"])
@permission_required("ticketing")
def void_ticket_order(order_id: int):
    reason = request.form.get("void_reason", "").strip()
    connection = get_db()
    order = connection.execute(
        "SELECT recital_show_id,order_status FROM ticket_orders WHERE id=?",
        (order_id,),
    ).fetchone()
    if order and order["order_status"] != "Voided":
        connection.execute(
            """
            UPDATE ticket_orders SET
                order_status='Voided',
                voided_at=CURRENT_TIMESTAMP,
                voided_by=?,
                void_reason=?
            WHERE id=?
            """,
            (
                int(session.get("admin_user_id") or 0) or None,
                reason,
                order_id,
            ),
        )
        connection.execute(
            "UPDATE tickets SET status='Voided' WHERE order_id=?",
            (order_id,),
        )
        connection.commit()

    show_id = int(order["recital_show_id"]) if order else 0
    connection.close()
    flash("Ticket order voided and seats released.", "success")
    return redirect(url_for("ticket_show", show_id=show_id))


@app.route("/admin/competitions")
@permission_required("competitions")
def competition_center():
    connection = get_db()
    competitions = connection.execute(
        """
        SELECT c.*,
               COUNT(DISTINCT r.id) AS routine_count,
               COUNT(DISTINCT d.student_id) AS dancer_count,
               COALESCE(SUM(CASE WHEN r.music_status!='Ready' THEN 1 ELSE 0 END),0) AS music_missing,
               COALESCE(SUM(CASE WHEN r.entry_status NOT IN ('Submitted','Confirmed') THEN 1 ELSE 0 END),0) AS entries_pending
        FROM competitions c
        LEFT JOIN competition_routines r ON r.competition_id=c.id
        LEFT JOIN competition_dancers d ON d.routine_id=r.id
        GROUP BY c.id,c.name,c.venue,c.city,c.state,c.start_date,c.end_date,
                 c.registration_deadline,c.status,c.website,c.hotel_name,
                 c.hotel_deadline,c.notes,c.created_at,c.updated_at
        ORDER BY c.start_date DESC,c.id DESC
        """
    ).fetchall()
    connection.close()
    return render_template("competition_center.html", competitions=[dict(r) for r in competitions])


@app.route("/admin/competitions/save", methods=["POST"])
@permission_required("competitions")
def save_competition():
    competition_id=request.form.get("id","").strip()
    values=(
        request.form.get("name","").strip(),
        request.form.get("venue","").strip(),
        request.form.get("city","").strip(),
        request.form.get("state","").strip(),
        request.form.get("start_date","").strip(),
        request.form.get("end_date","").strip(),
        request.form.get("registration_deadline","").strip(),
        request.form.get("status","Planning").strip(),
        request.form.get("website","").strip(),
        request.form.get("hotel_name","").strip(),
        request.form.get("hotel_deadline","").strip(),
        request.form.get("notes","").strip(),
    )
    connection=get_db()
    if competition_id:
        connection.execute(
            """UPDATE competitions SET name=?,venue=?,city=?,state=?,start_date=?,
               end_date=?,registration_deadline=?,status=?,website=?,hotel_name=?,
               hotel_deadline=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            values+(int(competition_id),)
        )
        saved_id=int(competition_id); event_type="competition_updated"
    else:
        sql="""INSERT INTO competitions
               (name,venue,city,state,start_date,end_date,registration_deadline,
                status,website,hotel_name,hotel_deadline,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"""
        if connection.backend=="postgresql": sql+=" RETURNING id"
        cursor=connection.execute(sql,values)
        saved_id=int(cursor.fetchone()["id"]) if connection.backend=="postgresql" else int(cursor.lastrowid)
        event_type="competition_created"
    connection.commit(); connection.close()
    event_id=create_workflow_event(event_type,"competitions","Competition saved",values[0],"info",str(saved_id))
    evaluate_workflow_rules(event_id)
    flash("Competition saved.","success")
    return redirect(url_for("competition_profile",competition_id=saved_id))


@app.route("/admin/competitions/<int:competition_id>")
@permission_required("competitions")
def competition_profile(competition_id):
    connection=get_db()
    competition=connection.execute("SELECT * FROM competitions WHERE id=?",(competition_id,)).fetchone()
    if not competition:
        connection.close(); return ("Competition not found",404)
    routines=connection.execute(
        """
        SELECT r.*,c.name AS class_name,co.name AS costume_name,
               COUNT(DISTINCT d.student_id) AS dancer_count,
               COALESCE(SUM(CASE WHEN d.costume_ready=1 THEN 1 ELSE 0 END),0) AS costumes_ready
        FROM competition_routines r
        LEFT JOIN classes c ON c.id=r.class_id
        LEFT JOIN costumes co ON co.id=r.costume_id
        LEFT JOIN competition_dancers d ON d.routine_id=r.id
        WHERE r.competition_id=?
        GROUP BY r.id,r.competition_id,r.class_id,r.recital_performance_id,r.costume_id,
                 r.title,r.division,r.category,r.level,r.age_group,r.music_title,
                 r.music_status,r.entry_status,r.performance_date,r.performance_time,
                 r.stage,r.entry_fee,r.notes,r.created_at,r.updated_at,c.name,co.name
        ORDER BY r.performance_date,r.performance_time,r.title
        """,(competition_id,)
    ).fetchall()
    classes=connection.execute("SELECT id,name FROM classes WHERE active=1 ORDER BY name").fetchall()
    costumes=connection.execute("SELECT id,name FROM costumes WHERE active=1 ORDER BY name").fetchall()
    performances=connection.execute("SELECT id,title FROM recital_performances ORDER BY title").fetchall()
    connection.close()
    return render_template("competition_profile.html",competition=dict(competition),
        routines=[dict(r) for r in routines],classes=[dict(r) for r in classes],
        costumes=[dict(r) for r in costumes],performances=[dict(r) for r in performances])


@app.route("/admin/competitions/<int:competition_id>/routines/save",methods=["POST"])
@permission_required("competitions")
def save_competition_routine(competition_id):
    class_value=request.form.get("class_id","").strip()
    costume_value=request.form.get("costume_id","").strip()
    performance_value=request.form.get("recital_performance_id","").strip()
    values=(competition_id,int(class_value) if class_value else None,
        int(performance_value) if performance_value else None,
        int(costume_value) if costume_value else None,
        request.form.get("title","").strip(),request.form.get("division","").strip(),
        request.form.get("category","").strip(),request.form.get("level","").strip(),
        request.form.get("age_group","").strip(),request.form.get("music_title","").strip(),
        request.form.get("music_status","Missing").strip(),request.form.get("entry_status","Planning").strip(),
        request.form.get("performance_date","").strip(),request.form.get("performance_time","").strip(),
        request.form.get("stage","").strip(),float(request.form.get("entry_fee","0") or 0),
        request.form.get("notes","").strip())
    connection=get_db()
    sql="""INSERT INTO competition_routines
           (competition_id,class_id,recital_performance_id,costume_id,title,division,
            category,level,age_group,music_title,music_status,entry_status,
            performance_date,performance_time,stage,entry_fee,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    if connection.backend=="postgresql": sql+=" RETURNING id"
    cursor=connection.execute(sql,values)
    routine_id=int(cursor.fetchone()["id"]) if connection.backend=="postgresql" else int(cursor.lastrowid)
    if values[1]:
        students=connection.execute(
            """SELECT s.id,s.family_id FROM class_enrollments ce
               JOIN students s ON s.id=ce.student_id
               WHERE ce.class_id=? AND ce.status='Active'""",(values[1],)
        ).fetchall()
        for student in students:
            connection.execute(
                """INSERT INTO competition_dancers (routine_id,student_id,family_id)
                   VALUES (?,?,?) ON CONFLICT(routine_id,student_id) DO NOTHING""",
                (routine_id,student["id"],student["family_id"])
            )
    connection.commit(); connection.close()
    event_id=create_workflow_event("competition_routine_created","competitions",
        "Competition routine created",values[4],"info",str(routine_id))
    evaluate_workflow_rules(event_id)
    flash("Routine created and active class dancers assigned.","success")
    return redirect(url_for("competition_routine",routine_id=routine_id))


@app.route("/admin/competitions/routines/<int:routine_id>")
@permission_required("competitions")
def competition_routine(routine_id):
    connection=get_db()
    routine=connection.execute(
        """SELECT r.*,c.name AS competition_name,cl.name AS class_name,co.name AS costume_name
           FROM competition_routines r JOIN competitions c ON c.id=r.competition_id
           LEFT JOIN classes cl ON cl.id=r.class_id LEFT JOIN costumes co ON co.id=r.costume_id
           WHERE r.id=?""",(routine_id,)
    ).fetchone()
    if not routine:
        connection.close(); return ("Routine not found",404)
    dancers=connection.execute(
        """SELECT d.*,s.first_name,s.last_name,s.preferred_name,f.family_name
           FROM competition_dancers d JOIN students s ON s.id=d.student_id
           LEFT JOIN families f ON f.id=d.family_id
           WHERE d.routine_id=? ORDER BY s.last_name,s.first_name""",(routine_id,)
    ).fetchall()
    awards=connection.execute("SELECT * FROM competition_awards WHERE routine_id=? ORDER BY id DESC",(routine_id,)).fetchall()
    connection.close()
    return render_template("competition_routine.html",routine=dict(routine),
        dancers=[dict(r) for r in dancers],awards=[dict(r) for r in awards])


@app.route("/admin/competitions/dancers/<int:dancer_id>/update",methods=["POST"])
@permission_required("competitions")
def update_competition_dancer(dancer_id):
    connection=get_db()
    dancer=connection.execute(
        """SELECT d.*,r.entry_fee,r.title FROM competition_dancers d
           JOIN competition_routines r ON r.id=d.routine_id WHERE d.id=?""",(dancer_id,)
    ).fetchone()
    if not dancer:
        connection.close(); return ("Dancer not found",404)
    fee_charge_id=dancer["fee_charge_id"]
    if request.form.get("create_fee_charge")=="on" and not fee_charge_id and dancer["family_id"] and float(dancer["entry_fee"] or 0)>0:
        sql="""INSERT INTO billing_charges
               (family_id,student_id,charge_type,description,amount,due_date,status,reference,created_by)
               VALUES (?,?,'Competition',?,?,?,'Open',?,?)"""
        if connection.backend=="postgresql": sql+=" RETURNING id"
        cursor=connection.execute(sql,(dancer["family_id"],dancer["student_id"],dancer["title"],
            float(dancer["entry_fee"]),request.form.get("due_date","").strip(),
            f"Competition dancer #{dancer_id}",int(session.get("admin_user_id") or 0) or None))
        fee_charge_id=int(cursor.fetchone()["id"]) if connection.backend=="postgresql" else int(cursor.lastrowid)
    connection.execute(
        """UPDATE competition_dancers SET registration_status=?,waiver_status=?,
           travel_status=?,costume_ready=?,fee_charge_id=?,notes=?,updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (request.form.get("registration_status","Assigned").strip(),
         request.form.get("waiver_status","Missing").strip(),
         request.form.get("travel_status","Unknown").strip(),
         1 if request.form.get("costume_ready")=="on" else 0,
         fee_charge_id,request.form.get("notes","").strip(),dancer_id)
    )
    connection.commit(); routine_id=int(dancer["routine_id"]); connection.close()
    flash("Dancer updated.","success")
    return redirect(url_for("competition_routine",routine_id=routine_id))


@app.route("/admin/competitions/routines/<int:routine_id>/awards",methods=["POST"])
@permission_required("competitions")
def add_competition_award(routine_id):
    connection=get_db()
    connection.execute(
        """INSERT INTO competition_awards
           (routine_id,award_name,placement,score,judge_notes) VALUES (?,?,?,?,?)""",
        (routine_id,request.form.get("award_name","").strip(),
         request.form.get("placement","").strip(),float(request.form.get("score","0") or 0),
         request.form.get("judge_notes","").strip())
    )
    connection.commit(); connection.close()
    event_id=create_workflow_event("competition_award_recorded","competitions",
        "Competition award recorded",request.form.get("award_name","").strip(),
        "success",str(routine_id))
    evaluate_workflow_rules(event_id)
    flash("Award recorded.","success")
    return redirect(url_for("competition_routine",routine_id=routine_id))


@app.route("/admin/costumes")
@permission_required("costumes")
def costume_center():
    connection=get_db()
    costumes=connection.execute("""SELECT c.*,v.name AS vendor_name,COUNT(DISTINCT sca.student_id) AS student_count FROM costumes c LEFT JOIN costume_vendors v ON v.id=c.vendor_id LEFT JOIN student_costume_assignments sca ON sca.costume_id=c.id GROUP BY c.id,c.vendor_id,c.name,c.style_number,c.color,c.season,c.category,c.unit_cost,c.charge_amount,c.order_status,c.tracking_number,c.expected_date,c.received_date,c.notes,c.active,c.created_at,c.updated_at,v.name ORDER BY c.id DESC""").fetchall()
    vendors=connection.execute("SELECT * FROM costume_vendors ORDER BY active DESC,name").fetchall()
    summary=connection.execute("""SELECT COUNT(*) AS costume_count,COALESCE(SUM(CASE WHEN order_status='Ordered' THEN 1 ELSE 0 END),0) AS ordered_count,COALESCE(SUM(CASE WHEN order_status='Received' THEN 1 ELSE 0 END),0) AS received_count,(SELECT COUNT(*) FROM student_costume_assignments WHERE alteration_status='Needed') AS alterations_needed,(SELECT COUNT(*) FROM student_costume_assignments WHERE pickup_status='Ready') AS pickup_ready FROM costumes""").fetchone()
    connection.close()
    return render_template('costume_center.html',costumes=[dict(r) for r in costumes],vendors=[dict(r) for r in vendors],summary=dict(summary))

@app.route("/admin/costumes/vendors/save",methods=["POST"])
@permission_required("costumes")
def save_costume_vendor():
    c=get_db(); c.execute("INSERT INTO costume_vendors (name,website,contact_name,email,phone,notes,active) VALUES (?,?,?,?,?,?,?)",(request.form.get('name','').strip(),request.form.get('website','').strip(),request.form.get('contact_name','').strip(),request.form.get('email','').strip(),request.form.get('phone','').strip(),request.form.get('notes','').strip(),1 if request.form.get('active')=='on' else 0)); c.commit(); c.close(); flash('Vendor saved.','success'); return redirect(url_for('costume_center'))

@app.route("/admin/costumes/save",methods=["POST"])
@permission_required("costumes")
def save_costume():
    f=request.form; vendor=int(f.get('vendor_id')) if f.get('vendor_id') else None
    vals=(vendor,f.get('name','').strip(),f.get('style_number','').strip(),f.get('color','').strip(),f.get('season','').strip(),f.get('category','').strip(),float(f.get('unit_cost','0') or 0),float(f.get('charge_amount','0') or 0),f.get('order_status','Planned').strip(),f.get('tracking_number','').strip(),f.get('expected_date','').strip(),f.get('received_date','').strip(),f.get('notes','').strip(),1 if f.get('active')=='on' else 0)
    c=get_db(); sql="INSERT INTO costumes (vendor_id,name,style_number,color,season,category,unit_cost,charge_amount,order_status,tracking_number,expected_date,received_date,notes,active) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"; sql += " RETURNING id" if c.backend=='postgresql' else ''
    cur=c.execute(sql,vals); cid=int(cur.fetchone()['id']) if c.backend=='postgresql' else int(cur.lastrowid); c.commit(); c.close()
    eid=create_workflow_event('costume_created','costumes','Costume created',vals[1],'info',str(cid)); evaluate_workflow_rules(eid)
    return redirect(url_for('costume_profile',costume_id=cid))

@app.route("/admin/costumes/<int:costume_id>")
@permission_required("costumes")
def costume_profile(costume_id):
    c=get_db(); costume=c.execute("SELECT c.*,v.name AS vendor_name FROM costumes c LEFT JOIN costume_vendors v ON v.id=c.vendor_id WHERE c.id=?",(costume_id,)).fetchone()
    if not costume: c.close(); return ('Costume not found',404)
    assignments=c.execute("""SELECT sca.*,s.first_name,s.last_name,s.preferred_name,f.family_name,cl.name AS class_name FROM student_costume_assignments sca JOIN students s ON s.id=sca.student_id LEFT JOIN families f ON f.id=sca.family_id LEFT JOIN classes cl ON cl.id=sca.class_id WHERE sca.costume_id=? ORDER BY s.last_name,s.first_name""",(costume_id,)).fetchall()
    classes=c.execute("SELECT id,name,day_of_week,start_time FROM classes WHERE active=1 ORDER BY name").fetchall(); performances=c.execute("SELECT rp.id,rp.title,rs.name AS show_name FROM recital_performances rp JOIN recital_shows rs ON rs.id=rp.show_id ORDER BY rs.show_date,rp.performance_order").fetchall(); c.close()
    return render_template('costume_profile.html',costume=dict(costume),assignments=[dict(r) for r in assignments],classes=[dict(r) for r in classes],performances=[dict(r) for r in performances])

@app.route("/admin/costumes/<int:costume_id>/assign-class",methods=["POST"])
@permission_required("costumes")
def assign_costume_class(costume_id):
    class_id=int(request.form.get('class_id','0') or 0); perf=int(request.form.get('recital_performance_id')) if request.form.get('recital_performance_id') else None
    c=get_db(); c.execute("INSERT INTO costume_class_assignments (costume_id,class_id,recital_performance_id,notes) VALUES (?,?,?,?) ON CONFLICT(costume_id,class_id) DO UPDATE SET recital_performance_id=excluded.recital_performance_id,notes=excluded.notes",(costume_id,class_id,perf,request.form.get('notes','').strip()))
    students=c.execute("SELECT s.id,s.family_id,s.costume_size,s.shoe_size FROM class_enrollments ce JOIN students s ON s.id=ce.student_id WHERE ce.class_id=? AND ce.status='Active'",(class_id,)).fetchall()
    for s in students: c.execute("INSERT INTO student_costume_assignments (costume_id,class_id,student_id,family_id,costume_size,shoe_size) VALUES (?,?,?,?,?,?) ON CONFLICT(costume_id,student_id) DO NOTHING",(costume_id,class_id,s['id'],s['family_id'],s['costume_size'] or '',s['shoe_size'] or ''))
    c.commit(); c.close(); flash('Costume assigned to class and active students.','success'); return redirect(url_for('costume_profile',costume_id=costume_id))

@app.route("/admin/costumes/assignments/<int:assignment_id>/update",methods=["POST"])
@permission_required("costumes")
def update_costume_assignment(assignment_id):
    f=request.form; c=get_db(); a=c.execute("SELECT sca.*,co.name AS costume_name,co.charge_amount FROM student_costume_assignments sca JOIN costumes co ON co.id=sca.costume_id WHERE sca.id=?",(assignment_id,)).fetchone(); charge=a['billing_charge_id']
    if f.get('create_billing_charge')=='on' and not charge and a['family_id'] and float(a['charge_amount'] or 0)>0:
        sql="INSERT INTO billing_charges (family_id,student_id,charge_type,description,amount,due_date,status,reference,created_by) VALUES (?,?,'Costume',?,?,?,'Open',?,?)"; sql += " RETURNING id" if c.backend=='postgresql' else ''
        cur=c.execute(sql,(a['family_id'],a['student_id'],a['costume_name'],float(a['charge_amount']),f.get('due_date',''),f'Costume assignment #{assignment_id}',int(session.get('admin_user_id') or 0) or None)); charge=int(cur.fetchone()['id']) if c.backend=='postgresql' else int(cur.lastrowid)
    c.execute("UPDATE student_costume_assignments SET costume_size=?,tights_size=?,shoe_size=?,accessories=?,assignment_status=?,alteration_status=?,pickup_status=?,billing_charge_id=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(f.get('costume_size',''),f.get('tights_size',''),f.get('shoe_size',''),f.get('accessories',''),f.get('assignment_status','Assigned'),f.get('alteration_status','Not Needed'),f.get('pickup_status','Not Ready'),charge,f.get('notes',''),assignment_id)); c.commit(); cid=int(a['costume_id']); c.close(); flash('Assignment updated.','success'); return redirect(url_for('costume_profile',costume_id=cid))

@app.route("/admin/recitals")
@permission_required("recitals")
def recital_center():
    connection = get_db()
    productions = connection.execute(
        """
        SELECT
            p.*,
            COUNT(DISTINCT s.id) AS show_count,
            COUNT(DISTINCT rp.id) AS performance_count,
            COUNT(DISTINCT rr.id) AS rehearsal_count,
            COALESCE(
                SUM(CASE WHEN rp.music_status='Ready' THEN 1 ELSE 0 END),
                0
            ) AS music_ready_count
        FROM recital_productions p
        LEFT JOIN recital_shows s ON s.production_id=p.id
        LEFT JOIN recital_performances rp ON rp.show_id=s.id
        LEFT JOIN recital_rehearsals rr ON rr.production_id=p.id
        GROUP BY
            p.id, p.name, p.season, p.venue, p.status,
            p.description, p.ticket_status,
            p.created_at, p.updated_at
        ORDER BY p.id DESC
        """
    ).fetchall()

    summary = connection.execute(
        """
        SELECT
            COUNT(*) AS production_count,
            COALESCE(
                (SELECT COUNT(*) FROM recital_shows),
                0
            ) AS show_count,
            COALESCE(
                (SELECT COUNT(*) FROM recital_performances),
                0
            ) AS performance_count,
            COALESCE(
                (
                    SELECT COUNT(*)
                    FROM recital_performances
                    WHERE music_status!='Ready'
                ),
                0
            ) AS music_missing_count
        FROM recital_productions
        """
    ).fetchone()
    connection.close()

    return render_template(
        "recital_center.html",
        productions=[dict(row) for row in productions],
        summary=dict(summary),
    )


@app.route("/admin/recitals/productions/save", methods=["POST"])
@permission_required("recitals")
def save_recital_production():
    production_id = request.form.get("id", "").strip()
    values = (
        request.form.get("name", "").strip(),
        request.form.get("season", "").strip(),
        request.form.get("venue", "").strip(),
        request.form.get("status", "Planning").strip(),
        request.form.get("description", "").strip(),
        request.form.get("ticket_status", "Not On Sale").strip(),
    )

    connection = get_db()
    if production_id:
        connection.execute(
            """
            UPDATE recital_productions SET
                name=?, season=?, venue=?, status=?,
                description=?, ticket_status=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            values + (int(production_id),),
        )
        saved_id = int(production_id)
        event_type = "recital_production_updated"
        event_title = "Recital production updated"
    else:
        sql = """
            INSERT INTO recital_productions (
                name, season, venue, status,
                description, ticket_status
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        if connection.backend == "postgresql":
            sql += " RETURNING id"
        cursor = connection.execute(sql, values)
        saved_id = (
            int(cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(cursor.lastrowid)
        )
        event_type = "recital_production_created"
        event_title = "Recital production created"

    connection.commit()
    connection.close()

    event_id = create_workflow_event(
        event_type,
        "recitals",
        event_title,
        values[0],
        "info",
        str(saved_id),
    )
    evaluate_workflow_rules(event_id)

    flash("Recital production saved.", "success")
    return redirect(url_for("recital_production", production_id=saved_id))


@app.route("/admin/recitals/productions/<int:production_id>")
@permission_required("recitals")
def recital_production(production_id: int):
    connection = get_db()
    production = connection.execute(
        "SELECT * FROM recital_productions WHERE id=?",
        (production_id,),
    ).fetchone()
    if not production:
        connection.close()
        return ("Production not found", 404)

    shows = connection.execute(
        """
        SELECT
            s.*,
            COUNT(rp.id) AS performance_count,
            COALESCE(
                SUM(CASE WHEN rp.music_status='Ready' THEN 1 ELSE 0 END),
                0
            ) AS music_ready_count
        FROM recital_shows s
        LEFT JOIN recital_performances rp ON rp.show_id=s.id
        WHERE s.production_id=?
        GROUP BY
            s.id, s.production_id, s.name, s.show_date,
            s.start_time, s.end_time, s.doors_open_time,
            s.notes, s.status, s.created_at, s.updated_at
        ORDER BY s.show_date, s.start_time, s.id
        """,
        (production_id,),
    ).fetchall()

    rehearsals = connection.execute(
        """
        SELECT rr.*, rs.name AS show_name
        FROM recital_rehearsals rr
        LEFT JOIN recital_shows rs ON rs.id=rr.show_id
        WHERE rr.production_id=?
        ORDER BY rr.rehearsal_date, rr.start_time, rr.id
        """,
        (production_id,),
    ).fetchall()
    connection.close()

    return render_template(
        "recital_production.html",
        production=dict(production),
        shows=[dict(row) for row in shows],
        rehearsals=[dict(row) for row in rehearsals],
    )


@app.route("/admin/recitals/productions/<int:production_id>/shows/save", methods=["POST"])
@permission_required("recitals")
def save_recital_show(production_id: int):
    show_id = request.form.get("id", "").strip()
    values = (
        request.form.get("name", "").strip(),
        request.form.get("show_date", "").strip(),
        request.form.get("start_time", "").strip(),
        request.form.get("end_time", "").strip(),
        request.form.get("doors_open_time", "").strip(),
        request.form.get("notes", "").strip(),
        request.form.get("status", "Scheduled").strip(),
    )

    connection = get_db()
    if show_id:
        connection.execute(
            """
            UPDATE recital_shows SET
                name=?, show_date=?, start_time=?, end_time=?,
                doors_open_time=?, notes=?, status=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND production_id=?
            """,
            values + (int(show_id), production_id),
        )
        saved_id = int(show_id)
        title = "Recital show updated"
        event_type = "recital_show_updated"
    else:
        sql = """
            INSERT INTO recital_shows (
                production_id, name, show_date, start_time,
                end_time, doors_open_time, notes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        if connection.backend == "postgresql":
            sql += " RETURNING id"
        cursor = connection.execute(
            sql,
            (production_id,) + values,
        )
        saved_id = (
            int(cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(cursor.lastrowid)
        )
        title = "Recital show created"
        event_type = "recital_show_created"

    connection.commit()
    connection.close()

    event_id = create_workflow_event(
        event_type,
        "recitals",
        title,
        values[0],
        "info",
        str(saved_id),
    )
    evaluate_workflow_rules(event_id)

    flash("Show saved.", "success")
    return redirect(url_for("recital_show", show_id=saved_id))


@app.route("/admin/recitals/shows/<int:show_id>")
@permission_required("recitals")
def recital_show(show_id: int):
    connection = get_db()
    show = connection.execute(
        """
        SELECT
            s.*,
            p.name AS production_name,
            p.id AS production_id,
            p.venue
        FROM recital_shows s
        JOIN recital_productions p ON p.id=s.production_id
        WHERE s.id=?
        """,
        (show_id,),
    ).fetchone()
    if not show:
        connection.close()
        return ("Show not found", 404)

    performances = connection.execute(
        """
        SELECT
            rp.*,
            c.name AS class_name,
            c.day_of_week,
            c.start_time,
            t.first_name AS teacher_first_name,
            t.last_name AS teacher_last_name,
            COUNT(DISTINCT ce.student_id) AS student_count
        FROM recital_performances rp
        LEFT JOIN classes c ON c.id=rp.class_id
        LEFT JOIN teachers t ON t.id=c.teacher_id
        LEFT JOIN class_enrollments ce
          ON ce.class_id=c.id
         AND ce.status='Active'
        WHERE rp.show_id=?
        GROUP BY
            rp.id, rp.show_id, rp.class_id, rp.title,
            rp.performance_order, rp.performance_type,
            rp.duration_seconds, rp.music_title,
            rp.music_url, rp.music_status,
            rp.entrance_notes, rp.exit_notes,
            rp.costume_notes, rp.status,
            rp.created_at, rp.updated_at,
            c.name, c.day_of_week, c.start_time,
            t.first_name, t.last_name
        ORDER BY rp.performance_order, rp.id
        """,
        (show_id,),
    ).fetchall()

    classes = connection.execute(
        """
        SELECT c.id, c.name, c.day_of_week, c.start_time
        FROM classes c
        WHERE c.active=1
        ORDER BY c.name
        """
    ).fetchall()
    connection.close()

    return render_template(
        "recital_show.html",
        show=dict(show),
        performances=[dict(row) for row in performances],
        classes=[dict(row) for row in classes],
    )


@app.route("/admin/recitals/shows/<int:show_id>/performances/save", methods=["POST"])
@permission_required("recitals")
def save_recital_performance(show_id: int):
    performance_id = request.form.get("id", "").strip()
    class_value = request.form.get("class_id", "").strip()
    class_id = int(class_value) if class_value else None
    values = (
        class_id,
        request.form.get("title", "").strip(),
        int(request.form.get("performance_order", "0") or 0),
        request.form.get("performance_type", "Dance").strip(),
        int(request.form.get("duration_seconds", "0") or 0),
        request.form.get("music_title", "").strip(),
        request.form.get("music_url", "").strip(),
        request.form.get("music_status", "Missing").strip(),
        request.form.get("entrance_notes", "").strip(),
        request.form.get("exit_notes", "").strip(),
        request.form.get("costume_notes", "").strip(),
        request.form.get("status", "Planning").strip(),
    )

    connection = get_db()
    if performance_id:
        connection.execute(
            """
            UPDATE recital_performances SET
                class_id=?, title=?, performance_order=?,
                performance_type=?, duration_seconds=?,
                music_title=?, music_url=?, music_status=?,
                entrance_notes=?, exit_notes=?, costume_notes=?,
                status=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND show_id=?
            """,
            values + (int(performance_id), show_id),
        )
        saved_id = int(performance_id)
        title = "Recital performance updated"
        event_type = "recital_performance_updated"
    else:
        sql = """
            INSERT INTO recital_performances (
                show_id, class_id, title, performance_order,
                performance_type, duration_seconds,
                music_title, music_url, music_status,
                entrance_notes, exit_notes, costume_notes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if connection.backend == "postgresql":
            sql += " RETURNING id"
        cursor = connection.execute(
            sql,
            (show_id,) + values,
        )
        saved_id = (
            int(cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(cursor.lastrowid)
        )
        title = "Recital performance added"
        event_type = "recital_performance_created"

    connection.commit()
    connection.close()

    event_id = create_workflow_event(
        event_type,
        "recitals",
        title,
        values[1],
        "info",
        str(saved_id),
    )
    evaluate_workflow_rules(event_id)

    flash("Performance saved.", "success")
    return redirect(url_for("recital_show", show_id=show_id))


@app.route("/admin/recitals/performances/<int:performance_id>/move", methods=["POST"])
@permission_required("recitals")
def move_recital_performance(performance_id: int):
    direction = request.form.get("direction", "").strip()
    connection = get_db()
    current = connection.execute(
        """
        SELECT id, show_id, performance_order
        FROM recital_performances
        WHERE id=?
        """,
        (performance_id,),
    ).fetchone()

    if not current:
        connection.close()
        return ("Performance not found", 404)

    operator = "<" if direction == "up" else ">"
    ordering = "DESC" if direction == "up" else "ASC"
    neighbor = connection.execute(
        f"""
        SELECT id, performance_order
        FROM recital_performances
        WHERE show_id=?
          AND performance_order {operator} ?
        ORDER BY performance_order {ordering}, id {ordering}
        LIMIT 1
        """,
        (
            current["show_id"],
            current["performance_order"],
        ),
    ).fetchone()

    if neighbor:
        connection.execute(
            """
            UPDATE recital_performances
            SET performance_order=?
            WHERE id=?
            """,
            (neighbor["performance_order"], current["id"]),
        )
        connection.execute(
            """
            UPDATE recital_performances
            SET performance_order=?
            WHERE id=?
            """,
            (current["performance_order"], neighbor["id"]),
        )
        connection.commit()

    show_id = int(current["show_id"])
    connection.close()
    return redirect(url_for("recital_show", show_id=show_id))


@app.route("/admin/recitals/productions/<int:production_id>/rehearsals/save", methods=["POST"])
@permission_required("recitals")
def save_recital_rehearsal(production_id: int):
    show_value = request.form.get("show_id", "").strip()
    show_id = int(show_value) if show_value else None

    connection = get_db()
    connection.execute(
        """
        INSERT INTO recital_rehearsals (
            production_id, show_id, title,
            rehearsal_date, start_time, end_time,
            location, notes, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            production_id,
            show_id,
            request.form.get("title", "").strip(),
            request.form.get("rehearsal_date", "").strip(),
            request.form.get("start_time", "").strip(),
            request.form.get("end_time", "").strip(),
            request.form.get("location", "").strip(),
            request.form.get("notes", "").strip(),
            request.form.get("status", "Scheduled").strip(),
        ),
    )
    connection.commit()
    connection.close()

    event_id = create_workflow_event(
        "recital_rehearsal_created",
        "recitals",
        "Recital rehearsal scheduled",
        request.form.get("title", "").strip(),
        "info",
        str(production_id),
    )
    evaluate_workflow_rules(event_id)

    flash("Rehearsal saved.", "success")
    return redirect(url_for("recital_production", production_id=production_id))


def create_workflow_event(
    event_type: str,
    source_module: str,
    title: str,
    details: str = "",
    severity: str = "info",
    source_id: str = "",
) -> int:
    connection = get_db()
    insert_sql = """
        INSERT INTO workflow_events (
            event_type, source_module, source_id,
            title, details, severity, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    if connection.backend == "postgresql":
        insert_sql += " RETURNING id"

    cursor = connection.execute(
        insert_sql,
        (
            event_type,
            source_module,
            source_id,
            title,
            details,
            severity,
            int(session.get("admin_user_id") or 0) or None,
        ),
    )
    event_id = (
        int(cursor.fetchone()["id"])
        if connection.backend == "postgresql"
        else int(cursor.lastrowid)
    )
    connection.commit()
    connection.close()
    return event_id


def evaluate_workflow_rules(event_id: int) -> int:
    connection = get_db()
    event = connection.execute(
        "SELECT * FROM workflow_events WHERE id=?",
        (event_id,),
    ).fetchone()
    if not event:
        connection.close()
        return 0

    rules = connection.execute(
        """
        SELECT *
        FROM workflow_rules
        WHERE active=1
          AND event_type=?
        ORDER BY id
        """,
        (event["event_type"],),
    ).fetchall()

    created = 0
    for rule in rules:
        title = rule["title_template"].replace(
            "{event_title}",
            event["title"],
        )
        message = rule["message_template"].replace(
            "{event_details}",
            event["details"] or "",
        )

        task_sql = """
            INSERT INTO workflow_tasks (
                rule_id, event_id, task_type,
                status, title, payload
            ) VALUES (?, ?, ?, 'Pending', ?, ?)
        """
        if connection.backend == "postgresql":
            task_sql += " RETURNING id"

        task_cursor = connection.execute(
            task_sql,
            (
                rule["id"],
                event_id,
                rule["action_type"],
                title,
                message,
            ),
        )
        task_id = (
            int(task_cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(task_cursor.lastrowid)
        )

        if rule["action_type"] == "dashboard_notification":
            users = connection.execute(
                """
                SELECT id
                FROM admin_users
                WHERE active=1
                """
            ).fetchall()

            for user in users:
                connection.execute(
                    """
                    INSERT INTO notifications (
                        admin_user_id, title, message,
                        severity, source_module, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user["id"],
                        title,
                        message,
                        rule["severity"],
                        event["source_module"],
                        "",
                    ),
                )

            connection.execute(
                """
                UPDATE workflow_tasks SET
                    status='Completed',
                    completed_at=CURRENT_TIMESTAMP,
                    attempts=attempts+1
                WHERE id=?
                """,
                (task_id,),
            )

        created += 1

    connection.commit()
    connection.close()
    return created


@app.route("/admin/workflows")
@permission_required("workflow")
def workflow_center():
    connection = get_db()
    summary = connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM workflow_events) AS event_count,
            (SELECT COUNT(*) FROM workflow_rules WHERE active=1) AS active_rules,
            (SELECT COUNT(*) FROM workflow_tasks WHERE status='Pending') AS pending_tasks,
            (
                SELECT COUNT(*)
                FROM notifications
                WHERE dismissed_at IS NULL
                  AND read_at IS NULL
            ) AS unread_notifications
        """
    ).fetchone()

    rules = connection.execute(
        """
        SELECT *
        FROM workflow_rules
        ORDER BY active DESC, id DESC
        """
    ).fetchall()

    tasks = connection.execute(
        """
        SELECT
            wt.*,
            wr.name AS rule_name,
            we.event_type
        FROM workflow_tasks wt
        LEFT JOIN workflow_rules wr ON wr.id=wt.rule_id
        LEFT JOIN workflow_events we ON we.id=wt.event_id
        ORDER BY wt.id DESC
        LIMIT 100
        """
    ).fetchall()

    events = connection.execute(
        """
        SELECT
            we.*,
            au.display_name AS created_by_name
        FROM workflow_events we
        LEFT JOIN admin_users au ON au.id=we.created_by
        ORDER BY we.id DESC
        LIMIT 100
        """
    ).fetchall()
    connection.close()

    return render_template(
        "workflow_center.html",
        summary=dict(summary),
        rules=[dict(row) for row in rules],
        tasks=[dict(row) for row in tasks],
        events=[dict(row) for row in events],
    )


@app.route("/admin/workflows/rules/save", methods=["POST"])
@permission_required("workflow")
def save_workflow_rule():
    connection = get_db()
    connection.execute(
        """
        INSERT INTO workflow_rules (
            name, event_type, action_type,
            title_template, message_template,
            severity, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.form.get("name", "").strip(),
            request.form.get("event_type", "").strip(),
            request.form.get(
                "action_type",
                "dashboard_notification",
            ).strip(),
            request.form.get("title_template", "").strip(),
            request.form.get("message_template", "").strip(),
            request.form.get("severity", "info").strip(),
            1 if request.form.get("active") == "on" else 0,
        ),
    )
    connection.commit()
    connection.close()
    flash("Workflow rule created.", "success")
    return redirect(url_for("workflow_center"))


@app.route("/admin/workflows/rules/<int:rule_id>/toggle", methods=["POST"])
@permission_required("workflow")
def toggle_workflow_rule(rule_id: int):
    connection = get_db()
    rule = connection.execute(
        "SELECT active FROM workflow_rules WHERE id=?",
        (rule_id,),
    ).fetchone()
    if rule:
        connection.execute(
            """
            UPDATE workflow_rules SET
                active=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (0 if rule["active"] else 1, rule_id),
        )
        connection.commit()
    connection.close()
    return redirect(url_for("workflow_center"))


@app.route("/admin/workflows/events/create", methods=["POST"])
@permission_required("workflow")
def create_manual_workflow_event():
    event_id = create_workflow_event(
        event_type=request.form.get("event_type", "").strip(),
        source_module=request.form.get("source_module", "manual").strip(),
        source_id=request.form.get("source_id", "").strip(),
        title=request.form.get("title", "").strip(),
        details=request.form.get("details", "").strip(),
        severity=request.form.get("severity", "info").strip(),
    )
    count = evaluate_workflow_rules(event_id)
    flash(
        f"Event created. {count} workflow task(s) generated.",
        "success",
    )
    return redirect(url_for("workflow_center"))


@app.route("/admin/notifications")
@login_required
def notifications_center():
    connection = get_db()
    rows = connection.execute(
        """
        SELECT *
        FROM notifications
        WHERE admin_user_id=?
          AND dismissed_at IS NULL
        ORDER BY read_at IS NULL DESC, id DESC
        """,
        (int(session.get("admin_user_id")),),
    ).fetchall()
    connection.close()

    return render_template(
        "notifications_center.html",
        notifications=[dict(row) for row in rows],
    )


@app.route("/admin/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id: int):
    connection = get_db()
    connection.execute(
        """
        UPDATE notifications SET
            read_at=COALESCE(read_at, CURRENT_TIMESTAMP)
        WHERE id=? AND admin_user_id=?
        """,
        (
            notification_id,
            int(session.get("admin_user_id")),
        ),
    )
    connection.commit()
    connection.close()
    return redirect(url_for("notifications_center"))


@app.route("/admin/notifications/<int:notification_id>/dismiss", methods=["POST"])
@login_required
def dismiss_notification(notification_id: int):
    connection = get_db()
    connection.execute(
        """
        UPDATE notifications SET
            dismissed_at=CURRENT_TIMESTAMP
        WHERE id=? AND admin_user_id=?
        """,
        (
            notification_id,
            int(session.get("admin_user_id")),
        ),
    )
    connection.commit()
    connection.close()
    return redirect(url_for("notifications_center"))


def get_family_billing_summary(connection, family_id: int) -> dict:
    charges = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM billing_charges
        WHERE family_id=? AND status!='Voided'
        """,
        (family_id,),
    ).fetchone()

    payments = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM billing_payments
        WHERE family_id=? AND status!='Voided'
        """,
        (family_id,),
    ).fetchone()

    overdue = connection.execute(
        """
        SELECT
            COUNT(*) AS count,
            COALESCE(SUM(amount), 0) AS total
        FROM billing_charges
        WHERE family_id=?
          AND status='Open'
          AND due_date!=''
          AND due_date<?
        """,
        (family_id, date.today().isoformat()),
    ).fetchone()

    total_charges = float(charges["total"] or 0)
    total_payments = float(payments["total"] or 0)

    return {
        "charges": total_charges,
        "payments": total_payments,
        "balance": total_charges - total_payments,
        "overdue_count": int(overdue["count"] or 0),
        "overdue_total": float(overdue["total"] or 0),
    }


@app.route("/admin/billing")
@permission_required("billing")
def billing_center():
    query = request.args.get("q", "").strip()
    balance_filter = request.args.get("balance", "all").strip()

    conditions = []
    parameters = []

    if query:
        like = f"%{query.lower()}%"
        conditions.append(
            """
            (
                LOWER(f.family_name) LIKE ?
                OR LOWER(f.primary_email) LIKE ?
                OR LOWER(f.primary_phone) LIKE ?
            )
            """
        )
        parameters.extend((like, like, like))

    connection = get_db()
    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    rows = connection.execute(
        f"""
        SELECT
            f.id,
            f.family_name,
            f.primary_email,
            f.primary_phone,
            COALESCE(ch.total_charges, 0) AS total_charges,
            COALESCE(py.total_payments, 0) AS total_payments,
            COALESCE(ch.total_charges, 0)
              - COALESCE(py.total_payments, 0) AS balance,
            COALESCE(ch.overdue_count, 0) AS overdue_count,
            ch.next_due_date
        FROM families f
        LEFT JOIN (
            SELECT
                family_id,
                SUM(CASE WHEN status!='Voided' THEN amount ELSE 0 END) AS total_charges,
                SUM(
                    CASE
                        WHEN status='Open'
                         AND due_date!=''
                         AND due_date<?
                        THEN 1 ELSE 0
                    END
                ) AS overdue_count,
                MIN(
                    CASE
                        WHEN status='Open'
                         AND due_date!=''
                        THEN due_date
                    END
                ) AS next_due_date
            FROM billing_charges
            GROUP BY family_id
        ) ch ON ch.family_id=f.id
        LEFT JOIN (
            SELECT
                family_id,
                SUM(CASE WHEN status!='Voided' THEN amount ELSE 0 END) AS total_payments
            FROM billing_payments
            GROUP BY family_id
        ) py ON py.family_id=f.id
        {where_clause}
        ORDER BY balance DESC, f.family_name
        """,
        tuple([date.today().isoformat()] + parameters),
    ).fetchall()

    accounts = []
    for row in rows:
        item = dict(row)
        balance = float(item["balance"] or 0)
        if balance_filter == "due" and balance <= 0:
            continue
        if balance_filter == "credit" and balance >= 0:
            continue
        if balance_filter == "zero" and abs(balance) >= 0.005:
            continue
        accounts.append(item)

    summary = connection.execute(
        """
        SELECT
            COALESCE(
                (SELECT SUM(amount) FROM billing_charges WHERE status!='Voided'),
                0
            ) AS charges,
            COALESCE(
                (SELECT SUM(amount) FROM billing_payments WHERE status!='Voided'),
                0
            ) AS payments,
            COALESCE(
                (
                    SELECT SUM(amount)
                    FROM billing_charges
                    WHERE status='Open'
                      AND due_date!=''
                      AND due_date<?
                ),
                0
            ) AS overdue
        """,
        (date.today().isoformat(),),
    ).fetchone()
    connection.close()

    summary_data = dict(summary)
    summary_data["balance"] = (
        float(summary_data["charges"] or 0)
        - float(summary_data["payments"] or 0)
    )

    return render_template(
        "billing_center.html",
        accounts=accounts,
        summary=summary_data,
        query=query,
        balance_filter=balance_filter,
    )


@app.route("/admin/billing/families/<int:family_id>")
@permission_required("billing")
def family_billing(family_id: int):
    connection = get_db()
    family = connection.execute(
        "SELECT * FROM families WHERE id=?",
        (family_id,),
    ).fetchone()

    if not family:
        connection.close()
        return ("Family not found", 404)

    students = connection.execute(
        """
        SELECT id, first_name, last_name, preferred_name, status
        FROM students
        WHERE family_id=?
        ORDER BY last_name, first_name
        """,
        (family_id,),
    ).fetchall()

    charges = connection.execute(
        """
        SELECT
            ch.*,
            s.first_name,
            s.last_name,
            s.preferred_name,
            a.display_name AS created_by_name
        FROM billing_charges ch
        LEFT JOIN students s ON s.id=ch.student_id
        LEFT JOIN admin_users a ON a.id=ch.created_by
        WHERE ch.family_id=?
        ORDER BY ch.id DESC
        """,
        (family_id,),
    ).fetchall()

    payments = connection.execute(
        """
        SELECT
            py.*,
            a.display_name AS received_by_name
        FROM billing_payments py
        LEFT JOIN admin_users a ON a.id=py.received_by
        WHERE py.family_id=?
        ORDER BY py.payment_date DESC, py.id DESC
        """,
        (family_id,),
    ).fetchall()

    summary = get_family_billing_summary(connection, family_id)
    connection.close()

    ledger = []
    for row in charges:
        item = dict(row)
        ledger.append({
            "kind": "charge",
            "id": item["id"],
            "date": str(item["created_at"] or ""),
            "description": item["description"],
            "detail": item["charge_type"],
            "amount": float(item["amount"] or 0),
            "status": item["status"],
        })
    for row in payments:
        item = dict(row)
        ledger.append({
            "kind": "payment",
            "id": item["id"],
            "date": item["payment_date"],
            "description": f"{item['payment_method']} payment",
            "detail": item["reference"] or item["note"],
            "amount": -float(item["amount"] or 0),
            "status": item["status"],
        })
    ledger.sort(key=lambda item: (str(item["date"]), item["id"]), reverse=True)

    return render_template(
        "family_billing.html",
        family=dict(family),
        students=[dict(row) for row in students],
        charges=[dict(row) for row in charges],
        payments=[dict(row) for row in payments],
        ledger=ledger,
        summary=summary,
        today=date.today().isoformat(),
    )


@app.route("/admin/billing/families/<int:family_id>/charges", methods=["POST"])
@permission_required("billing")
def add_billing_charge(family_id: int):
    amount = float(request.form.get("amount", "0") or 0)
    description = request.form.get("description", "").strip()
    if amount <= 0 or not description:
        flash("Charge description and a positive amount are required.", "error")
        return redirect(url_for("family_billing", family_id=family_id))

    student_value = request.form.get("student_id", "").strip()
    student_id = int(student_value) if student_value else None

    connection = get_db()
    connection.execute(
        """
        INSERT INTO billing_charges (
            family_id, student_id, charge_type,
            description, amount, due_date,
            status, reference, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, 'Open', ?, ?)
        """,
        (
            family_id,
            student_id,
            request.form.get("charge_type", "Tuition").strip(),
            description,
            amount,
            request.form.get("due_date", "").strip(),
            request.form.get("reference", "").strip(),
            int(session.get("admin_user_id") or 0) or None,
        ),
    )
    connection.commit()
    connection.close()

    log_activity(
        "Billing charge added",
        f"Family #{family_id} · {description} · ${amount:.2f}",
    )
    event_id = create_workflow_event(
        "billing_charge_created",
        "billing",
        "Billing charge created",
        f"Family #{family_id} · {description} · ${amount:.2f}",
        "info",
        str(family_id),
    )
    evaluate_workflow_rules(event_id)
    flash("Charge added.", "success")
    return redirect(url_for("family_billing", family_id=family_id))


@app.route("/admin/billing/families/<int:family_id>/payments", methods=["POST"])
@permission_required("billing")
def add_billing_payment(family_id: int):
    amount = float(request.form.get("amount", "0") or 0)
    if amount <= 0:
        flash("Payment amount must be greater than zero.", "error")
        return redirect(url_for("family_billing", family_id=family_id))

    connection = get_db()
    insert_sql = """
        INSERT INTO billing_payments (
            family_id, amount, payment_method,
            payment_date, reference, note,
            status, received_by
        ) VALUES (?, ?, ?, ?, ?, ?, 'Posted', ?)
    """
    if connection.backend == "postgresql":
        insert_sql += " RETURNING id"

    cursor = connection.execute(
        insert_sql,
        (
            family_id,
            amount,
            request.form.get("payment_method", "Cash").strip(),
            request.form.get(
                "payment_date",
                date.today().isoformat(),
            ).strip(),
            request.form.get("reference", "").strip(),
            request.form.get("note", "").strip(),
            int(session.get("admin_user_id") or 0) or None,
        ),
    )
    payment_id = (
        int(cursor.fetchone()["id"])
        if connection.backend == "postgresql"
        else int(cursor.lastrowid)
    )
    connection.commit()
    connection.close()

    log_activity(
        "Billing payment recorded",
        f"Family #{family_id} · ${amount:.2f}",
    )
    event_id = create_workflow_event(
        "billing_payment_recorded",
        "billing",
        "Payment recorded",
        f"Family #{family_id} · ${amount:.2f}",
        "success",
        str(payment_id),
    )
    evaluate_workflow_rules(event_id)
    flash("Payment recorded.", "success")
    return redirect(url_for("billing_receipt", payment_id=payment_id))


@app.route("/admin/billing/charges/<int:charge_id>/void", methods=["POST"])
@permission_required("billing")
def void_billing_charge(charge_id: int):
    reason = request.form.get("void_reason", "").strip()
    connection = get_db()
    charge = connection.execute(
        "SELECT family_id, status FROM billing_charges WHERE id=?",
        (charge_id,),
    ).fetchone()
    if charge and charge["status"] != "Voided":
        connection.execute(
            """
            UPDATE billing_charges SET
                status='Voided',
                voided_at=CURRENT_TIMESTAMP,
                voided_by=?,
                void_reason=?
            WHERE id=?
            """,
            (
                int(session.get("admin_user_id") or 0) or None,
                reason,
                charge_id,
            ),
        )
        connection.commit()
    connection.close()
    flash("Charge voided.", "success")
    return redirect(
        url_for(
            "family_billing",
            family_id=int(charge["family_id"]) if charge else 0,
        )
    )


@app.route("/admin/billing/payments/<int:payment_id>/void", methods=["POST"])
@permission_required("billing")
def void_billing_payment(payment_id: int):
    reason = request.form.get("void_reason", "").strip()
    connection = get_db()
    payment = connection.execute(
        "SELECT family_id, status FROM billing_payments WHERE id=?",
        (payment_id,),
    ).fetchone()
    if payment and payment["status"] != "Voided":
        connection.execute(
            """
            UPDATE billing_payments SET
                status='Voided',
                voided_at=CURRENT_TIMESTAMP,
                voided_by=?,
                void_reason=?
            WHERE id=?
            """,
            (
                int(session.get("admin_user_id") or 0) or None,
                reason,
                payment_id,
            ),
        )
        connection.commit()
    connection.close()
    flash("Payment voided.", "success")
    return redirect(
        url_for(
            "family_billing",
            family_id=int(payment["family_id"]) if payment else 0,
        )
    )


@app.route("/admin/billing/receipts/<int:payment_id>")
@permission_required("billing")
def billing_receipt(payment_id: int):
    connection = get_db()
    payment = connection.execute(
        """
        SELECT
            py.*,
            f.family_name,
            f.primary_email,
            f.primary_phone,
            a.display_name AS received_by_name
        FROM billing_payments py
        JOIN families f ON f.id=py.family_id
        LEFT JOIN admin_users a ON a.id=py.received_by
        WHERE py.id=?
        """,
        (payment_id,),
    ).fetchone()

    if not payment:
        connection.close()
        return ("Receipt not found", 404)

    summary = get_family_billing_summary(
        connection,
        int(payment["family_id"]),
    )
    connection.close()

    return render_template(
        "billing_receipt.html",
        payment=dict(payment),
        summary=summary,
    )


def teacher_can_access_class(connection, class_id: int) -> bool:
    if session.get("admin_role") != "teacher":
        return True

    row = connection.execute(
        """
        SELECT t.admin_user_id
        FROM classes c
        LEFT JOIN teachers t ON t.id = c.teacher_id
        WHERE c.id=?
        """,
        (class_id,),
    ).fetchone()

    return bool(
        row
        and int(row["admin_user_id"] or 0)
        == int(session.get("admin_user_id") or 0)
    )


def get_or_create_class_session(
    connection,
    class_id: int,
    session_date: str,
) -> int:
    row = connection.execute(
        """
        SELECT id
        FROM class_sessions
        WHERE class_id=? AND session_date=?
        """,
        (class_id, session_date),
    ).fetchone()

    if row:
        return int(row["id"])

    insert_sql = """
        INSERT INTO class_sessions (
            class_id, session_date, created_by
        ) VALUES (?, ?, ?)
    """
    if connection.backend == "postgresql":
        insert_sql += " RETURNING id"

    cursor = connection.execute(
        insert_sql,
        (
            class_id,
            session_date,
            int(session.get("admin_user_id") or 0) or None,
        ),
    )

    return (
        int(cursor.fetchone()["id"])
        if connection.backend == "postgresql"
        else int(cursor.lastrowid)
    )


@app.route("/admin/attendance")
@permission_required("attendance")
def attendance_center():
    selected_date = request.args.get(
        "date",
        date.today().isoformat(),
    ).strip()

    conditions = ["c.active=1"]
    parameters = [selected_date]

    if session.get("admin_role") == "teacher":
        conditions.append("t.admin_user_id=?")
        parameters.append(int(session.get("admin_user_id")))

    connection = get_db()
    rows = connection.execute(
        f"""
        SELECT
            c.id,
            c.name,
            c.room,
            c.day_of_week,
            c.start_time,
            c.end_time,
            t.first_name AS teacher_first_name,
            t.last_name AS teacher_last_name,
            cs.id AS session_id,
            cs.status AS session_status,
            COUNT(DISTINCT e.student_id) AS roster_count,
            COUNT(DISTINCT CASE WHEN ar.status='Present' THEN ar.student_id END) AS present_count,
            COUNT(DISTINCT CASE WHEN ar.status='Late' THEN ar.student_id END) AS late_count,
            COUNT(DISTINCT CASE WHEN ar.status='Absent' THEN ar.student_id END) AS absent_count,
            COUNT(DISTINCT CASE WHEN ar.status='Excused' THEN ar.student_id END) AS excused_count
        FROM classes c
        LEFT JOIN teachers t ON t.id=c.teacher_id
        LEFT JOIN class_enrollments e
          ON e.class_id=c.id
         AND e.status='Active'
        LEFT JOIN class_sessions cs
          ON cs.class_id=c.id
         AND cs.session_date=?
        LEFT JOIN attendance_records ar
          ON ar.session_id=cs.id
         AND ar.student_id=e.student_id
        WHERE {" AND ".join(conditions)}
        GROUP BY
            c.id, c.name, c.room, c.day_of_week,
            c.start_time, c.end_time,
            t.first_name, t.last_name,
            cs.id, cs.status
        ORDER BY
            CASE c.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
                ELSE 8
            END,
            c.start_time,
            c.name
        """,
        tuple(parameters),
    ).fetchall()
    connection.close()

    classes = []
    totals = {
        "classes": len(rows),
        "roster": 0,
        "present": 0,
        "late": 0,
        "absent": 0,
        "excused": 0,
        "unmarked": 0,
    }

    for row in rows:
        item = dict(row)
        marked = (
            int(item["present_count"] or 0)
            + int(item["late_count"] or 0)
            + int(item["absent_count"] or 0)
            + int(item["excused_count"] or 0)
        )
        item["unmarked_count"] = max(
            int(item["roster_count"] or 0) - marked,
            0,
        )
        classes.append(item)

        totals["roster"] += int(item["roster_count"] or 0)
        totals["present"] += int(item["present_count"] or 0)
        totals["late"] += int(item["late_count"] or 0)
        totals["absent"] += int(item["absent_count"] or 0)
        totals["excused"] += int(item["excused_count"] or 0)
        totals["unmarked"] += int(item["unmarked_count"] or 0)

    marked_total = (
        totals["present"]
        + totals["late"]
        + totals["absent"]
        + totals["excused"]
    )
    totals["attendance_rate"] = (
        round(
            (totals["present"] + totals["late"])
            / marked_total
            * 100,
            1,
        )
        if marked_total else 0
    )

    return render_template(
        "attendance_center.html",
        classes=classes,
        totals=totals,
        selected_date=selected_date,
    )


@app.route("/admin/attendance/classes/<int:class_id>")
@permission_required("attendance")
def take_attendance(class_id: int):
    selected_date = request.args.get(
        "date",
        date.today().isoformat(),
    ).strip()

    connection = get_db()

    if not teacher_can_access_class(connection, class_id):
        connection.close()
        flash(
            "You can only take attendance for classes assigned to you.",
            "error",
        )
        return redirect(
            url_for("attendance_center", date=selected_date)
        )

    class_record = connection.execute(
        """
        SELECT
            c.*,
            t.first_name AS teacher_first_name,
            t.last_name AS teacher_last_name
        FROM classes c
        LEFT JOIN teachers t ON t.id=c.teacher_id
        WHERE c.id=?
        """,
        (class_id,),
    ).fetchone()

    if not class_record:
        connection.close()
        return ("Class not found", 404)

    session_id = get_or_create_class_session(
        connection,
        class_id,
        selected_date,
    )

    session_record = connection.execute(
        "SELECT * FROM class_sessions WHERE id=?",
        (session_id,),
    ).fetchone()

    roster = connection.execute(
        """
        SELECT
            s.id AS student_id,
            s.first_name,
            s.last_name,
            s.preferred_name,
            s.photo_url,
            s.birth_date,
            f.family_name,
            COALESCE(ar.status, 'Unmarked') AS attendance_status,
            COALESCE(ar.minutes_late, 0) AS minutes_late,
            COALESCE(ar.note, '') AS attendance_note
        FROM class_enrollments e
        JOIN students s ON s.id=e.student_id
        LEFT JOIN families f ON f.id=s.family_id
        LEFT JOIN attendance_records ar
          ON ar.session_id=?
         AND ar.student_id=s.id
        WHERE e.class_id=?
          AND e.status='Active'
        ORDER BY s.last_name, s.first_name
        """,
        (session_id, class_id),
    ).fetchall()

    connection.commit()
    connection.close()

    roster_list = [dict(row) for row in roster]
    counts = {
        status: sum(
            1
            for row in roster_list
            if row["attendance_status"] == status
        )
        for status in (
            "Present",
            "Late",
            "Absent",
            "Excused",
            "Unmarked",
        )
    }

    return render_template(
        "take_attendance.html",
        class_record=dict(class_record),
        session_record=dict(session_record),
        roster=roster_list,
        selected_date=selected_date,
        counts=counts,
    )


@app.route(
    "/admin/attendance/sessions/<int:session_id>/save",
    methods=["POST"],
)
@permission_required("attendance")
def save_attendance_session(session_id: int):
    connection = get_db()

    session_record = connection.execute(
        """
        SELECT class_id, session_date
        FROM class_sessions
        WHERE id=?
        """,
        (session_id,),
    ).fetchone()

    if not session_record:
        connection.close()
        flash("Attendance session not found.", "error")
        return redirect(url_for("attendance_center"))

    class_id = int(session_record["class_id"])

    if not teacher_can_access_class(connection, class_id):
        connection.close()
        flash("You cannot edit this attendance session.", "error")
        return redirect(url_for("attendance_center"))

    session_status = request.form.get(
        "session_status",
        "Completed",
    ).strip()
    if session_status not in {
        "Scheduled",
        "Completed",
        "Cancelled",
    }:
        session_status = "Completed"

    connection.execute(
        """
        UPDATE class_sessions SET
            status=?,
            topic=?,
            teacher_notes=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (
            session_status,
            request.form.get("topic", "").strip(),
            request.form.get("teacher_notes", "").strip(),
            session_id,
        ),
    )

    student_ids = request.form.getlist("student_id")
    allowed_statuses = {
        "Present",
        "Late",
        "Absent",
        "Excused",
        "Unmarked",
    }

    for student_id_text in student_ids:
        student_id = int(student_id_text)
        status = request.form.get(
            f"status_{student_id}",
            "Unmarked",
        ).strip()
        if status not in allowed_statuses:
            status = "Unmarked"

        minutes_late = int(
            request.form.get(
                f"minutes_{student_id}",
                "0",
            )
            or 0
        )

        note = request.form.get(
            f"note_{student_id}",
            "",
        ).strip()

        connection.execute(
            """
            INSERT INTO attendance_records (
                session_id,
                student_id,
                status,
                minutes_late,
                note,
                marked_by
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, student_id) DO UPDATE SET
                status=excluded.status,
                minutes_late=excluded.minutes_late,
                note=excluded.note,
                marked_by=excluded.marked_by,
                marked_at=CURRENT_TIMESTAMP
            """,
            (
                session_id,
                student_id,
                status,
                max(minutes_late, 0),
                note,
                int(session.get("admin_user_id") or 0) or None,
            ),
        )

    connection.commit()
    connection.close()

    log_activity(
        "Attendance saved",
        f"Class #{class_id} · {session_record['session_date']}",
    )
    flash("Attendance saved.", "success")

    return redirect(
        url_for(
            "take_attendance",
            class_id=class_id,
            date=session_record["session_date"],
        )
    )


@app.route("/admin/attendance/history")
@permission_required("attendance")
def attendance_history():
    query = request.args.get("q", "").strip()
    selected_status = request.args.get("status", "").strip()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()

    conditions = []
    parameters = []

    if query:
        like = f"%{query.lower()}%"
        conditions.append(
            """
            (
                LOWER(s.first_name) LIKE ?
                OR LOWER(s.last_name) LIKE ?
                OR LOWER(c.name) LIKE ?
                OR LOWER(f.family_name) LIKE ?
            )
            """
        )
        parameters.extend((like, like, like, like))

    if selected_status:
        conditions.append("ar.status=?")
        parameters.append(selected_status)

    if date_from:
        conditions.append("cs.session_date>=?")
        parameters.append(date_from)

    if date_to:
        conditions.append("cs.session_date<=?")
        parameters.append(date_to)

    if session.get("admin_role") == "teacher":
        conditions.append("t.admin_user_id=?")
        parameters.append(int(session.get("admin_user_id")))

    where_clause = (
        "WHERE " + " AND ".join(conditions)
        if conditions else ""
    )

    connection = get_db()
    rows = connection.execute(
        f"""
        SELECT
            ar.status,
            ar.minutes_late,
            ar.note,
            ar.marked_at,
            cs.session_date,
            c.id AS class_id,
            c.name AS class_name,
            s.id AS student_id,
            s.first_name,
            s.last_name,
            s.preferred_name,
            f.family_name,
            t.first_name AS teacher_first_name,
            t.last_name AS teacher_last_name
        FROM attendance_records ar
        JOIN class_sessions cs ON cs.id=ar.session_id
        JOIN classes c ON c.id=cs.class_id
        JOIN students s ON s.id=ar.student_id
        LEFT JOIN families f ON f.id=s.family_id
        LEFT JOIN teachers t ON t.id=c.teacher_id
        {where_clause}
        ORDER BY
            cs.session_date DESC,
            c.start_time,
            s.last_name,
            s.first_name
        LIMIT 1000
        """,
        tuple(parameters),
    ).fetchall()

    summary = connection.execute(
        """
        SELECT
            COUNT(*) AS records,
            COALESCE(SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END),0) AS present,
            COALESCE(SUM(CASE WHEN status='Late' THEN 1 ELSE 0 END),0) AS late,
            COALESCE(SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END),0) AS absent,
            COALESCE(SUM(CASE WHEN status='Excused' THEN 1 ELSE 0 END),0) AS excused
        FROM attendance_records
        """
    ).fetchone()
    connection.close()

    summary_data = dict(summary)
    marked = sum(
        int(summary_data[key] or 0)
        for key in (
            "present",
            "late",
            "absent",
            "excused",
        )
    )
    summary_data["attendance_rate"] = (
        round(
            (
                int(summary_data["present"] or 0)
                + int(summary_data["late"] or 0)
            )
            / marked
            * 100,
            1,
        )
        if marked else 0
    )

    return render_template(
        "attendance_history.html",
        records=[dict(row) for row in rows],
        summary=summary_data,
        query=query,
        selected_status=selected_status,
        date_from=date_from,
        date_to=date_to,
    )


@app.route("/admin/classes")
@permission_required("classes")
def classes_dashboard():
    query = request.args.get("q", "").strip()
    day = request.args.get("day", "").strip()
    active_filter = request.args.get("active", "1").strip()

    conditions = []
    parameters = []

    if query:
        like = f"%{query.lower()}%"
        conditions.append(
            """
            (
                LOWER(c.name) LIKE ?
                OR LOWER(c.category) LIKE ?
                OR LOWER(c.level) LIKE ?
                OR LOWER(c.room) LIKE ?
                OR LOWER(t.first_name) LIKE ?
                OR LOWER(t.last_name) LIKE ?
            )
            """
        )
        parameters.extend((like, like, like, like, like, like))

    if day:
        conditions.append("c.day_of_week = ?")
        parameters.append(day)

    if active_filter in {"0", "1"}:
        conditions.append("c.active = ?")
        parameters.append(int(active_filter))

    # Teachers only see classes linked to their admin account.
    if session.get("admin_role") == "teacher":
        conditions.append("t.admin_user_id = ?")
        parameters.append(int(session.get("admin_user_id")))

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    connection = get_db()
    rows = connection.execute(
        f"""
        SELECT
            c.*,
            t.first_name AS teacher_first_name,
            t.last_name AS teacher_last_name,
            COUNT(CASE WHEN e.status='Active' THEN 1 END) AS enrolled_count
        FROM classes c
        LEFT JOIN teachers t ON t.id = c.teacher_id
        LEFT JOIN class_enrollments e ON e.class_id = c.id
        {where_clause}
        GROUP BY
            c.id, c.name, c.category, c.level, c.teacher_id,
            c.room, c.day_of_week, c.start_time, c.end_time,
            c.capacity, c.active, c.season, c.description,
            c.created_at, c.updated_at,
            t.first_name, t.last_name
        ORDER BY
            CASE c.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
                ELSE 8
            END,
            c.start_time,
            c.name
        """,
        tuple(parameters),
    ).fetchall()

    summary = connection.execute(
        """
        SELECT
            COUNT(*) AS class_count,
            COALESCE(SUM(CASE WHEN active=1 THEN 1 ELSE 0 END), 0) AS active_count,
            COALESCE(SUM(capacity), 0) AS total_capacity
        FROM classes
        """
    ).fetchone()

    enrollment_summary = connection.execute(
        """
        SELECT COUNT(*) AS enrolled_count
        FROM class_enrollments
        WHERE status='Active'
        """
    ).fetchone()
    connection.close()

    summary_data = dict(summary)
    summary_data["enrolled_count"] = int(
        enrollment_summary["enrolled_count"] or 0
    )

    return render_template(
        "classes.html",
        classes=[dict(row) for row in rows],
        summary=summary_data,
        query=query,
        selected_day=day,
        selected_active=active_filter,
    )


@app.route("/admin/classes/new")
@permission_required("classes")
def new_class():
    if session.get("admin_role") == "teacher":
        flash("Teachers cannot create classes.", "error")
        return redirect(url_for("classes_dashboard"))

    connection = get_db()
    teachers = connection.execute(
        """
        SELECT id, first_name, last_name
        FROM teachers
        WHERE active=1
        ORDER BY last_name, first_name
        """
    ).fetchall()
    connection.close()

    return render_template(
        "class_form.html",
        class_record=None,
        teachers=[dict(row) for row in teachers],
    )


@app.route("/admin/classes/save", methods=["POST"])
@permission_required("classes")
def save_class():
    if session.get("admin_role") == "teacher":
        flash("Teachers cannot create or edit classes.", "error")
        return redirect(url_for("classes_dashboard"))

    form = request.form
    class_id = form.get("id", "").strip()
    teacher_value = form.get("teacher_id", "").strip()
    teacher_id = int(teacher_value) if teacher_value else None

    values = (
        form.get("name", "").strip(),
        form.get("category", "").strip(),
        form.get("level", "").strip(),
        teacher_id,
        form.get("room", "").strip(),
        form.get("day_of_week", "").strip(),
        form.get("start_time", "").strip(),
        form.get("end_time", "").strip(),
        int(form.get("capacity", "0") or 0),
        1 if form.get("active") == "on" else 0,
        form.get("season", "").strip(),
        form.get("description", "").strip(),
    )

    connection = get_db()
    if class_id:
        connection.execute(
            """
            UPDATE classes SET
                name=?, category=?, level=?, teacher_id=?,
                room=?, day_of_week=?, start_time=?, end_time=?,
                capacity=?, active=?, season=?, description=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            values + (int(class_id),),
        )
        class_record_id = int(class_id)
        action = "Class updated"
    else:
        sql = """
            INSERT INTO classes (
                name, category, level, teacher_id, room,
                day_of_week, start_time, end_time,
                capacity, active, season, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if connection.backend == "postgresql":
            sql += " RETURNING id"
        cursor = connection.execute(sql, values)
        class_record_id = (
            int(cursor.fetchone()["id"])
            if connection.backend == "postgresql"
            else int(cursor.lastrowid)
        )
        action = "Class created"

    connection.commit()
    connection.close()

    log_activity(action, form.get("name", "").strip())
    flash("Class saved.", "success")
    return redirect(url_for("class_profile", class_id=class_record_id))


@app.route("/admin/classes/<int:class_id>")
@permission_required("classes")
def class_profile(class_id: int):
    connection = get_db()

    class_record = connection.execute(
        """
        SELECT
            c.*,
            t.first_name AS teacher_first_name,
            t.last_name AS teacher_last_name,
            t.admin_user_id AS teacher_admin_user_id
        FROM classes c
        LEFT JOIN teachers t ON t.id = c.teacher_id
        WHERE c.id=?
        """,
        (class_id,),
    ).fetchone()

    if not class_record:
        connection.close()
        return ("Class not found", 404)

    if (
        session.get("admin_role") == "teacher"
        and int(class_record["teacher_admin_user_id"] or 0)
        != int(session.get("admin_user_id") or 0)
    ):
        connection.close()
        flash("You can only open classes assigned to you.", "error")
        return redirect(url_for("classes_dashboard"))

    roster = connection.execute(
        """
        SELECT
            e.id AS enrollment_id,
            e.status AS enrollment_status,
            e.enrolled_at,
            s.id AS student_id,
            s.first_name,
            s.last_name,
            s.preferred_name,
            s.photo_url,
            s.status AS student_status,
            s.birth_date,
            f.id AS family_id,
            f.family_name
        FROM class_enrollments e
        JOIN students s ON s.id = e.student_id
        LEFT JOIN families f ON f.id = s.family_id
        WHERE e.class_id=?
        ORDER BY s.last_name, s.first_name
        """,
        (class_id,),
    ).fetchall()

    students = connection.execute(
        """
        SELECT
            s.id, s.first_name, s.last_name, s.preferred_name,
            f.family_name
        FROM students s
        LEFT JOIN families f ON f.id = s.family_id
        WHERE s.status IN ('Active', 'Trial')
          AND s.id NOT IN (
              SELECT student_id
              FROM class_enrollments
              WHERE class_id=?
                AND status='Active'
          )
        ORDER BY s.last_name, s.first_name
        """,
        (class_id,),
    ).fetchall()

    teachers = connection.execute(
        """
        SELECT id, first_name, last_name
        FROM teachers
        WHERE active=1
        ORDER BY last_name, first_name
        """
    ).fetchall()
    connection.close()

    active_enrolled = sum(
        1 for row in roster if row["enrollment_status"] == "Active"
    )
    capacity = int(class_record["capacity"] or 0)
    spaces_left = max(capacity - active_enrolled, 0) if capacity else None

    return render_template(
        "class_profile.html",
        class_record=dict(class_record),
        roster=[dict(row) for row in roster],
        students=[dict(row) for row in students],
        teachers=[dict(row) for row in teachers],
        active_enrolled=active_enrolled,
        spaces_left=spaces_left,
        can_edit=session.get("admin_role") != "teacher",
    )


@app.route("/admin/classes/<int:class_id>/enroll", methods=["POST"])
@permission_required("classes")
def enroll_student(class_id: int):
    if session.get("admin_role") == "teacher":
        flash("Teachers cannot change enrollment.", "error")
        return redirect(url_for("class_profile", class_id=class_id))

    student_id = int(request.form.get("student_id", "0") or 0)
    if not student_id:
        flash("Select a student.", "error")
        return redirect(url_for("class_profile", class_id=class_id))

    connection = get_db()
    connection.execute(
        """
        INSERT INTO class_enrollments (
            class_id, student_id, status
        ) VALUES (?, ?, 'Active')
        ON CONFLICT(class_id, student_id) DO UPDATE SET
            status='Active',
            enrolled_at=CURRENT_TIMESTAMP
        """,
        (class_id, student_id),
    )
    connection.commit()

    student = connection.execute(
        "SELECT first_name, last_name FROM students WHERE id=?",
        (student_id,),
    ).fetchone()
    class_record = connection.execute(
        "SELECT name FROM classes WHERE id=?",
        (class_id,),
    ).fetchone()
    connection.close()

    if student and class_record:
        log_activity(
            "Student enrolled",
            f"{student['first_name']} {student['last_name']} → {class_record['name']}",
        )

    flash("Student enrolled.", "success")
    return redirect(url_for("class_profile", class_id=class_id))


@app.route(
    "/admin/classes/<int:class_id>/enrollments/<int:enrollment_id>/status",
    methods=["POST"],
)
@permission_required("classes")
def update_enrollment_status(class_id: int, enrollment_id: int):
    if session.get("admin_role") == "teacher":
        flash("Teachers cannot change enrollment.", "error")
        return redirect(url_for("class_profile", class_id=class_id))

    status = request.form.get("status", "Active").strip()
    if status not in {"Active", "Waitlist", "Dropped", "Completed"}:
        flash("Invalid enrollment status.", "error")
        return redirect(url_for("class_profile", class_id=class_id))

    connection = get_db()
    connection.execute(
        """
        UPDATE class_enrollments
        SET status=?
        WHERE id=? AND class_id=?
        """,
        (status, enrollment_id, class_id),
    )
    connection.commit()
    connection.close()

    flash("Enrollment status updated.", "success")
    return redirect(url_for("class_profile", class_id=class_id))


@app.route("/admin/teachers")
@permission_required("teachers")
def teachers_dashboard():
    connection = get_db()
    teachers = connection.execute(
        """
        SELECT
            t.*,
            a.display_name AS account_display_name,
            a.username AS account_username,
            COUNT(c.id) AS class_count
        FROM teachers t
        LEFT JOIN admin_users a ON a.id = t.admin_user_id
        LEFT JOIN classes c ON c.teacher_id = t.id AND c.active=1
        GROUP BY
            t.id, t.admin_user_id, t.first_name, t.last_name,
            t.email, t.phone, t.active, t.bio,
            t.created_at, t.updated_at,
            a.display_name, a.username
        ORDER BY t.active DESC, t.last_name, t.first_name
        """
    ).fetchall()

    teacher_accounts = connection.execute(
        """
        SELECT id, username, display_name, email
        FROM admin_users
        WHERE role='teacher'
          AND active=1
        ORDER BY display_name
        """
    ).fetchall()
    connection.close()

    return render_template(
        "teachers.html",
        teachers=[dict(row) for row in teachers],
        teacher_accounts=[dict(row) for row in teacher_accounts],
    )


@app.route("/admin/teachers/save", methods=["POST"])
@permission_required("teachers")
def save_teacher():
    form = request.form
    teacher_id = form.get("id", "").strip()
    admin_value = form.get("admin_user_id", "").strip()
    admin_user_id = int(admin_value) if admin_value else None

    values = (
        admin_user_id,
        form.get("first_name", "").strip(),
        form.get("last_name", "").strip(),
        form.get("email", "").strip().lower(),
        form.get("phone", "").strip(),
        1 if form.get("active") == "on" else 0,
        form.get("bio", "").strip(),
    )

    connection = get_db()
    if teacher_id:
        connection.execute(
            """
            UPDATE teachers SET
                admin_user_id=?, first_name=?, last_name=?,
                email=?, phone=?, active=?, bio=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            values + (int(teacher_id),),
        )
        action = "Teacher updated"
    else:
        connection.execute(
            """
            INSERT INTO teachers (
                admin_user_id, first_name, last_name,
                email, phone, active, bio
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        action = "Teacher created"

    connection.commit()
    connection.close()

    log_activity(
        action,
        f"{form.get('first_name', '').strip()} {form.get('last_name', '').strip()}",
    )
    flash("Teacher saved.", "success")
    return redirect(url_for("teachers_dashboard"))


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
