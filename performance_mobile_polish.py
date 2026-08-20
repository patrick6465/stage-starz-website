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
  body{
    padding-bottom:160px!important;
    scroll-padding-bottom:145px!important;
  }
  body .wrap{
    width:calc(100% - 20px)!important;
    max-width:none!important;
    padding-bottom:170px!important;
  }
  html body.ss-ticket-checkin-mobile .wrap,
  html body.ss-ticket-order-mobile .wrap,
  html body.ss-ticket-hold-mobile .wrap{
    padding-bottom:170px!important;
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
    scroll-margin-bottom:120px!important;
  }
  body input,
  body textarea,
  body select,
  body .ticket,
  body .item{
    scroll-margin-bottom:120px!important;
  }
  .ss-performance-mobile-dock{
    grid-template-columns:repeat(5,minmax(0,1fr))!important;
    bottom:max(8px,env(safe-area-inset-bottom))!important;
    padding:4px!important;
    border-radius:15px!important;
  }
  .ss-performance-mobile-dock a{
    min-width:0!important;
    min-height:48px!important;
    padding:3px 1px!important;
    border-radius:12px!important;
    transition:background .18s ease,color .18s ease!important;
    display:flex!important;
    flex-direction:column!important;
    align-items:center!important;
    justify-content:center!important;
    line-height:1.05!important;
  }
  .ss-performance-mobile-dock b{
    font-size:.95rem!important;
    line-height:1!important;
    margin-bottom:2px!important;
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
  .ss-performance-tabs{
    display:grid!important;
    grid-template-columns:repeat(4,minmax(0,1fr))!important;
    width:100%!important;
    gap:4px!important;
    overflow-x:hidden!important;
    padding:0 7px 9px!important;
  }
  .ss-performance-tab{
    width:auto!important;
    min-width:0!important;
    padding:7px 3px!important;
    gap:3px!important;
    justify-content:center!important;
    font-size:.61rem!important;
    line-height:1.05!important;
    letter-spacing:-.01em!important;
  }
  .ss-performance-tab span:first-child{
    flex:0 0 auto!important;
    font-size:.86rem!important;
    line-height:1!important;
  }
  .ss-performance-tab span:last-child{
    min-width:0!important;
    overflow:hidden!important;
    text-overflow:clip!important;
  }
  .ss-performance-mobile-dock a{font-size:.54rem!important;padding:3px 1px!important}
  .ss-performance-mobile-dock b{font-size:.92rem!important}
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
  function alignTabs(){
    if(window.innerWidth>430){return;}
    var nav=document.querySelector('.ss-performance-tabs');
    if(nav){nav.scrollLeft=0;}
  }
  function finishMobileNav(){
    markActiveDock();
    alignTabs();
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',finishMobileNav,{once:true});
  }else{
    finishMobileNav();
  }
  window.addEventListener('resize',alignTabs);
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
