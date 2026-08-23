from __future__ import annotations

import re

from flask import request

from store_two_shop_experience import _admin_panel, _public_shell, _shop_settings


RESULTS_HEAD = """
  <div class="ss-shop-results-head"><div><h2 id="ssShopResultsTitle">Official Spirit Wear</h2><p id="ssShopResultsCopy">Team and studio apparel offered during limited Stage Starz ordering windows.</p></div></div>
  <div id="ssShopWindowBanner" class="ss-shop-window-banner"></div>
"""


def register_two_shop_injection_fix(app) -> None:
    """Ensure the two-shop HTML panels render even when CSS class names are already present."""

    @app.after_request
    def two_shop_injection_fix(response):
        if (
            request.method != "GET"
            or response.status_code != 200
            or response.mimetype != "text/html"
            or request.path not in {"/admin/store", "/store"}
        ):
            return response

        try:
            body = response.get_data(as_text=True)
            values = _shop_settings()

            if request.path == "/admin/store":
                if 'id="shop-availability"' not in body:
                    marker = '<section class="card" id="new-product">'
                    if marker in body:
                        body = body.replace(marker, _admin_panel(values) + "\n" + marker, 1)
            else:
                if 'aria-label="Choose a Stage Starz shop"' not in body:
                    body = re.sub(
                        r'<section class="hero">.*?</section>',
                        _public_shell(values),
                        body,
                        count=1,
                        flags=re.DOTALL,
                    )
                if 'id="ssShopResultsTitle"' not in body:
                    body = body.replace(
                        '<section id="grid" class="grid"></section>',
                        RESULTS_HEAD + '<section id="grid" class="grid"></section>',
                        1,
                    )

            response.set_data(body)
        except Exception:
            app.logger.exception("Could not apply two-shop HTML injection fix")
        return response
