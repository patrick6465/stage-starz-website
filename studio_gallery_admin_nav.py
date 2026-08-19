from __future__ import annotations

from flask import request

from website_workspace_polish import WORKSPACE_STYLE


GALLERY_PATH = "/admin/website/studio-gallery"
WORKSPACE_PATHS = {
    "/admin/website/homepage",
    "/admin/website/page-text",
    "/admin/website/classes",
    "/admin/website/videos",
    "/admin/media",
    "/admin/website/inquiries",
    GALLERY_PATH,
}


def _gallery_workspace_markup() -> str:
    tabs = (
        '<a class="ss-workspace-tab" href="/admin/website/homepage"><span>🏠</span><span>Homepage</span></a>'
        '<a class="ss-workspace-tab" href="/admin/website/page-text"><span>✏️</span><span>Page Text</span></a>'
        '<a class="ss-workspace-tab" href="/admin/website/classes"><span>📄</span><span>Class Pages</span></a>'
        '<a class="ss-workspace-tab" href="/admin/website/videos"><span>🎬</span><span>Videos</span></a>'
        '<a class="ss-workspace-tab" href="/admin/media"><span>🖼️</span><span>Media</span></a>'
        '<a class="ss-workspace-tab" href="/admin/website/inquiries"><span>📨</span><span>Inquiries</span></a>'
        '<a class="ss-workspace-tab active" href="/admin/website/studio-gallery"><span>📷</span><span>Studio Gallery</span></a>'
    )
    return f"""
<header id="ss-website-workspace">
  <div class="ss-workspace-top">
    <div class="ss-workspace-brand">
      <a class="ss-workspace-back" href="/admin#website-management" aria-label="Back to Command Center">←</a>
      <div class="ss-workspace-heading">
        <div class="ss-workspace-kicker">Website Management</div>
        <h1>📷 Studio Gallery</h1>
        <p>Current studio, dancer, staff and exterior photos used on public pages.</p>
      </div>
    </div>
    <div class="ss-workspace-actions">
      <a class="ss-workspace-action ss-open-site" href="/" target="_blank">↗ <span class="wide-label">Open Website</span></a>
      <a class="ss-workspace-action" href="/admin">◈ <span class="wide-label">Command Center</span></a>
    </div>
  </div>
  <nav class="ss-workspace-tabs" aria-label="Website Management tools">{tabs}</nav>
</header>
<nav class="ss-workspace-mobile-dock" aria-label="Website workspace mobile navigation">
  <a href="/admin"><b>◈</b>Home</a>
  <a href="/admin#website-management"><b>🌐</b>Website</a>
  <a href="/" target="_blank"><b>↗</b>Live Site</a>
  <a href="/admin/logout"><b>↪</b>Log Out</a>
</nav>
"""


def register_studio_gallery_admin_nav(app) -> None:
    """Surface Studio Gallery in Command Center and Website Management navigation."""

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

            changed = False

            # Studio Gallery is a Website Management screen, so give it the same
            # sticky workspace header, tabs and mobile dock as the other editors.
            if path == GALLERY_PATH and 'id="ss-website-workspace"' not in body:
                if 'id="ss-website-workspace-style"' not in body and "</head>" in body:
                    body = body.replace("</head>", WORKSPACE_STYLE + "</head>", 1)
                markup = _gallery_workspace_markup()
                body_start = body.find("<body")
                body_close = body.find(">", body_start) if body_start >= 0 else -1
                if body_close >= 0:
                    body = body[: body_close + 1] + markup + body[body_close + 1 :]
                    changed = True

            # The redesigned Command Center uses .tool-link cards. Insert Gallery
            # immediately after Media Library inside Website Management.
            elif path == "/admin" and GALLERY_PATH not in body:
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

            # Existing Website Management shells were built before Gallery existed.
            # Append the Gallery tab to those screens once, without duplicating it.
            elif path in WORKSPACE_PATHS and path != GALLERY_PATH and GALLERY_PATH not in body:
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
