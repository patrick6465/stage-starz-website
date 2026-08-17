from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from config import BASE_DIR


TEEN_PHOTO_PARTS = [
    "asset_payloads/teen_photo/part01.txt",
    "asset_payloads/teen_photo/part02.txt",
    "asset_payloads/teen_photo/part03.txt",
    "asset_payloads/teen_photo/part04.txt",
    "asset_payloads/teen_photo/part05.txt",
    "asset_payloads/teen_photo/part06.txt",
]
TEEN_PHOTO_PATH = BASE_DIR / "site" / "assets" / "images" / "teen-competition-team.webp"
EXPECTED_TEEN_PHOTO_BYTES = 43410


def install_bundled_assets() -> None:
    """Materialize binary web assets stored as text-safe base64 payloads."""
    try:
        encoded = "".join((BASE_DIR / part).read_text(encoding="ascii").strip() for part in TEEN_PHOTO_PARTS)
        payload = base64.b64decode(encoded, validate=True)
        if len(payload) != EXPECTED_TEEN_PHOTO_BYTES:
            raise ValueError(
                f"Teen photo payload is {len(payload)} bytes; expected {EXPECTED_TEEN_PHOTO_BYTES}."
            )
        # WEBP files begin with RIFF....WEBP. Validate before replacing the public asset.
        if payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
            raise ValueError("Teen photo payload is not a valid WEBP image.")
        TEEN_PHOTO_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not TEEN_PHOTO_PATH.exists() or TEEN_PHOTO_PATH.read_bytes() != payload:
            TEEN_PHOTO_PATH.write_bytes(payload)
    except Exception as exc:
        raise RuntimeError(f"Could not install bundled Teen competition photo: {exc}") from exc
