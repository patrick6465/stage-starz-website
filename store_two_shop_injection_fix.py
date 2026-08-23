from __future__ import annotations

import re

from flask import request

from store_two_shop_experience import _admin_panel, _public_shell, _shop_settings


RESULTS_HEAD = """
  <div class="ss-shop-results-head"><div><h2 id="ssShopResultsTitle">Official Spirit Wear</h2><p id="ssShopResultsCopy">Team and studio apparel offered during limited Stage Starz ordering windows.</p></div></div>
  <div id="ssShopWindowBanner" class="ss-shop-window-banner"></div>
"""

PRODUCT_IMAGE_FIT_STYLE = r"""
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

PRODUCT_IMAGE_FIT_SCRIPT = r"""
<script id="ss-store-product-image-fit-script">
(function(){
  function fitStoreImages(){
    document.querySelectorAll('#grid .card .media img').forEach(function(img){
      img.style.setProperty('display','block','important');
      img.style.setProperty('width','100%','important');
      img.style.setProperty('height','100%','important');
      img.style.setProperty('max-width','100%','important');
      img.style.setProperty('max-height','100%','important');
      img.style.setProperty('object-fit','contain','important');
      img.style.setProperty('object-position','center','important');
    });
  }

  document.addEventListener('DOMContentLoaded',function(){
    fitStoreImages();
    var grid=document.getElementById('grid');
    if(grid){
      new MutationObserver(fitStoreImages).observe(grid,{childList:true,subtree:true});
    }
  });
  window.addEventListener('load',fitStoreImages);
})();
</script>
"""


def register_two_shop_injection_fix(app) -> None:
    """Ensure the two-shop HTML panels render and product photos stay inside their cards."""

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
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            values = _shop_settings()

            if request.path == "/admin/store":
                if 'id="shop-availability"' not in body:
                    marker = '<section class="card" id="new-product">'
                    if marker in body:
                        body = body.replace(marker, _admin_panel(values) + "\n" + marker, 1)
            else:
                if "ss-store-product-image-fit-fix" not in body:
                    body = body.replace("</head>", PRODUCT_IMAGE_FIT_STYLE + "\n</head>", 1)
                if "ss-store-product-image-fit-script" not in body:
                    body = body.replace("</body>", PRODUCT_IMAGE_FIT_SCRIPT + "\n</body>", 1)
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
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply two-shop HTML injection fix")
        return response
