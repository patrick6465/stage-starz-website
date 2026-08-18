from __future__ import annotations

import mimetypes
from pathlib import Path

from flask import request

from database import get_db
import website_video_manager as video_manager
from website_video_manager import MAX_VIDEO_BYTES, VIDEO_EXTENSIONS, VIDEO_FOLDER


VIDEO_URL_PREFIX = "/media/videos/"


def ensure_video_asset_schema() -> None:
    """Create persistent database storage for uploaded website videos."""
    connection = get_db()
    blob_type = "BYTEA" if getattr(connection, "backend", "sqlite") == "postgresql" else "BLOB"
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS website_video_assets (
            filename TEXT PRIMARY KEY,
            original_name TEXT NOT NULL DEFAULT '',
            mime_type TEXT NOT NULL DEFAULT 'video/mp4',
            data {blob_type} NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()


def _stored_video_sizes() -> dict[str, int]:
    ensure_video_asset_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT filename, size_bytes FROM website_video_assets"
    ).fetchall()
    connection.close()

    sizes: dict[str, int] = {}
    for row in rows:
        try:
            filename, size_bytes = row["filename"], row["size_bytes"]
        except (TypeError, KeyError, IndexError):
            filename, size_bytes = row[0], row[1]
        sizes[str(filename)] = int(size_bytes or 0)
    return sizes


def _stored_video_metadata() -> list[dict[str, object]]:
    """Return video names and sizes without loading any large BLOB data."""
    ensure_video_asset_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT filename, size_bytes FROM website_video_assets ORDER BY filename"
    ).fetchall()
    connection.close()

    videos: list[dict[str, object]] = []
    for row in rows:
        try:
            filename, size_bytes = row["filename"], row["size_bytes"]
        except (TypeError, KeyError, IndexError):
            filename, size_bytes = row[0], row[1]
        clean = Path(str(filename)).name
        if not clean or clean != str(filename):
            continue
        if Path(clean).suffix.lower().lstrip(".") not in VIDEO_EXTENSIONS:
            continue
        videos.append({"filename": clean, "size_bytes": int(size_bytes or 0)})
    return videos


def _store_video(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    extension = path.suffix.lower().lstrip(".")
    if extension not in VIDEO_EXTENSIONS:
        return False

    size = path.stat().st_size
    if size <= 0 or size > MAX_VIDEO_BYTES:
        return False

    existing = _stored_video_sizes().get(path.name)
    if existing == size:
        return False

    try:
        data = path.read_bytes()
    except Exception:
        return False
    if not data or len(data) > MAX_VIDEO_BYTES:
        return False

    mime_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
    ensure_video_asset_schema()
    connection = get_db()
    connection.execute(
        """
        INSERT INTO website_video_assets (
            filename, original_name, mime_type, data, size_bytes, created_at
        ) VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(filename) DO UPDATE SET
            original_name=excluded.original_name,
            mime_type=excluded.mime_type,
            data=excluded.data,
            size_bytes=excluded.size_bytes,
            created_at=CURRENT_TIMESTAMP
        """,
        (path.name, path.name, mime_type, data, len(data)),
    )
    connection.commit()
    connection.close()
    return True


def backup_video_folder() -> int:
    """Copy new/changed website videos from disk into persistent database storage."""
    ensure_video_asset_schema()
    VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)
    stored = _stored_video_sizes()
    backed_up = 0

    for path in VIDEO_FOLDER.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower().lstrip(".") not in VIDEO_EXTENSIONS:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if stored.get(path.name) == size:
            continue
        if _store_video(path):
            backed_up += 1
    return backed_up


def restore_persistent_video(filename: str) -> bool:
    """Restore one requested video instead of loading the full library at startup."""
    clean = Path(str(filename)).name
    if not clean or clean != str(filename):
        return False
    if Path(clean).suffix.lower().lstrip(".") not in VIDEO_EXTENSIONS:
        return False

    target = VIDEO_FOLDER / clean
    stored_sizes = _stored_video_sizes()
    expected = int(stored_sizes.get(clean, 0) or 0)
    if expected <= 0:
        return False

    try:
        if target.exists() and target.is_file() and target.stat().st_size == expected:
            return True
    except OSError:
        pass

    ensure_video_asset_schema()
    connection = get_db()
    row = connection.execute(
        "SELECT data, size_bytes FROM website_video_assets WHERE filename=?",
        (clean,),
    ).fetchone()
    connection.close()
    if not row:
        return False

    try:
        data = row["data"]
        size_bytes = row["size_bytes"]
    except (TypeError, KeyError, IndexError):
        data, size_bytes = row[0], row[1]

    try:
        expected = int(size_bytes or 0)
        if expected <= 0 or expected > MAX_VIDEO_BYTES:
            return False
        VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)
        payload = bytes(data)
        if len(payload) != expected:
            return False
        target.write_bytes(payload)
        return True
    except Exception:
        return False


def restore_persistent_videos() -> int:
    """Compatibility helper: restore videos one at a time when explicitly requested."""
    restored = 0
    for item in _stored_video_metadata():
        if restore_persistent_video(str(item["filename"])):
            restored += 1
    return restored


def delete_persistent_video(video_url: str) -> None:
    if not video_url.startswith(VIDEO_URL_PREFIX):
        return
    filename = Path(video_url[len(VIDEO_URL_PREFIX):]).name
    if not filename:
        return

    ensure_video_asset_schema()
    connection = get_db()
    connection.execute(
        "DELETE FROM website_video_assets WHERE filename=?",
        (filename,),
    )
    connection.commit()
    connection.close()


def _persistent_valid_video_url(video_url: str) -> str:
    if not video_url.startswith(VIDEO_URL_PREFIX):
        return ""
    filename = Path(video_url[len(VIDEO_URL_PREFIX):]).name
    if not filename or filename != video_url[len(VIDEO_URL_PREFIX):]:
        return ""
    if Path(filename).suffix.lower().lstrip(".") not in VIDEO_EXTENSIONS:
        return ""

    target = VIDEO_FOLDER / filename
    if target.exists() and target.is_file():
        return f"{VIDEO_URL_PREFIX}{filename}"
    if filename in _stored_video_sizes():
        return f"{VIDEO_URL_PREFIX}{filename}"
    return ""


def _persistent_video_list() -> list[dict[str, str]]:
    """List the library from lightweight DB metadata plus any current disk files."""
    indexed: dict[str, int] = {}
    for item in _stored_video_metadata():
        indexed[str(item["filename"])] = int(item["size_bytes"] or 0)

    if VIDEO_FOLDER.exists():
        for path in VIDEO_FOLDER.iterdir():
            if not path.is_file() or path.suffix.lower().lstrip(".") not in VIDEO_EXTENSIONS:
                continue
            try:
                indexed[path.name] = path.stat().st_size
            except OSError:
                continue

    videos = [
        {
            "name": filename,
            "url": f"{VIDEO_URL_PREFIX}{filename}",
            "size_mb": f"{size / (1024 * 1024):.1f}",
        }
        for filename, size in indexed.items()
        if size > 0
    ]
    return sorted(videos, key=lambda item: item["name"].lower())


def register_persistent_videos(app) -> None:
    """Keep website videos persistent without blocking Railway startup."""
    ensure_video_asset_schema()
    VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)

    # The public/editor helpers should recognize database-backed videos even when
    # the new Railway container has not materialized those large files to disk yet.
    video_manager._valid_video_url = _persistent_valid_video_url
    video_manager._list_videos = _persistent_video_list

    app.logger.info(
        "Persistent website video storage ready; large files restore lazily on request"
    )

    @app.before_request
    def materialize_requested_video():
        try:
            if request.method == "GET" and request.path.startswith(VIDEO_URL_PREFIX):
                filename = request.path[len(VIDEO_URL_PREFIX):]
                target = VIDEO_FOLDER / Path(filename).name
                if not target.exists() or not target.is_file():
                    restore_persistent_video(filename)
            elif request.method == "POST" and request.path == "/admin/website/videos/delete":
                video_url = request.form.get("video_url", "").strip()
                if video_url.startswith(VIDEO_URL_PREFIX):
                    filename = video_url[len(VIDEO_URL_PREFIX):]
                    target = VIDEO_FOLDER / Path(filename).name
                    if not target.exists() or not target.is_file():
                        restore_persistent_video(filename)
        except Exception:
            app.logger.exception("Could not lazily restore persistent website video")

    @app.after_request
    def persist_website_video_changes(response):
        try:
            if request_path_is_video_save(response):
                backed_up = backup_video_folder()
                if backed_up:
                    app.logger.info(
                        "Backed up %s website video(s) to persistent storage",
                        backed_up,
                    )
            elif request_path_is_video_delete(response):
                delete_persistent_video(request.form.get("video_url", "").strip())
        except Exception:
            app.logger.exception("Could not synchronize persistent website video storage")
        return response


def request_path_is_video_save(response) -> bool:
    return (
        request.method == "POST"
        and request.path == "/admin/website/videos/save"
        and response.status_code < 400
    )


def request_path_is_video_delete(response) -> bool:
    return (
        request.method == "POST"
        and request.path == "/admin/website/videos/delete"
        and response.status_code < 400
    )
