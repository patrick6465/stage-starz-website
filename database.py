from __future__ import annotations

import sqlite3

from config import DB_PATH


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', price REAL NOT NULL DEFAULT 0, sale_price REAL,
            fulfillment_fee REAL NOT NULL DEFAULT 0, stock INTEGER NOT NULL DEFAULT 0,
            sizes TEXT NOT NULL DEFAULT 'One Size', colors TEXT NOT NULL DEFAULT 'Default',
            show_color INTEGER NOT NULL DEFAULT 1, allow_name INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1, image_url TEXT NOT NULL DEFAULT '',
            emoji TEXT NOT NULL DEFAULT '⭐', image_data BLOB, image_mime TEXT NOT NULL DEFAULT ''
        )
    """)
    columns = {row["name"] for row in cursor.execute("PRAGMA table_info(products)").fetchall()}
    upgrades = {
        "show_color": "ALTER TABLE products ADD COLUMN show_color INTEGER NOT NULL DEFAULT 1",
        "image_data": "ALTER TABLE products ADD COLUMN image_data BLOB",
        "image_mime": "ALTER TABLE products ADD COLUMN image_mime TEXT NOT NULL DEFAULT ''",
    }
    for column, statement in upgrades.items():
        if column not in columns:
            cursor.execute(statement)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
            image_data BLOB NOT NULL, image_mime TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0, is_primary INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_images_product ON product_images(product_id, sort_order, id)")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_number TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
            customer_name TEXT NOT NULL, customer_email TEXT NOT NULL, customer_phone TEXT NOT NULL DEFAULT '',
            fulfillment_method TEXT NOT NULL DEFAULT 'shipping', address1 TEXT NOT NULL DEFAULT '', address2 TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '', state TEXT NOT NULL DEFAULT '', postal_code TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
            payment_method TEXT NOT NULL DEFAULT 'Venmo', payment_status TEXT NOT NULL DEFAULT 'Unpaid', status TEXT NOT NULL DEFAULT 'New',
            subtotal REAL NOT NULL DEFAULT 0, name_fees REAL NOT NULL DEFAULT 0, fulfillment_fees REAL NOT NULL DEFAULT 0,
            shipping REAL NOT NULL DEFAULT 0, tax REAL NOT NULL DEFAULT 0, total REAL NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, product_id INTEGER,
            product_name TEXT NOT NULL, size TEXT NOT NULL DEFAULT '', color TEXT NOT NULL DEFAULT '', requested_name TEXT NOT NULL DEFAULT '',
            quantity INTEGER NOT NULL DEFAULT 1, unit_price REAL NOT NULL DEFAULT 0, name_fee REAL NOT NULL DEFAULT 0,
            fulfillment_fee REAL NOT NULL DEFAULT 0, line_total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC)")
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

    defaults = {
        "store_name": "Stardust Ship-it-Shop", "order_email": "stagestarzacademy@gmail.com",
        "venmo_username": "@StageStarzDance", "name_fee": "10.00", "name_max_chars": "20",
        "name_instructions": "Enter the name exactly as you want it printed.", "sales_tax_rate": "0.06",
        "shipping_mode": "per_item", "shipping_rate": "5.00", "free_shipping_threshold": "100.00",
        "allow_customer_shipping": "1", "customer_shipping_fee": "0.00", "low_stock_threshold": "5",
    }
    for key, value in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", (key, value))

    connection.commit()
    connection.close()
