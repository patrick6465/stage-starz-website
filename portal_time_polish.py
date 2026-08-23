"""Format Parent/Staff Portal admin timestamps in Stage Starz local time."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import request


STUDIO_TZ = ZoneInfo("America/New_York")
_RAW_DB_TIMESTAMP = re.compile(
    r"(?<!\d)(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(?!\d)"
)


def _format_timestamp(match: re.Match[str]) -> str:
    raw = f"{match.group(1)} {match.group(2)}"
    if match.group(3):
        raw += f".{match.group(3)}"
    try:
        value = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        local = value.astimezone(STUDIO_TZ)
        return local.strftime("%b %d, %Y · %I:%M %p").replace(" 0", " ")
    except (TypeError, ValueError):
        return match.group(0)


def register_portal_time_polish(app) -> None:
    """Keep access-center timestamps readable and local without changing DB storage."""

    @app.after_request
    def polish_portal_admin_times(response):
        if request.method != "GET":
            return response
        if not (
            request.path.startswith("/admin/parent-portal")
            or request.path.startswith("/admin/staff-portal")
        ):
            return response
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body:
                return response
            body = _RAW_DB_TIMESTAMP.sub(_format_timestamp, body)
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply portal timestamp polish")
        return response
