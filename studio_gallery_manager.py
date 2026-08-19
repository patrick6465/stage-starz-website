from __future__ import annotations

from pathlib import Path

from flask import flash, redirect, render_template, request

from config import UPLOAD_FOLDER
from database import get_db
from persistent_media import delete_persistent_image, save_persistent_image


GALLERY_SLOTS = {
    "class_in_progress": {
        "label": "Class in Action",
        "description": "Featured homepage photo showing a real Stage Starz class in progress.",
        "placement": "Homepage • featured",
    },
    "room_wide": {
        "label": "Studio Room",
        "description": "Wide view of the dance floor, mirrors and ballet barres.",
        "placement": "Homepage • facility",
    },
    "parent_viewing": {
        "label": "Parent Viewing Area",
        "description": "Waiting/viewing space that helps prospective families picture their visit.",
        "placement": "Homepage • family experience",
    },
    "awards_wall": {
        "label": "Awards & Achievement",
        "description": "Awards or banners that communicate studio accomplishment and growth.",
        "placement": "Homepage • achievement",
    },
    "first_day_dancers": {
        "label": "Current Dancers",
        "description": "Current dancers for the welcoming-place-to-begin gallery card.",
        "placement": "Homepage • community",
    },
    "staff_first_day": {
        "label": "Stage Starz Staff",
        "description": "Current staff photo used on the About page.",
        "placement": "About page",
    },
    "exterior": {
        "label": "Studio Exterior",
        "description": "Building/storefront photo so new families know what to look for.",
        "placement": "Contact / Directions",
    },
}


def ensure_gallery_schema() -> None:
    connection = get_db()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_gallery_settings (
            slot TEXT PRIMARY KEY,
            image_url TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()


def gallery_settings() -> dict[str, str]:
    ensure_gallery_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT slot, image_url FROM studio_gallery_settings"
    ).fetchall()
    connection.close()

    values = {key: "" for key in GALLERY_SLOTS}
    for row in rows:
        try:
            slot, image_url = row["slot"], row["image_url"]
        except (TypeError, KeyError, IndexError):
            slot, image_url = row[0], row[1]
        if slot in values:
            values[slot] = image_url or ""
    return values


def _valid_persistent_image(image_url: str) -> str:
    prefix = "/uploads/"
    if not image_url.startswith(prefix):
        return ""
    filename = Path(image_url[len(prefix):]).name
    if not filename:
        return ""
    target = UPLOAD_FOLDER / filename
    if not target.exists() or not target.is_file():
        return ""
    return f"/uploads/{filename}"


def published_gallery_settings() -> dict[str, str]:
    """Return only DB-backed images that are currently available on disk."""
    values = gallery_settings()
    return {slot: _valid_persistent_image(url) for slot, url in values.items()}


def _set_gallery_slot(slot: str, image_url: str) -> None:
    ensure_gallery_schema()
    connection = get_db()
    connection.execute(
        """
        INSERT INTO studio_gallery_settings (slot, image_url, updated_at)
        VALUES (?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(slot) DO UPDATE SET
            image_url=excluded.image_url,
            updated_at=CURRENT_TIMESTAMP
        """,
        (slot, image_url),
    )
    connection.commit()
    connection.close()


def register_studio_gallery_manager(app, permission_required, log_activity=None) -> None:
    """Manage prospect-facing studio photography with persistent DB-backed uploads."""
    ensure_gallery_schema()

    @app.route("/admin/website/studio-gallery")
    @permission_required("website")
    def studio_gallery_editor():
        current = published_gallery_settings()
        slots = []
        for key, info in GALLERY_SLOTS.items():
            slots.append(
                {
                    "key": key,
                    "label": info["label"],
                    "description": info["description"],
                    "placement": info["placement"],
                    "image_url": current.get(key, ""),
                }
            )
        return render_template("studio_gallery_editor.html", slots=slots)

    @app.route("/admin/website/studio-gallery/save", methods=["POST"])
    @permission_required("website")
    def save_studio_gallery():
        current = gallery_settings()
        changed = 0

        for slot, info in GALLERY_SLOTS.items():
            if request.form.get(f"clear_{slot}") == "1":
                old_url = current.get(slot, "")
                _set_gallery_slot(slot, "")
                if old_url:
                    try:
                        delete_persistent_image(old_url)
                    except Exception:
                        app.logger.exception("Could not delete old Studio Gallery photo")
                changed += 1
                continue

            uploaded = request.files.get(slot)
            if not uploaded or not uploaded.filename:
                continue

            try:
                new_url = save_persistent_image(uploaded)
            except ValueError as error:
                flash(f"{info['label']}: {error}", "error")
                return redirect(f"/admin/website/studio-gallery#slot-{slot}")

            if not new_url:
                continue

            old_url = current.get(slot, "")
            _set_gallery_slot(slot, new_url)
            if old_url and old_url != new_url:
                try:
                    delete_persistent_image(old_url)
                except Exception:
                    app.logger.exception("Could not delete replaced Studio Gallery photo")
            changed += 1

        if changed:
            flash(f"Studio Gallery updated — {changed} photo slot{'s' if changed != 1 else ''} saved.", "success")
            if log_activity:
                try:
                    log_activity("Studio Gallery updated", f"{changed} photo slot(s)")
                except Exception:
                    app.logger.exception("Could not log Studio Gallery update")
        else:
            flash("No Studio Gallery changes were selected.", "info")

        return redirect("/admin/website/studio-gallery")
