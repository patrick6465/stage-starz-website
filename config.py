from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

_explicit_database_path = os.environ.get("DATABASE_PATH", "").strip()
_volume_mount_path = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()

if _explicit_database_path:
    DB_PATH = Path(_explicit_database_path)
elif _volume_mount_path:
    DB_PATH = Path(_volume_mount_path) / "store.db"
else:
    DB_PATH = BASE_DIR / "data" / "store.db"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "StageStarz123!")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_PRODUCT_IMAGES = 6
ORDER_STATUSES = {"New", "Awaiting Payment", "Paid", "Processing", "Ready", "Completed", "Cancelled"}
