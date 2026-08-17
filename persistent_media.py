from __future__ import annotations

import io
import mimetypes
import uuid
from pathlib import Path

from flask import flash, redirect, request, url_for
from werkzeug.utils import secure_filename

from config import UPLOAD_FOLDER
from database import get_db

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover - deployment dependency guards this
    Image = None
    ImageOps = None
    UnidentifiedImageError = OSError

try:
    from pillow_heif import register_heif_opener
except ImportError:  # pragma: no cover
    register_heif_opener = None

if register_heif_opener is not None:
    try:
        register_heif_opener()
    except Exception:
        pass

MAX_SOURCE_BYTES = 25 * 1024 * 1024
MAX_IMAGE_DIMENSION = 2400


def ensure_media_schema() -> None:
    connection = get_db()
    blob_type = "BYTEA" if getattr(connection, "backend", "sqlite") == "postgresql" else "BLOB"
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS media_assets (
            filename TEXT PRIMARY KEY,
            original_name TEXT NOT NULL DEFAULT '',
            mime_type TEXT NOT NULL DEFAULT 'image/webp',
            data {blob_type} NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()


def _normalize_image(raw: bytes) -> tuple[bytes, str]:
    if Image is None:
        raise ValueError("Image processing is temporarily unavailable. Please try again shortly.")
    if not raw:
        raise ValueError("That image file is empty. Please choose another photo.")
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("That photo is too large. Please choose an image under 25 MB.")

    try:
        with Image.open(io.BytesIO(raw)) as opened:
            try:
                opened.seek(0)
            except Exception:
                pass
            image = ImageOps.exif_transpose(opened) if ImageOps is not None else opened.copy()
            image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError(
            "That photo format could not be read. Try JPG, PNG, WEBP, HEIC, or HEIF."
        )

    if max(image.size) > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

    has_alpha = image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )
    image = image.convert("RGBA" if has_alpha else "RGB")

    output = io.BytesIO()
    try:
        image.save(output, format="WEBP", quality=88, method=5)
    except OSError:
        # Extremely unusual Pillow builds may lack WEBP support. JPEG remains a
        # safe browser format; flatten transparency against white when needed.
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue(), "image/jpeg"

    return output.getvalue(), "image/webp"


def _store_asset(filename: str, original_name: str, mime_type: str, data: bytes) -> None:
    ensure_media_schema()
    connection = get_db()
    connection.execute(
        """
        INSERT INTO media_assets (filename, original_name, mime_type, data, size_bytes, created_at)
        VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(filename) DO UPDATE SET
            original_name=excluded.original_name,
            mime_type=excluded.mime_type,
            data=excluded.data,
            size_bytes=excluded.size_bytes,
            created_at=CURRENT_TIMESTAMP
        """,
        (filename, original_name, mime_type, data, len(data)),
    )
    connection.commit()
    connection.close()


def save_persistent_image(file_storage) -> str:
    """Normalize a user image, save it to persistent DB storage, and mirror it to disk."""
    if not file_storage or not file_storage.filename:
        return ""

    original_name = secure_filename(file_storage.filename) or "stage-starz-photo"
    try:
        raw = file_storage.read(MAX_SOURCE_BYTES + 1)
    except Exception as error:
        raise ValueError("That photo could not be read. Please choose it again.") from error

    data, mime_type = _normalize_image(raw)
    extension = ".webp" if mime_type == "image/webp" else ".jpg"
    stem = Path(original_name).stem[:60] or "stage-starz-photo"
    filename = f"{stem}-{uuid.uuid4().hex[:10]}{extension}"

    _store_asset(filename, original_name, mime_type, data)

    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    (UPLOAD_FOLDER / filename).write_bytes(data)
    return f"/uploads/{filename}"


def delete_persistent_image(image_url: str) -> None:
    if not image_url.startswith("/uploads/"):
        return
    filename = Path(image_url).name
    ensure_media_schema()
    connection = get_db()
    connection.execute("DELETE FROM media_assets WHERE filename=?", (filename,))
    connection.commit()
    connection.close()
    target = UPLOAD_FOLDER / filename
    if target.exists() and target.is_file():
        target.unlink()


def _import_existing_disk_media() -> None:
    """Back up any files bundled/present on disk into persistent storage when possible."""
    ensure_media_schema()
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    connection = get_db()
    existing = {
        row["filename"] if hasattr(row, "keys") else row[0]
        for row in connection.execute("SELECT filename FROM media_assets").fetchall()
    }
    connection.close()

    for path in UPLOAD_FOLDER.iterdir():
        if not path.is_file() or path.name in existing:
            continue
        try:
            raw = path.read_bytes()
            if not raw or len(raw) > MAX_SOURCE_BYTES:
                continue
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            _store_asset(path.name, path.name, mime_type, raw)
        except Exception:
            # Startup should never fail because one legacy image cannot be migrated.
            continue


def restore_persistent_media() -> int:
    """Rehydrate uploaded files after every Railway deployment/restart."""
    ensure_media_schema()
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    _import_existing_disk_media()

    connection = get_db()
    rows = connection.execute(
        "SELECT filename, data FROM media_assets ORDER BY created_at"
    ).fetchall()
    connection.close()

    restored = 0
    for row in rows:
        try:
            filename = row["filename"]
            data = row["data"]
        except (TypeError, KeyError, IndexError):
            filename, data = row[0], row[1]
        try:
            (UPLOAD_FOLDER / Path(filename).name).write_bytes(bytes(data))
            restored += 1
        except Exception:
            continue
    return restored


def register_persistent_media(app) -> None:
    """Install persistent media behavior and clearer upload failures."""
    ensure_media_schema()
    restored = restore_persistent_media()
    app.logger.info("Persistent media ready; restored %s uploaded image(s)", restored)

    # Modern phone photos can exceed 10 MB before optimization. We accept up to
    # 25 MB, then normalize them to a web-sized WEBP/JPEG before storage.
    app.config["MAX_CONTENT_LENGTH"] = MAX_SOURCE_BYTES

    @app.errorhandler(413)
    def persistent_media_too_large(_error):
        flash("That photo is larger than 25 MB. Please choose a smaller image.", "error")
        return redirect(request.referrer or url_for("admin_dashboard"))
