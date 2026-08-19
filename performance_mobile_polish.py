from __future__ import annotations

from flask import request


PERFORMANCE_PREFIXES = (
    "/admin/competitions",
    "/admin/recitals",
    "/admin/production",
    "/admin/ticketing",
)


PERFORMANCE_MOBILE_STYLE = r"""
<style id="ss-performance-mobile-polish-style">
@media(max-width:760px){
  body .wrap{
    width:calc(100% - 20px)!important;
    max-width:none!important;
  }
  body .card,
  body .panel,
  body .section,
  body .table-wrap{
    padding:16px!important;
  }
  body .stats{
    grid-template-columns:repeat(2,minmax(0,1fr))!important;
    gap:10px!important;
  }
  body .stats .card{
    min-width:0!important;
    margin-bottom:0!important;
  }
  body .value{
    font-size:1.55rem!important;
    line-height:1.05!important;
    overflow-wrap:anywhere!important;
  }
  body .row{
    flex-wrap:wrap!important;
    align-items:flex-start!important;
  }
  body .item,
  body .card,
  body .panel{
    min-width:0!important;
    overflow-wrap:anywhere!important;
  }
  body .tabs{
    display:flex!important;
    flex-wrap:nowrap!important;
    gap:8px!important;
    overflow-x:auto!important;
    padding-bottom:4px!important;
    scrollbar-width:none!important;
    -webkit-overflow-scrolling:touch!important;
  }
  body .tabs::-webkit-scrollbar{display:none!important}
  body .canvas-shell{
    max-width:100%!important;
    overflow:auto!important;
    -webkit-overflow-scrolling:touch!important;
    overscroll-behavior-x:contain!important;
  }
  body input:not([type="checkbox"]):not([type="radio"]),
  body textarea,
  body select{
    min-width:0!important;
    max-width:100%!important;
  }
  body button,
  body .button,
  body .btn{
    max-width:100%!important;
    white-space:normal!important;
  }
  .ss-performance-mobile-dock{
    grid-template-columns:repeat(5,minmax(0,1fr))!important;
  }
  .ss-performance-mobile-dock a{
    min-width:0!important;
    border-radius:12px!important;
    transition:background .18s ease,color .18s ease!important;
  }
  .ss-performance-mobile-dock a.active{
    color:#fff!important;
    background:linear-gradient(110deg,rgba(239,61,152,.22),rgba(155,77,204,.28),rgba(80,214,208,.16))!important;
  }
  .ss-performance-mobile-dock a.active b{
    color:#fff!important;
  }
}
@media(max-width:430px){
  .ss-performance-mobile-dock a{font-size:.54rem!important;padding:5px 1px!important}
  .ss-performance-mobile-dock b{font-size:1rem!important}
}
</style>
"""


PERFORMANCE_MOBILE_SCRIPT = r"""
<script id="ss-performance-mobile-polish-script">
(function(){
  'use strict';
  function markActiveDock(){
    var path=(window.location.pathname||'/').replace(/\/$/,'')||'/';
    document.querySelectorAll('.ss-performance-mobile-dock a[href]').forEach(function(link){
      var href=(link.getAttribute('href')||'').replace(/\/$/,'')||'/';
      var active=href!='/admin' && (path===href || path.indexOf(href + '/')===0);
      link.classList.toggle('active',active);
      if(active){link.setAttribute('aria-current','page');}
      else{link.removeAttribute('aria-current');}
    });
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',markActiveDock,{once:true});
  }else{
    markActiveDock();
  }
})();
</script>
"""


def register_performance_mobile_polish(app) -> None:
    """Finish the mobile UX for Recital & Competition admin workspaces."""

    @app.after_request
    def polish_performance_mobile(response):
        if request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html":
            return response

        path = request.path.rstrip("/") or "/"
        if not any(path == prefix or path.startswith(prefix + "/") for prefix in PERFORMANCE_PREFIXES):
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or 'id="ss-performance-workspace"' not in body:
                return response

            changed = False

            # Production is a full work area and should be reachable from the
            # fixed mobile dock without first opening the horizontal tab strip.
            if 'href="/admin/production"><b>🎬</b>Production</a>' not in body:
                recital_link = '<a href="/admin/recitals"><b>🎭</b>Recital</a>'
                production_link = '<a href="/admin/production"><b>🎬</b>Production</a>'
                if recital_link in body:
                    body = body.replace(recital_link, recital_link + "\n  " + production_link, 1)
                    changed = True

            if 'id="ss-performance-mobile-polish-style"' not in body and "</head>" in body:
                body = body.replace("</head>", PERFORMANCE_MOBILE_STYLE + "</head>", 1)
                changed = True

            if 'id="ss-performance-mobile-polish-script"' not in body and "</body>" in body:
                body = body.replace("</body>", PERFORMANCE_MOBILE_SCRIPT + "</body>", 1)
                changed = True

            if changed:
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
                response.headers.pop("Last-Modified", None)
        except Exception:
            app.logger.exception("Could not apply Recital & Competition mobile polish")

        return response
