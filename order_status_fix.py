from __future__ import annotations

import logging

from flask import flash, redirect, request, url_for

from app import get_db, log_activity, login_required, sync_customer_from_email

logger = logging.getLogger("stage_starz.order_status_fix")


def register_order_status_fix(app) -> None:
    """Replace the legacy order-status handler with a failure-resistant version.

    The order status itself is the primary transaction. CRM/family refresh and
    activity logging are useful follow-up work, but neither should turn a
    successfully committed status change into a 500 error page.
    """

    @login_required
    def safe_update_order_status(order_id: int):
        allowed = {"New", "Processing", "Ready", "Completed", "Cancelled"}
        status = request.form.get("status", "").strip()
        if status not in allowed:
            flash("Invalid order status.", "error")
            return redirect(url_for("order_detail", order_id=order_id))

        connection = None
        order = None
        try:
            connection = get_db()
            order = connection.execute(
                "SELECT order_number, customer_email FROM orders WHERE id=?",
                (order_id,),
            ).fetchone()
            if not order:
                flash("Order not found.", "error")
                return redirect(url_for("orders_dashboard"))

            connection.execute(
                "UPDATE orders SET status=? WHERE id=?",
                (status, order_id),
            )
            connection.commit()
        except Exception:
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass
            logger.exception("Order status update failed for order %s", order_id)
            flash("The order status could not be updated. Please try again.", "error")
            return redirect(url_for("order_detail", order_id=order_id))
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

        # These are intentionally best-effort after the primary update commits.
        try:
            customer_email = (order["customer_email"] or "").strip()
            if customer_email:
                sync_customer_from_email(customer_email)
        except Exception:
            logger.exception(
                "Customer/family sync failed after order %s status update",
                order_id,
            )

        try:
            log_activity(
                "Order status updated",
                f"{order['order_number']} → {status}",
            )
        except Exception:
            logger.exception(
                "Activity logging failed after order %s status update",
                order_id,
            )

        flash("Order status updated.", "success")
        return redirect(url_for("order_detail", order_id=order_id))

    safe_update_order_status.__name__ = "safe_update_order_status"
    app.view_functions["update_order_status"] = safe_update_order_status
