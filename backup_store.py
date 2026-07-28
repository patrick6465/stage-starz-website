from __future__ import annotations

import base64
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database import get_db


TABLES = (
    "settings",
    "products",
    "product_images",
    "product_variants",
    "customers",
    "orders",
    "order_items",
    "inventory_movements",
    "order_status_history",
    "customer_notifications",
    "support_messages",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"__base64__": base64.b64encode(bytes(value)).decode("ascii")}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def create_backup(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = destination / f"stage-starz-store-backup-{timestamp}.zip"

    connection = get_db()
    manifest: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "format_version": 1,
        "tables": {},
    }

    try:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for table in TABLES:
                try:
                    rows = connection.execute(f"SELECT * FROM {table}").fetchall()
                except Exception:
                    connection.rollback()
                    manifest["tables"][table] = {"status": "not_present", "rows": 0}
                    continue

                serialized = [
                    {key: _json_value(value) for key, value in dict(row).items()}
                    for row in rows
                ]
                archive.writestr(
                    f"tables/{table}.json",
                    json.dumps(serialized, indent=2, ensure_ascii=False),
                )
                manifest["tables"][table] = {"status": "exported", "rows": len(serialized)}

            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    finally:
        connection.close()

    return archive_path


if __name__ == "__main__":
    backup_dir = Path(os.environ.get("BACKUP_DIR", "backups"))
    created = create_backup(backup_dir)
    print(created)
