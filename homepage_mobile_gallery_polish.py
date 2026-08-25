from __future__ import annotations

import base64
import re
from functools import lru_cache
from pathlib import Path

from flask import Response, request


BANNER_CHUNKS = tuple(
    Path(__file__).resolve().parent / "assets" / "media" / f"stardust_shipit_banner_{index}.b64"
    for index in range(6)
)

# Use the actual animated GIF directly. This avoids mobile autoplay/video codec
# behavior that could leave shoppers seeing only the old static poster image.
ANIMATED_BANNER = '''<img class="ss-approved-shop-gif" src="/assets/images/stardust-ship-it-shop.gif?v=20260824-2" alt="Stardust Ship-it-Shop spirit wear banner">'''

BANNER_LINK_RE = re.compile(
    r'(<a\b[^>]*class=["\'][^"\']*\bapproved-shop-link\b[^"\']*["\'][^>]*>).*?(</a>)',
    re.IGNORECASE | re.DOTALL,
)


@lru_cache(maxsize=1)
def _stardust_banner_video() -> bytes:
    payload = "".join(path.read_text(encoding="utf-8").strip() for path in BANNER_CHUNKS)
    return base64.b64decode(payload)


def _replace_stardust_banner(body: str) -> tuple[str, bool]:
    """Replace the clickable homepage shop banner without depending on exact img markup."""

    if 'class="ss-approved-shop-gif"' in body or "class='ss-approved-shop-gif'" in body:
        return body, False

    def replacement(match: re.Match[str]) -> str:
        return f"{match.group(1)}\n      {ANIMATED_BANNER}\n    {match.group(2)}"

    updated, count = BANNER_LINK_RE.subn(replacement, body, count=1)
    return updated, bool(count)


MOBILE_GALLERY_STYLE = r"""
<style id="ss-home-gallery-mobile-polish-style">
.approved-shop-link .ss-approved-shop-gif{
  display:block;
  width:100%;
  height:auto;
  object-fit:contain;
  object-position:center;
  pointer-events:none;
}
@media(max-width:640px){
  .ss-studio-gallery{grid-auto-rows:auto!important;}
  .ss-studio-photo,.ss-studio-photo.featured{position:relative!important;height:auto!important;min-height:0!important;aspect-ratio:4/3!important;}
  .ss-studio-photo img{position:absolute!important;inset:0!important;width:100%!important;height:100%!important;object-fit:cover!important;}
  .ss-mobile-cta{bottom:max(10px, env(safe-area-inset-bottom))!important;transition:transform .24s ease,opacity .20s ease!important;will-change:transform,opacity;}
  .ss-mobile-cta.ss-gallery-hidden{transform:translateY(calc(100% + 34px))!important;opacity:0!important;pointer-events:none!important;}
  .ss-public-admin-pill{bottom:max(84px, calc(env(safe-area-inset-bottom) + 76px))!important;transition:bottom .24s ease,transform .24s ease,opacity .20s ease!important;will-change:transform,opacity;}
  body.ss-gallery-mode .ss-public-admin-pill{transform:translateY(calc(100% + 34px))!important;opacity:0!important;pointer-events:none!important;}
}
</style>
"""


MOBILE_GALLERY_SCRIPT = r"""
<script id="ss-home-gallery-mobile-polish-script">
(function(){
  'use strict';
  function isAdminLink(link){if(!link||!link.getAttribute){return false;}var href=link.getAttribute('href')||'';try{var url=new URL(href,window.location.href);return url.pathname.replace(/\/$/,'')==='/admin'&&/admin/i.test(link.textContent||'');}catch(_error){return false;}}
  function markFloatingAdmin(){document.querySelectorAll('a[href]').forEach(function(link){if(!isAdminLink(link)){return;}var target=link;var node=link;while(node&&node!==document.body){if(window.getComputedStyle(node).position==='fixed'){target=node;break;}node=node.parentElement;}target.classList.add('ss-public-admin-pill');});}
  function initGalleryGuard(){var gallery=document.getElementById('inside-stage-starz');if(!gallery){return;}function getCta(){return document.querySelector('.ss-mobile-cta');}function setGalleryMode(active){var cta=getCta();document.body.classList.toggle('ss-gallery-mode',active);if(cta){cta.classList.toggle('ss-gallery-hidden',active);}markFloatingAdmin();}if('IntersectionObserver' in window){var observer=new IntersectionObserver(function(entries){entries.forEach(function(entry){if(entry.target===gallery){setGalleryMode(entry.isIntersecting);}});},{threshold:.04,rootMargin:'-24px 0px -24px 0px'});observer.observe(gallery);}markFloatingAdmin();var mutationObserver=new MutationObserver(function(){markFloatingAdmin();if(document.body.classList.contains('ss-gallery-mode')){var cta=getCta();if(cta){cta.classList.add('ss-gallery-hidden');}}});mutationObserver.observe(document.body,{childList:true,subtree:true});}
  function honorReducedMotion(){if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches){document.querySelectorAll('.ss-approved-shop-video').forEach(function(video){video.pause();});}}
  function init(){initGalleryGuard();honorReducedMotion();}
  if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',init,{once:true});}else{init();}
})();
</script>
"""


def register_homepage_mobile_gallery_polish(app) -> None:
    """Keep fixed mobile homepage controls from covering the Studio Gallery."""

    @app.route("/assets/media/stardust-ship-it-shop.mp4")
    def stardust_shipit_banner_video():
        response = Response(_stardust_banner_video(), mimetype="video/mp4")
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

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
            if not body:
                return response
            changed = False

            body, banner_changed = _replace_stardust_banner(body)
            changed = changed or banner_changed

            if "National competition opportunities" in body:
                body = body.replace("National competition opportunities", "Regional competition opportunities", 1)
                changed = True
            if 'id="inside-stage-starz"' in body:
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
