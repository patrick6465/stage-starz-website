from __future__ import annotations

from flask import request


PERFORMANCE_PREFIXES = (
    "/admin/competitions",
    "/admin/recitals",
    "/admin/production",
    "/admin/ticketing",
)


MOBILE_NAV_FIX_STYLE = r"""
<style id="ss-performance-mobile-nav-spacing-fix">
@media (max-width: 760px) {
  body {
    padding-bottom: 160px !important;
    scroll-padding-bottom: 145px !important;
  }

  body .wrap,
  body.ss-ticket-checkin-mobile .wrap,
  body.ss-ticket-order-mobile .wrap,
  body.ss-ticket-hold-mobile .wrap {
    padding-bottom: 170px !important;
  }

  .ss-performance-mobile-dock {
    bottom: max(8px, env(safe-area-inset-bottom)) !important;
    padding: 4px !important;
    border-radius: 15px !important;
  }

  .ss-performance-mobile-dock a {
    min-height: 48px !important;
    padding: 3px 1px !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    line-height: 1.05 !important;
  }

  .ss-performance-mobile-dock b {
    font-size: .95rem !important;
    line-height: 1 !important;
    margin-bottom: 2px !important;
  }

  body button,
  body .button,
  body .btn,
  body input,
  body textarea,
  body select,
  body .ticket,
  body .item {
    scroll-margin-bottom: 120px !important;
  }
}

@media (max-width: 430px) {
  .ss-performance-tabs {
    display: grid !important;
    grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
    gap: 4px !important;
    overflow-x: hidden !important;
    padding: 0 7px 9px !important;
  }

  .ss-performance-tab {
    width: auto !important;
    min-width: 0 !important;
    padding: 7px 3px !important;
    gap: 3px !important;
    justify-content: center !important;
    font-size: .61rem !important;
    line-height: 1.05 !important;
    letter-spacing: -.01em !important;
  }

  .ss-performance-tab span:first-child {
    flex: 0 0 auto !important;
    font-size: .86rem !important;
    line-height: 1 !important;
  }

  .ss-performance-tab span:last-child {
    min-width: 0 !important;
    overflow: hidden !important;
    text-overflow: clip !important;
  }
}
</style>
<script id="ss-performance-mobile-nav-spacing-script">
(function () {
  'use strict';

  function alignTabs() {
    if (window.innerWidth > 430) return;
    var nav = document.querySelector('.ss-performance-tabs');
    if (nav) nav.scrollLeft = 0;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', alignTabs, { once: true });
  } else {
    alignTabs();
  }
  window.addEventListener('resize', alignTabs);
})();
</script>
"""


def register_performance_mobile_nav_spacing_fix(app) -> None:
    """Keep mobile performance tabs fully visible and content clear of the fixed dock."""

    @app.after_request
    def polish_performance_mobile_navigation(response):
        if request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html":
            return response

        path = request.path.rstrip("/") or "/"
        if not any(path == prefix or path.startswith(prefix + "/") for prefix in PERFORMANCE_PREFIXES):
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or 'id="ss-performance-workspace"' not in body:
                return response
            if 'id="ss-performance-mobile-nav-spacing-fix"' in body:
                return response
            if "</head>" in body:
                body = body.replace("</head>", MOBILE_NAV_FIX_STYLE + "</head>", 1)
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
                response.headers.pop("Last-Modified", None)
        except Exception:
            app.logger.exception("Could not apply performance mobile navigation spacing fix")

        return response
