from __future__ import annotations

from flask import request


WORKSPACE_PATHS = {
    "/admin/website/homepage",
    "/admin/website/page-text",
    "/admin/website/classes",
    "/admin/website/videos",
    "/admin/media",
    "/admin/website/inquiries",
    "/admin/website/studio-gallery",
}


def register_studio_gallery_admin_nav(app) -> None:
    """Surface Studio Gallery in Command Center and Website Management tabs."""

    @app.after_request
    def add_studio_gallery_navigation(response):
        if request.method != "GET" or response.status_code != 200 or response.mimetype != "text/html":
            return response

        path = request.path.rstrip("/") or "/"
        if path not in WORKSPACE_PATHS and path != "/admin":
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body:
                return response

            gallery_url = "/admin/website/studio-gallery"
            changed = False

            # The redesigned Command Center uses .tool-link cards rather than the
            # older plain anchors. Insert Gallery immediately after Media Library
            # so it appears naturally inside Website Management on desktop/mobile.
            if path == "/admin" and gallery_url not in body:
                gallery_link = (
                    '<a class="tool-link" href="/admin/website/studio-gallery">'
                    '<span class="tool-icon">📷</span><span>Studio Gallery</span></a>'
                )
                media_link = (
                    '<a class="tool-link" href="/admin/media">'
                    '<span class="tool-icon">🖼</span><span>Media Library</span></a>'
                )
                if media_link in body:
                    body = body.replace(media_link, media_link + gallery_link, 1)
                    changed = True
                else:
                    card_start = body.find('id="website-management"')
                    card_end = body.find("</article>", card_start) if card_start >= 0 else -1
                    tool_start = body.find('<div class="tool-list">', card_start, card_end) if card_end >= 0 else -1
                    tool_end = body.find("</div>", tool_start, card_end) if tool_start >= 0 else -1
                    if tool_end >= 0:
                        body = body[:tool_end] + gallery_link + body[tool_end:]
                        changed = True

            # Existing Website Management pages already receive the shared shell.
            # If an older deployed shell lacks Gallery, append its tab once.
            elif path in WORKSPACE_PATHS and path != gallery_url and gallery_url not in body:
                nav_start = body.find('<nav class="ss-workspace-tabs"')
                nav_end = body.find("</nav>", nav_start) if nav_start >= 0 else -1
                if nav_end >= 0:
                    gallery_tab = (
                        '<a class="ss-workspace-tab" href="/admin/website/studio-gallery">'
                        '<span>📷</span><span>Studio Gallery</span></a>'
                    )
                    body = body[:nav_end] + gallery_tab + body[nav_end:]
                    changed = True

            if changed:
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not add Studio Gallery admin navigation")
        return response
