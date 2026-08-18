from __future__ import annotations

import re

from flask import request


DETAIL_TITLES = {
    "/admin/families": ("🏠", "Family Profile"),
    "/admin/customers": ("👥", "Customer Profile"),
    "/admin/students": ("🩰", "Student Profile"),
    "/admin/classes": ("📚", "Class Details"),
    "/admin/teachers": ("👩‍🏫", "Teacher Profile"),
    "/admin/attendance": ("✅", "Attendance Details"),
    "/admin/billing": ("💳", "Billing Account"),
    "/admin/costumes": ("👗", "Costume Details"),
}


def _detail_title(path: str):
    for prefix, value in DETAIL_TITLES.items():
        if path.startswith(prefix + "/"):
            return value
    return None


def register_studio_detail_title_polish(app) -> None:
    """Give nested Studio Operations pages a specific workspace title."""

    @app.after_request
    def polish_studio_detail_title(response):
        if request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html":
            return response

        detail = _detail_title(request.path.rstrip("/"))
        if not detail:
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if 'id="ss-studio-workspace"' not in body:
                return response

            icon, title = detail
            header_start = body.find('<header id="ss-studio-workspace">')
            header_end = body.find("</header>", header_start)
            if header_start < 0 or header_end < 0:
                return response

            header_end += len("</header>")
            header = body[header_start:header_end]
            updated = re.sub(
                r'<h1>.*?</h1>',
                f'<h1>{icon} {title}</h1>',
                header,
                count=1,
                flags=re.DOTALL,
            )
            if updated == header:
                return response

            body = body[:header_start] + updated + body[header_end:]
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not polish Studio Operations detail title")
        return response
