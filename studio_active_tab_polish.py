from __future__ import annotations

from flask import request


ACTIVE_TAB_SCRIPT = r"""
<script id="ss-studio-active-tab-script">
(function(){
  function showActiveStudioTab(){
    var nav=document.querySelector('.ss-studio-tabs');
    var active=nav&&nav.querySelector('.ss-studio-tab.active');
    if(!nav||!active)return;
    var left=active.offsetLeft-(nav.clientWidth-active.offsetWidth)/2;
    nav.scrollLeft=Math.max(0,left);
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',showActiveStudioTab,{once:true});
  }else{
    showActiveStudioTab();
  }
  window.addEventListener('pageshow',showActiveStudioTab);
})();
</script>
"""


def register_studio_active_tab_polish(app) -> None:
    """Center the active Studio Operations tab in the horizontal mobile nav."""

    @app.after_request
    def keep_active_studio_tab_visible(response):
        if request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html":
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if 'id="ss-studio-workspace"' not in body:
                return response
            if 'id="ss-studio-active-tab-script"' in body:
                return response
            if "</body>" in body:
                body = body.replace("</body>", ACTIVE_TAB_SCRIPT + "</body>", 1)
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not center active Studio Operations tab")
        return response
