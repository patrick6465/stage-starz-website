from __future__ import annotations

import html

from flask import request


STUDIO_SECTIONS = [
    {
        "prefix": "/admin/families",
        "path": "/admin/families",
        "label": "Families",
        "title": "Families",
        "icon": "🏠",
        "description": "Households, contacts, notes, family activity and linked dancers.",
    },
    {
        "prefix": "/admin/customers",
        "path": "/admin/customers",
        "label": "Customers",
        "title": "Customers",
        "icon": "👥",
        "description": "Customer records, contact details, order history and CRM notes.",
    },
    {
        "prefix": "/admin/students",
        "path": "/admin/students",
        "label": "Students",
        "title": "Student Management",
        "icon": "🩰",
        "description": "Dancer profiles, family links, sizing, status and enrollment information.",
    },
    {
        "prefix": "/admin/classes",
        "path": "/admin/classes",
        "label": "Classes",
        "title": "Class Management",
        "icon": "📚",
        "description": "Studio classes, rosters, schedules, rooms, capacity and enrollment.",
    },
    {
        "prefix": "/admin/teachers",
        "path": "/admin/teachers",
        "label": "Teachers",
        "title": "Teacher Management",
        "icon": "👩‍🏫",
        "description": "Faculty records and class assignments.",
    },
    {
        "prefix": "/admin/attendance",
        "path": "/admin/attendance",
        "label": "Attendance",
        "title": "Attendance Center",
        "icon": "✅",
        "description": "Take attendance, review sessions and follow dancer attendance history.",
    },
    {
        "prefix": "/admin/billing",
        "path": "/admin/billing",
        "label": "Billing",
        "title": "Billing & Tuition",
        "icon": "💳",
        "description": "Family charges, payments, balances, due dates and receipts.",
    },
    {
        "prefix": "/admin/costumes",
        "path": "/admin/costumes",
        "label": "Costumes",
        "title": "Costume Center",
        "icon": "👗",
        "description": "Costume catalog, assignments, sizing, fulfillment and billing status.",
    },
]


STUDIO_STYLE = r"""
<style id="ss-studio-workspace-style">
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
    radial-gradient(circle at 5% 0%,rgba(239,61,152,.18),transparent 28rem),
    radial-gradient(circle at 96% 5%,rgba(80,214,208,.12),transparent 30rem),
    linear-gradient(145deg,var(--ss-night),var(--ss-night2))!important;
  padding-bottom:28px;
}
body > header:not(#ss-studio-workspace){display:none!important}
#ss-studio-workspace{
  display:block!important;width:100%!important;box-sizing:border-box!important;
  position:sticky;top:0;z-index:1000;background:rgba(9,5,16,.96);
  border-bottom:1px solid var(--ss-line);backdrop-filter:blur(22px);
  box-shadow:0 10px 34px rgba(0,0,0,.22)
}
.ss-studio-top{
  width:100%;box-sizing:border-box;min-height:72px;padding:12px clamp(14px,4vw,44px);
  display:flex!important;align-items:center;justify-content:space-between;gap:18px
}
.ss-studio-brand{display:flex;align-items:center;gap:12px;min-width:0}
.ss-studio-back{
  width:42px;height:42px;flex:0 0 42px;display:grid;place-items:center;border-radius:13px;
  border:1px solid var(--ss-line);background:rgba(255,255,255,.055);font-size:1.15rem
}
.ss-studio-heading{min-width:0}.ss-studio-kicker{
  color:var(--ss-teal);font-size:.68rem;font-weight:950;text-transform:uppercase;
  letter-spacing:.12em;margin-bottom:2px
}
.ss-studio-heading h1{margin:0;font-size:clamp(1.12rem,3vw,1.5rem);line-height:1.15}
.ss-studio-heading p{margin:4px 0 0;color:var(--ss-muted);font-size:.78rem;line-height:1.35}
.ss-studio-actions{display:flex;gap:8px;align-items:center;flex:0 0 auto}
.ss-studio-action{
  display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:40px;
  padding:9px 12px;border:1px solid var(--ss-line);border-radius:12px;
  background:rgba(255,255,255,.05);color:#fff!important;font-size:.78rem;font-weight:850
}
.ss-studio-action:hover{border-color:rgba(80,214,208,.42);background:rgba(80,214,208,.07)}
.ss-studio-tabs{
  width:100%;box-sizing:border-box;display:flex!important;gap:7px;overflow-x:auto;
  padding:0 clamp(14px,4vw,44px) 11px;scrollbar-width:none;-webkit-overflow-scrolling:touch
}
.ss-studio-tabs::-webkit-scrollbar{display:none}
.ss-studio-tab{
  flex:0 0 auto;display:flex;align-items:center;gap:7px;padding:9px 12px;border-radius:11px;
  border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.035);
  color:#ddd4e8!important;font-size:.78rem;font-weight:850;white-space:nowrap
}
.ss-studio-tab:hover{border-color:rgba(80,214,208,.34)}
.ss-studio-tab.active{
  color:#fff!important;border-color:rgba(80,214,208,.30);
  background:linear-gradient(110deg,rgba(239,61,152,.20),rgba(155,77,204,.25),rgba(80,214,208,.15))
}

/* Bring older operations screens into the same visual system without changing logic. */
body .card,body .panel,body .stat,body .section,body .toolbar,body .table-wrap{
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

.ss-studio-mobile-dock{display:none}
@media(max-width:760px){
  body{padding-bottom:112px!important}
  #ss-studio-workspace{display:block!important;width:100%!important}
  .ss-studio-top{width:100%!important;min-height:66px;padding:10px 12px;gap:10px}
  .ss-studio-brand{flex:1 1 auto;min-width:0}
  .ss-studio-back{width:40px;height:40px;flex-basis:40px}
  .ss-studio-heading p{display:none}
  .ss-studio-actions{flex:0 0 auto}
  .ss-studio-actions .ss-studio-action:first-child{display:none!important}
  .ss-studio-action{padding:8px 10px;min-width:40px}
  .ss-studio-tabs{display:flex!important;width:100%!important;padding:0 12px 10px;gap:6px}
  .ss-studio-tab{padding:8px 10px;font-size:.73rem}
  body .wrap{margin-top:14px!important}
  body .card,body .panel,body .section,body .table-wrap{border-radius:18px!important}
  body .actions{gap:10px}
  .ss-studio-mobile-dock{
    position:fixed;display:grid;grid-template-columns:repeat(4,1fr);left:10px;right:10px;bottom:10px;
    z-index:1100;border:1px solid var(--ss-line);background:rgba(10,6,18,.96);
    backdrop-filter:blur(22px);border-radius:17px;padding:6px;box-shadow:0 14px 38px rgba(0,0,0,.36)
  }
  .ss-studio-mobile-dock a{
    text-align:center;color:var(--ss-muted)!important;font-size:.62rem;padding:5px 2px
  }
  .ss-studio-mobile-dock b{display:block;color:#fff;font-size:1.08rem;margin-bottom:2px}
}
@media(max-width:460px){
  .ss-studio-kicker{font-size:.6rem}.ss-studio-heading h1{font-size:1.05rem}
  .ss-studio-action{font-size:.72rem}.ss-studio-action .wide-label{display:none}
}
</style>
"""


def _section_for_path(path: str):
    # Specific billing routes should remain Billing even when they reference families.
    if path.startswith("/admin/billing"):
        return next(item for item in STUDIO_SECTIONS if item["prefix"] == "/admin/billing")
    for item in STUDIO_SECTIONS:
        if path == item["prefix"] or path.startswith(item["prefix"] + "/"):
            return item
    return None


def _workspace_markup(current: dict) -> str:
    tabs = []
    for item in STUDIO_SECTIONS:
        active = " active" if item["prefix"] == current["prefix"] else ""
        tabs.append(
            f'<a class="ss-studio-tab{active}" href="{item["path"]}">'
            f'<span>{item["icon"]}</span><span>{html.escape(item["label"])}</span></a>'
        )

    return f"""
<header id="ss-studio-workspace">
  <div class="ss-studio-top">
    <div class="ss-studio-brand">
      <a class="ss-studio-back" href="/admin#studio-operations" aria-label="Back to Command Center">←</a>
      <div class="ss-studio-heading">
        <div class="ss-studio-kicker">Studio Operations</div>
        <h1>{current['icon']} {html.escape(current['title'])}</h1>
        <p>{html.escape(current['description'])}</p>
      </div>
    </div>
    <div class="ss-studio-actions">
      <a class="ss-studio-action" href="/admin/search">⌕ <span class="wide-label">Search</span></a>
      <a class="ss-studio-action" href="/admin">◈ <span class="wide-label">Command Center</span></a>
    </div>
  </div>
  <nav class="ss-studio-tabs" aria-label="Studio Operations tools">
    {''.join(tabs)}
  </nav>
</header>
<nav class="ss-studio-mobile-dock" aria-label="Studio Operations mobile navigation">
  <a href="/admin"><b>◈</b>Home</a>
  <a href="/admin/families"><b>🏠</b>Families</a>
  <a href="/admin/students"><b>🩰</b>Students</a>
  <a href="/admin/search"><b>⌕</b>Search</a>
</nav>
"""


def register_studio_workspace_polish(app) -> None:
    """Give studio-management screens one consistent shell without changing workflows."""

    @app.after_request
    def add_studio_workspace(response):
        path = request.path.rstrip("/") or "/"
        current = _section_for_path(path)
        if not current or response.mimetype != "text/html":
            return response
        if request.method != "GET" or response.status_code != 200:
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or 'id="ss-studio-workspace"' in body:
                return response
            if "</head>" in body:
                body = body.replace("</head>", STUDIO_STYLE + "</head>", 1)
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
            app.logger.exception("Could not apply Studio Operations workspace UI")
        return response
