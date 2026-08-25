from __future__ import annotations

import html
import re
from pathlib import Path

from flask import request

import website_video_manager as video_manager


SLOT_KEY = "home_shop_banner"

BANNER_LINK_RE = re.compile(
    r'(<a\b[^>]*class=["\'][^"\']*\bapproved-shop-link\b[^"\']*["\'][^>]*>).*?(</a>)',
    re.IGNORECASE | re.DOTALL,
)

BANNER_STYLE = r"""
<style id="ss-home-shop-banner-media-style">
.approved-shop-link .ss-home-shop-banner-media{
  display:block;
  width:100%;
  height:auto;
  max-width:100%;
  object-fit:contain;
  object-position:center;
  pointer-events:none;
}
.approved-shop-link video.ss-home-shop-banner-media{
  background:#05050c;
}
</style>
"""


def _is_gif(media_url: str) -> bool:
    return Path(media_url.split("?", 1)[0]).suffix.lower() == ".gif"


def _banner_media_markup(media_url: str) -> str:
    safe_url = html.escape(media_url, quote=True)
    if _is_gif(media_url):
        return (
            f'<img class="ss-home-shop-banner-media" src="{safe_url}" '
            'alt="Stardust Ship-it-Shop animated banner" loading="eager">'
        )
    return (
        f'<video class="ss-home-shop-banner-media" src="{safe_url}" '
        'autoplay muted loop playsinline preload="metadata" '
        'aria-label="Stardust Ship-it-Shop banner video"></video>'
    )


def register_homepage_shop_banner_library(app) -> None:
    """Let the Website Video Library control the clickable homepage shop banner."""

    video_manager.VIDEO_SLOTS.setdefault(
        SLOT_KEY,
        {
            "label": "Homepage Shop Banner",
            "description": (
                "Replaces the clickable Stardust Ship-it-Shop banner below the homepage hero. "
                "Animated GIFs play automatically; MP4 videos loop silently."
            ),
            "page_url": "/",
        },
    )

    @app.after_request
    def render_homepage_shop_banner(response):
        if request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html":
            return response
        path = request.path.rstrip("/") or "/"
        if path not in {"/", "/index.html", "/index-new.html"}:
            return response

        try:
            values = video_manager._settings()
            media_url = video_manager._valid_video_url(values.get(SLOT_KEY, ""))
            if not media_url:
                return response

            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body:
                return response

            media_markup = _banner_media_markup(media_url)

            def replacement(match: re.Match[str]) -> str:
                return f"{match.group(1)}\n      {media_markup}\n    {match.group(2)}"

            updated, count = BANNER_LINK_RE.subn(replacement, body, count=1)
            if not count:
                return response

            if 'id="ss-home-shop-banner-media-style"' not in updated and "</head>" in updated:
                updated = updated.replace("</head>", BANNER_STYLE + "</head>", 1)

            response.set_data(updated)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
            response.headers.pop("Last-Modified", None)
        except Exception:
            app.logger.exception("Could not render Homepage Shop Banner media")
        return response
