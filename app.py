from __future__ import annotations

import os
import threading

from flask import Flask, request

from config import SECRET_KEY
from database import Cursor, init_db
from routes_admin import register_admin_routes
from routes_public import register_public_routes
from routes_reports import register_report_routes


def _postgres_lastrowid(cursor: Cursor) -> int:
    row = cursor._cursor.connection.execute("SELECT lastval() AS id").fetchone()
    return int(row["id"])


# Preserve the existing route code's cursor.lastrowid behavior while PostgreSQL
# supplies IDs from SERIAL sequences.
Cursor.lastrowid = property(_postgres_lastrowid)

_database_ready = False
_database_lock = threading.Lock()


def _ensure_database() -> None:
    """Initialize PostgreSQL after the web process is already accepting traffic.

    Railway can start the application before the private database network is
    fully ready. Keeping this work out of module import allows /health to answer
    immediately instead of causing Gunicorn to exit during deployment.
    """
    global _database_ready
    if _database_ready:
        return
    with _database_lock:
        if _database_ready:
            return
        init_db()
        _database_ready = True


def create_app() -> Flask:
    application = Flask(__name__)
    application.secret_key = SECRET_KEY
    application.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,
    )
    register_public_routes(application)
    register_admin_routes(application)
    register_report_routes(application)

    @application.before_request
    def initialize_database_when_needed():
        # The health endpoint must never depend on database availability.
        if request.endpoint == "health_check":
            return None
        _ensure_database()
        return None

    return application


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
