from __future__ import annotations

import mimetypes
from pathlib import Path

from database import get_db
from website_video_manager import MAX_VIDEO_BYTES, VIDEO_EXTENSIONS, VIDEO_FOLDER


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


def restore_persistent_videos() -> int:
    """Restore database-backed videos to the Railway filesystem after a deploy/restart."""
    ensure_video_asset_schema()
    VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)

    # If a real Railway volume is mounted, import anything already present before
    # restoring the database copy. This also safely migrates legacy disk-only files.
    backup_video_folder()

    connection = get_db()
    rows = connection.execute(
        "SELECT filename, data, size_bytes FROM website_video_assets ORDER BY created_at"
    ).fetchall()
    connection.close()

    restored = 0
    for row in rows:
        try:
            filename, data, size_bytes = row["filename"], row["data"], row["size_bytes"]
        except (TypeError, KeyError, IndexError):
            filename, data, size_bytes = row[0], row[1], row[2]

        clean = Path(str(filename)).name
        if not clean or clean != str(filename):
            continue
        if Path(clean).suffix.lower().lstrip(".") not in VIDEO_EXTENSIONS:
            continue

        target = VIDEO_FOLDER / clean
        try:
            expected = int(size_bytes or 0)
            if target.exists() and target.is_file() and target.stat().st_size == expected:
                restored += 1
                continue
            target.write_bytes(bytes(data))
            restored += 1
        except Exception:
            continue
    return restored


def delete_persistent_video(video_url: str) -> None:
    prefix = "/media/videos/"
    if not video_url.startswith(prefix):
        return
    filename = Path(video_url[len(prefix):]).name
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


def register_persistent_videos(app) -> None:
    """Keep website video uploads through Railway deploys and restarts."""
    restored = restore_persistent_videos()
    app.logger.info(
        "Persistent website videos ready; restored %s video(s)",
        restored,
    )

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
                from flask import request

                delete_persistent_video(request.form.get("video_url", "").strip())
        except Exception:
            app.logger.exception("Could not synchronize persistent website video storage")
        return response


def request_path_is_video_save(response) -> bool:
    from flask import request

    return (
        request.method == "POST"
        and request.path == "/admin/website/videos/save"
        and response.status_code < 400
    )


def request_path_is_video_delete(response) -> bool:
    from flask import request

    return (
        request.method == "POST"
        and request.path == "/admin/website/videos/delete"
        and response.status_code < 400
    )
