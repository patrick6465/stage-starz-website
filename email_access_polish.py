from __future__ import annotations

from flask import request


EMAIL_ACCESS_SHORTCUT = r"""
<style id="ss-global-email-shortcut-style">
.ss-global-email-shortcut{display:none}
@media(max-width:760px){
  .ss-global-email-shortcut{
    position:fixed;right:14px;bottom:86px;z-index:1180;display:inline-flex;align-items:center;gap:7px;
    min-height:44px;padding:10px 13px;border:1px solid rgba(255,255,255,.16);border-radius:999px;
    background:linear-gradient(110deg,rgba(239,61,152,.96),rgba(155,77,204,.96),rgba(80,214,208,.93));
    color:#fff!important;text-decoration:none!important;font:850 13px/1 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
    box-shadow:0 12px 28px rgba(0,0,0,.38);backdrop-filter:blur(14px)
  }
  .ss-global-email-shortcut:active{transform:translateY(1px)}
}
</style>
<a class="ss-global-email-shortcut" href="/admin/email" aria-label="Open Stage Starz Email">✉️ <span>Email</span></a>
"""


def register_email_access_polish(app) -> None:
    """Keep Stage Starz Email one tap away on manager screens, especially phones."""

    @app.after_request
    def add_email_access_shortcut(response):
        path = request.path.rstrip("/") or "/"
        if response.mimetype != "text/html" or request.method != "GET" or response.status_code != 200:
            return response
        if not path.startswith("/admin"):
            return response
        if path == "/admin" or path.startswith("/admin/email") or path in {"/admin/login", "/admin/logout"}:
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or 'id="ss-global-email-shortcut-style"' in body or "</body>" not in body:
                return response
            body = body.replace("</body>", EMAIL_ACCESS_SHORTCUT + "</body>", 1)
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not add global Email shortcut")
        return response
