from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

VOLUME_MOUNT_PATH = os.environ.get(
    "RAILWAY_VOLUME_MOUNT_PATH",
    "",
).strip()

_default_upload_folder = (
    Path(VOLUME_MOUNT_PATH) / "uploads"
    if VOLUME_MOUNT_PATH
    else BASE_DIR / "data" / "uploads"
)

UPLOAD_FOLDER = Path(
    os.environ.get("UPLOAD_FOLDER", str(_default_upload_folder))
)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

SQLITE_DB_PATH = Path(
    os.environ.get(
        "SQLITE_DATABASE_PATH",
        str(BASE_DIR / "data" / "store.db"),
    )
)
SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key",
)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "StageStarz123!",
)
FLASK_ENV = os.environ.get("FLASK_ENV", "")
PORT = int(os.environ.get("PORT", "5000"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG") == "1"
