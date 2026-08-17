from __future__ import annotations

import html
import re

from flask import request

from database import get_db


PROGRAM_PATH_KEYS = {
    "/preschool-class-registration.html": "preschool",
    "/primary-class-registration.html": "primary",
    "/elementary-class-registration.html": "elementary",
    "/intermediate-advanced-registration.html": "intermediate_advanced",
    "/specialized-class-registration.html": "specialized",
    "/mini-competition-team.html": "mini_competition",
    "/petite-competition-team.html": "petite_competition",
    "/juniorettes-competition-team.html": "juniorettes_competition",
    "/junior-competition-team.html": "junior_competition",
}

FINAL_STYLE = r"""
<style id="ss-program-hero-finalizer-style">
body .hero{
  background-image:none!important;
  background-color:#05050c!important;
}
body .hero:before,
body .hero::before{
  background:
    radial-gradient(circle at 82% 22%,rgba(181,59,212,.24),transparent 28rem),
    radial-gradient(circle at 72% 78%,rgba(32,200,199,.13),transparent 30rem),
    linear-gradient(135deg,#05050c 0%,#10091b 52%,#06050d 100%)!important;
  background-image:
    radial-gradient(circle at 82% 22%,rgba(181,59,212,.24),transparent 28rem),
    radial-gradient(circle at 72% 78%,rgba(32,200,199,.13),transparent 30rem),
    linear-gradient(135deg,#05050c 0%,#10091b 52%,#06050d 100%)!important;
  background-color:#05050c!important;
}
</style>
"""


def _saved_photo(path: str) -> str:
    page_key = PROGRAM_PATH_KEYS.get(path)
    if not page_key:
        return ""
    connection = None
    try:
        connection = get_db()
        row = connection.execute(
            "SELECT hero_image FROM class_page_content WHERE page_key=?",
            (page_key,),
        ).fetchone()
        if not row:
            return ""
        try:
            value = row["hero_image"]
        except (TypeError, KeyError, IndexError):
            value = row[0]
        value = (value or "").strip()
        return value if value.startswith("/uploads/") else ""
    except Exception:
        return ""
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def _strip_legacy_hero_urls(body: str) -> str:
    """Remove old photo URLs from every .hero:before rule, including mobile media rules."""
    block_pattern = re.compile(
        r'(?P<start>\.hero(?:::|:)before\s*\{)(?P<body>[^{}]*)(?P<end>\})',
        flags=re.IGNORECASE | re.DOTALL,
    )
    url_pattern = re.compile(
        r'url\(\s*["\']?[^\)"\']+["\']?\s*\)',
        flags=re.IGNORECASE,
    )

    def scrub(match: re.Match) -> str:
        css = url_pattern.sub("linear-gradient(#05050c,#05050c)", match.group("body"))
        return match.group("start") + css + match.group("end")

    return block_pattern.sub(scrub, body)


def _force_photo_card_src(body: str, photo_url: str) -> str:
    if not photo_url:
        return body
    safe_url = html.escape(photo_url, quote=True)
    pattern = re.compile(
        r'(<figure\b[^>]*class=["\'][^"\']*ss-program-photo-panel[^"\']*["\'][^>]*>.*?'
        r'<img\b[^>]*\bsrc=["\'])([^"\']*)(["\'])',
        flags=re.IGNORECASE | re.DOTALL,
    )
    return pattern.sub(lambda m: m.group(1) + safe_url + m.group(3), body, count=1)


def register_program_hero_finalizer(app) -> None:
    """Apply the final hero state after the photo-card renderer has run."""

    @app.after_request
    def finalize_program_hero(response):
        if request.path not in PROGRAM_PATH_KEYS or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)

            # The old class pages contain their hero picture in CSS. Eliminate that
            # image completely so the photo can exist only in the new framed card.
            body = _strip_legacy_hero_urls(body)

            # If the owner published a new image in the backend, make the framed
            # card use that exact saved image instead of any built-in fallback.
            saved_photo = _saved_photo(request.path)
            if saved_photo:
                body = _force_photo_card_src(body, saved_photo)

            # This style is deliberately appended at the end of the document so it
            # wins over old desktop/mobile background rules and refinement CSS.
            if 'id="ss-program-hero-finalizer-style"' not in body:
                body = body.replace("</body>", FINAL_STYLE + "</body>", 1)

            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        except Exception:
            app.logger.exception("Could not finalize program hero")
        return response
