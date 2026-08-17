from __future__ import annotations

import base64
from functools import lru_cache

from flask import Response

from config import BASE_DIR


PART_DIR = BASE_DIR / "asset_data" / "classes_hero"
EXPECTED_BYTES = 77048
HERO_URL = "/assets/images/classes-hero-dancer.webp"


@lru_cache(maxsize=1)
def _classes_hero_bytes() -> bytes:
    encoded = "".join(
        (PART_DIR / f"part{index:02d}.b64").read_text(encoding="utf-8").strip()
        for index in range(1, 8)
    )
    payload = base64.b64decode(encoded, validate=True)
    if len(payload) != EXPECTED_BYTES:
        raise ValueError(
            f"Classes hero image is {len(payload)} bytes; expected {EXPECTED_BYTES}."
        )
    if payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        raise ValueError("Classes hero payload is not a valid WEBP image.")
    return payload


def register_classes_hero_asset(app) -> None:
    """Serve the user-selected Classes hero from bundled image data."""

    @app.route(HERO_URL, methods=["GET"])
    def classes_hero_dancer():
        response = Response(_classes_hero_bytes(), mimetype="image/webp")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
