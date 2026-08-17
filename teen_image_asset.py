from __future__ import annotations

import base64
from functools import lru_cache

from flask import Response

from config import BASE_DIR


PART_DIR = BASE_DIR / "asset_data" / "teen_competition_team"


@lru_cache(maxsize=1)
def _teen_photo_bytes() -> bytes:
    encoded = "".join(
        (PART_DIR / f"part{index:02d}.b64").read_text(encoding="utf-8").strip()
        for index in range(1, 14)
    )
    return base64.b64decode(encoded)


def register_teen_image_asset(app) -> None:
    """Serve the sharp Teen Competition Team photo from the bundled image data."""

    @app.route("/assets/images/teen-competition-team-sharp.webp", methods=["GET"])
    def teen_competition_team_sharp():
        response = Response(_teen_photo_bytes(), mimetype="image/webp")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
