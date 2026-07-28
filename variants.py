from __future__ import annotations


def split_options(value: str, fallback: str) -> list[str]:
    values = [item.strip() for item in (value or '').split(',') if item.strip()]
    return values or [fallback]


def sync_product_variants(connection, product_id: int) -> None:
    product = connection.execute(
        "SELECT id,sizes,colors,show_color,track_variants FROM products WHERE id=?",
        (product_id,),
    ).fetchone()
    if not product:
        return

    sizes = split_options(product['sizes'], 'One Size')
    colors = split_options(product['colors'], 'Default') if product['show_color'] else ['Default']
    desired = {(size, color) for size in sizes for color in colors}

    existing = connection.execute(
        "SELECT id,size,color FROM product_variants WHERE product_id=?",
        (product_id,),
    ).fetchall()
    existing_pairs = {(row['size'], row['color']) for row in existing}

    for size, color in sorted(desired):
        if (size, color) not in existing_pairs:
            connection.execute(
                "INSERT INTO product_variants (product_id,size,color,stock,active) VALUES (?,?,?,?,1)",
                (product_id, size, color, 0),
            )

    for row in existing:
        active = 1 if (row['size'], row['color']) in desired else 0
        connection.execute("UPDATE product_variants SET active=? WHERE id=?", (active, row['id']))


def refresh_product_stock(connection, product_id: int) -> int:
    row = connection.execute(
        "SELECT COALESCE(SUM(stock),0) AS stock FROM product_variants WHERE product_id=? AND active=1",
        (product_id,),
    ).fetchone()
    total = max(0, int(row['stock'] or 0))
    connection.execute("UPDATE products SET stock=? WHERE id=?", (total, product_id))
    return total
