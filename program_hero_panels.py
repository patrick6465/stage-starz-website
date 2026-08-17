from __future__ import annotations

import html
import re

from flask import request


PHOTO_PANEL_PATHS = {
    "/preschool-class-registration.html",
    "/primary-class-registration.html",
    "/elementary-class-registration.html",
    "/intermediate-advanced-registration.html",
    "/specialized-class-registration.html",
    "/mini-competition-team.html",
    "/petite-competition-team.html",
    "/juniorettes-competition-team.html",
    "/junior-competition-team.html",
}

PANEL_STYLE = r"""
<style id="ss-program-photo-hero-style">
.hero:before{
  background:
    radial-gradient(circle at 82% 22%,rgba(181,59,212,.24),transparent 28rem),
    radial-gradient(circle at 72% 78%,rgba(32,200,199,.13),transparent 30rem),
    linear-gradient(135deg,#05050c 0%,#10091b 52%,#06050d 100%)!important;
}
.hero-inner.ss-program-photo-grid{
  display:grid!important;
  grid-template-columns:minmax(0,.9fr) minmax(380px,1.1fr)!important;
  gap:42px!important;
  align-items:center!important;
}
.ss-program-photo-panel{
  margin:0;
  padding:9px;
  border:1px solid rgba(255,255,255,.16);
  border-radius:27px;
  overflow:hidden;
  background:linear-gradient(145deg,rgba(181,59,212,.20),rgba(32,200,199,.10));
  box-shadow:0 26px 72px rgba(0,0,0,.46),0 0 36px rgba(181,59,212,.14);
}
.ss-program-photo-panel img{
  display:block;
  width:100%;
  aspect-ratio:4/3;
  object-fit:cover;
  object-position:center;
  border-radius:20px;
  image-rendering:auto;
  background:#05050c;
}
.ss-program-photo-panel figcaption{
  padding:10px 7px 2px;
  color:#d8d1e4;
  font-size:.78rem;
  font-weight:800;
  text-align:center;
}
@media(max-width:920px){
  .hero-inner.ss-program-photo-grid{
    grid-template-columns:1fr!important;
    gap:30px!important;
  }
  .ss-program-photo-panel{margin-top:4px}
  .ss-program-photo-panel img{aspect-ratio:16/10}
}
@media(max-width:640px){
  .ss-program-photo-panel{padding:7px;border-radius:22px}
  .ss-program-photo-panel img{border-radius:16px;aspect-ratio:4/3}
}
</style>
"""


def _hero_photo_url(body: str) -> str:
    """Return the image currently assigned to the desktop hero background."""
    hero_block = re.search(
        r'\.hero:before\s*\{(?P<body>[^{}]*)\}',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not hero_block:
        return ""
    urls = re.findall(
        r'url\(\s*["\']?([^"\')]+)["\']?\s*\)',
        hero_block.group("body"),
        flags=re.IGNORECASE,
    )
    return urls[-1].strip() if urls else ""


def register_program_hero_panels(app) -> None:
    """Move program/team hero photography out of the background into a dedicated photo card."""

    @app.after_request
    def add_program_photo_panel(response):
        if request.path not in PHOTO_PANEL_PATHS or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            if 'id="ss-program-photo-hero-style"' in body:
                return response

            photo_url = _hero_photo_url(body)
            if not photo_url:
                return response

            safe_url = html.escape(photo_url, quote=True)
            script = f"""
<script id="ss-program-photo-hero-script">
(function(){{
  function setup(){{
    var hero=document.querySelector('.hero');
    var inner=hero&&hero.querySelector('.hero-inner');
    if(!hero||!inner||inner.querySelector('.ss-program-photo-panel')) return;
    inner.classList.add('ss-program-photo-grid');
    var title=(hero.querySelector('h1')&&hero.querySelector('h1').textContent||'Stage Starz Program').replace(/\\s+/g,' ').trim();
    var figure=document.createElement('figure');
    figure.className='ss-program-photo-panel';
    figure.innerHTML='<img src="{safe_url}" alt="'+title.replace(/"/g,'&quot;')+'"><figcaption>'+title+'</figcaption>';
    inner.appendChild(figure);
  }}
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',setup);
  else setup();
}})();
</script>
"""
            body = body.replace("</head>", PANEL_STYLE + "</head>", 1)
            body = body.replace("</body>", script + "</body>", 1)
            response.set_data(body)
        except Exception:
            app.logger.exception("Could not build program photo-card hero")
        return response
