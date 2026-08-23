"""Polish Command Center greetings and activity timestamps for Stage Starz local time."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import request

from communication_time_polish import register_communication_time_polish
from portal_time_polish import register_portal_time_polish
from workflow_counter_fix import register_workflow_counter_fix


STUDIO_TZ = ZoneInfo("America/New_York")


def _local_greeting() -> str:
    hour = datetime.now(STUDIO_TZ).hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def _format_activity_timestamp(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return text
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if value.tzinfo is None:
            # Railway/PostgreSQL activity timestamps are stored in UTC.
            value = value.replace(tzinfo=timezone.utc)
        local = value.astimezone(STUDIO_TZ)
        return local.strftime("%b %d, %Y · %I:%M %p").replace(" 0", " ")
    except (TypeError, ValueError):
        return text


def register_command_center_time_polish(app) -> None:
    """Use America/New_York time on the Command Center without changing DB storage."""

    # The workflow summary historically counted unread notifications across all
    # active admin accounts. Keep that card aligned with Notification Center by
    # showing only unread notifications owned by the currently logged-in admin.
    register_workflow_counter_fix(app)

    # Communication pages historically displayed Railway/PostgreSQL UTC values
    # verbatim, including microseconds. Format them for the studio's local time.
    register_communication_time_polish(app)

    # Parent and Staff access centers use the same UTC database timestamps.
    register_portal_time_polish(app)

    @app.after_request
    def polish_command_center_time(response):
        if request.path.rstrip("/") != "/admin" or request.method != "GET":
            return response
        if response.status_code != 200 or response.mimetype != "text/html":
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body:
                return response

            greeting = _local_greeting()
            body = re.sub(
                r"<h2>Good (?:morning|afternoon|evening),",
                f"<h2>{greeting},",
                body,
                count=1,
            )

            def replace_activity_time(match):
                return (
                    match.group(1)
                    + _format_activity_timestamp(match.group(2))
                    + match.group(3)
                )

            body = re.sub(
                r'(<span class="activity-time">)([^<]*)(</span>)',
                replace_activity_time,
                body,
            )
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply Command Center time polish")
        return response
