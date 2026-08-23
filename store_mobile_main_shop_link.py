from __future__ import annotations

from flask import request


MAIN_SHOP_URL = "https://www.stagestarzdance.net/shop"

STYLE = r"""
<style id="ss-main-shop-manager-link-style">
.ss-main-shop-manager-action{border-color:rgba(83,215,210,.36)!important}
.ss-main-shop-manager-action:hover{border-color:rgba(83,215,210,.72)!important;background:rgba(83,215,210,.09)!important}
@media(max-width:760px){
  .ss-main-shop-manager-action{display:inline-flex!important}
}
</style>
"""

LINK = f"""
<a class="ss-store-action ss-main-shop-manager-action" href="{MAIN_SHOP_URL}" target="_blank" rel="noopener" title="Open the Stage Starz Shop page on the main website">↗ <span class="wide-label">Main Website Shop</span></a>
"""


def register_store_mobile_main_shop_link(app) -> None:
    """Keep the main-website shop shortcut inside Store Manager, not the public store."""

    @app.after_request
    def store_manager_main_shop_link(response):
        if (
            request.method != "GET"
            or request.path != "/admin/store"
            or response.status_code != 200
            or response.mimetype != "text/html"
        ):
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if "ss-main-shop-manager-link-style" not in body:
                body = body.replace("</head>", STYLE + "\n</head>", 1)
            if "ss-main-shop-manager-action" not in body:
                marker = '<a class="ss-store-action" href="/admin">◈ <span class="wide-label">Command Center</span></a>'
                if marker in body:
                    body = body.replace(marker, LINK + "\n      " + marker, 1)
                else:
                    actions = '<div class="ss-store-actions">'
                    if actions in body:
                        body = body.replace(actions, actions + "\n      " + LINK, 1)
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not add main website Shop link to Store Manager")
        return response
