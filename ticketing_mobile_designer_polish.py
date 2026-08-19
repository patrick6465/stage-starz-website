from __future__ import annotations

from flask import request


MOBILE_STYLE = r"""
<style id="ss-ticketing-mobile-designer-polish">
@media (max-width: 900px) {
  body.ss-ticket-venue-mobile .canvas-shell,
  body.ss-ticket-show-mobile .canvas-shell {
    position: relative !important;
    width: 100% !important;
    max-width: 100% !important;
    height: min(68vh, 680px) !important;
    min-height: 430px !important;
    overflow: auto !important;
    -webkit-overflow-scrolling: touch !important;
    overscroll-behavior: contain !important;
    touch-action: pan-x pan-y !important;
    scroll-behavior: smooth;
    scroll-padding: 18px 18px 125px;
    padding: 12px 12px 125px !important;
  }

  body.ss-ticket-venue-mobile .canvas-shell.ss-layout-locked .section,
  body.ss-ticket-venue-mobile .canvas-shell.ss-layout-locked .object {
    pointer-events: none !important;
    touch-action: pan-x pan-y !important;
    cursor: default !important;
  }

  body.ss-ticket-venue-mobile .ss-mobile-canvas-hint,
  body.ss-ticket-show-mobile .ss-mobile-canvas-hint {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px 12px;
    margin: 12px 0;
    padding: 12px 14px;
    border: 1px solid #38294a;
    border-radius: 12px;
    background: #100a1d;
    color: #d9cfdf;
    font-size: .9rem;
    line-height: 1.4;
    font-weight: 750;
  }

  body.ss-ticket-venue-mobile .ss-mobile-canvas-hint strong,
  body.ss-ticket-show-mobile .ss-mobile-canvas-hint strong {
    color: #50d6d0;
  }

  body.ss-ticket-show-mobile .ss-mobile-seat-count {
    margin-left: auto;
    color: #fff;
    font-size: .82rem;
    white-space: nowrap;
  }

  body.ss-ticket-show-mobile .seat-choice {
    touch-action: manipulation !important;
    -webkit-tap-highlight-color: transparent;
  }

  body.ss-ticket-show-mobile .seat-choice span {
    min-width: 44px !important;
    box-sizing: border-box;
  }

  body.ss-ticket-show-mobile .seat-choice input:checked + span {
    box-shadow: 0 0 0 2px rgba(80,214,208,.32);
  }

  body.ss-ticket-venue-mobile .drag-help {
    line-height: 1.45;
  }

  body.ss-ticket-venue-mobile .card:has(.canvas-shell),
  body.ss-ticket-show-mobile .card:has(.canvas-shell) {
    padding-bottom: 24px !important;
  }

  body.ss-ticket-venue-mobile main.wrap,
  body.ss-ticket-show-mobile main.wrap {
    padding-bottom: 138px !important;
  }

  body.ss-ticket-show-mobile .tabs {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    padding-bottom: 3px;
  }
}
</style>
"""


MOBILE_SCRIPT = r"""
<script id="ss-ticketing-mobile-designer-script">
(() => {
  const setup = () => {
    if (!window.matchMedia('(max-width: 900px)').matches) return;
    const shell = document.querySelector('.canvas-shell');
    if (!shell) return;

    const path = window.location.pathname.replace(/\/$/, '');
    const venueMode = /^\/admin\/ticketing\/venues\/\d+$/.test(path);
    const showMode = /^\/admin\/ticketing\/shows\/\d+$/.test(path);
    if (!venueMode && !showMode) return;

    const addHint = (html) => {
      if (shell.previousElementSibling && shell.previousElementSibling.classList.contains('ss-mobile-canvas-hint')) {
        return shell.previousElementSibling;
      }
      const hint = document.createElement('div');
      hint.className = 'ss-mobile-canvas-hint';
      hint.innerHTML = html;
      shell.parentNode.insertBefore(hint, shell);
      return hint;
    };

    const centerCanvas = () => {
      requestAnimationFrame(() => {
        if (shell.scrollWidth > shell.clientWidth && shell.scrollLeft === 0) {
          shell.scrollLeft = Math.max(0, (shell.scrollWidth - shell.clientWidth) / 2);
        }
      });
    };

    if (venueMode) {
      document.body.classList.add('ss-ticket-venue-mobile');

      const heading = Array.from(document.querySelectorAll('h2')).find(
        h => h.textContent.trim() === 'Mouse-Position Venue Designer'
      );
      if (heading) heading.textContent = 'Venue Layout Designer';

      const help = document.querySelector('.drag-help');
      const status = document.getElementById('drag-status');
      const locked = !!(status && /layout locked/i.test(status.textContent || ''));

      if (locked) shell.classList.add('ss-layout-locked');

      if (help) {
        help.textContent = locked
          ? 'This seating layout is locked because ticket history exists. Swipe inside the theater map to explore the full chart.'
          : 'Swipe empty areas to pan around the theater. Press and drag a seating section or theater object to reposition it.';
      }

      addHint(
        locked
          ? '<strong>↔ Swipe to explore</strong><span>The full theater is wider and taller than your phone screen.</span>'
          : '<strong>Touch controls</strong><span>Swipe empty space to pan; press and drag a section or object to move it.</span>'
      );

      centerCanvas();
      return;
    }

    document.body.classList.add('ss-ticket-show-mobile');

    const selectHeading = Array.from(document.querySelectorAll('h2')).find(
      h => h.textContent.trim() === 'Select Seats'
    );
    const mapCard = selectHeading ? selectHeading.closest('.card') : null;
    const mapHelp = mapCard ? mapCard.querySelector('.muted') : null;
    if (mapHelp) {
      mapHelp.textContent = 'Swipe the theater map to explore. Tap any available seat to select it; sold and held seats are read-only.';
    }

    const hint = addHint(
      '<strong>↔ Swipe to explore</strong><span>Tap available seats to select them.</span><span class="ss-mobile-seat-count">0 selected</span>'
    );
    const countNode = hint.querySelector('.ss-mobile-seat-count');
    const seatInputs = Array.from(document.querySelectorAll('input[name="seat_id"]'));

    const updateCount = () => {
      if (!countNode) return;
      const count = seatInputs.filter(input => input.checked).length;
      countNode.textContent = `${count} seat${count === 1 ? '' : 's'} selected`;
    };

    seatInputs.forEach(input => input.addEventListener('change', updateCount));
    updateCount();
    centerCanvas();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(setup, 0), { once: true });
  } else {
    setTimeout(setup, 0);
  }
})();
</script>
"""


def register_ticketing_mobile_designer_polish(app) -> None:
    """Make reserved-ticketing venue and show canvases practical on touch screens."""

    @app.after_request
    def polish_ticketing_mobile(response):
        if request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html":
            return response

        path = request.path.rstrip("/") or "/"
        venue_page = path.startswith("/admin/ticketing/venues/") and path != "/admin/ticketing/venues/save"
        show_parts = path.split("/")
        show_page = (
            len(show_parts) == 5
            and show_parts[:4] == ["", "admin", "ticketing", "shows"]
            and show_parts[4].isdigit()
        )
        if not venue_page and not show_page:
            return response

        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if "canvas-shell" not in body:
                return response
            if venue_page and "Coordinate Venue Designer" not in body:
                return response
            if show_page and "Select Seats" not in body:
                return response

            if 'id="ss-ticketing-mobile-designer-polish"' not in body:
                body = body.replace("</head>", MOBILE_STYLE + "</head>", 1)
            if 'id="ss-ticketing-mobile-designer-script"' not in body:
                body = body.replace("</body>", MOBILE_SCRIPT + "</body>", 1)

            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply mobile ticketing canvas polish")

        return response
