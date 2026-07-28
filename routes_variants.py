from __future__ import annotations

from flask import abort, redirect, render_template, request, url_for

from database import get_db
from inventory import ensure_inventory_schema, record_inventory_movement
from services import get_settings, login_required
from variants import refresh_product_stock, sync_product_variants


def register_variant_routes(app):
    @app.route('/admin/variants')
    @login_required
    def admin_variants():
        connection = get_db()
        ensure_inventory_schema(connection)
        settings = get_settings(connection)
        try:
            threshold = max(0, int(settings.get('low_stock_threshold', '5') or 5))
        except ValueError:
            threshold = 5

        products = [dict(row) for row in connection.execute(
            'SELECT id,name,category,stock,track_variants,sizes,colors,show_color FROM products ORDER BY category,name'
        ).fetchall()]
        for product in products:
            if product['track_variants']:
                sync_product_variants(connection, product['id'])
            product['variants'] = [dict(row) for row in connection.execute(
                '''SELECT id,size,color,stock,active,
                          CASE WHEN stock<=0 THEN 'Out of stock'
                               WHEN stock<=? THEN 'Low stock'
                               ELSE 'Healthy' END AS status
                   FROM product_variants WHERE product_id=? AND active=1
                   ORDER BY size,color''',
                (threshold, product['id']),
            ).fetchall()]
        connection.commit()
        connection.close()
        return render_template('variants.html', products=products, threshold=threshold)

    @app.route('/admin/variants/<int:product_id>/save', methods=['POST'])
    @login_required
    def save_variants(product_id: int):
        connection = get_db()
        ensure_inventory_schema(connection)
        product = connection.execute(
            'SELECT id,name,stock,track_variants FROM products WHERE id=? FOR UPDATE',
            (product_id,),
        ).fetchone()
        if not product:
            connection.rollback()
            connection.close()
            abort(404)

        enable = request.form.get('track_variants') == 'on'
        old_total = int(product['stock'])
        connection.execute('UPDATE products SET track_variants=? WHERE id=?', (1 if enable else 0, product_id))

        if enable:
            sync_product_variants(connection, product_id)
            variants = connection.execute(
                'SELECT id,stock FROM product_variants WHERE product_id=? AND active=1 FOR UPDATE',
                (product_id,),
            ).fetchall()
            for variant in variants:
                raw = request.form.get(f"stock_{variant['id']}", str(variant['stock']))
                try:
                    quantity = max(0, int(raw))
                except (TypeError, ValueError):
                    quantity = int(variant['stock'])
                connection.execute('UPDATE product_variants SET stock=? WHERE id=?', (quantity, variant['id']))
            new_total = refresh_product_stock(connection, product_id)
        else:
            try:
                new_total = max(0, int(request.form.get('product_stock', old_total)))
            except (TypeError, ValueError):
                new_total = old_total
            connection.execute('UPDATE products SET stock=? WHERE id=?', (new_total, product_id))

        change = new_total - old_total
        if change:
            record_inventory_movement(
                connection,
                product_id,
                change,
                new_total,
                'Variant inventory update' if enable else 'Product inventory update',
                note=request.form.get('note', '').strip()[:250],
            )
        connection.commit()
        connection.close()
        return redirect(url_for('admin_variants'))
