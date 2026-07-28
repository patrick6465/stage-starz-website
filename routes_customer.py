from __future__ import annotations

from functools import wraps

from flask import redirect, render_template, request, session, url_for

from database import get_db


def customer_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("customer_email"):
            return redirect(url_for("customer_center"))
        return view(*args, **kwargs)
    return wrapped


def register_customer_routes(app):
    @app.after_request
    def add_customer_center_store_link(response):
        if request.path == "/store" and response.mimetype == "text/html":
            html = response.get_data(as_text=True)
            admin_link = '<a href="/admin" style="color:white;text-decoration:none;font-weight:800;white-space:nowrap">Store Admin</a>'
            customer_link = '<a href="/customer-center" style="color:white;text-decoration:none;font-weight:800;white-space:nowrap">Customer Center</a>'
            if customer_link not in html and admin_link in html:
                response.set_data(html.replace(admin_link, customer_link + admin_link, 1))
        return response

    @app.route("/customer-center", methods=["GET", "POST"])
    def customer_center():
        error = ""
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            order_number = request.form.get("order_number", "").strip()
            connection = get_db()
            order = connection.execute(
                "SELECT id,customer_name,customer_email FROM orders WHERE lower(trim(customer_email))=? AND lower(trim(order_number))=?",
                (email, order_number.lower()),
            ).fetchone()
            connection.close()
            if order:
                session["customer_email"] = order["customer_email"].strip().lower()
                session["customer_name"] = order["customer_name"]
                return redirect(url_for("customer_dashboard"))
            error = "We could not find an order matching that email address and order number."
        if session.get("customer_email"):
            return redirect(url_for("customer_dashboard"))
        return render_template("customer_login.html", error=error)

    @app.route("/customer-center/dashboard")
    @customer_login_required
    def customer_dashboard():
        email = session["customer_email"]
        connection = get_db()
        orders = connection.execute(
            "SELECT id,order_number,created_at,status,payment_status,fulfillment_method,total FROM orders WHERE lower(trim(customer_email))=? ORDER BY created_at DESC",
            (email,),
        ).fetchall()
        connection.close()

        active_statuses = {"New", "Waiting to Order", "Ordered", "Received", "Ready for Pickup"}
        active_orders = [order for order in orders if order["status"] in active_statuses]
        ready_orders = [order for order in orders if order["status"] == "Ready for Pickup"]
        shipping_orders = [order for order in active_orders if order["fulfillment_method"] == "shipping"]
        return render_template(
            "customer_dashboard.html",
            customer_name=session.get("customer_name", "Customer"),
            orders=orders,
            active_count=len(active_orders),
            ready_count=len(ready_orders),
            shipping_count=len(shipping_orders),
        )

    @app.route("/customer-center/order/<int:order_id>")
    @customer_login_required
    def customer_order(order_id: int):
        email = session["customer_email"]
        connection = get_db()
        order = connection.execute(
            "SELECT * FROM orders WHERE id=? AND lower(trim(customer_email))=?",
            (order_id, email),
        ).fetchone()
        if not order:
            connection.close()
            return redirect(url_for("customer_dashboard"))
        items = connection.execute(
            "SELECT * FROM order_items WHERE order_id=? ORDER BY id",
            (order_id,),
        ).fetchall()
        connection.close()
        return render_template("customer_order.html", order=order, items=items)

    @app.route("/customer-center/logout")
    def customer_logout():
        session.pop("customer_email", None)
        session.pop("customer_name", None)
        return redirect(url_for("customer_center"))
