from __future__ import annotations

from datetime import datetime, timezone

from flask import Response, abort, jsonify, render_template, request, send_from_directory

from config import BASE_DIR
from database import get_db
from inventory import ensure_inventory_schema, record_inventory_movement
from services import get_settings, rows_to_products, shipping_amount
from variants import refresh_product_stock


def register_public_routes(app):
    @app.route("/")
    def website_home():
        return send_from_directory(BASE_DIR / "site", "index.html")

    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok"})

    @app.route("/store")
    def storefront():
        return render_template("store.html")

    @app.route("/product-image/<int:image_id>")
    def product_image(image_id: int):
        connection = get_db()
        row = connection.execute("SELECT image_data,image_mime FROM product_images WHERE id=?", (image_id,)).fetchone()
        connection.close()
        if not row:
            abort(404)
        return Response(row["image_data"], mimetype=row["image_mime"] or "application/octet-stream", headers={"Cache-Control": "public, max-age=3600"})

    @app.route("/api/products")
    def api_products():
        connection = get_db()
        rows = connection.execute("SELECT * FROM products WHERE active=1 ORDER BY category,name").fetchall()
        products = rows_to_products(rows, connection)
        connection.close()
        return jsonify(products)

    @app.route("/api/settings")
    def api_settings():
        return jsonify(get_settings())

    @app.route("/api/orders", methods=["POST"])
    def create_order():
        payload = request.get_json(silent=True) or {}
        customer = payload.get("customer") or {}
        raw_items = payload.get("items") or []
        name = str(customer.get("name", "")).strip()
        email = str(customer.get("email", "")).strip().lower()
        phone = str(customer.get("phone", "")).strip()
        method = str(customer.get("fulfillment_method", "shipping")).strip()
        if method not in {"shipping", "pickup"}:
            method = "shipping"
        if not name or not email or not raw_items:
            return jsonify({"error": "Name, email, and at least one cart item are required."}), 400

        connection = get_db()
        settings = get_settings(connection)
        validated = []
        reserved_by_product: dict[int, int] = {}
        reserved_by_variant: dict[int, int] = {}
        subtotal = name_fees = fulfillment_fees = 0.0
        total_quantity = 0
        try:
            ensure_inventory_schema(connection)
            for raw in raw_items:
                product_id = int(raw.get("id"))
                quantity = max(1, min(20, int(raw.get("quantity", 1))))
                product = connection.execute(
                    "SELECT * FROM products WHERE id=? AND active=1 FOR UPDATE", (product_id,)
                ).fetchone()
                if not product:
                    raise ValueError("A product in the cart is no longer available.")

                sizes = [x.strip() for x in product["sizes"].split(",") if x.strip()]
                colors = [x.strip() for x in product["colors"].split(",") if x.strip()]
                size = str(raw.get("size", "")).strip()
                color = str(raw.get("color", "")).strip()
                requested_name = str(raw.get("requestedName", "")).strip()
                if size not in sizes:
                    size = sizes[0] if sizes else "One Size"
                if product["show_color"] and color not in colors:
                    color = colors[0] if colors else "Default"
                if not product["show_color"]:
                    color = ""

                variant_id = None
                if product["track_variants"]:
                    lookup_color = color or "Default"
                    variant = connection.execute(
                        "SELECT id,stock FROM product_variants WHERE product_id=? AND size=? AND color=? AND active=1 FOR UPDATE",
                        (product_id, size, lookup_color),
                    ).fetchone()
                    if not variant:
                        raise ValueError(f"The selected size and color for {product['name']} is unavailable.")
                    variant_id = int(variant["id"])
                    requested_variant_total = reserved_by_variant.get(variant_id, 0) + quantity
                    if int(variant["stock"]) < requested_variant_total:
                        raise ValueError(f"Only {variant['stock']} unit(s) of {product['name']} in {size}{' / ' + color if color else ''} remain.")
                    reserved_by_variant[variant_id] = requested_variant_total
                else:
                    requested_total = reserved_by_product.get(product_id, 0) + quantity
                    if int(product["stock"]) < requested_total:
                        raise ValueError(f"Only {product['stock']} unit(s) of {product['name']} remain in stock.")
                    reserved_by_product[product_id] = requested_total

                max_chars = max(1, int(settings.get("name_max_chars", "20") or 20))
                if not product["allow_name"]:
                    requested_name = ""
                requested_name = requested_name[:max_chars]
                price = float(product["sale_price"] if product["sale_price"] is not None else product["price"])
                name_fee = float(settings.get("name_fee", "10") or 0) if requested_name else 0.0
                fulfillment_fee = float(product["fulfillment_fee"] or 0)
                line_total = quantity * (price + name_fee + fulfillment_fee)
                validated.append((product_id, product["name"], size, color, requested_name, quantity, price, name_fee, fulfillment_fee, line_total, variant_id))
                subtotal += quantity * price
                name_fees += quantity * name_fee
                fulfillment_fees += quantity * fulfillment_fee
                total_quantity += quantity

            shipping = shipping_amount(settings, subtotal, total_quantity, method)
            tax = subtotal * float(settings.get("sales_tax_rate", "0") or 0)
            total = subtotal + name_fees + fulfillment_fees + shipping + tax
            created_at = datetime.now(timezone.utc).isoformat()
            address1 = str(customer.get("address1", "")).strip()
            address2 = str(customer.get("address2", "")).strip()
            city = str(customer.get("city", "")).strip()
            state = str(customer.get("state", "")).strip()
            postal_code = str(customer.get("postal_code", "")).strip()

            connection.execute("""
                INSERT INTO customers (name,email,phone,address1,address2,city,state,postal_code,customer_since,last_order_date,total_orders,lifetime_spending)
                VALUES (?,?,?,?,?,?,?,?,?,?,1,?)
                ON CONFLICT(email) DO UPDATE SET
                    name=excluded.name, phone=excluded.phone,
                    address1=CASE WHEN excluded.address1!='' THEN excluded.address1 ELSE customers.address1 END,
                    address2=CASE WHEN excluded.address2!='' THEN excluded.address2 ELSE customers.address2 END,
                    city=CASE WHEN excluded.city!='' THEN excluded.city ELSE customers.city END,
                    state=CASE WHEN excluded.state!='' THEN excluded.state ELSE customers.state END,
                    postal_code=CASE WHEN excluded.postal_code!='' THEN excluded.postal_code ELSE customers.postal_code END,
                    last_order_date=excluded.last_order_date,
                    total_orders=customers.total_orders+1,
                    lifetime_spending=customers.lifetime_spending+excluded.lifetime_spending,
                    status='Active'
            """, (name, email, phone, address1, address2, city, state, postal_code, created_at, created_at, round(total, 2)))
            customer_id = connection.execute("SELECT id FROM customers WHERE email=? COLLATE NOCASE", (email,)).fetchone()["id"]

            cursor = connection.execute(
                """INSERT INTO orders (order_number,created_at,customer_name,customer_email,customer_phone,fulfillment_method,address1,address2,city,state,postal_code,notes,payment_method,payment_status,status,subtotal,name_fees,fulfillment_fees,shipping,tax,total,customer_id) VALUES ('PENDING',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (created_at, name, email, phone, method, address1, address2, city, state, postal_code, str(customer.get("notes", "")).strip(), str(customer.get("payment_method", "Venmo")).strip() or "Venmo", "Unpaid", "New", round(subtotal, 2), round(name_fees, 2), round(fulfillment_fees, 2), round(shipping, 2), round(tax, 2), round(total, 2), customer_id),
            )
            order_id = int(cursor.lastrowid)
            order_number = f"SS-{datetime.now().strftime('%y%m%d')}-{order_id:04d}"
            connection.execute("UPDATE orders SET order_number=? WHERE id=?", (order_number, order_id))
            connection.executemany(
                "INSERT INTO order_items (order_id,product_id,product_name,size,color,requested_name,quantity,unit_price,name_fee,fulfillment_fee,line_total,variant_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [(order_id,) + item for item in validated],
            )

            for variant_id, quantity in reserved_by_variant.items():
                connection.execute("UPDATE product_variants SET stock=stock-? WHERE id=?", (quantity, variant_id))
            variant_product_ids = {item[0] for item in validated if item[10] is not None}
            for product_id in variant_product_ids:
                old_stock = int(connection.execute("SELECT stock FROM products WHERE id=?", (product_id,)).fetchone()["stock"])
                new_stock = refresh_product_stock(connection, product_id)
                record_inventory_movement(connection, product_id, new_stock - old_stock, new_stock, "Order placed", reference=order_number)

            for product_id, quantity in reserved_by_product.items():
                updated = connection.execute(
                    "UPDATE products SET stock=stock-? WHERE id=? RETURNING stock",
                    (quantity, product_id),
                ).fetchone()
                record_inventory_movement(connection, product_id, -quantity, int(updated["stock"]), "Order placed", reference=order_number)
            connection.commit()
        except (ValueError, TypeError) as exc:
            connection.rollback()
            connection.close()
            return jsonify({"error": str(exc)}), 400
        except Exception:
            connection.rollback()
            connection.close()
            return jsonify({"error": "The order could not be saved. Please try again."}), 500

        connection.close()
        return jsonify({"ok": True, "order_number": order_number, "total": round(total, 2), "venmo_username": settings.get("venmo_username", "")})

    @app.route("/<path:filename>")
    def website_file(filename: str):
        requested = BASE_DIR / "site" / filename
        if requested.exists() and requested.is_file():
            return send_from_directory(BASE_DIR / "site", filename)
        return ("Page not found", 404)
