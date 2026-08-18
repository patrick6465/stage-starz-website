from __future__ import annotations

import html

from flask import request


PERFORMANCE_SECTIONS = [
    {
        "prefix": "/admin/competitions",
        "path": "/admin/competitions",
        "label": "Competitions",
        "title": "Competition Center",
        "icon": "🏆",
        "description": "Competition events, routines, dancers, deadlines, music, travel and awards.",
    },
    {
        "prefix": "/admin/recitals",
        "path": "/admin/recitals",
        "label": "Recitals",
        "title": "Recital Center",
        "icon": "🎭",
        "description": "Recital productions, shows, lineups, rehearsals and performance planning.",
    },
    {
        "prefix": "/admin/production",
        "path": "/admin/production",
        "label": "Production",
        "title": "Production Center",
        "icon": "🎬",
        "description": "Show running order, dancers, backstage cues, readiness and live control.",
    },
    {
        "prefix": "/admin/ticketing",
        "path": "/admin/ticketing",
        "label": "Ticketing",
        "title": "Reserved Ticketing",
        "icon": "🎟️",
        "description": "Venues, reserved seats, ticket orders, holds, check-in and show sales.",
    },
]


PERFORMANCE_STYLE = r"""
<style id="ss-performance-workspace-style">
:root{
  --ss-night:#090510;--ss-night2:#17102a;--ss-panel:#17102a;--ss-panel2:#100a1d;
  --ss-line:rgba(255,255,255,.13);--ss-muted:#b8adca;--ss-pink:#ef3d98;
  --ss-purple:#9b4dcc;--ss-teal:#50d6d0;--ss-gold:#ffc867;--ss-success:#62e6aa;
}
html{scroll-behavior:smooth}
body{
  min-height:100vh!important;color:#fff!important;
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;
  background:
    radial-gradient(circle at 6% 0%,rgba(239,61,152,.18),transparent 28rem),
    radial-gradient(circle at 95% 4%,rgba(80,214,208,.12),transparent 30rem),
    linear-gradient(145deg,var(--ss-night),var(--ss-night2))!important;
  padding-bottom:28px;
}
body > header:not(#ss-performance-workspace){display:none!important}
#ss-performance-workspace{
  display:block!important;width:100%!important;box-sizing:border-box!important;
  position:sticky;top:0;z-index:1000;background:rgba(9,5,16,.96);
  border-bottom:1px solid var(--ss-line);backdrop-filter:blur(22px);
  box-shadow:0 10px 34px rgba(0,0,0,.22)
}
.ss-performance-top{
  width:100%;box-sizing:border-box;min-height:72px;padding:12px clamp(14px,4vw,44px);
  display:flex!important;align-items:center;justify-content:space-between;gap:18px
}
.ss-performance-brand{display:flex;align-items:center;gap:12px;min-width:0}
.ss-performance-back{
  width:42px;height:42px;flex:0 0 42px;display:grid;place-items:center;border-radius:13px;
  border:1px solid var(--ss-line);background:rgba(255,255,255,.055);font-size:1.15rem
}
.ss-performance-heading{min-width:0}.ss-performance-kicker{
  color:var(--ss-teal);font-size:.68rem;font-weight:950;text-transform:uppercase;
  letter-spacing:.12em;margin-bottom:2px
}
.ss-performance-heading h1{margin:0;font-size:clamp(1.12rem,3vw,1.5rem);line-height:1.15}
.ss-performance-heading p{margin:4px 0 0;color:var(--ss-muted);font-size:.78rem;line-height:1.35}
.ss-performance-actions{display:flex;gap:8px;align-items:center;flex:0 0 auto}
.ss-performance-action{
  display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:40px;
  padding:9px 12px;border:1px solid var(--ss-line);border-radius:12px;
  background:rgba(255,255,255,.05);color:#fff!important;font-size:.78rem;font-weight:850
}
.ss-performance-action:hover{border-color:rgba(80,214,208,.42);background:rgba(80,214,208,.07)}
.ss-performance-tabs{
  width:100%;box-sizing:border-box;display:flex!important;gap:7px;overflow-x:auto;
  padding:0 clamp(14px,4vw,44px) 11px;scrollbar-width:none;-webkit-overflow-scrolling:touch
}
.ss-performance-tabs::-webkit-scrollbar{display:none}
.ss-performance-tab{
  flex:0 0 auto;display:flex;align-items:center;gap:7px;padding:9px 12px;border-radius:11px;
  border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.035);
  color:#ddd4e8!important;font-size:.78rem;font-weight:850;white-space:nowrap
}
.ss-performance-tab:hover{border-color:rgba(80,214,208,.34)}
.ss-performance-tab.active{
  color:#fff!important;border-color:rgba(80,214,208,.30);
  background:linear-gradient(110deg,rgba(239,61,152,.20),rgba(155,77,204,.25),rgba(80,214,208,.15))
}
body .card,body .panel,body .stat,body .section,body .toolbar,body .table-wrap,body .item{
  border-color:var(--ss-line)!important
}
body .card,body .panel,body .section{
  background:rgba(23,16,42,.94)!important;color:#fff!important;
  box-shadow:0 18px 50px rgba(0,0,0,.16)
}
body .wrap{margin-top:20px!important}
body .muted,body .label,body .small,body .helper,body .note{color:var(--ss-muted)!important}
body input:not([type="checkbox"]):not([type="radio"]),body textarea,body select{
  border:1px solid #49365f!important;border-radius:11px!important;background:var(--ss-panel2)!important;
  color:#fff!important;font:inherit!important;outline:none
}
body input:not([type="checkbox"]):not([type="radio"]):focus,body textarea:focus,body select:focus{
  border-color:var(--ss-teal)!important;box-shadow:0 0 0 3px rgba(80,214,208,.10)!important
}
body button,body .button,body .btn{font-family:inherit}
body .primary,body button.primary{
  background:linear-gradient(110deg,var(--ss-pink),var(--ss-purple),var(--ss-teal))!important;color:#fff!important
}
body table{background:rgba(23,16,42,.95)!important;color:#fff!important}
body th{color:#d8cfdf!important}
body td,body th{border-color:rgba(255,255,255,.10)!important}
body .table-wrap{background:rgba(23,16,42,.94)!important}
body a{color:inherit}
.ss-performance-mobile-dock{display:none}
@media(max-width:760px){
  body{padding-bottom:112px!important}
  #ss-performance-workspace{display:block!important;width:100%!important}
  .ss-performance-top{width:100%!important;min-height:66px;padding:10px 12px;gap:10px}
  .ss-performance-brand{flex:1 1 auto;min-width:0}
  .ss-performance-back{width:40px;height:40px;flex-basis:40px}
  .ss-performance-heading p{display:none}
  .ss-performance-actions{flex:0 0 auto}
  .ss-performance-actions .ss-performance-action:first-child{display:none!important}
  .ss-performance-action{padding:8px 10px;min-width:40px}
  .ss-performance-tabs{display:flex!important;width:100%!important;padding:0 12px 10px;gap:6px}
  .ss-performance-tab{padding:8px 10px;font-size:.73rem}
  body .wrap{margin-top:14px!important}
  body .card,body .panel,body .section,body .table-wrap{border-radius:18px!important}
  .ss-performance-mobile-dock{
    position:fixed;display:grid;grid-template-columns:repeat(4,1fr);left:10px;right:10px;bottom:10px;
    z-index:1100;border:1px solid var(--ss-line);background:rgba(10,6,18,.96);
    backdrop-filter:blur(22px);border-radius:17px;padding:6px;box-shadow:0 14px 38px rgba(0,0,0,.36)
  }
  .ss-performance-mobile-dock a{text-align:center;color:var(--ss-muted)!important;font-size:.62rem;padding:5px 2px}
  .ss-performance-mobile-dock b{display:block;color:#fff;font-size:1.08rem;margin-bottom:2px}
}
@media(max-width:460px){
  .ss-performance-kicker{font-size:.6rem}.ss-performance-heading h1{font-size:1.05rem}
  .ss-performance-action{font-size:.72rem}.ss-performance-action .wide-label{display:none}
}
</style>
<script id="ss-performance-workspace-script">
document.addEventListener('DOMContentLoaded',function(){
  var nav=document.querySelector('.ss-performance-tabs');
  var active=nav&&nav.querySelector('.ss-performance-tab.active');
  if(nav&&active){
    var left=active.offsetLeft-(nav.clientWidth-active.offsetWidth)/2;
    nav.scrollLeft=Math.max(0,left);
  }
});
</script>
"""


def _base_section(path: str):
    for item in PERFORMANCE_SECTIONS:
        if path == item["prefix"] or path.startswith(item["prefix"] + "/"):
            return dict(item)
    return None


def _section_for_path(path: str):
    current = _base_section(path)
    if not current:
        return None

    if current["prefix"] == "/admin/competitions":
        if "/routines/" in path:
            current["title"] = "Routine Details"
            current["description"] = "Routine dancers, entry status, music, fees, travel and awards."
        elif path != "/admin/competitions":
            current["title"] = "Competition Details"
            current["description"] = "Competition routines, dancers, deadlines, travel and event readiness."

    elif current["prefix"] == "/admin/recitals":
        if "/shows/" in path:
            current["title"] = "Recital Show"
            current["description"] = "Show lineup, performance order, music status and rehearsal planning."
        elif "/productions/" in path:
            current["title"] = "Recital Production"
            current["description"] = "Production shows, venue, season, ticket status and rehearsal planning."

    elif current["prefix"] == "/admin/production":
        if "/performances/" in path:
            current["title"] = "Performance Details"
            current["description"] = "Dancer assignments, quick changes, backstage notes and technical cues."
        elif path.endswith("/live"):
            current["title"] = "Live Show Control"
            current["description"] = "Run the current, next and on-deck performances during the show."
        elif "/shows/" in path:
            current["title"] = "Production Show"
            current["description"] = "Running order, backstage checklist, dancers, cues and readiness."

    elif current["prefix"] == "/admin/ticketing":
        if path.endswith("/checkin"):
            current["title"] = "Ticket Check-In"
            current["description"] = "Door check-in, ticket lookup, re-entry rules and attendance."
        elif "/shows/" in path:
            current["title"] = "Show Ticketing"
            current["description"] = "Seat map, sales status, pricing, holds and digital ticket settings."
        elif "/venues/" in path:
            current["title"] = "Venue & Seating"
            current["description"] = "Reserved seating sections, rows, seats and venue configuration."
        elif "/orders/" in path:
            current["title"] = "Ticket Order"
            current["description"] = "Customer order details, reserved seats, payment and ticket status."
        elif "/holds/" in path:
            current["title"] = "Seat Hold"
            current["description"] = "Reserved-seat hold details, family assignment and release controls."

    return current


def _workspace_markup(current: dict) -> str:
    tabs = []
    for item in PERFORMANCE_SECTIONS:
        active = " active" if item["prefix"] == current["prefix"] else ""
        tabs.append(
            f'<a class="ss-performance-tab{active}" href="{item["path"]}">'
            f'<span>{item["icon"]}</span><span>{html.escape(item["label"])}</span></a>'
        )

    return f"""
<header id="ss-performance-workspace">
  <div class="ss-performance-top">
    <div class="ss-performance-brand">
      <a class="ss-performance-back" href="/admin#recital-competition" aria-label="Back to Command Center">←</a>
      <div class="ss-performance-heading">
        <div class="ss-performance-kicker">Recital &amp; Competition</div>
        <h1>{current['icon']} {html.escape(current['title'])}</h1>
        <p>{html.escape(current['description'])}</p>
      </div>
    </div>
    <div class="ss-performance-actions">
      <a class="ss-performance-action" href="/recital-2027.html" target="_blank">↗ <span class="wide-label">Recital Page</span></a>
      <a class="ss-performance-action" href="/admin">◈ <span class="wide-label">Command Center</span></a>
    </div>
  </div>
  <nav class="ss-performance-tabs" aria-label="Recital and Competition tools">
    {''.join(tabs)}
  </nav>
</header>
<nav class="ss-performance-mobile-dock" aria-label="Recital and Competition mobile navigation">
  <a href="/admin"><b>◈</b>Home</a>
  <a href="/admin/competitions"><b>🏆</b>Competition</a>
  <a href="/admin/recitals"><b>🎭</b>Recital</a>
  <a href="/admin/ticketing"><b>🎟️</b>Tickets</a>
</nav>
"""


def register_performance_workspace_polish(app) -> None:
    """Unify recital, competition, production and ticketing admin screens."""

    @app.after_request
    def add_performance_workspace(response):
        path = request.path.rstrip("/") or "/"
        current = _section_for_path(path)
        if not current or response.mimetype != "text/html":
            return response
        if request.method != "GET" or response.status_code != 200:
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or 'id="ss-performance-workspace"' in body:
                return response
            if "</head>" in body:
                body = body.replace("</head>", PERFORMANCE_STYLE + "</head>", 1)
            markup = _workspace_markup(current)
            body_start = body.find("<body")
            if body_start >= 0:
                body_close = body.find(">", body_start)
                if body_close >= 0:
                    body = body[: body_close + 1] + markup + body[body_close + 1 :]
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply Recital & Competition workspace UI")
        return response
