from __future__ import annotations

import html
import re

from flask import request

from database import get_db


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

PATH_PAGE_KEYS = {
    "/preschool-class-registration.html": "preschool",
    "/primary-class-registration.html": "primary",
    "/elementary-class-registration.html": "elementary",
    "/intermediate-advanced-registration.html": "intermediate_advanced",
    "/specialized-class-registration.html": "specialized",
    "/mini-competition-team.html": "mini_competition",
    "/petite-competition-team.html": "petite_competition",
    "/juniorettes-competition-team.html": "juniorettes_competition",
    "/junior-competition-team.html": "junior_competition",
}

# The non-Teen competition pages currently do not contain a built-in hero image.
# Use the locally bundled full-team photo as a reliable starter image. Each team
# can then be given its own photo through the Class Page Editor / Media Library.
COMPETITION_FALLBACK = "/assets/images/full-team-picture.jpg"
DEFAULT_PHOTOS = {
    "/mini-competition-team.html": COMPETITION_FALLBACK,
    "/petite-competition-team.html": COMPETITION_FALLBACK,
    "/juniorettes-competition-team.html": COMPETITION_FALLBACK,
    "/junior-competition-team.html": COMPETITION_FALLBACK,
}

PANEL_STYLE = r"""
<style id="ss-program-photo-hero-style">
.hero{
  min-height:auto!important;
}
.hero:before,.hero::before{
  background-image:
    radial-gradient(circle at 82% 22%,rgba(181,59,212,.24),transparent 28rem),
    radial-gradient(circle at 72% 78%,rgba(32,200,199,.13),transparent 30rem),
    linear-gradient(135deg,#05050c 0%,#10091b 52%,#06050d 100%)!important;
  background-color:#05050c!important;
  background-position:center!important;
  background-size:cover!important;
  background-repeat:no-repeat!important;
}
.hero-inner.ss-program-photo-grid{
  display:grid!important;
  grid-template-columns:minmax(0,.9fr) minmax(380px,1.1fr)!important;
  gap:42px!important;
  align-items:center!important;
  padding-top:72px!important;
  padding-bottom:72px!important;
}
.ss-program-hero-copy{min-width:0}
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
    padding-top:46px!important;
    padding-bottom:46px!important;
  }
  .ss-program-photo-panel{margin-top:4px}
  .ss-program-photo-panel img{aspect-ratio:16/10}
}
@media(max-width:640px){
  .hero-inner.ss-program-photo-grid{padding-top:34px!important;padding-bottom:38px!important}
  .ss-program-photo-panel{padding:7px;border-radius:22px}
  .ss-program-photo-panel img{border-radius:16px;aspect-ratio:4/3}
}
</style>
"""


def _hero_photo_url(body: str) -> str:
    """Return the image currently assigned to the page's desktop hero background."""
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


def _saved_photo_url(path: str) -> str:
    """Prefer a photo already published from the backend editor."""
    page_key = PATH_PAGE_KEYS.get(path)
    if not page_key:
        return ""
    try:
        connection = get_db()
        row = connection.execute(
            "SELECT hero_image FROM class_page_content WHERE page_key=?",
            (page_key,),
        ).fetchone()
        connection.close()
        if row:
            try:
                value = row["hero_image"]
            except (TypeError, KeyError, IndexError):
                value = row[0]
            value = (value or "").strip()
            if value.startswith("/uploads/"):
                return value
    except Exception:
        return ""
    return ""


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

            fallback_url = DEFAULT_PHOTOS.get(request.path, "")
            photo_url = (
                _saved_photo_url(request.path)
                or _hero_photo_url(body)
                or fallback_url
            )
            if not photo_url:
                return response

            safe_url = html.escape(photo_url, quote=True)
            safe_fallback = html.escape(fallback_url, quote=True)
            onerror = ""
            if safe_fallback and safe_fallback != safe_url:
                onerror = (
                    " onerror=\"if(this.dataset.fallback!=='1'){this.dataset.fallback='1';"
                    f"this.src='{safe_fallback}';}}\""
                )

            script = f"""
<script id="ss-program-photo-hero-script">
(function(){{
  function setup(){{
    var hero=document.querySelector('.hero');
    var inner=hero&&hero.querySelector('.hero-inner');
    if(!hero||!inner||inner.querySelector('.ss-program-photo-panel')) return;

    inner.classList.add('ss-program-photo-grid');
    var title=(hero.querySelector('h1')&&hero.querySelector('h1').textContent||'Stage Starz Program').replace(/\\s+/g,' ').trim();

    // Keep all hero wording/buttons together in the left column. Previously the
    // grid treated each heading, paragraph and button row as a separate grid item.
    var copy=document.createElement('div');
    copy.className='ss-program-hero-copy';
    while(inner.firstChild) copy.appendChild(inner.firstChild);

    var figure=document.createElement('figure');
    figure.className='ss-program-photo-panel';
    figure.innerHTML='<img src="{safe_url}" alt="'+title.replace(/"/g,'&quot;')+'"{onerror}><figcaption>'+title+'</figcaption>';

    inner.appendChild(copy);
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
