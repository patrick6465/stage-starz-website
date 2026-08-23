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
# Current flagship phones can create roughly 200 MP JPEGs. Pillow's default
# decompression-bomb guard rejects those before we get a chance to resize them,
# so we inspect the header under our own limit and use JPEG draft decoding to
# reduce memory use before loading the pixels.
MAX_SOURCE_PIXELS = 260_000_000
MAX_DIRECT_DECODE_PIXELS = 40_000_000


class _ImageDimensionsTooLarge(Exception):
    pass


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


def _has_alpha(image) -> bool:
    return image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )


def _trim_transparent_margins(image):
    """Crop oversized transparent canvases while preserving a small safe border.

    Printful and other print-on-demand mockups are often exported on a large
    transparent canvas. Without trimming, the actual product can render as a tiny
    strip inside a storefront card even though the browser is sizing the image
    correctly. Opaque JPG/HEIC photos are intentionally left untouched.
    """
    if not _has_alpha(image):
        return image

    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return rgba

    width, height = rgba.size
    left, top, right, bottom = bbox
    content_width = max(1, right - left)
    content_height = max(1, bottom - top)

    # If transparency is only a negligible edge, keep the original framing.
    if content_width >= width * 0.97 and content_height >= height * 0.97:
        return rgba

    # Preserve a modest visual border around the detected product so anti-aliased
    # edges, shadows, and embroidery details are not cropped too tightly.
    padding = max(8, int(max(content_width, content_height) * 0.04))
    crop_box = (
        max(0, left - padding),
        max(0, top - padding),
        min(width, right + padding),
        min(height, bottom + padding),
    )

    cropped_width = crop_box[2] - crop_box[0]
    cropped_height = crop_box[3] - crop_box[1]
    if cropped_width <= 0 or cropped_height <= 0:
        return rgba
    return rgba.crop(crop_box)


def _normalize_image(raw: bytes) -> tuple[bytes, str]:
    if Image is None:
        raise ValueError("Image processing is temporarily unavailable. Please try again shortly.")
    if not raw:
        raise ValueError("That image file is empty. Please choose another photo.")
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("That photo is too large. Please choose an image under 25 MB.")

    previous_pixel_limit = getattr(Image, "MAX_IMAGE_PIXELS", None)
    try:
        # Image.open performs Pillow's decompression-bomb size check while only
        # reading the header. Temporarily disable that built-in threshold, then
        # immediately enforce our own hard pixel ceiling before decoding.
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(io.BytesIO(raw)) as opened:
            try:
                opened.seek(0)
            except Exception:
                pass

            width, height = opened.size
            source_pixels = int(width or 0) * int(height or 0)
            source_format = (opened.format or "").upper()

            if width <= 0 or height <= 0 or source_pixels > MAX_SOURCE_PIXELS:
                raise _ImageDimensionsTooLarge(
                    "That photo has extremely large pixel dimensions. Please use a photo under about 260 megapixels."
                )

            # JPEG supports decoder-level downsampling. This is important for
            # 100/200 MP phone photos because it prevents a several-hundred-MB
            # full-resolution bitmap from being allocated just to make a web image.
            if source_pixels > MAX_DIRECT_DECODE_PIXELS:
                if source_format in {"JPEG", "JPG", "MPO"}:
                    try:
                        opened.draft(
                            "RGB",
                            (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
                        )
                    except Exception:
                        pass

                    drafted_pixels = int(opened.size[0]) * int(opened.size[1])
                    if drafted_pixels > MAX_DIRECT_DECODE_PIXELS:
                        raise _ImageDimensionsTooLarge(
                            "That photo is too large to process safely. Please resize it or use your phone's standard-resolution photo mode."
                        )
                else:
                    raise _ImageDimensionsTooLarge(
                        "That photo is too large to process safely in this format. Please resize it first or save it as a JPG."
                    )

            image = ImageOps.exif_transpose(opened) if ImageOps is not None else opened.copy()
            image.load()
    except _ImageDimensionsTooLarge as error:
        raise ValueError(str(error)) from error
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValueError(
            "That photo format could not be read. Try JPG, PNG, WEBP, HEIC, or HEIF."
        ) from error
    finally:
        Image.MAX_IMAGE_PIXELS = previous_pixel_limit

    # Transparent print-on-demand mockups frequently include a large empty canvas.
    # Trim only transparency; regular opaque product photos keep their framing.
    image = _trim_transparent_margins(image)

    if max(image.size) > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

    has_alpha = _has_alpha(image)
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
