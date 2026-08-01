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

    # Build or refresh customer records from all non-cancelled orders.
    order_customers = cursor.execute(
        """
        SELECT
            LOWER(TRIM(customer_email)) AS email_key,
            MAX(customer_name) AS customer_name,
            MAX(customer_email) AS customer_email,
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

    for customer in order_customers:
        cursor.execute(
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
    connection.close()
