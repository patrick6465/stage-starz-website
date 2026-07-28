from __future__ import annotations

from datetime import datetime, timezone


def ensure_inventory_schema(connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS inventory_movements (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            change_quantity INTEGER NOT NULL,
            quantity_after INTEGER NOT NULL,
            reason TEXT NOT NULL,
            reference TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT ''
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_inventory_movements_product ON inventory_movements(product_id, id DESC)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_inventory_movements_created ON inventory_movements(id DESC)")


def record_inventory_movement(connection, product_id: int, change_quantity: int, quantity_after: int, reason: str, reference: str = "", note: str = "") -> None:
    ensure_inventory_schema(connection)
    connection.execute(
        """INSERT INTO inventory_movements
           (product_id,created_at,change_quantity,quantity_after,reason,reference,note)
           VALUES (?,?,?,?,?,?,?)""",
        (
            product_id,
            datetime.now(timezone.utc).isoformat(),
            change_quantity,
            quantity_after,
            reason,
            reference,
            note,
        ),
    )
