from __future__ import annotations

from flask import Response, request

from config import BASE_DIR


CLASSES_HERO_LAYOUT = r"""
<style id="ss-classes-hero-right-layout">
/* Use the new dancer photo on the left and reserve the open right side for copy. */
@media(min-width:921px){
  .hero{
    background-color:#080712!important;
    background-image:url("/assets/images/classes-hero-dancer.webp")!important;
    background-repeat:no-repeat!important;
    background-size:auto 100%!important;
    background-position:left center!important;
  }
  .hero:before{
    background:
      linear-gradient(to left,
        rgba(8,7,18,.98) 0%,
        rgba(8,7,18,.93) 34%,
        rgba(8,7,18,.48) 57%,
        rgba(8,7,18,.12) 76%,
        rgba(8,7,18,.06) 100%),
      linear-gradient(0deg,rgba(8,7,18,.48),transparent 45%)!important;
  }
  .hero-inner{
    display:flex!important;
    justify-content:flex-end!important;
  }
  .hero-copy{
    width:min(49%,580px)!important;
    max-width:580px!important;
    margin-left:auto!important;
    margin-right:0!important;
  }
}

/* At medium desktop widths give the copy enough room while keeping it off the dancer. */
@media(min-width:921px) and (max-width:1080px){
  .hero-copy{
    width:50%!important;
    max-width:520px!important;
  }
  .hero{
    background-size:auto 96%!important;
    background-position:left center!important;
  }
}

/* Mobile keeps the proven stacked copy treatment and crops the photo around the dancer. */
@media(max-width:920px){
  .hero{
    background-image:url("/assets/images/classes-hero-dancer.webp")!important;
    background-size:cover!important;
    background-position:42% center!important;
    background-repeat:no-repeat!important;
  }
}

/* Phones: keep the hero headline strong without letting it overpower the dancer photo. */
@media(max-width:640px){
  .hero h1{
    font-size:clamp(2.5rem,11.4vw,4.2rem)!important;
    line-height:1.06!important;
  }

  /* Tighten the handoff from the Class Finder card into Easy Enrollment. */
  .section:has(.finder){
    padding-bottom:16px!important;
  }
  .section:has(.finder) + .section{
    padding-top:16px!important;
  }
}
</style>
"""


def _render_classes_page() -> Response:
    """Serve Classes directly so layout changes cannot be hidden by a stale static-file ETag."""
    source = (BASE_DIR / "site" / "classes.html").read_text(encoding="utf-8")
    if 'id="ss-classes-hero-right-layout"' not in source:
        source = source.replace("</head>", CLASSES_HERO_LAYOUT + "</head>", 1)
    response = Response(source, mimetype="text/html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def register_classes_hero_layout(app) -> None:
    """Use the selected Classes hero photo and keep desktop copy to the dancer's right."""

    # Use an exact route instead of the generic static-file route. The static
    # response carries an ETag based only on classes.html, so Python-only layout
    # changes can otherwise be answered with 304 Not Modified by the browser.
    app.add_url_rule(
        "/classes.html",
        endpoint="classes_page_right_hero",
        view_func=_render_classes_page,
        methods=["GET"],
    )

    @app.after_request
    def position_classes_hero_copy(response):
        if request.path != "/classes.html" or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            if body and 'id="ss-classes-hero-right-layout"' not in body:
                body = body.replace("</head>", CLASSES_HERO_LAYOUT + "</head>", 1)
                response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not adjust Classes page hero layout")
        return response
