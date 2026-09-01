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

FLASK_ENV = os.environ.get("FLASK_ENV", "").strip().lower()
_RUNNING_ON_RAILWAY = bool(
    os.environ.get("RAILWAY_ENVIRONMENT")
    or os.environ.get("RAILWAY_PROJECT_ID")
    or os.environ.get("RAILWAY_SERVICE_ID")
)
_PRODUCTION_LIKE = FLASK_ENV == "production" or _RUNNING_ON_RAILWAY

# Production must never fall back to publicly known credentials or a predictable
# Flask signing key. Railway should provide all three as environment variables.
if _PRODUCTION_LIKE:
    SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "").strip()
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    missing = [
        name
        for name, value in (
            ("SECRET_KEY", SECRET_KEY),
            ("ADMIN_USERNAME", ADMIN_USERNAME),
            ("ADMIN_PASSWORD", ADMIN_PASSWORD),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required production environment variable(s): "
            + ", ".join(missing)
        )
else:
    # Local-only convenience values. Never used by Railway/production.
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-dev-only-change-me")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "local-dev-only-change-me")
PORT = int(os.environ.get("PORT", "5000"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG") == "1"
