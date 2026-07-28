from __future__ import annotations

from flask import redirect, render_template, request, url_for

from services import login_required


def register_menu_routes(app):
    @app.before_request
    def redirect_admin_dashboard_to_menu():
        if request.endpoint == "admin_dashboard":
            return redirect(url_for("admin_menu"))
        return None

    @app.route("/admin/menu")
    @login_required
    def admin_menu():
        return render_template("admin_menu.html")

    @app.route("/admin/products")
    @login_required
    def admin_products():
        return app.view_functions["admin_dashboard"]()
