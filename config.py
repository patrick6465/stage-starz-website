from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "StageStarz123!")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_PRODUCT_IMAGES = 6
ORDER_STATUSES = {"New", "Awaiting Payment", "Paid", "Processing", "Ready", "Completed", "Cancelled"}
