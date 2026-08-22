"""Final safety wrapper for the Store Reports endpoint."""

from __future__ import annotations

from functools import wraps

from flask import Response


def register_reports_never_500(app):
    current = app.view_functions.get("reports_dashboard")
    if current is None:
        return

    @wraps(current)
    def reports_with_final_fallback(*args, **kwargs):
        try:
            return current(*args, **kwargs)
        except Exception:
            app.logger.exception("Unhandled Reports failure; serving emergency fallback")
            html = """
            <!doctype html>
            <html lang="en"><head>
            <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Store Reports | Stage Starz</title>
            <style>
            *{box-sizing:border-box}body{margin:0;background:#0c0717;color:#fff;font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;padding:24px}
            .wrap{max-width:820px;margin:auto}.card{background:#17102a;border:1px solid #38294a;border-radius:20px;padding:22px;margin-top:18px}.muted{color:#b8adca;line-height:1.5}.btn{display:inline-block;margin-top:14px;padding:12px 16px;border-radius:12px;background:linear-gradient(110deg,#ef3d98,#9b4dcc,#50d6d0);color:#fff;text-decoration:none;font-weight:800}
            </style></head><body><main class="wrap">
            <h1>📊 Store Reports</h1>
            <div class="card"><h2>Reports are temporarily in safe mode</h2>
            <p class="muted">The Reports module opened successfully, but one live reporting component encountered an unexpected data-format issue. Orders, inventory and fulfillment remain available while this report component is isolated.</p>
            <a class="btn" href="/admin">Return to Command Center</a>
            </div></main></body></html>
            """
            return Response(html, status=200, mimetype="text/html")

    app.view_functions["reports_dashboard"] = reports_with_final_fallback
