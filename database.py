from __future__ import annotations

import sqlite3
from typing import Any, Iterable

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

from config import DATABASE_URL, SQLITE_DB_PATH, USE_POSTGRES


class DatabaseConnection:
    """Small compatibility layer for PostgreSQL and SQLite."""

    def __init__(self):
        if USE_POSTGRES:
            if psycopg is None:
                raise RuntimeError(
                    "DATABASE_URL is configured but psycopg is not installed."
                )
            self.backend = "postgresql"
            self.connection = psycopg.connect(
                DATABASE_URL,
                row_factory=dict_row,
                autocommit=False,
                connect_timeout=5,
            )
        else:
            self.backend = "sqlite"
            self.connection = sqlite3.connect(SQLITE_DB_PATH)
            self.connection.row_factory = sqlite3.Row

    def _sql(self, statement: str) -> str:
        if self.backend == "postgresql":
            return statement.replace("?", "%s")
        return statement

    def execute(self, statement: str, parameters: Iterable[Any] = ()):
        return self.connection.execute(self._sql(statement), tuple(parameters))

    def executemany(self, statement: str, parameter_rows):
        return self.connection.executemany(
            self._sql(statement),
            parameter_rows,
        )

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


def get_db() -> DatabaseConnection:
    return DatabaseConnection()




def init_db() -> None:
    connection = get_db()
    cursor = connection

    if connection.backend == "postgresql":
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price DOUBLE PRECISION NOT NULL DEFAULT 0,
                sale_price DOUBLE PRECISION,
                fulfillment_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
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
        cursor.execute(
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS show_color INTEGER NOT NULL DEFAULT 1"
        )
    else:
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
        columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(products)").fetchall()
        }
        if "show_color" not in columns:
            cursor.execute(
                "ALTER TABLE products ADD COLUMN show_color INTEGER NOT NULL DEFAULT 1"
            )

    id_column = "SERIAL PRIMARY KEY" if connection.backend == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS activity_log (
            id {id_column},
            action TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS announcements (
            id {id_column},
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            button_text TEXT NOT NULL DEFAULT '',
            button_link TEXT NOT NULL DEFAULT '',
            start_date TEXT NOT NULL DEFAULT '',
            end_date TEXT NOT NULL DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS orders (
            id {id_column},
            order_number TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            customer_phone TEXT NOT NULL DEFAULT '',
            payment_method TEXT NOT NULL,
            fulfillment_method TEXT NOT NULL DEFAULT 'Studio Pickup',
            notes TEXT NOT NULL DEFAULT '',
            subtotal DOUBLE PRECISION NOT NULL DEFAULT 0,
            name_fees DOUBLE PRECISION NOT NULL DEFAULT 0,
            fulfillment_fees DOUBLE PRECISION NOT NULL DEFAULT 0,
            shipping_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
            tax DOUBLE PRECISION NOT NULL DEFAULT 0,
            total DOUBLE PRECISION NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'New',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS order_items (
            id {id_column},
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            size TEXT NOT NULL DEFAULT '',
            color TEXT NOT NULL DEFAULT '',
            requested_name TEXT NOT NULL DEFAULT '',
            item_price DOUBLE PRECISION NOT NULL DEFAULT 0,
            name_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
            fulfillment_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS customers (
            id {id_column},
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Active',
            tags TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            order_count INTEGER NOT NULL DEFAULT 0,
            lifetime_value DOUBLE PRECISION NOT NULL DEFAULT 0,
            last_order_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS customer_notes (
            id {id_column},
            customer_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS families (
            id {id_column},
            family_name TEXT NOT NULL,
            primary_email TEXT NOT NULL DEFAULT '',
            primary_phone TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            customer_count INTEGER NOT NULL DEFAULT 0,
            order_count INTEGER NOT NULL DEFAULT 0,
            lifetime_value DOUBLE PRECISION NOT NULL DEFAULT 0,
            last_activity_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS family_notes (
            id {id_column},
            family_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(family_id) REFERENCES families(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id {id_column},
            migration_key TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'applied',
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            execution_ms INTEGER NOT NULL DEFAULT 0,
            details TEXT NOT NULL DEFAULT ''
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS students (
            id {id_column},
            family_id INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            preferred_name TEXT NOT NULL DEFAULT '',
            birth_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Active',
            competition_team INTEGER NOT NULL DEFAULT 0,
            photo_url TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            school TEXT NOT NULL DEFAULT '',
            grade TEXT NOT NULL DEFAULT '',
            leotard_size TEXT NOT NULL DEFAULT '',
            costume_size TEXT NOT NULL DEFAULT '',
            shoe_size TEXT NOT NULL DEFAULT '',
            warmup_size TEXT NOT NULL DEFAULT '',
            medical_notes TEXT NOT NULL DEFAULT '',
            general_notes TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(family_id) REFERENCES families(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS student_notes (
            id {id_column},
            student_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS admin_users (
            id {id_column},
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'office_staff',
            active INTEGER NOT NULL DEFAULT 1,
            last_login_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS admin_login_history (
            id {id_column},
            admin_user_id INTEGER,
            username TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0,
            ip_address TEXT NOT NULL DEFAULT '',
            user_agent TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(admin_user_id) REFERENCES admin_users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS teachers (
            id {id_column},
            admin_user_id INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            bio TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(admin_user_id) REFERENCES admin_users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS classes (
            id {id_column},
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            level TEXT NOT NULL DEFAULT '',
            teacher_id INTEGER,
            room TEXT NOT NULL DEFAULT '',
            day_of_week TEXT NOT NULL DEFAULT '',
            start_time TEXT NOT NULL DEFAULT '',
            end_time TEXT NOT NULL DEFAULT '',
            capacity INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            season TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS class_enrollments (
            id {id_column},
            class_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            notes TEXT NOT NULL DEFAULT '',
            UNIQUE(class_id, student_id),
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS class_sessions (
            id {id_column},
            class_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Scheduled',
            topic TEXT NOT NULL DEFAULT '',
            teacher_notes TEXT NOT NULL DEFAULT '',
            created_by INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(class_id, session_date),
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
            FOREIGN KEY(created_by) REFERENCES admin_users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS attendance_records (
            id {id_column},
            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Unmarked',
            minutes_late INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            marked_by INTEGER,
            marked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, student_id),
            FOREIGN KEY(session_id) REFERENCES class_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY(marked_by) REFERENCES admin_users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS billing_charges (
            id {id_column},
            family_id INTEGER NOT NULL,
            student_id INTEGER,
            charge_type TEXT NOT NULL DEFAULT 'Tuition',
            description TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            due_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Open',
            reference TEXT NOT NULL DEFAULT '',
            created_by INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            voided_at TIMESTAMP,
            voided_by INTEGER,
            void_reason TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(family_id) REFERENCES families(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE SET NULL,
            FOREIGN KEY(created_by) REFERENCES admin_users(id) ON DELETE SET NULL,
            FOREIGN KEY(voided_by) REFERENCES admin_users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS billing_payments (
            id {id_column},
            family_id INTEGER NOT NULL,
            amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'Cash',
            payment_date TEXT NOT NULL,
            reference TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Posted',
            received_by INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            voided_at TIMESTAMP,
            voided_by INTEGER,
            void_reason TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(family_id) REFERENCES families(id) ON DELETE CASCADE,
            FOREIGN KEY(received_by) REFERENCES admin_users(id) ON DELETE SET NULL,
            FOREIGN KEY(voided_by) REFERENCES admin_users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS workflow_events (
            id {id_column},
            event_type TEXT NOT NULL,
            source_module TEXT NOT NULL DEFAULT '',
            source_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT 'info',
            created_by INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(created_by) REFERENCES admin_users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS workflow_rules (
            id {id_column},
            name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            action_type TEXT NOT NULL DEFAULT 'dashboard_notification',
            title_template TEXT NOT NULL,
            message_template TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT 'info',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS workflow_tasks (
            id {id_column},
            rule_id INTEGER,
            event_id INTEGER,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            title TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '',
            scheduled_for TIMESTAMP,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY(rule_id) REFERENCES workflow_rules(id) ON DELETE SET NULL,
            FOREIGN KEY(event_id) REFERENCES workflow_events(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS notifications (
            id {id_column},
            admin_user_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT 'info',
            source_module TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            read_at TIMESTAMP,
            dismissed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(admin_user_id) REFERENCES admin_users(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS recital_productions (
            id {id_column},
            name TEXT NOT NULL,
            season TEXT NOT NULL DEFAULT '',
            venue TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Planning',
            description TEXT NOT NULL DEFAULT '',
            ticket_status TEXT NOT NULL DEFAULT 'Not On Sale',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS recital_shows (
            id {id_column},
            production_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            show_date TEXT NOT NULL DEFAULT '',
            start_time TEXT NOT NULL DEFAULT '',
            end_time TEXT NOT NULL DEFAULT '',
            doors_open_time TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Scheduled',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(production_id) REFERENCES recital_productions(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS recital_performances (
            id {id_column},
            show_id INTEGER NOT NULL,
            class_id INTEGER,
            title TEXT NOT NULL,
            performance_order INTEGER NOT NULL DEFAULT 0,
            performance_type TEXT NOT NULL DEFAULT 'Dance',
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            music_title TEXT NOT NULL DEFAULT '',
            music_url TEXT NOT NULL DEFAULT '',
            music_status TEXT NOT NULL DEFAULT 'Missing',
            entrance_notes TEXT NOT NULL DEFAULT '',
            exit_notes TEXT NOT NULL DEFAULT '',
            costume_notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Planning',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(show_id) REFERENCES recital_shows(id) ON DELETE CASCADE,
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS recital_rehearsals (
            id {id_column},
            production_id INTEGER NOT NULL,
            show_id INTEGER,
            title TEXT NOT NULL,
            rehearsal_date TEXT NOT NULL DEFAULT '',
            start_time TEXT NOT NULL DEFAULT '',
            end_time TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Scheduled',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(production_id) REFERENCES recital_productions(id) ON DELETE CASCADE,
            FOREIGN KEY(show_id) REFERENCES recital_shows(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS costume_vendors (
            id {id_column}, name TEXT NOT NULL, website TEXT NOT NULL DEFAULT '',
            contact_name TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS costumes (
            id {id_column}, vendor_id INTEGER, name TEXT NOT NULL,
            style_number TEXT NOT NULL DEFAULT '', color TEXT NOT NULL DEFAULT '',
            season TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '',
            unit_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
            charge_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            order_status TEXT NOT NULL DEFAULT 'Planned',
            tracking_number TEXT NOT NULL DEFAULT '', expected_date TEXT NOT NULL DEFAULT '',
            received_date TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(vendor_id) REFERENCES costume_vendors(id) ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS costume_class_assignments (
            id {id_column}, costume_id INTEGER NOT NULL, class_id INTEGER NOT NULL,
            recital_performance_id INTEGER, notes TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(costume_id,class_id),
            FOREIGN KEY(costume_id) REFERENCES costumes(id) ON DELETE CASCADE,
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
            FOREIGN KEY(recital_performance_id) REFERENCES recital_performances(id) ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS student_costume_assignments (
            id {id_column}, costume_id INTEGER NOT NULL, class_id INTEGER,
            student_id INTEGER NOT NULL, family_id INTEGER,
            costume_size TEXT NOT NULL DEFAULT '', tights_size TEXT NOT NULL DEFAULT '',
            shoe_size TEXT NOT NULL DEFAULT '', accessories TEXT NOT NULL DEFAULT '',
            assignment_status TEXT NOT NULL DEFAULT 'Assigned',
            alteration_status TEXT NOT NULL DEFAULT 'Not Needed',
            pickup_status TEXT NOT NULL DEFAULT 'Not Ready',
            billing_charge_id INTEGER, notes TEXT NOT NULL DEFAULT '',
            assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(costume_id,student_id),
            FOREIGN KEY(costume_id) REFERENCES costumes(id) ON DELETE CASCADE,
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE SET NULL,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY(family_id) REFERENCES families(id) ON DELETE SET NULL,
            FOREIGN KEY(billing_charge_id) REFERENCES billing_charges(id) ON DELETE SET NULL
        )
        """
    )

    # Upgrade older customer tables created by earlier CRM versions.
    if connection.backend == "postgresql":
        costume_tables = {
            "costume_vendors": [("name","TEXT NOT NULL DEFAULT ''"),("website","TEXT NOT NULL DEFAULT ''"),("contact_name","TEXT NOT NULL DEFAULT ''"),("email","TEXT NOT NULL DEFAULT ''"),("phone","TEXT NOT NULL DEFAULT ''"),("notes","TEXT NOT NULL DEFAULT ''"),("active","INTEGER NOT NULL DEFAULT 1"),("created_at","TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),("updated_at","TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP")],
            "costumes": [("vendor_id","INTEGER"),("name","TEXT NOT NULL DEFAULT ''"),("style_number","TEXT NOT NULL DEFAULT ''"),("color","TEXT NOT NULL DEFAULT ''"),("season","TEXT NOT NULL DEFAULT ''"),("category","TEXT NOT NULL DEFAULT ''"),("unit_cost","DOUBLE PRECISION NOT NULL DEFAULT 0"),("charge_amount","DOUBLE PRECISION NOT NULL DEFAULT 0"),("order_status","TEXT NOT NULL DEFAULT 'Planned'"),("tracking_number","TEXT NOT NULL DEFAULT ''"),("expected_date","TEXT NOT NULL DEFAULT ''"),("received_date","TEXT NOT NULL DEFAULT ''"),("notes","TEXT NOT NULL DEFAULT ''"),("active","INTEGER NOT NULL DEFAULT 1"),("created_at","TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),("updated_at","TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP")],
            "costume_class_assignments": [("costume_id","INTEGER"),("class_id","INTEGER"),("recital_performance_id","INTEGER"),("notes","TEXT NOT NULL DEFAULT ''"),("created_at","TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP")],
            "student_costume_assignments": [("costume_id","INTEGER"),("class_id","INTEGER"),("student_id","INTEGER"),("family_id","INTEGER"),("costume_size","TEXT NOT NULL DEFAULT ''"),("tights_size","TEXT NOT NULL DEFAULT ''"),("shoe_size","TEXT NOT NULL DEFAULT ''"),("accessories","TEXT NOT NULL DEFAULT ''"),("assignment_status","TEXT NOT NULL DEFAULT 'Assigned'"),("alteration_status","TEXT NOT NULL DEFAULT 'Not Needed'"),("pickup_status","TEXT NOT NULL DEFAULT 'Not Ready'"),("billing_charge_id","INTEGER"),("notes","TEXT NOT NULL DEFAULT ''"),("assigned_at","TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),("updated_at","TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP")],
        }
        for table_name, columns in costume_tables.items():
            for column_name, column_definition in columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_definition}")

        recital_production_columns = [
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("season", "TEXT NOT NULL DEFAULT ''"),
            ("venue", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Planning'"),
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("ticket_status", "TEXT NOT NULL DEFAULT 'Not On Sale'"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in recital_production_columns:
            cursor.execute(
                f"ALTER TABLE recital_productions ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        recital_show_columns = [
            ("production_id", "INTEGER"),
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("show_date", "TEXT NOT NULL DEFAULT ''"),
            ("start_time", "TEXT NOT NULL DEFAULT ''"),
            ("end_time", "TEXT NOT NULL DEFAULT ''"),
            ("doors_open_time", "TEXT NOT NULL DEFAULT ''"),
            ("notes", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Scheduled'"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in recital_show_columns:
            cursor.execute(
                f"ALTER TABLE recital_shows ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        recital_performance_columns = [
            ("show_id", "INTEGER"),
            ("class_id", "INTEGER"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("performance_order", "INTEGER NOT NULL DEFAULT 0"),
            ("performance_type", "TEXT NOT NULL DEFAULT 'Dance'"),
            ("duration_seconds", "INTEGER NOT NULL DEFAULT 0"),
            ("music_title", "TEXT NOT NULL DEFAULT ''"),
            ("music_url", "TEXT NOT NULL DEFAULT ''"),
            ("music_status", "TEXT NOT NULL DEFAULT 'Missing'"),
            ("entrance_notes", "TEXT NOT NULL DEFAULT ''"),
            ("exit_notes", "TEXT NOT NULL DEFAULT ''"),
            ("costume_notes", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Planning'"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in recital_performance_columns:
            cursor.execute(
                f"ALTER TABLE recital_performances ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        recital_rehearsal_columns = [
            ("production_id", "INTEGER"),
            ("show_id", "INTEGER"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("rehearsal_date", "TEXT NOT NULL DEFAULT ''"),
            ("start_time", "TEXT NOT NULL DEFAULT ''"),
            ("end_time", "TEXT NOT NULL DEFAULT ''"),
            ("location", "TEXT NOT NULL DEFAULT ''"),
            ("notes", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Scheduled'"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in recital_rehearsal_columns:
            cursor.execute(
                f"ALTER TABLE recital_rehearsals ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        workflow_event_columns = [
            ("event_type", "TEXT NOT NULL DEFAULT ''"),
            ("source_module", "TEXT NOT NULL DEFAULT ''"),
            ("source_id", "TEXT NOT NULL DEFAULT ''"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("details", "TEXT NOT NULL DEFAULT ''"),
            ("severity", "TEXT NOT NULL DEFAULT 'info'"),
            ("created_by", "INTEGER"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in workflow_event_columns:
            cursor.execute(
                f"ALTER TABLE workflow_events ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        workflow_rule_columns = [
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("event_type", "TEXT NOT NULL DEFAULT ''"),
            ("action_type", "TEXT NOT NULL DEFAULT 'dashboard_notification'"),
            ("title_template", "TEXT NOT NULL DEFAULT ''"),
            ("message_template", "TEXT NOT NULL DEFAULT ''"),
            ("severity", "TEXT NOT NULL DEFAULT 'info'"),
            ("active", "INTEGER NOT NULL DEFAULT 1"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in workflow_rule_columns:
            cursor.execute(
                f"ALTER TABLE workflow_rules ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        workflow_task_columns = [
            ("rule_id", "INTEGER"),
            ("event_id", "INTEGER"),
            ("task_type", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Pending'"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("payload", "TEXT NOT NULL DEFAULT ''"),
            ("scheduled_for", "TIMESTAMP"),
            ("attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("last_error", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("completed_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in workflow_task_columns:
            cursor.execute(
                f"ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        notification_columns = [
            ("admin_user_id", "INTEGER"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("message", "TEXT NOT NULL DEFAULT ''"),
            ("severity", "TEXT NOT NULL DEFAULT 'info'"),
            ("source_module", "TEXT NOT NULL DEFAULT ''"),
            ("source_url", "TEXT NOT NULL DEFAULT ''"),
            ("read_at", "TIMESTAMP"),
            ("dismissed_at", "TIMESTAMP"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in notification_columns:
            cursor.execute(
                f"ALTER TABLE notifications ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        billing_charge_columns = [
            ("family_id", "INTEGER"),
            ("student_id", "INTEGER"),
            ("charge_type", "TEXT NOT NULL DEFAULT 'Tuition'"),
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("amount", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
            ("due_date", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Open'"),
            ("reference", "TEXT NOT NULL DEFAULT ''"),
            ("created_by", "INTEGER"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("voided_at", "TIMESTAMP"),
            ("voided_by", "INTEGER"),
            ("void_reason", "TEXT NOT NULL DEFAULT ''"),
        ]
        for column_name, column_definition in billing_charge_columns:
            cursor.execute(
                f"ALTER TABLE billing_charges ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        billing_payment_columns = [
            ("family_id", "INTEGER"),
            ("amount", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
            ("payment_method", "TEXT NOT NULL DEFAULT 'Cash'"),
            ("payment_date", "TEXT NOT NULL DEFAULT ''"),
            ("reference", "TEXT NOT NULL DEFAULT ''"),
            ("note", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Posted'"),
            ("received_by", "INTEGER"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("voided_at", "TIMESTAMP"),
            ("voided_by", "INTEGER"),
            ("void_reason", "TEXT NOT NULL DEFAULT ''"),
        ]
        for column_name, column_definition in billing_payment_columns:
            cursor.execute(
                f"ALTER TABLE billing_payments ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        class_session_columns = [
            ("class_id", "INTEGER"),
            ("session_date", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Scheduled'"),
            ("topic", "TEXT NOT NULL DEFAULT ''"),
            ("teacher_notes", "TEXT NOT NULL DEFAULT ''"),
            ("created_by", "INTEGER"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in class_session_columns:
            cursor.execute(
                f"ALTER TABLE class_sessions ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        attendance_columns = [
            ("session_id", "INTEGER"),
            ("student_id", "INTEGER"),
            ("status", "TEXT NOT NULL DEFAULT 'Unmarked'"),
            ("minutes_late", "INTEGER NOT NULL DEFAULT 0"),
            ("note", "TEXT NOT NULL DEFAULT ''"),
            ("marked_by", "INTEGER"),
            ("marked_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in attendance_columns:
            cursor.execute(
                f"ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        teacher_columns = [
            ("admin_user_id", "INTEGER"),
            ("first_name", "TEXT NOT NULL DEFAULT ''"),
            ("last_name", "TEXT NOT NULL DEFAULT ''"),
            ("email", "TEXT NOT NULL DEFAULT ''"),
            ("phone", "TEXT NOT NULL DEFAULT ''"),
            ("active", "INTEGER NOT NULL DEFAULT 1"),
            ("bio", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in teacher_columns:
            cursor.execute(
                f"ALTER TABLE teachers ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        class_columns = [
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("category", "TEXT NOT NULL DEFAULT ''"),
            ("level", "TEXT NOT NULL DEFAULT ''"),
            ("teacher_id", "INTEGER"),
            ("room", "TEXT NOT NULL DEFAULT ''"),
            ("day_of_week", "TEXT NOT NULL DEFAULT ''"),
            ("start_time", "TEXT NOT NULL DEFAULT ''"),
            ("end_time", "TEXT NOT NULL DEFAULT ''"),
            ("capacity", "INTEGER NOT NULL DEFAULT 0"),
            ("active", "INTEGER NOT NULL DEFAULT 1"),
            ("season", "TEXT NOT NULL DEFAULT ''"),
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in class_columns:
            cursor.execute(
                f"ALTER TABLE classes ADD COLUMN IF NOT EXISTS {column_name} {column_definition}"
            )

        admin_user_columns = [
            ("display_name", "TEXT NOT NULL DEFAULT 'Administrator'"),
            ("email", "TEXT NOT NULL DEFAULT ''"),
            ("password_hash", "TEXT NOT NULL DEFAULT ''"),
            ("role", "TEXT NOT NULL DEFAULT 'office_staff'"),
            ("active", "INTEGER NOT NULL DEFAULT 1"),
            ("last_login_at", "TIMESTAMP"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in admin_user_columns:
            cursor.execute(f"ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS {column_name} {column_definition}")

        student_columns = [
            ("family_id", "INTEGER"),
            ("preferred_name", "TEXT NOT NULL DEFAULT ''"),
            ("birth_date", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Active'"),
            ("competition_team", "INTEGER NOT NULL DEFAULT 0"),
            ("photo_url", "TEXT NOT NULL DEFAULT ''"),
            ("email", "TEXT NOT NULL DEFAULT ''"),
            ("phone", "TEXT NOT NULL DEFAULT ''"),
            ("school", "TEXT NOT NULL DEFAULT ''"),
            ("grade", "TEXT NOT NULL DEFAULT ''"),
            ("leotard_size", "TEXT NOT NULL DEFAULT ''"),
            ("costume_size", "TEXT NOT NULL DEFAULT ''"),
            ("shoe_size", "TEXT NOT NULL DEFAULT ''"),
            ("warmup_size", "TEXT NOT NULL DEFAULT ''"),
            ("medical_notes", "TEXT NOT NULL DEFAULT ''"),
            ("general_notes", "TEXT NOT NULL DEFAULT ''"),
            ("tags", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in student_columns:
            cursor.execute(
                f"""
                ALTER TABLE students
                ADD COLUMN IF NOT EXISTS {column_name} {column_definition}
                """
            )

        customer_columns = [
            ("family_id", "INTEGER"),
            ("phone", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Active'"),
            ("tags", "TEXT NOT NULL DEFAULT ''"),
            ("notes", "TEXT NOT NULL DEFAULT ''"),
            ("order_count", "INTEGER NOT NULL DEFAULT 0"),
            ("lifetime_value", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
            ("last_order_at", "TIMESTAMP"),
            ("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ]
        for column_name, column_definition in customer_columns:
            cursor.execute(
                f"""
                ALTER TABLE customers
                ADD COLUMN IF NOT EXISTS {column_name} {column_definition}
                """
            )
    else:
        existing_customer_columns = {
            row["name"]
            for row in cursor.execute(
                "PRAGMA table_info(customers)"
            ).fetchall()
        }
        sqlite_costume_tables = {
            "costume_vendors": [("name","TEXT NOT NULL DEFAULT ''"),("website","TEXT NOT NULL DEFAULT ''"),("contact_name","TEXT NOT NULL DEFAULT ''"),("email","TEXT NOT NULL DEFAULT ''"),("phone","TEXT NOT NULL DEFAULT ''"),("notes","TEXT NOT NULL DEFAULT ''"),("active","INTEGER NOT NULL DEFAULT 1"),("created_at","TIMESTAMP"),("updated_at","TIMESTAMP")],
            "costumes": [("vendor_id","INTEGER"),("name","TEXT NOT NULL DEFAULT ''"),("style_number","TEXT NOT NULL DEFAULT ''"),("color","TEXT NOT NULL DEFAULT ''"),("season","TEXT NOT NULL DEFAULT ''"),("category","TEXT NOT NULL DEFAULT ''"),("unit_cost","REAL NOT NULL DEFAULT 0"),("charge_amount","REAL NOT NULL DEFAULT 0"),("order_status","TEXT NOT NULL DEFAULT 'Planned'"),("tracking_number","TEXT NOT NULL DEFAULT ''"),("expected_date","TEXT NOT NULL DEFAULT ''"),("received_date","TEXT NOT NULL DEFAULT ''"),("notes","TEXT NOT NULL DEFAULT ''"),("active","INTEGER NOT NULL DEFAULT 1"),("created_at","TIMESTAMP"),("updated_at","TIMESTAMP")],
            "costume_class_assignments": [("costume_id","INTEGER"),("class_id","INTEGER"),("recital_performance_id","INTEGER"),("notes","TEXT NOT NULL DEFAULT ''"),("created_at","TIMESTAMP")],
            "student_costume_assignments": [("costume_id","INTEGER"),("class_id","INTEGER"),("student_id","INTEGER"),("family_id","INTEGER"),("costume_size","TEXT NOT NULL DEFAULT ''"),("tights_size","TEXT NOT NULL DEFAULT ''"),("shoe_size","TEXT NOT NULL DEFAULT ''"),("accessories","TEXT NOT NULL DEFAULT ''"),("assignment_status","TEXT NOT NULL DEFAULT 'Assigned'"),("alteration_status","TEXT NOT NULL DEFAULT 'Not Needed'"),("pickup_status","TEXT NOT NULL DEFAULT 'Not Ready'"),("billing_charge_id","INTEGER"),("notes","TEXT NOT NULL DEFAULT ''"),("assigned_at","TIMESTAMP"),("updated_at","TIMESTAMP")],
        }
        for table_name, columns in sqlite_costume_tables.items():
            existing = {row["name"] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()}
            for column_name, column_definition in columns:
                if column_name not in existing:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

        existing_recital_production_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(recital_productions)").fetchall()
        }
        sqlite_recital_production_columns = [
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("season", "TEXT NOT NULL DEFAULT ''"),
            ("venue", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Planning'"),
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("ticket_status", "TEXT NOT NULL DEFAULT 'Not On Sale'"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_recital_production_columns:
            if column_name not in existing_recital_production_columns:
                cursor.execute(f"ALTER TABLE recital_productions ADD COLUMN {column_name} {column_definition}")

        existing_recital_show_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(recital_shows)").fetchall()
        }
        sqlite_recital_show_columns = [
            ("production_id", "INTEGER"),
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("show_date", "TEXT NOT NULL DEFAULT ''"),
            ("start_time", "TEXT NOT NULL DEFAULT ''"),
            ("end_time", "TEXT NOT NULL DEFAULT ''"),
            ("doors_open_time", "TEXT NOT NULL DEFAULT ''"),
            ("notes", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Scheduled'"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_recital_show_columns:
            if column_name not in existing_recital_show_columns:
                cursor.execute(f"ALTER TABLE recital_shows ADD COLUMN {column_name} {column_definition}")

        existing_recital_performance_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(recital_performances)").fetchall()
        }
        sqlite_recital_performance_columns = [
            ("show_id", "INTEGER"),
            ("class_id", "INTEGER"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("performance_order", "INTEGER NOT NULL DEFAULT 0"),
            ("performance_type", "TEXT NOT NULL DEFAULT 'Dance'"),
            ("duration_seconds", "INTEGER NOT NULL DEFAULT 0"),
            ("music_title", "TEXT NOT NULL DEFAULT ''"),
            ("music_url", "TEXT NOT NULL DEFAULT ''"),
            ("music_status", "TEXT NOT NULL DEFAULT 'Missing'"),
            ("entrance_notes", "TEXT NOT NULL DEFAULT ''"),
            ("exit_notes", "TEXT NOT NULL DEFAULT ''"),
            ("costume_notes", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Planning'"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_recital_performance_columns:
            if column_name not in existing_recital_performance_columns:
                cursor.execute(f"ALTER TABLE recital_performances ADD COLUMN {column_name} {column_definition}")

        existing_recital_rehearsal_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(recital_rehearsals)").fetchall()
        }
        sqlite_recital_rehearsal_columns = [
            ("production_id", "INTEGER"),
            ("show_id", "INTEGER"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("rehearsal_date", "TEXT NOT NULL DEFAULT ''"),
            ("start_time", "TEXT NOT NULL DEFAULT ''"),
            ("end_time", "TEXT NOT NULL DEFAULT ''"),
            ("location", "TEXT NOT NULL DEFAULT ''"),
            ("notes", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Scheduled'"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_recital_rehearsal_columns:
            if column_name not in existing_recital_rehearsal_columns:
                cursor.execute(f"ALTER TABLE recital_rehearsals ADD COLUMN {column_name} {column_definition}")

        existing_workflow_event_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(workflow_events)").fetchall()
        }
        sqlite_workflow_event_columns = [
            ("event_type", "TEXT NOT NULL DEFAULT ''"),
            ("source_module", "TEXT NOT NULL DEFAULT ''"),
            ("source_id", "TEXT NOT NULL DEFAULT ''"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("details", "TEXT NOT NULL DEFAULT ''"),
            ("severity", "TEXT NOT NULL DEFAULT 'info'"),
            ("created_by", "INTEGER"),
            ("created_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_workflow_event_columns:
            if column_name not in existing_workflow_event_columns:
                cursor.execute(f"ALTER TABLE workflow_events ADD COLUMN {column_name} {column_definition}")

        existing_workflow_rule_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(workflow_rules)").fetchall()
        }
        sqlite_workflow_rule_columns = [
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("event_type", "TEXT NOT NULL DEFAULT ''"),
            ("action_type", "TEXT NOT NULL DEFAULT 'dashboard_notification'"),
            ("title_template", "TEXT NOT NULL DEFAULT ''"),
            ("message_template", "TEXT NOT NULL DEFAULT ''"),
            ("severity", "TEXT NOT NULL DEFAULT 'info'"),
            ("active", "INTEGER NOT NULL DEFAULT 1"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_workflow_rule_columns:
            if column_name not in existing_workflow_rule_columns:
                cursor.execute(f"ALTER TABLE workflow_rules ADD COLUMN {column_name} {column_definition}")

        existing_workflow_task_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(workflow_tasks)").fetchall()
        }
        sqlite_workflow_task_columns = [
            ("rule_id", "INTEGER"),
            ("event_id", "INTEGER"),
            ("task_type", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Pending'"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("payload", "TEXT NOT NULL DEFAULT ''"),
            ("scheduled_for", "TIMESTAMP"),
            ("attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("last_error", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "TIMESTAMP"),
            ("completed_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_workflow_task_columns:
            if column_name not in existing_workflow_task_columns:
                cursor.execute(f"ALTER TABLE workflow_tasks ADD COLUMN {column_name} {column_definition}")

        existing_notification_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(notifications)").fetchall()
        }
        sqlite_notification_columns = [
            ("admin_user_id", "INTEGER"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("message", "TEXT NOT NULL DEFAULT ''"),
            ("severity", "TEXT NOT NULL DEFAULT 'info'"),
            ("source_module", "TEXT NOT NULL DEFAULT ''"),
            ("source_url", "TEXT NOT NULL DEFAULT ''"),
            ("read_at", "TIMESTAMP"),
            ("dismissed_at", "TIMESTAMP"),
            ("created_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_notification_columns:
            if column_name not in existing_notification_columns:
                cursor.execute(f"ALTER TABLE notifications ADD COLUMN {column_name} {column_definition}")

        existing_billing_charge_columns = {
            row["name"]
            for row in cursor.execute(
                "PRAGMA table_info(billing_charges)"
            ).fetchall()
        }
        sqlite_billing_charge_columns = [
            ("family_id", "INTEGER"),
            ("student_id", "INTEGER"),
            ("charge_type", "TEXT NOT NULL DEFAULT 'Tuition'"),
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("amount", "REAL NOT NULL DEFAULT 0"),
            ("due_date", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Open'"),
            ("reference", "TEXT NOT NULL DEFAULT ''"),
            ("created_by", "INTEGER"),
            ("created_at", "TIMESTAMP"),
            ("voided_at", "TIMESTAMP"),
            ("voided_by", "INTEGER"),
            ("void_reason", "TEXT NOT NULL DEFAULT ''"),
        ]
        for column_name, column_definition in sqlite_billing_charge_columns:
            if column_name not in existing_billing_charge_columns:
                cursor.execute(
                    f"ALTER TABLE billing_charges ADD COLUMN {column_name} {column_definition}"
                )

        existing_billing_payment_columns = {
            row["name"]
            for row in cursor.execute(
                "PRAGMA table_info(billing_payments)"
            ).fetchall()
        }
        sqlite_billing_payment_columns = [
            ("family_id", "INTEGER"),
            ("amount", "REAL NOT NULL DEFAULT 0"),
            ("payment_method", "TEXT NOT NULL DEFAULT 'Cash'"),
            ("payment_date", "TEXT NOT NULL DEFAULT ''"),
            ("reference", "TEXT NOT NULL DEFAULT ''"),
            ("note", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Posted'"),
            ("received_by", "INTEGER"),
            ("created_at", "TIMESTAMP"),
            ("voided_at", "TIMESTAMP"),
            ("voided_by", "INTEGER"),
            ("void_reason", "TEXT NOT NULL DEFAULT ''"),
        ]
        for column_name, column_definition in sqlite_billing_payment_columns:
            if column_name not in existing_billing_payment_columns:
                cursor.execute(
                    f"ALTER TABLE billing_payments ADD COLUMN {column_name} {column_definition}"
                )

        existing_class_session_columns = {
            row["name"]
            for row in cursor.execute(
                "PRAGMA table_info(class_sessions)"
            ).fetchall()
        }
        sqlite_class_session_columns = [
            ("class_id", "INTEGER"),
            ("session_date", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Scheduled'"),
            ("topic", "TEXT NOT NULL DEFAULT ''"),
            ("teacher_notes", "TEXT NOT NULL DEFAULT ''"),
            ("created_by", "INTEGER"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_class_session_columns:
            if column_name not in existing_class_session_columns:
                cursor.execute(
                    f"ALTER TABLE class_sessions ADD COLUMN {column_name} {column_definition}"
                )

        existing_attendance_columns = {
            row["name"]
            for row in cursor.execute(
                "PRAGMA table_info(attendance_records)"
            ).fetchall()
        }
        sqlite_attendance_columns = [
            ("session_id", "INTEGER"),
            ("student_id", "INTEGER"),
            ("status", "TEXT NOT NULL DEFAULT 'Unmarked'"),
            ("minutes_late", "INTEGER NOT NULL DEFAULT 0"),
            ("note", "TEXT NOT NULL DEFAULT ''"),
            ("marked_by", "INTEGER"),
            ("marked_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_attendance_columns:
            if column_name not in existing_attendance_columns:
                cursor.execute(
                    f"ALTER TABLE attendance_records ADD COLUMN {column_name} {column_definition}"
                )

        existing_teacher_columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(teachers)").fetchall()
        }
        sqlite_teacher_columns = [
            ("admin_user_id", "INTEGER"),
            ("first_name", "TEXT NOT NULL DEFAULT ''"),
            ("last_name", "TEXT NOT NULL DEFAULT ''"),
            ("email", "TEXT NOT NULL DEFAULT ''"),
            ("phone", "TEXT NOT NULL DEFAULT ''"),
            ("active", "INTEGER NOT NULL DEFAULT 1"),
            ("bio", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_teacher_columns:
            if column_name not in existing_teacher_columns:
                cursor.execute(
                    f"ALTER TABLE teachers ADD COLUMN {column_name} {column_definition}"
                )

        existing_class_columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(classes)").fetchall()
        }
        sqlite_class_columns = [
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("category", "TEXT NOT NULL DEFAULT ''"),
            ("level", "TEXT NOT NULL DEFAULT ''"),
            ("teacher_id", "INTEGER"),
            ("room", "TEXT NOT NULL DEFAULT ''"),
            ("day_of_week", "TEXT NOT NULL DEFAULT ''"),
            ("start_time", "TEXT NOT NULL DEFAULT ''"),
            ("end_time", "TEXT NOT NULL DEFAULT ''"),
            ("capacity", "INTEGER NOT NULL DEFAULT 0"),
            ("active", "INTEGER NOT NULL DEFAULT 1"),
            ("season", "TEXT NOT NULL DEFAULT ''"),
            ("description", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_class_columns:
            if column_name not in existing_class_columns:
                cursor.execute(
                    f"ALTER TABLE classes ADD COLUMN {column_name} {column_definition}"
                )

        existing_admin_user_columns = {
            row["name"] for row in cursor.execute("PRAGMA table_info(admin_users)").fetchall()
        }
        sqlite_admin_user_columns = [
            ("display_name", "TEXT NOT NULL DEFAULT 'Administrator'"),
            ("email", "TEXT NOT NULL DEFAULT ''"),
            ("password_hash", "TEXT NOT NULL DEFAULT ''"),
            ("role", "TEXT NOT NULL DEFAULT 'office_staff'"),
            ("active", "INTEGER NOT NULL DEFAULT 1"),
            ("last_login_at", "TIMESTAMP"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_admin_user_columns:
            if column_name not in existing_admin_user_columns:
                cursor.execute(f"ALTER TABLE admin_users ADD COLUMN {column_name} {column_definition}")

        existing_student_columns = {
            row["name"]
            for row in cursor.execute(
                "PRAGMA table_info(students)"
            ).fetchall()
        }
        sqlite_student_columns = [
            ("family_id", "INTEGER"),
            ("preferred_name", "TEXT NOT NULL DEFAULT ''"),
            ("birth_date", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Active'"),
            ("competition_team", "INTEGER NOT NULL DEFAULT 0"),
            ("photo_url", "TEXT NOT NULL DEFAULT ''"),
            ("email", "TEXT NOT NULL DEFAULT ''"),
            ("phone", "TEXT NOT NULL DEFAULT ''"),
            ("school", "TEXT NOT NULL DEFAULT ''"),
            ("grade", "TEXT NOT NULL DEFAULT ''"),
            ("leotard_size", "TEXT NOT NULL DEFAULT ''"),
            ("costume_size", "TEXT NOT NULL DEFAULT ''"),
            ("shoe_size", "TEXT NOT NULL DEFAULT ''"),
            ("warmup_size", "TEXT NOT NULL DEFAULT ''"),
            ("medical_notes", "TEXT NOT NULL DEFAULT ''"),
            ("general_notes", "TEXT NOT NULL DEFAULT ''"),
            ("tags", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_student_columns:
            if column_name not in existing_student_columns:
                cursor.execute(
                    f"""
                    ALTER TABLE students
                    ADD COLUMN {column_name} {column_definition}
                    """
                )

        sqlite_customer_columns = [
            ("family_id", "INTEGER"),
            ("phone", "TEXT NOT NULL DEFAULT ''"),
            ("status", "TEXT NOT NULL DEFAULT 'Active'"),
            ("tags", "TEXT NOT NULL DEFAULT ''"),
            ("notes", "TEXT NOT NULL DEFAULT ''"),
            ("order_count", "INTEGER NOT NULL DEFAULT 0"),
            ("lifetime_value", "REAL NOT NULL DEFAULT 0"),
            ("last_order_at", "TIMESTAMP"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_definition in sqlite_customer_columns:
            if column_name not in existing_customer_columns:
                cursor.execute(
                    f"""
                    ALTER TABLE customers
                    ADD COLUMN {column_name} {column_definition}
                    """
                )

    # Early PostgreSQL versions may have created these date fields as TEXT.
    # Convert them to proper TIMESTAMP columns before dashboard queries run.
    if connection.backend == "postgresql":
        for table_name in ("orders", "activity_log", "announcements"):
            column_type = cursor.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = ?
                  AND column_name = 'created_at'
                """,
                (table_name,),
            ).fetchone()

            if column_type and column_type["data_type"] in (
                "text",
                "character varying",
            ):
                cursor.execute(
                    f"""
                    ALTER TABLE {table_name}
                    ALTER COLUMN created_at TYPE TIMESTAMP
                    USING CASE
                        WHEN created_at IS NULL
                          OR BTRIM(created_at::text) = ''
                        THEN CURRENT_TIMESTAMP
                        ELSE created_at::timestamp
                    END
                    """
                )

    if cursor.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"] == 0:
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
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO NOTHING
            """,
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
            """
            INSERT INTO homepage_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (key, value),
        )

    connection.commit()
    connection.close()
