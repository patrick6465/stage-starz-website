from __future__ import annotations

from flask import request


WORKSPACE_PATHS = {
    "/admin/website/homepage",
    "/admin/website/page-text",
    "/admin/website/classes",
    "/admin/website/videos",
    "/admin/media",
    "/admin/website/inquiries",
}


def register_studio_gallery_admin_nav(app) -> None:
    """Surface Studio Gallery in Command Center and the existing website workspace tabs."""

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
            if not body or '/admin/website/studio-gallery' in body:
                return response

            changed = False
            if path in WORKSPACE_PATHS and 'class="ss-workspace-tabs"' in body:
                nav_start = body.find('<nav class="ss-workspace-tabs"')
                nav_end = body.find("</nav>", nav_start)
                if nav_start >= 0 and nav_end >= 0:
                    gallery_tab = (
                        '<a class="ss-workspace-tab" href="/admin/website/studio-gallery">'
                        '<span>📷</span><span>Studio Gallery</span></a>'
                    )
                    body = body[:nav_end] + gallery_tab + body[nav_end:]
                    changed = True

            elif path == "/admin":
                gallery_link = '<a href="/admin/website/studio-gallery">📷 Studio Gallery</a>'
                video_link = '<a href="/admin/website/videos">🎬 Website Videos</a>'
                media_link = '<a href="/admin/media">🖼️ Media Library</a>'
                if video_link in body:
                    body = body.replace(video_link, video_link + gallery_link, 1)
                    changed = True
                elif media_link in body:
                    body = body.replace(media_link, gallery_link + media_link, 1)
                    changed = True

            if changed:
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not add Studio Gallery admin navigation")
        return response
