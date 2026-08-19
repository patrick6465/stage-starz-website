from __future__ import annotations

from flask import request


MOBILE_GALLERY_STYLE = r"""
<style id="ss-home-gallery-mobile-polish-style">
@media(max-width:640px){
  /* The base gallery used fixed grid rows while the featured card had a larger
     min-height, which let the following photo visually climb over it. Give each
     mobile card its own intrinsic row and a predictable photo ratio instead. */
  .ss-studio-gallery{
    grid-auto-rows:auto!important;
  }
  .ss-studio-photo,
  .ss-studio-photo.featured{
    position:relative!important;
    height:auto!important;
    min-height:0!important;
    aspect-ratio:4/3!important;
  }
  .ss-studio-photo img{
    position:absolute!important;
    inset:0!important;
    width:100%!important;
    height:100%!important;
    object-fit:cover!important;
  }

  .ss-mobile-cta{
    bottom:max(10px, env(safe-area-inset-bottom))!important;
    transition:transform .24s ease,opacity .20s ease!important;
    will-change:transform,opacity;
  }
  .ss-mobile-cta.ss-gallery-hidden{
    transform:translateY(calc(100% + 34px))!important;
    opacity:0!important;
    pointer-events:none!important;
  }
  .ss-public-admin-pill{
    bottom:max(84px, calc(env(safe-area-inset-bottom) + 76px))!important;
    transition:bottom .24s ease,transform .24s ease,opacity .20s ease!important;
    will-change:transform,opacity;
  }
  body.ss-gallery-mode .ss-public-admin-pill{
    transform:translateY(calc(100% + 34px))!important;
    opacity:0!important;
    pointer-events:none!important;
  }
}
</style>
"""


MOBILE_GALLERY_SCRIPT = r"""
<script id="ss-home-gallery-mobile-polish-script">
(function(){
  'use strict';

  function isAdminLink(link){
    if(!link || !link.getAttribute){return false;}
    var href=link.getAttribute('href') || '';
    try{
      var url=new URL(href,window.location.href);
      return url.pathname.replace(/\/$/,'')==='/admin' && /admin/i.test(link.textContent || '');
    }catch(_error){
      return false;
    }
  }

  function markFloatingAdmin(){
    document.querySelectorAll('a[href]').forEach(function(link){
      if(!isAdminLink(link)){return;}
      var target=link;
      var node=link;
      while(node && node!==document.body){
        if(window.getComputedStyle(node).position==='fixed'){
          target=node;
          break;
        }
        node=node.parentElement;
      }
      target.classList.add('ss-public-admin-pill');
    });
  }

  function initGalleryGuard(){
    var gallery=document.getElementById('inside-stage-starz');
    if(!gallery){return;}

    function getCta(){return document.querySelector('.ss-mobile-cta');}
    function setGalleryMode(active){
      var cta=getCta();
      document.body.classList.toggle('ss-gallery-mode',active);
      if(cta){cta.classList.toggle('ss-gallery-hidden',active);}
      markFloatingAdmin();
    }

    if('IntersectionObserver' in window){
      var observer=new IntersectionObserver(function(entries){
        entries.forEach(function(entry){
          if(entry.target===gallery){setGalleryMode(entry.isIntersecting);}
        });
      },{threshold:.04,rootMargin:'-24px 0px -24px 0px'});
      observer.observe(gallery);
    }

    markFloatingAdmin();
    var mutationObserver=new MutationObserver(function(){
      markFloatingAdmin();
      if(document.body.classList.contains('ss-gallery-mode')){
        var cta=getCta();
        if(cta){cta.classList.add('ss-gallery-hidden');}
      }
    });
    mutationObserver.observe(document.body,{childList:true,subtree:true});
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',initGalleryGuard,{once:true});
  }else{
    initGalleryGuard();
  }
})();
</script>
"""


def register_homepage_mobile_gallery_polish(app) -> None:
    """Keep fixed mobile homepage controls from covering the Studio Gallery."""

    @app.after_request
    def polish_homepage_gallery_mobile_controls(response):
        if request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html":
            return response

        path = request.path.rstrip("/") or "/"
        if path not in {"/", "/index.html", "/index-new.html"}:
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or 'id="inside-stage-starz"' not in body:
                return response

            changed = False
            if 'id="ss-home-gallery-mobile-polish-style"' not in body and "</head>" in body:
                body = body.replace("</head>", MOBILE_GALLERY_STYLE + "</head>", 1)
                changed = True
            if 'id="ss-home-gallery-mobile-polish-script"' not in body and "</body>" in body:
                body = body.replace("</body>", MOBILE_GALLERY_SCRIPT + "</body>", 1)
                changed = True

            if changed:
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
                response.headers.pop("Last-Modified", None)
        except Exception:
            app.logger.exception("Could not apply homepage mobile Studio Gallery polish")

        return response
