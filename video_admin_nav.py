from __future__ import annotations

from flask import request


VIDEO_LINK = '<a href="/admin/website/videos">🎬 Website Videos</a>'
MOBILE_VIDEO_LINK = '<a href="/admin/website/videos"><b>🎬</b>Videos</a>'


def register_video_admin_nav(app) -> None:
    """Keep Website Videos easy to reach from desktop and mobile admin screens."""

    @app.after_request
    def add_video_admin_navigation(response):
        if response.mimetype != "text/html":
            return response
        if request.path not in {"/admin", "/admin/website/homepage", "/admin/media"}:
            return response

        try:
            body = response.get_data(as_text=True)
            changed = False

            if request.path == "/admin":
                # Desktop sidebar: place Videos directly beneath Homepage Editor.
                homepage = '<a href="/admin/website/homepage">🏠 Homepage Editor</a>'
                if VIDEO_LINK not in body and homepage in body:
                    body = body.replace(homepage, homepage + VIDEO_LINK, 1)
                    changed = True

                # Mobile bottom nav: Class Pages is injected by the class editor;
                # add Videos as another direct website-maintenance destination.
                if MOBILE_VIDEO_LINK not in body:
                    logout = '<a href="/admin/logout"><b>↪</b>Log Out</a>'
                    if logout in body:
                        body = body.replace(logout, MOBILE_VIDEO_LINK + logout, 1)
                        changed = True

                style = """
<style id="website-video-mobile-nav-fix">
@media(max-width:760px){
  .mobile-nav{grid-template-columns:repeat(6,1fr)!important}
  .mobile-nav a{font-size:.58rem!important;line-height:1.15}
}
</style>
"""
                if 'id="website-video-mobile-nav-fix"' not in body:
                    body = body.replace("</head>", style + "</head>", 1)
                    changed = True

            elif request.path == "/admin/website/homepage":
                plain_link = '<a href="/admin/website/videos">Website Videos</a>'
                if plain_link not in body:
                    media = '<a href="/admin/media">Media Library</a>'
                    if media in body:
                        body = body.replace(media, media + plain_link, 1)
                        changed = True

            elif request.path == "/admin/media":
                plain_link = '<a href="/admin/website/videos">Website Videos</a>'
                if plain_link not in body:
                    command = '<a href="/admin">Command Center</a>'
                    if command in body:
                        body = body.replace(command, command + ' &nbsp; ' + plain_link, 1)
                        changed = True
                # Persistent image storage now accepts phone photos up to 25 MB.
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
            app.logger.exception("Could not add Website Videos to admin navigation")
        return response
