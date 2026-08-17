from __future__ import annotations

import base64
from functools import lru_cache

from flask import Response, request

from config import BASE_DIR


PART_DIR = BASE_DIR / "asset_data" / "teen_competition_team"
EXPECTED_BYTES = 36550
SHARP_URL = "/assets/images/teen-competition-team-sharp.webp"


@lru_cache(maxsize=1)
def _teen_photo_bytes() -> bytes:
    encoded = "".join(
        (PART_DIR / f"part{index:02d}.b64").read_text(encoding="utf-8").strip()
        for index in range(1, 14)
    )
    payload = base64.b64decode(encoded, validate=True)
    if len(payload) != EXPECTED_BYTES:
        raise ValueError(f"Sharp Teen photo is {len(payload)} bytes; expected {EXPECTED_BYTES}.")
    if payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        raise ValueError("Sharp Teen photo payload is not a valid WEBP image.")
    return payload


def register_teen_image_asset(app) -> None:
    """Serve the sharp Teen photo and replace the old blurred asset wherever it appears."""

    @app.route(SHARP_URL, methods=["GET"])
    def teen_competition_team_sharp():
        response = Response(_teen_photo_bytes(), mimetype="image/webp")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.after_request
    def use_sharp_teen_photo(response):
        if response.mimetype != "text/html":
            return response
        if request.path not in {"/teen-competition-team.html", "/admin/website/classes"}:
            return response
        try:
            body = response.get_data(as_text=True)
            body = body.replace("assets/images/teen-competition-team.jpg", SHARP_URL)
            body = body.replace("/assets/images/teen-competition-team.jpg", SHARP_URL)
            body = body.replace("assets/images/teen-competition-team.webp", SHARP_URL)
            body = body.replace("/assets/images/teen-competition-team.webp", SHARP_URL)
            response.set_data(body)
        except Exception:
            app.logger.exception("Could not swap in the sharp Teen competition photo")
        return response
