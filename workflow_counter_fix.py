"""Keep the Workflow Center unread count scoped to the logged-in admin."""

import re

from flask import request, session

from database import get_db


def register_workflow_counter_fix(app):
    @app.after_request
    def _scope_workflow_unread_counter(response):
        if (
            request.path != "/admin/workflows"
            or response.status_code != 200
            or response.mimetype != "text/html"
            or not session.get("admin_user_id")
        ):
            return response

        connection = get_db()
        try:
            row = connection.execute(
                """
                SELECT COUNT(*) AS unread_count
                FROM notifications
                WHERE admin_user_id=?
                  AND dismissed_at IS NULL
                  AND read_at IS NULL
                """,
                (int(session["admin_user_id"]),),
            ).fetchone()
            unread_count = int(row["unread_count"] or 0) if row else 0
        finally:
            connection.close()

        html = response.get_data(as_text=True)
        html = re.sub(
            r'<div class="value">\d+</div><div class="muted">Unread notifications</div>',
            f'<div class="value">{unread_count}</div><div class="muted">Unread notifications</div>',
            html,
            count=1,
        )
        response.set_data(html)
        response.headers["Content-Length"] = str(len(response.get_data()))
        return response
