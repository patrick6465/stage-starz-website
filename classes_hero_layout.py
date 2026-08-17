from __future__ import annotations

from flask import request


CLASSES_HERO_LAYOUT = r"""
<style id="ss-classes-hero-right-layout">
/* Keep the dancer unobstructed on desktop by using the open space to her right. */
@media(min-width:921px){
  .hero{
    background-position:43% center!important;
  }
  .hero:before{
    background:
      linear-gradient(to left,
        rgba(8,7,18,.97) 0%,
        rgba(8,7,18,.88) 36%,
        rgba(8,7,18,.38) 68%,
        rgba(8,7,18,.24) 100%),
      linear-gradient(0deg,rgba(8,7,18,.62),transparent 48%)!important;
  }
  .hero-inner{
    display:flex!important;
    justify-content:flex-end!important;
  }
  .hero-copy{
    width:min(52%,610px)!important;
    max-width:610px!important;
    margin-left:auto!important;
  }
}

/* At medium widths keep a little more breathing room without covering the dancer. */
@media(min-width:921px) and (max-width:1080px){
  .hero-copy{
    width:54%!important;
    max-width:560px!important;
  }
  .hero{
    background-position:39% center!important;
  }
}
</style>
"""


def register_classes_hero_layout(app) -> None:
    """Move Classes-page hero copy into the open space to the dancer's right."""

    @app.after_request
    def position_classes_hero_copy(response):
        if request.path != "/classes.html" or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            if 'id="ss-classes-hero-right-layout"' not in body:
                body = body.replace("</head>", CLASSES_HERO_LAYOUT + "</head>", 1)
                response.set_data(body)
        except Exception:
            app.logger.exception("Could not adjust Classes page hero layout")
        return response
