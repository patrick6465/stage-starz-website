from __future__ import annotations

from flask import request


VIDEO_LINK = '<a href="/admin/website/videos">🎬 Website Videos</a>'
TEXT_LINK = '<a href="/admin/website/page-text">✏️ Page Text Editor</a>'
MOBILE_VIDEO_LINK = '<a href="/admin/website/videos"><b>🎬</b>Videos</a>'
MOBILE_TEXT_LINK = '<a href="/admin/website/page-text"><b>✏️</b>Text</a>'


def register_video_admin_nav(app) -> None:
    """Keep website maintenance tools easy to reach from admin screens."""

    @app.after_request
    def add_video_admin_navigation(response):
        if response.mimetype != "text/html":
            return response
        if request.path not in {
            "/admin",
            "/admin/website/homepage",
            "/admin/media",
            "/admin/website/videos",
            "/admin/website/page-text",
        }:
            return response

        try:
            body = response.get_data(as_text=True)
            changed = False

            # Command Center 3 groups these destinations natively. Do not let the
            # older link injector crowd its sidebar or mobile navigation again.
            if request.path == "/admin" and 'id="command-center-v3"' in body:
                return response

            if request.path == "/admin":
                homepage = '<a href="/admin/website/homepage">🏠 Homepage Editor</a>'
                if VIDEO_LINK not in body and homepage in body:
                    body = body.replace(homepage, homepage + VIDEO_LINK, 1)
                    changed = True
                if TEXT_LINK not in body:
                    anchor = VIDEO_LINK if VIDEO_LINK in body else homepage
                    if anchor in body:
                        body = body.replace(anchor, anchor + TEXT_LINK, 1)
                        changed = True

                if MOBILE_VIDEO_LINK not in body:
                    logout = '<a href="/admin/logout"><b>↪</b>Log Out</a>'
                    if logout in body:
                        body = body.replace(logout, MOBILE_VIDEO_LINK + logout, 1)
                        changed = True
                if MOBILE_TEXT_LINK not in body:
                    logout = '<a href="/admin/logout"><b>↪</b>Log Out</a>'
                    if logout in body:
                        body = body.replace(logout, MOBILE_TEXT_LINK + logout, 1)
                        changed = True

                style = """
<style id="website-video-mobile-nav-fix">
@media(max-width:760px){
  .mobile-nav{grid-template-columns:repeat(7,1fr)!important}
  .mobile-nav a{font-size:.54rem!important;line-height:1.15}
}
</style>
"""
                if 'id="website-video-mobile-nav-fix"' not in body:
                    body = body.replace("</head>", style + "</head>", 1)
                    changed = True

            elif request.path == "/admin/website/homepage":
                video_plain = '<a href="/admin/website/videos">Website Videos</a>'
                text_plain = '<a href="/admin/website/page-text">Page Text Editor</a>'
                if video_plain not in body:
                    media = '<a href="/admin/media">Media Library</a>'
                    if media in body:
                        body = body.replace(media, media + video_plain, 1)
                        changed = True
                if text_plain not in body:
                    anchor = video_plain if video_plain in body else '<a href="/admin/media">Media Library</a>'
                    if anchor in body:
                        body = body.replace(anchor, anchor + text_plain, 1)
                        changed = True

            elif request.path == "/admin/media":
                video_plain = '<a href="/admin/website/videos">Website Videos</a>'
                text_plain = '<a href="/admin/website/page-text">Page Text Editor</a>'
                command = '<a href="/admin">Command Center</a>'
                if video_plain not in body and command in body:
                    body = body.replace(command, command + ' &nbsp; ' + video_plain, 1)
                    changed = True
                if text_plain not in body:
                    anchor = video_plain if video_plain in body else command
                    if anchor in body:
                        body = body.replace(anchor, anchor + ' &nbsp; ' + text_plain, 1)
                        changed = True

                old = "Accepted: JPG, PNG, WEBP, or GIF. Maximum size: 10 MB."
                new = "Accepted: JPG, PNG, WEBP, or GIF. Maximum source size: 25 MB."
                if old in body:
                    body = body.replace(old, new, 1)
                    changed = True

            if changed:
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not add website maintenance tools to admin navigation")
        return response