from __future__ import annotations

import os

from flask import Flask

from config import SECRET_KEY
from database import init_db
from routes_admin import register_admin_routes
from routes_public import register_public_routes


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
    init_db()
    return application


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
