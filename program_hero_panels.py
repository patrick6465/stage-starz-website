from __future__ import annotations

import html
import re

from flask import request

import class_content_editor as class_editor


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

# These competition pages were rebuilt without a dedicated built-in hero image.
# Keep a local, reliable starter image until a team-specific photo is published
# through the Class Page Editor.
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
  background:
    radial-gradient(circle at 82% 22%,rgba(181,59,212,.24),transparent 28rem),
    radial-gradient(circle at 72% 78%,rgba(32,200,199,.13),transparent 30rem),
    linear-gradient(135deg,#05050c 0%,#10091b 52%,#06050d 100%)!important;
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
  height:auto;
  max-height:560px;
  object-fit:contain;
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
  .ss-program-photo-panel img{height:auto;max-height:620px;object-fit:contain}
}
@media(max-width:640px){
  .hero-inner.ss-program-photo-grid{padding-top:34px!important;padding-bottom:38px!important}
  .ss-program-photo-panel{padding:7px;border-radius:22px}
  .ss-program-photo-panel img{border-radius:16px;height:auto;max-height:none;object-fit:contain}
}
</style>
"""


def _hero_photo_url(body: str) -> str:
    """Return the image currently assigned to a page's hero background."""
    hero_blocks = re.findall(
        r'\.hero:before\s*\{(?P<body>[^{}]*)\}',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in hero_blocks:
        urls = re.findall(
            r'url\(\s*["\']?([^"\')]+)["\']?\s*\)',
            block,
            flags=re.IGNORECASE,
        )
        if urls:
            return urls[-1].strip()
    return ""


def _saved_photo_url(path: str) -> str:
    """Use the exact saved editor value that the editor itself displays."""
    page_key = PATH_PAGE_KEYS.get(path)
    if not page_key:
        return ""
    try:
        saved = class_editor._get_saved_content(page_key)
    except Exception:
        return ""
    if not saved:
        return ""
    value = (saved.get("hero_image") or "").strip()
    return value if value.startswith("/uploads/") else ""


def _inject_photo_panel(body: str, photo_url: str, fallback_url: str = "") -> str:
    """Insert the photo card directly into the hero HTML; no client JS required."""
    if 'id="ss-program-photo-hero-style"' in body or "ss-program-photo-panel" in body:
        return body

    hero_pattern = re.compile(
        r'(?P<open><section\s+class="hero"[^>]*>\s*<div\s+class="hero-inner"[^>]*>)'
        r'(?P<content>.*?)'
        r'(?P<close></div>\s*</section>)',
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = hero_pattern.search(body)
    if not match:
        return body

    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', match.group("content"), flags=re.I | re.S)
    title = "Stage Starz Program"
    if title_match:
        title = re.sub(r"<[^>]+>", " ", title_match.group(1))
        title = html.unescape(re.sub(r"\s+", " ", title)).strip() or title

    safe_url = html.escape(photo_url, quote=True)
    safe_fallback = html.escape(fallback_url, quote=True)
    onerror = ""
    if safe_fallback and safe_fallback != safe_url:
        onerror = (
            " onerror=\"if(this.dataset.fallback!=='1'){this.dataset.fallback='1';"
            f"this.src='{safe_fallback}';}}\""
        )

    open_tag = match.group("open")
    open_tag = re.sub(
        r'class="hero-inner([^"]*)"',
        lambda m: f'class="hero-inner{m.group(1)} ss-program-photo-grid"',
        open_tag,
        count=1,
        flags=re.I,
    )

    figure = (
        '<figure class="ss-program-photo-panel">'
        f'<img src="{safe_url}" alt="{html.escape(title, quote=True)}"{onerror}>'
        f'<figcaption>{html.escape(title)}</figcaption>'
        '</figure>'
    )
    replacement = (
        open_tag
        + '<div class="ss-program-hero-copy">'
        + match.group("content")
        + '</div>'
        + figure
        + match.group("close")
    )
    body = body[: match.start()] + replacement + body[match.end() :]
    return body.replace("</head>", PANEL_STYLE + "</head>", 1)


def register_program_hero_panels(app) -> None:
    """Render program/team photography in a dedicated card instead of a background."""

    @app.after_request
    def add_program_photo_panel(response):
        if request.path not in PHOTO_PANEL_PATHS or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            fallback_url = DEFAULT_PHOTOS.get(request.path, "")
            photo_url = (
                _saved_photo_url(request.path)
                or _hero_photo_url(body)
                or fallback_url
            )
            if not photo_url:
                return response

            body = _inject_photo_panel(body, photo_url, fallback_url)
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        except Exception:
            app.logger.exception("Could not build program photo-card hero")
        return response
