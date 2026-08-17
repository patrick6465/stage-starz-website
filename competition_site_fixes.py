from __future__ import annotations

import html
import re

from flask import request


COMPETITION_HTML_PATHS = {
    "/competition.html",
    "/competition-auditions.html",
    "/mini-competition-team.html",
    "/petite-competition-team.html",
    "/juniorettes-competition-team.html",
    "/junior-competition-team.html",
    "/teen-competition-team.html",
    "/team-only.html",
}

TEAM_LINKS = """<div><h3>Competition</h3>
<a href=\"competition.html\">Team Overview</a>
<a href=\"competition-auditions.html\">Auditions</a>
<a href=\"mini-competition-team.html\">Mini Team</a>
<a href=\"petite-competition-team.html\">Petite Team</a>
<a href=\"juniorettes-competition-team.html\">Juniorettes Team</a>
<a href=\"junior-competition-team.html\">Junior Team</a>
<a href=\"teen-competition-team.html\">Teen Team</a></div>"""

TEEN_LABEL_FIX = """<script id=\"ss-teen-team-label-fix\">
document.querySelectorAll('a[href=\"teen-competition-team.html\"] h3').forEach(function(h){h.textContent='Teen Competition Team';});
</script>"""

TEEN_PHOTO_STYLE = """<style id=\"ss-teen-team-photo-style\">
@media(min-width:821px){
  body[data-competition-team] .hero .hero-inner.ss-teen-hero-grid{
    max-width:1180px!important;
    display:grid!important;
    grid-template-columns:minmax(0,.9fr) minmax(420px,1.1fr)!important;
    gap:42px!important;
    align-items:center!important;
  }
}
.ss-teen-hero-copy{min-width:0}
.ss-teen-team-photo{
  margin:0;
  padding:9px;
  border-radius:26px;
  overflow:hidden;
  border:1px solid rgba(255,255,255,.16);
  background:linear-gradient(145deg,rgba(140,76,255,.22),rgba(40,215,210,.12));
  box-shadow:0 26px 72px rgba(0,0,0,.46),0 0 36px rgba(140,76,255,.16);
}
.ss-teen-team-photo img{
  display:block;
  width:100%;
  height:auto;
  object-fit:contain;
  border-radius:19px;
  image-rendering:auto;
}
.ss-teen-team-photo figcaption{
  padding:10px 7px 2px;
  color:#d8d1e4;
  font-size:.78rem;
  font-weight:800;
  text-align:center;
}
@media(max-width:820px){
  body[data-competition-team] .hero .hero-inner.ss-teen-hero-grid{display:block!important}
  .ss-teen-team-photo{margin-top:30px}
}
</style>"""


def _teen_photo_url(body: str) -> str:
    """Read the Teen page's editable hero-image marker after admin overrides are applied."""
    marker = re.search(
        r'\.hero:before\s*\{[^{}]*?url\(\s*[\"\']?([^\"\')]+)',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if marker:
        return marker.group(1).strip()
    return "assets/images/teen-competition-team.webp"


def _add_teen_photo(body: str) -> str:
    if "ss-teen-team-photo" in body:
        return body

    hero_pattern = re.compile(
        r'(<section\s+class="hero"[^>]*>\s*<div\s+class="hero-inner"[^>]*>)(.*?)(</div>\s*</section>)',
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = hero_pattern.search(body)
    if not match:
        return body

    photo_url = html.escape(_teen_photo_url(body), quote=True)
    hero_content = match.group(2)
    photo = (
        '<figure class="ss-teen-team-photo">'
        f'<img class="ss-teen-team-photo-image" src="{photo_url}" '
        'alt="Stage Starz Teen Competition Team dancers performing on stage">'
        '<figcaption>Stage Starz Teen Competition Team</figcaption>'
        '</figure>'
    )
    replacement = (
        match.group(1).replace('class="hero-inner"', 'class="hero-inner ss-teen-hero-grid"')
        + '<div class="ss-teen-hero-copy">'
        + hero_content
        + '</div>'
        + photo
        + match.group(3)
    )
    body = body[: match.start()] + replacement + body[match.end() :]
    if 'id="ss-teen-team-photo-style"' not in body:
        body = body.replace("</head>", TEEN_PHOTO_STYLE + "</head>", 1)
    return body


def register_competition_site_fixes(app) -> None:
    """Keep competition-team navigation consistent across all public team pages."""

    @app.after_request
    def normalize_competition_team_links(response):
        if request.path not in COMPETITION_HTML_PATHS or response.mimetype != "text/html":
            return response

        try:
            body = response.get_data(as_text=True)

            # Remove the legacy Teen/Senior label everywhere it can still surface.
            body = body.replace("Teen / Senior Competition Team", "Teen Competition Team")
            body = body.replace("Teen & Senior Competition Team", "Teen Competition Team")
            body = body.replace("Teen / Senior Team", "Teen Team")

            # Every competition footer should expose the same complete team list.
            footer_pattern = re.compile(
                r'<div><h3>Competition</h3>.*?</div>',
                flags=re.IGNORECASE | re.DOTALL,
            )
            body = footer_pattern.sub(TEAM_LINKS, body, count=1)

            if request.path == "/teen-competition-team.html":
                body = _add_teen_photo(body)

            # site-refinements.js historically renamed Teen to Teen/Senior on the overview.
            if request.path == "/competition.html" and 'id="ss-teen-team-label-fix"' not in body:
                body = body.replace("</body>", TEEN_LABEL_FIX + "</body>", 1)

            response.set_data(body)
        except Exception:
            app.logger.exception("Could not normalize competition-team links")
        return response
