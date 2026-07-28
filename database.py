from __future__ import annotations

import re
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from config import DATABASE_URL


def _translate_sql(sql: str) -> str:
    sql = re.sub(r"\s+COLLATE\s+NOCASE", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bLIKE\b", "ILIKE", sql, flags=re.IGNORECASE)
    sql = sql.replace("MAX(0,stock-?)", "GREATEST(0,stock-?)")
    return sql.replace("?", "%s")


class Cursor:
    def __init__(self, cursor: psycopg.Cursor):
        self._cursor = cursor

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> "Cursor":
        self._cursor.execute(_translate_sql(sql), tuple(params or ()))
        return self

    def executemany(self, sql: str, params_seq: Iterable[Iterable[Any]]) -> "Cursor":
        self._cursor.executemany(_translate_sql(sql), params_seq)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class Connection:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def cursor(self) -> Cursor:
        return Cursor(self._connection.cursor())

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> Cursor:
        return self.cursor().execute(sql, params)

    def executemany(self, sql: str, params_seq: Iterable[Iterable[Any]]) -> Cursor:
        return self.cursor().executemany(sql, params_seq)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def get_db() -> Connection:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured. Add the Railway PostgreSQL reference variable to the web service.")
    return Connection(psycopg.connect(DATABASE_URL, row_factory=dict_row))


def init_db() -> None:
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext('stage_starz_database_init'))")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', price DOUBLE PRECISION NOT NULL DEFAULT 0, sale_price DOUBLE PRECISION,
            fulfillment_fee DOUBLE PRECISION NOT NULL DEFAULT 0, stock INTEGER NOT NULL DEFAULT 0,
            sizes TEXT NOT NULL DEFAULT 'One Size', colors TEXT NOT NULL DEFAULT 'Default',
            show_color INTEGER NOT NULL DEFAULT 1, allow_name INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1, image_url TEXT NOT NULL DEFAULT '',
            emoji TEXT NOT NULL DEFAULT '⭐', image_data BYTEA, image_mime TEXT NOT NULL DEFAULT ''
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id SERIAL PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            image_data BYTEA NOT NULL, image_mime TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0, is_primary INTEGER NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_images_product ON product_images(product_id, sort_order, id)")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL DEFAULT '', address1 TEXT NOT NULL DEFAULT '', address2 TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '', state TEXT NOT NULL DEFAULT '', postal_code TEXT NOT NULL DEFAULT '',
            customer_since TEXT NOT NULL, last_order_date TEXT NOT NULL,
            total_orders INTEGER NOT NULL DEFAULT 0, lifetime_spending DOUBLE PRECISION NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Active', notes TEXT NOT NULL DEFAULT ''
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(lower(name))")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_last_order ON customers(last_order_date DESC)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY, order_number TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
            customer_name TEXT NOT NULL, customer_email TEXT NOT NULL, customer_phone TEXT NOT NULL DEFAULT '',
            fulfillment_method TEXT NOT NULL DEFAULT 'shipping', address1 TEXT NOT NULL DEFAULT '', address2 TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '', state TEXT NOT NULL DEFAULT '', postal_code TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
            payment_method TEXT NOT NULL DEFAULT 'Venmo', payment_status TEXT NOT NULL DEFAULT 'Unpaid', status TEXT NOT NULL DEFAULT 'New',
            subtotal DOUBLE PRECISION NOT NULL DEFAULT 0, name_fees DOUBLE PRECISION NOT NULL DEFAULT 0,
            fulfillment_fees DOUBLE PRECISION NOT NULL DEFAULT 0, shipping DOUBLE PRECISION NOT NULL DEFAULT 0,
            tax DOUBLE PRECISION NOT NULL DEFAULT 0, total DOUBLE PRECISION NOT NULL DEFAULT 0,
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id INTEGER, product_name TEXT NOT NULL, size TEXT NOT NULL DEFAULT '', color TEXT NOT NULL DEFAULT '',
            requested_name TEXT NOT NULL DEFAULT '', quantity INTEGER NOT NULL DEFAULT 1,
            unit_price DOUBLE PRECISION NOT NULL DEFAULT 0, name_fee DOUBLE PRECISION NOT NULL DEFAULT 0,
            fulfillment_fee DOUBLE PRECISION NOT NULL DEFAULT 0, line_total DOUBLE PRECISION NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id, created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)")

    cursor.execute("SELECT COUNT(*) AS count FROM products")
    if cursor.fetchone()["count"] == 0:
        starter_products = [
            ("Stage Starz Team Jersey", "Apparel", "Moisture-wicking team jersey made for dance, stage, and studio events.", 32.00, 28.00, 5.00, 14, "Youth S,Youth M,Youth L,Adult S,Adult M,Adult L,Adult XL", "Black,Purple,Teal", 1, 1, 1, "", "👕"),
            ("Signature Dance Jacket", "Apparel", "Form-fitting four-way stretch jacket for dancers and team members.", 55.00, None, 5.00, 9, "Youth S,Youth M,Youth L,Adult S,Adult M,Adult L,Adult XL", "Black,Purple", 1, 1, 1, "", "🧥"),
            ("Stage Starz Duffle Bag", "Bags", "Durable dance bag with shoulder strap and room for shoes and apparel.", 38.00, None, 6.00, 6, "One Size", "Black,Purple,Teal", 1, 1, 1, "", "👜"),
        ]
        cursor.executemany("INSERT INTO products (name,category,description,price,sale_price,fulfillment_fee,stock,sizes,colors,show_color,allow_name,active,image_url,emoji) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", starter_products)

    cursor.execute("""
        INSERT INTO product_images (product_id,image_data,image_mime,sort_order,is_primary)
        SELECT p.id,p.image_data,p.image_mime,0,1 FROM products p
        WHERE p.image_data IS NOT NULL AND length(p.image_data)>0
          AND NOT EXISTS (SELECT 1 FROM product_images pi WHERE pi.product_id=p.id)
    """)

    historical = cursor.execute("""
        SELECT lower(trim(customer_email)) AS email_key,
               MAX(customer_name) AS name, MAX(customer_email) AS email, MAX(customer_phone) AS phone,
               MAX(address1) AS address1, MAX(address2) AS address2, MAX(city) AS city,
               MAX(state) AS state, MAX(postal_code) AS postal_code,
               MIN(created_at) AS customer_since, MAX(created_at) AS last_order_date,
               COUNT(*) AS total_orders,
               COALESCE(SUM(CASE WHEN status != 'Cancelled' THEN total ELSE 0 END),0) AS lifetime_spending
        FROM orders WHERE trim(customer_email) != '' GROUP BY lower(trim(customer_email))
    """).fetchall()
    for row in historical:
        cursor.execute("""
            INSERT INTO customers (name,email,phone,address1,address2,city,state,postal_code,customer_since,last_order_date,total_orders,lifetime_spending)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(email) DO UPDATE SET
                name=excluded.name, phone=excluded.phone, address1=excluded.address1, address2=excluded.address2,
                city=excluded.city, state=excluded.state, postal_code=excluded.postal_code,
                customer_since=excluded.customer_since, last_order_date=excluded.last_order_date,
                total_orders=excluded.total_orders, lifetime_spending=excluded.lifetime_spending
        """, (row["name"], row["email"].strip().lower(), row["phone"], row["address1"], row["address2"], row["city"], row["state"], row["postal_code"], row["customer_since"], row["last_order_date"], row["total_orders"], row["lifetime_spending"]))
    cursor.execute("""
        UPDATE orders SET customer_id=(SELECT c.id FROM customers c WHERE lower(trim(c.email))=lower(trim(orders.customer_email)))
        WHERE customer_id IS NULL AND trim(customer_email) != ''
    """)

    defaults = {
        "store_name": "Stardust Ship-it-Shop", "order_email": "stagestarzacademy@gmail.com",
        "venmo_username": "@StageStarzDance", "name_fee": "10.00", "name_max_chars": "20",
        "name_instructions": "Enter the name exactly as you want it printed.", "sales_tax_rate": "0.06",
        "shipping_mode": "per_item", "shipping_rate": "5.00", "free_shipping_threshold": "100.00",
        "allow_customer_shipping": "1", "customer_shipping_fee": "0.00", "low_stock_threshold": "5",
    }
    for key, value in defaults.items():
        cursor.execute("INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO NOTHING", (key, value))

    connection.commit()
    connection.close()
