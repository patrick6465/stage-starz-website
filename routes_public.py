from __future__ import annotations

from datetime import datetime, timezone

from flask import Response, abort, jsonify, render_template, request, send_from_directory

from config import BASE_DIR
from database import get_db
from services import get_settings, rows_to_products, shipping_amount


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
        email = str(customer.get("email", "")).strip()
        phone = str(customer.get("phone", "")).strip()
        method = str(customer.get("fulfillment_method", "shipping")).strip()
        if method not in {"shipping", "pickup"}:
            method = "shipping"
        if not name or not email or not raw_items:
            return jsonify({"error": "Name, email, and at least one cart item are required."}), 400

        connection = get_db()
        settings = get_settings(connection)
        validated = []
        subtotal = name_fees = fulfillment_fees = 0.0
        total_quantity = 0
        try:
            for raw in raw_items:
                product_id = int(raw.get("id"))
                quantity = max(1, min(20, int(raw.get("quantity", 1))))
                product = connection.execute("SELECT * FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
                if not product:
                    raise ValueError("A product in the cart is no longer available.")
                if int(product["stock"]) < quantity:
                    raise ValueError(f"Not enough stock is available for {product['name']}.")

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
                max_chars = max(1, int(settings.get("name_max_chars", "20") or 20))
                if not product["allow_name"]:
                    requested_name = ""
                requested_name = requested_name[:max_chars]
                price = float(product["sale_price"] if product["sale_price"] is not None else product["price"])
                name_fee = float(settings.get("name_fee", "10") or 0) if requested_name else 0.0
                fulfillment_fee = float(product["fulfillment_fee"] or 0)
                line_total = quantity * (price + name_fee + fulfillment_fee)
                validated.append((product_id, product["name"], size, color, requested_name, quantity, price, name_fee, fulfillment_fee, line_total))
                subtotal += quantity * price
                name_fees += quantity * name_fee
                fulfillment_fees += quantity * fulfillment_fee
                total_quantity += quantity

            shipping = shipping_amount(settings, subtotal, total_quantity, method)
            tax = subtotal * float(settings.get("sales_tax_rate", "0") or 0)
            total = subtotal + name_fees + fulfillment_fees + shipping + tax
            created_at = datetime.now(timezone.utc).isoformat()
            cursor = connection.execute(
                """INSERT INTO orders (order_number,created_at,customer_name,customer_email,customer_phone,fulfillment_method,address1,address2,city,state,postal_code,notes,payment_method,payment_status,status,subtotal,name_fees,fulfillment_fees,shipping,tax,total) VALUES ('PENDING',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (created_at, name, email, phone, method, str(customer.get("address1", "")).strip(), str(customer.get("address2", "")).strip(), str(customer.get("city", "")).strip(), str(customer.get("state", "")).strip(), str(customer.get("postal_code", "")).strip(), str(customer.get("notes", "")).strip(), str(customer.get("payment_method", "Venmo")).strip() or "Venmo", "Unpaid", "New", round(subtotal, 2), round(name_fees, 2), round(fulfillment_fees, 2), round(shipping, 2), round(tax, 2), round(total, 2)),
            )
            order_id = int(cursor.lastrowid)
            order_number = f"SS-{datetime.now().strftime('%y%m%d')}-{order_id:04d}"
            connection.execute("UPDATE orders SET order_number=? WHERE id=?", (order_number, order_id))
            connection.executemany("INSERT INTO order_items (order_id,product_id,product_name,size,color,requested_name,quantity,unit_price,name_fee,fulfillment_fee,line_total) VALUES (?,?,?,?,?,?,?,?,?,?,?)", [(order_id,) + item for item in validated])
            for item in validated:
                connection.execute("UPDATE products SET stock=MAX(0,stock-?) WHERE id=?", (item[5], item[0]))
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
