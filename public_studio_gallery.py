from __future__ import annotations

import html

from studio_gallery_manager import published_gallery_settings


STUDIO_PHOTO_STYLE = r"""
<style id="ss-studio-photo-style">
.ss-studio-story{
  position:relative;overflow:hidden;
  padding:clamp(72px,8vw,110px) 22px;
  border-top:1px solid rgba(255,255,255,.08);
  border-bottom:1px solid rgba(255,255,255,.08);
  background:
    radial-gradient(circle at 8% 8%,rgba(233,30,140,.18),transparent 25rem),
    radial-gradient(circle at 92% 88%,rgba(77,207,208,.17),transparent 30rem),
    linear-gradient(145deg,#090510 0%,#17102a 54%,#08171b 100%);
}
.ss-studio-story-inner{position:relative;z-index:1;width:min(1180px,100%);margin:0 auto}
.ss-studio-story-head{max-width:820px;margin:0 auto 34px;text-align:center}
.ss-studio-story .ss-eyebrow,
.ss-page-photo-panel .ss-eyebrow{
  margin:0 0 10px;color:#e91e8c;text-transform:uppercase;letter-spacing:.14em;
  font-size:.76rem;font-weight:950
}
.ss-studio-story .ss-eyebrow{color:#67e5df}
.ss-studio-story h2{
  margin:0 0 14px;color:#fff;font-size:clamp(2.25rem,5vw,4.25rem);
  line-height:1.04;letter-spacing:-.045em
}
.ss-studio-story .ss-lead{max-width:760px;margin:0 auto;color:#c9bfd7;font-size:1.08rem}
.ss-studio-gallery{
  display:grid;grid-template-columns:repeat(12,minmax(0,1fr));
  grid-auto-rows:215px;gap:16px
}
.ss-studio-photo{
  position:relative;margin:0;overflow:hidden;border-radius:24px;background:#17102a;
  border:1px solid rgba(255,255,255,.12);
  box-shadow:0 22px 58px rgba(0,0,0,.34),0 0 34px rgba(140,60,172,.08)
}
.ss-studio-photo img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .45s ease}
.ss-studio-photo:hover img{transform:scale(1.025)}
.ss-studio-photo figcaption{
  position:absolute;left:13px;right:13px;bottom:13px;padding:10px 12px;border-radius:13px;
  color:#fff;background:rgba(9,5,20,.72);border:1px solid rgba(255,255,255,.08);backdrop-filter:blur(10px);
  font-size:.82rem;font-weight:850
}
.ss-studio-photo.featured{grid-column:span 7;grid-row:span 2}
.ss-studio-photo.room{grid-column:span 5}
.ss-studio-photo.parents{grid-column:span 5}
.ss-studio-photo.awards{grid-column:span 5}
.ss-studio-photo.first-day{grid-column:span 7}
.ss-studio-story-actions{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:30px}
.ss-studio-story-actions a{
  display:inline-flex;align-items:center;justify-content:center;border-radius:999px;
  padding:13px 20px;font-weight:900;text-decoration:none
}
.ss-studio-story-actions .primary{
  color:#fff;background:linear-gradient(135deg,#e91e8c,#8c3cac 60%,#4dcfd0);
  box-shadow:0 14px 32px rgba(233,30,140,.25)
}
.ss-studio-story-actions .secondary{
  color:#fff;background:rgba(255,255,255,.055);
  border:1px solid rgba(103,229,223,.34);backdrop-filter:blur(8px)
}
.ss-studio-story-actions .secondary:hover{background:rgba(103,229,223,.10);border-color:rgba(103,229,223,.58)}
.ss-page-photo-panel{
  width:min(1180px,calc(100% - 44px));margin:10px auto 54px;
  display:grid;grid-template-columns:minmax(0,1.1fr) minmax(300px,.9fr);
  gap:30px;align-items:center;padding:24px;border-radius:28px;
  border:1px solid rgba(126,50,255,.16);background:rgba(255,255,255,.92);
  box-shadow:0 24px 70px rgba(31,18,74,.14)
}
.ss-page-photo-panel.reverse{grid-template-columns:minmax(300px,.9fr) minmax(0,1.1fr)}
.ss-page-photo-panel img{width:100%;height:100%;min-height:340px;object-fit:cover;border-radius:21px}
#meet-stage-starz-team img{object-position:center top}
.ss-page-photo-copy{padding:14px 12px}
.ss-page-photo-copy h2{margin:0 0 13px;color:#7e32ff;font-size:clamp(1.8rem,4vw,3rem);line-height:1.05}
.ss-page-photo-copy p{margin:0;color:#6f6780;font-size:1.04rem}
.ss-page-photo-copy .ss-small{margin-top:14px;font-size:.92rem}
@media(max-width:820px){
  .ss-studio-gallery{grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:230px}
  .ss-studio-photo.featured,.ss-studio-photo.room,.ss-studio-photo.parents,
  .ss-studio-photo.awards,.ss-studio-photo.first-day{grid-column:auto;grid-row:auto}
  .ss-studio-photo.featured{grid-column:1/-1;min-height:300px}
  .ss-page-photo-panel,.ss-page-photo-panel.reverse{grid-template-columns:1fr}
  .ss-page-photo-panel img{min-height:0;aspect-ratio:4/3}
  #meet-stage-starz-team img{
    display:block;width:100%;height:auto;min-height:0;aspect-ratio:auto;
    object-fit:contain;object-position:center top
  }
}
@media(max-width:560px){
  .ss-studio-story{padding:62px 14px}
  .ss-studio-gallery{grid-template-columns:1fr;grid-auto-rows:240px;gap:12px}
  .ss-studio-photo.featured{grid-column:auto;min-height:280px}
  .ss-studio-photo{border-radius:19px}
  .ss-page-photo-panel{width:calc(100% - 28px);padding:14px;margin-bottom:38px;border-radius:22px}
  .ss-page-photo-panel img{border-radius:16px}
}
@media(prefers-reduced-motion:reduce){.ss-studio-photo img{transition:none}}
</style>
"""


HOME_PHOTOS = (
    (
        "class_in_progress",
        "featured",
        "Stage Starz dancers participating in class inside the studio",
        "Classes in action",
    ),
    (
        "room_wide",
        "room",
        "Stage Starz dance room with professional floor, mirrors and ballet barres",
        "Bright, spacious dance rooms",
    ),
    (
        "parent_viewing",
        "parents",
        "Stage Starz parent waiting and viewing area",
        "A comfortable parent viewing area",
    ),
    (
        "awards_wall",
        "awards",
        "Competition awards displayed above a ballet barre at Stage Starz",
        "A studio built on growth and achievement",
    ),
    (
        "first_day_dancers",
        "first-day",
        "Current Stage Starz dancers celebrating their first day of dance",
        "A welcoming place to begin",
    ),
)


def _home_section(values: dict[str, str]) -> str:
    figures: list[str] = []
    for slot, css_class, alt_text, caption in HOME_PHOTOS:
        image_url = values.get(slot, "")
        if not image_url:
            continue
        figures.append(
            f'<figure class="ss-studio-photo {css_class}">'
            f'<img src="{html.escape(image_url, quote=True)}" alt="{html.escape(alt_text, quote=True)}" '
            'loading="lazy" decoding="async">'
            f'<figcaption>{html.escape(caption)}</figcaption>'
            '</figure>'
        )

    if not figures:
        return ""

    return f"""
<section class="ss-studio-story" id="inside-stage-starz" aria-labelledby="inside-stage-starz-title">
  <div class="ss-studio-story-inner">
    <div class="ss-studio-story-head">
      <p class="ss-eyebrow">Inside Stage Starz</p>
      <h2 id="inside-stage-starz-title">A place to learn, grow &amp; perform.</h2>
      <p class="ss-lead">Take a look inside the real spaces where Stage Starz dancers build confidence, technique, friendships and a love of performing.</p>
    </div>
    <div class="ss-studio-gallery">{''.join(figures)}</div>
    <div class="ss-studio-story-actions">
      <a class="primary" href="classes.html">Find Your Child's Class →</a>
      <a class="secondary" href="contact.html">Contact the Studio</a>
    </div>
  </div>
</section>
"""


def _about_section(image_url: str) -> str:
    if not image_url:
        return ""
    safe_url = html.escape(image_url, quote=True)
    return f"""
<section class="ss-page-photo-panel" id="meet-stage-starz-team" aria-labelledby="meet-stage-starz-team-title">
  <div>
    <img src="{safe_url}" alt="Stage Starz staff celebrating the first day of dance" loading="lazy" decoding="async">
  </div>
  <div class="ss-page-photo-copy">
    <p class="ss-eyebrow">The people behind the studio</p>
    <h2 id="meet-stage-starz-team-title">A team invested in every dancer.</h2>
    <p>Stage Starz combines decades of dance experience with a supportive, energetic studio culture. Our instructors help dancers develop strong technique while building confidence, creativity and lasting friendships.</p>
  </div>
</section>
"""


def _contact_section(image_url: str) -> str:
    if not image_url:
        return ""
    safe_url = html.escape(image_url, quote=True)
    return f"""
<section class="ss-page-photo-panel reverse" id="find-stage-starz" aria-labelledby="find-stage-starz-title">
  <div class="ss-page-photo-copy">
    <p class="ss-eyebrow">Find Stage Starz</p>
    <h2 id="find-stage-starz-title">Know what to look for when you arrive.</h2>
    <p>Visit Stage Starz Academy of Dance at 6800 Lewis Ave in Temperance, Michigan.</p>
    <p class="ss-small">The studio entrance is located in the Academy of Dance storefront shown here.</p>
  </div>
  <div>
    <img src="{safe_url}" alt="Exterior of Stage Starz Academy of Dance at 6800 Lewis Avenue in Temperance Michigan" loading="lazy" decoding="async">
  </div>
</section>
"""


def _decorate(app, response, page: str):
    response = app.make_response(response)
    if response.status_code != 200 or response.mimetype != "text/html":
        return response
    try:
        response.direct_passthrough = False
        body = response.get_data(as_text=True)
        if not body:
            return response

        values = published_gallery_settings()
        if page == "home":
            section = _home_section(values)
        elif page == "about":
            section = _about_section(values.get("staff_first_day", ""))
        elif page == "contact":
            section = _contact_section(values.get("exterior", ""))
        else:
            section = ""

        if not section:
            return response

        changed = False
        if 'id="ss-studio-photo-style"' not in body and "</head>" in body:
            body = body.replace("</head>", STUDIO_PHOTO_STYLE + "</head>", 1)
            changed = True

        if page == "home" and 'id="inside-stage-starz"' not in body:
            marker = '<section class="approved-why"'
            if marker in body:
                body = body.replace(marker, section + "\n" + marker, 1)
            elif "</main>" in body:
                body = body.replace("</main>", section + "\n</main>", 1)
            changed = True

        elif page == "about" and 'id="meet-stage-starz-team"' not in body:
            if "</main>" in body:
                body = body.replace("</main>", section + "\n</main>", 1)
                changed = True

        elif page == "contact" and 'id="find-stage-starz"' not in body:
            marker = '<section class="section grid two">'
            if marker in body:
                body = body.replace(marker, section + "\n" + marker, 1)
            elif "</main>" in body:
                body = body.replace("</main>", section + "\n</main>", 1)
            changed = True

        if changed:
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
            response.headers.pop("Last-Modified", None)
    except Exception:
        app.logger.exception("Could not decorate public pages with Studio Gallery photography")
    return response


def register_public_studio_gallery(app) -> None:
    """Add persistent real Stage Starz photography to prospect-facing public pages."""

    home_endpoint = "website_home"
    file_endpoint = "website_file"

    original_home = app.view_functions.get(home_endpoint)
    if original_home and not getattr(original_home, "_ss_studio_gallery_wrapped", False):
        def website_home_with_studio_gallery(*args, **kwargs):
            return _decorate(app, original_home(*args, **kwargs), "home")

        website_home_with_studio_gallery._ss_studio_gallery_wrapped = True
        website_home_with_studio_gallery.__name__ = getattr(original_home, "__name__", home_endpoint)
        app.view_functions[home_endpoint] = website_home_with_studio_gallery

    original_file = app.view_functions.get(file_endpoint)
    if original_file and not getattr(original_file, "_ss_studio_gallery_wrapped", False):
        def website_file_with_studio_gallery(filename: str, *args, **kwargs):
            response = original_file(filename, *args, **kwargs)
            clean = (filename or "").strip("/").lower()
            if clean in {"index.html", "index-new.html"}:
                return _decorate(app, response, "home")
            if clean in {"about.html", "about"}:
                return _decorate(app, response, "about")
            if clean in {"contact.html", "contact"}:
                return _decorate(app, response, "contact")
            return response

        website_file_with_studio_gallery._ss_studio_gallery_wrapped = True
        website_file_with_studio_gallery.__name__ = getattr(original_file, "__name__", file_endpoint)
        app.view_functions[file_endpoint] = website_file_with_studio_gallery
