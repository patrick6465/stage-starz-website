from __future__ import annotations

from flask import request


MAIN_SHOP_URL = "https://www.stagestarzdance.net/shop"

STYLE = r"""
<style id="ss-mobile-main-shop-link-style">
.ss-mobile-main-shop-link-wrap{display:none}
@media(max-width:700px){
  .ss-mobile-main-shop-link-wrap{
    display:block;
    padding:12px 18px 0;
    background:#0b0712;
  }
  .ss-mobile-main-shop-link{
    display:flex;
    align-items:center;
    justify-content:center;
    width:100%;
    min-height:46px;
    padding:11px 14px;
    border:1px solid rgba(83,215,210,.36);
    border-radius:14px;
    color:#fff!important;
    background:linear-gradient(110deg,rgba(132,63,208,.28),rgba(25,159,171,.20));
    text-decoration:none!important;
    font-weight:900;
    font-size:.92rem;
    box-shadow:0 8px 24px rgba(0,0,0,.18);
  }
  .ss-mobile-main-shop-link:active{transform:translateY(1px)}
}
</style>
"""

LINK = f"""
<div class="ss-mobile-main-shop-link-wrap" id="ssMobileMainShopLink">
  <a class="ss-mobile-main-shop-link" href="{MAIN_SHOP_URL}">← Stage Starz Shop Main Page</a>
</div>
"""


def register_store_mobile_main_shop_link(app) -> None:
    @app.after_request
    def store_mobile_main_shop_link(response):
        if (
            request.method != "GET"
            or request.path != "/store"
            or response.status_code != 200
            or response.mimetype != "text/html"
        ):
            return response
        try:
            body = response.get_data(as_text=True)
            if "ss-mobile-main-shop-link-style" not in body:
                body = body.replace("</head>", STYLE + "\n</head>", 1)
            if 'id="ssMobileMainShopLink"' not in body:
                body = body.replace("</header>", "</header>\n" + LINK, 1)
            response.set_data(body)
        except Exception:
            app.logger.exception("Could not add mobile main-shop link")
        return response
