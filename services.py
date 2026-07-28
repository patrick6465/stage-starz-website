from __future__ import annotations

import sqlite3
from functools import wraps
from typing import Any

from flask import redirect, session, url_for

from database import get_db


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def image_rows_for_products(connection: sqlite3.Connection, product_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    grouped = {pid: [] for pid in product_ids}
    if not product_ids:
        return grouped
    marks = ",".join("?" for _ in product_ids)
    rows = connection.execute(
        f"SELECT id,product_id,sort_order,is_primary FROM product_images WHERE product_id IN ({marks}) ORDER BY product_id,is_primary DESC,sort_order,id",
        product_ids,
    ).fetchall()
    for row in rows:
        grouped[row["product_id"]].append({
            "id": row["id"],
            "sort_order": row["sort_order"],
            "is_primary": bool(row["is_primary"]),
            "url": url_for("product_image", image_id=row["id"]),
        })
    return grouped


def rows_to_products(rows: list[sqlite3.Row], connection: sqlite3.Connection) -> list[dict[str, Any]]:
    galleries = image_rows_for_products(connection, [row["id"] for row in rows])
    products = []
    for row in rows:
        item = dict(row)
        item.pop("image_data", None)
        item.pop("image_mime", None)
        item["external_image_url"] = item.get("image_url", "")
        item["images"] = galleries.get(item["id"], [])
        item["has_uploaded_image"] = bool(item["images"])
        if item["images"]:
            item["image_url"] = item["images"][0]["url"]
        item["sizes"] = [x.strip() for x in item["sizes"].split(",") if x.strip()]
        item["colors"] = [x.strip() for x in item["colors"].split(",") if x.strip()]
        item["show_color"] = bool(item["show_color"])
        item["allow_name"] = bool(item["allow_name"])
        item["active"] = bool(item["active"])
        products.append(item)
    return products


def get_settings(connection: sqlite3.Connection | None = None) -> dict[str, str]:
    own = connection is None
    connection = connection or get_db()
    rows = connection.execute("SELECT key,value FROM settings").fetchall()
    if own:
        connection.close()
    return {row["key"]: row["value"] for row in rows}


def build_dashboard(products: list[dict[str, Any]], settings: dict[str, str]) -> dict[str, Any]:
    try:
        threshold = max(0, int(settings.get("low_stock_threshold", "5")))
    except ValueError:
        threshold = 5
    low_stock = sorted([p for p in products if 0 < p["stock"] <= threshold], key=lambda p: (p["stock"], p["name"].lower()))
    out_of_stock = sorted([p for p in products if p["stock"] <= 0], key=lambda p: p["name"].lower())
    categories: dict[str, dict[str, Any]] = {}
    for product in products:
        current_price = float(product["sale_price"] if product["sale_price"] is not None else product["price"])
        category_name = product["category"] or "Uncategorized"
        category = categories.setdefault(category_name, {"name": category_name, "products": 0, "units": 0, "value": 0.0})
        category["products"] += 1
        category["units"] += max(0, int(product["stock"]))
        category["value"] += max(0, int(product["stock"])) * current_price
    return {
        "total_products": len(products),
        "active_products": sum(1 for p in products if p["active"]),
        "hidden_products": sum(1 for p in products if not p["active"]),
        "inventory_units": sum(max(0, int(p["stock"])) for p in products),
        "inventory_value": sum(max(0, int(p["stock"])) * float(p["sale_price"] if p["sale_price"] is not None else p["price"]) for p in products),
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "categories": sorted(categories.values(), key=lambda x: x["name"].lower()),
        "threshold": threshold,
    }


def shipping_amount(settings: dict[str, str], subtotal: float, quantity: int, fulfillment_method: str) -> float:
    if fulfillment_method == "pickup" or settings.get("allow_customer_shipping") == "0":
        return 0.0
    mode = settings.get("shipping_mode", "per_item")
    rate = float(settings.get("shipping_rate", "0") or 0)
    threshold = float(settings.get("free_shipping_threshold", "0") or 0)
    if mode == "none":
        return 0.0
    if mode == "flat":
        return rate
    if mode == "free_over":
        return 0.0 if subtotal >= threshold else rate
    return quantity * rate
