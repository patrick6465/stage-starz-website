from __future__ import annotations

from flask import request


STYLE = r"""
<style id="ss-store-product-image-fit-fix">
#grid .card .media{
  position:relative!important;
  overflow:hidden!important;
  display:grid!important;
  place-items:center!important;
}
#grid .card .media > img{
  display:block!important;
  width:100%!important;
  height:100%!important;
  max-width:100%!important;
  max-height:100%!important;
  object-fit:contain!important;
  object-position:center!important;
}
</style>
"""


def register_store_product_image_fit_fix(app) -> None:
    """Keep public-store product images fully visible inside their media cards."""

    @app.after_request
    def store_product_image_fit_fix(response):
        if (
            request.method != "GET"
            or request.path != "/store"
            or response.status_code != 200
            or response.mimetype != "text/html"
        ):
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if "ss-store-product-image-fit-fix" not in body:
                body = body.replace("</head>", STYLE + "\n</head>", 1)
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not constrain storefront product images")
        return response
