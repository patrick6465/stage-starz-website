from __future__ import annotations

import html as html_lib
import re
from pathlib import Path

from flask import Response, flash, redirect, render_template, request

from config import BASE_DIR
from database import get_db


CLASS_PAGES = {
    "preschool": {
        "label": "Preschool",
        "filename": "preschool-class-registration.html",
        "audience": "Ages 3–4",
    },
    "primary": {
        "label": "Primary",
        "filename": "primary-class-registration.html",
        "audience": "Ages 5–8",
    },
    "elementary": {
        "label": "Elementary",
        "filename": "elementary-class-registration.html",
        "audience": "Ages 9–12",
    },
    "intermediate_advanced": {
        "label": "Intermediate & Advanced",
        "filename": "intermediate-advanced-registration.html",
        "audience": "Experienced dancers",
    },
    "specialized": {
        "label": "Specialized",
        "filename": "specialized-class-registration.html",
        "audience": "Private & small-group training",
    },
}


def ensure_class_page_content_schema() -> None:
    connection = get_db()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS class_page_content (
            page_key TEXT PRIMARY KEY,
            hero_description TEXT NOT NULL DEFAULT '',
            program_description TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()


def _site_path(filename: str) -> Path:
    return BASE_DIR / "site" / filename


def _read_source(filename: str) -> str:
    return _site_path(filename).read_text(encoding="utf-8")


def _html_block_to_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<li[^>]*>", "- ", value, flags=re.IGNORECASE)
    value = re.sub(r"</li\s*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html_lib.unescape(value)
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _extract_original_content(filename: str) -> dict[str, str]:
    source = _read_source(filename)
    hero_match = re.search(
        r'<p\s+class="lead">(.*?)</p>',
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    details_match = re.search(
        r'<div\s+class="copied-content">(.*?)</div>',
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return {
        "hero_description": _html_block_to_text(hero_match.group(1)) if hero_match else "",
        "program_description": _html_block_to_text(details_match.group(1)) if details_match else "",
    }


def _plain_text_to_program_html(value: str) -> str:
    """Turn simple editor text into safe paragraphs and bullet lists."""
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    parts: list[str] = []
    paragraph: list[str] = []
    bullets: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            escaped_lines = [html_lib.escape(line.strip()) for line in paragraph if line.strip()]
            if escaped_lines:
                parts.append("<p>" + "<br>".join(escaped_lines) + "</p>")
            paragraph = []

    def flush_bullets() -> None:
        nonlocal bullets
        if bullets:
            items = "".join(f"<li>{html_lib.escape(item)}</li>" for item in bullets)
            parts.append(f"<ul>{items}</ul>")
            bullets = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_bullets()
            continue
        if line.startswith("- ") or line.startswith("• "):
            flush_paragraph()
            bullets.append(line[2:].strip())
            continue
        flush_bullets()
        paragraph.append(line)

    flush_paragraph()
    flush_bullets()
    return "\n".join(parts)


def _get_saved_content(page_key: str):
    connection = get_db()
    row = connection.execute(
        """
        SELECT page_key, hero_description, program_description, updated_at
        FROM class_page_content
        WHERE page_key=?
        """,
        (page_key,),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def _apply_saved_content(source: str, saved: dict[str, str]) -> str:
    hero = saved.get("hero_description", "").strip()
    details = saved.get("program_description", "").strip()

    escaped_hero = html_lib.escape(hero)
    source = re.sub(
        r'(<p\s+class="lead">).*?(</p>)',
        lambda match: match.group(1) + escaped_hero + match.group(2),
        source,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Keep the search description aligned with the editable hero description.
    source = re.sub(
        r'(<meta\s+name="description"\s+content=").*?("\s*/?>)',
        lambda match: match.group(1) + html_lib.escape(hero, quote=True) + match.group(2),
        source,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )

    details_html = _plain_text_to_program_html(details)
    source = re.sub(
        r'(<div\s+class="copied-content">).*?(</div>)',
        lambda match: match.group(1) + details_html + match.group(2),
        source,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return source


def register_class_content_editor(app, permission_required, log_activity=None) -> None:
    """Add an admin editor and database-backed descriptions to class pages."""
    ensure_class_page_content_schema()

    def make_public_class_view(page_key: str):
        page = CLASS_PAGES[page_key]

        def public_class_page():
            source = _read_source(page["filename"])
            saved = _get_saved_content(page_key)
            if saved:
                source = _apply_saved_content(source, saved)
            response = Response(source, mimetype="text/html")
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response

        return public_class_page

    # Exact rules take precedence over the site's generic static-file route.
    for page_key, page in CLASS_PAGES.items():
        app.add_url_rule(
            f"/{page['filename']}",
            endpoint=f"editable_class_page_{page_key}",
            view_func=make_public_class_view(page_key),
            methods=["GET"],
        )

    @app.route("/admin/website/classes")
    @permission_required("website")
    def class_description_editor():
        pages = []
        for page_key, page in CLASS_PAGES.items():
            original = _extract_original_content(page["filename"])
            saved = _get_saved_content(page_key)
            pages.append(
                {
                    "key": page_key,
                    "label": page["label"],
                    "filename": page["filename"],
                    "audience": page["audience"],
                    "hero_description": (
                        saved["hero_description"] if saved else original["hero_description"]
                    ),
                    "program_description": (
                        saved["program_description"] if saved else original["program_description"]
                    ),
                    "is_custom": bool(saved),
                    "updated_at": saved.get("updated_at") if saved else None,
                }
            )
        return render_template("class_description_editor.html", pages=pages)

    @app.route("/admin/website/classes/save", methods=["POST"])
    @permission_required("website")
    def save_class_description():
        page_key = request.form.get("page_key", "").strip()
        if page_key not in CLASS_PAGES:
            flash("That class page could not be found.", "error")
            return redirect("/admin/website/classes")

        page = CLASS_PAGES[page_key]
        action = request.form.get("action", "save")

        connection = get_db()
        if action == "reset":
            connection.execute(
                "DELETE FROM class_page_content WHERE page_key=?",
                (page_key,),
            )
            connection.commit()
            connection.close()
            flash(f"{page['label']} was restored to the original website text.", "success")
            if log_activity:
                try:
                    log_activity(
                        "Class page description restored",
                        page["label"],
                    )
                except Exception:
                    app.logger.exception("Could not log class description reset")
            return redirect(f"/admin/website/classes#page-{page_key}")

        hero_description = request.form.get("hero_description", "").strip()[:1500]
        program_description = request.form.get("program_description", "").strip()[:20000]

        if not hero_description:
            connection.close()
            flash("The short page description cannot be blank.", "error")
            return redirect(f"/admin/website/classes#page-{page_key}")
        if not program_description:
            connection.close()
            flash("The program description cannot be blank.", "error")
            return redirect(f"/admin/website/classes#page-{page_key}")

        connection.execute(
            """
            INSERT INTO class_page_content (
                page_key, hero_description, program_description, updated_at
            ) VALUES (?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(page_key) DO UPDATE SET
                hero_description=excluded.hero_description,
                program_description=excluded.program_description,
                updated_at=CURRENT_TIMESTAMP
            """,
            (page_key, hero_description, program_description),
        )
        connection.commit()
        connection.close()

        if log_activity:
            try:
                log_activity(
                    "Class page description updated",
                    page["label"],
                )
            except Exception:
                app.logger.exception("Could not log class description update")

        flash(f"{page['label']} descriptions published.", "success")
        return redirect(f"/admin/website/classes#page-{page_key}")

    @app.after_request
    def add_class_editor_to_command_center(response):
        """Surface the editor beside Homepage Editor without altering dashboard markup."""
        if request.path != "/admin" or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            needle = '<a href="/admin/website/homepage">🏠 Homepage Editor</a>'
            new_link = '<a href="/admin/website/classes">✏️ Class Description Editor</a>'
            if needle in body and new_link not in body:
                response.set_data(body.replace(needle, needle + new_link, 1))
        except Exception:
            app.logger.exception("Could not add Class Description Editor link to dashboard")
        return response
