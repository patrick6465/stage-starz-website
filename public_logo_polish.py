from __future__ import annotations

import re

from flask import request


LOGO_STYLE = r"""
<style id="ss-public-logo-polish-style">
.logo.ss-brand-logo{
  display:flex!important;
  align-items:center!important;
  gap:0!important;
}
.logo.ss-brand-logo img{
  display:block!important;
  width:92px!important;
  height:62px!important;
  max-width:none!important;
  object-fit:contain!important;
  object-position:center!important;
  filter:drop-shadow(0 7px 13px rgba(0,0,0,.16));
}
@media(max-width:640px){
  .logo.ss-brand-logo img{
    width:92px!important;
    height:62px!important;
  }
}
</style>
"""


GENERIC_LOGO_RE = re.compile(
    r'<a\s+class=["\']logo["\']\s+href=["\'][^"\']*["\']>\s*'
    r'<span\s+class=["\']logo-mark["\']>.*?</span>\s*'
    r'<span>\s*Stage\s+Starz\s*</span>\s*</a>',
    re.IGNORECASE | re.DOTALL,
)

REAL_LOGO = (
    '<a class="logo ss-brand-logo" href="/" aria-label="Stage Starz Academy of Dance home">'
    '<img src="/assets/images/stage-starz-logo.png" alt="Stage Starz Academy of Dance">'
    '</a>'
)


def register_public_logo_polish(app) -> None:
    """Replace legacy generic star header marks with the real Stage Starz logo."""

    @app.after_request
    def polish_public_logo(response):
        if request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html" or request.path.startswith("/admin"):
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or "logo-mark" not in body:
                return response

            body, count = GENERIC_LOGO_RE.subn(REAL_LOGO, body)
            if not count:
                return response

            if 'id="ss-public-logo-polish-style"' not in body and "</head>" in body:
                body = body.replace("</head>", LOGO_STYLE + "</head>", 1)

            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
            response.headers.pop("Last-Modified", None)
        except Exception:
            app.logger.exception("Could not replace legacy public header logo")

        return response
