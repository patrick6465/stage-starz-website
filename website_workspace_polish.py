from __future__ import annotations

import html

from flask import request


WORKSPACE_PAGES = {
    "/admin/website/homepage": {
        "label": "Homepage",
        "title": "Homepage Editor",
        "icon": "🏠",
        "description": "Hero content, announcement bar, buttons, images and countdown.",
    },
    "/admin/website/page-text": {
        "label": "Page Text",
        "title": "Page Text Editor",
        "icon": "✏️",
        "description": "Parent Hub, Dancer Portal and recital-page wording.",
    },
    "/admin/website/classes": {
        "label": "Class Pages",
        "title": "Class Page Editor",
        "icon": "📄",
        "description": "Class and competition page wording, details and hero photos.",
    },
    "/admin/website/videos": {
        "label": "Videos",
        "title": "Website Video Editor",
        "icon": "🎬",
        "description": "Upload, reuse and publish performance videos.",
    },
    "/admin/media": {
        "label": "Media",
        "title": "Media Library",
        "icon": "🖼️",
        "description": "Persistent website images used by editors and public pages.",
    },
    "/admin/website/inquiries": {
        "label": "Inquiries",
        "title": "Website Inquiries",
        "icon": "📨",
        "description": "Review contact-form leads, statuses and staff notes.",
    },
}


WORKSPACE_STYLE = r"""
<style id="ss-website-workspace-style">
:root{
  --ss-night:#090510;--ss-night2:#17102a;--ss-panel:#17102a;--ss-panel2:#100a1d;
  --ss-line:rgba(255,255,255,.13);--ss-muted:#b8adca;--ss-pink:#ef3d98;
  --ss-purple:#9b4dcc;--ss-teal:#50d6d0;--ss-gold:#ffc867;--ss-white:#fff;
}
html{scroll-behavior:smooth}
body{
  min-height:100vh!important;color:var(--ss-white)!important;
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;
  background:
    radial-gradient(circle at 5% 0%,rgba(155,77,204,.28),transparent 30rem),
    radial-gradient(circle at 96% 7%,rgba(80,214,208,.12),transparent 30rem),
    linear-gradient(145deg,var(--ss-night),var(--ss-night2))!important;
  padding-bottom:28px;
}
body > header:not(#ss-website-workspace){display:none!important}
#ss-website-workspace{
  position:sticky;top:0;z-index:1000;background:rgba(9,5,16,.96);
  border-bottom:1px solid var(--ss-line);backdrop-filter:blur(22px);
  box-shadow:0 10px 34px rgba(0,0,0,.22)
}
.ss-workspace-top{
  min-height:72px;padding:12px clamp(14px,4vw,44px);display:flex;align-items:center;
  justify-content:space-between;gap:18px
}
.ss-workspace-brand{display:flex;align-items:center;gap:12px;min-width:0}
.ss-workspace-back{
  width:42px;height:42px;flex:0 0 42px;display:grid;place-items:center;border-radius:13px;
  border:1px solid var(--ss-line);background:rgba(255,255,255,.055);font-size:1.15rem
}
.ss-workspace-heading{min-width:0}.ss-workspace-kicker{
  color:var(--ss-teal);font-size:.68rem;font-weight:950;text-transform:uppercase;
  letter-spacing:.12em;margin-bottom:2px
}
.ss-workspace-heading h1{margin:0;font-size:clamp(1.12rem,3vw,1.5rem);line-height:1.15}
.ss-workspace-heading p{margin:4px 0 0;color:var(--ss-muted);font-size:.78rem;line-height:1.35}
.ss-workspace-actions{display:flex;gap:8px;align-items:center;flex:0 0 auto}
.ss-workspace-action{
  display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:40px;
  padding:9px 12px;border:1px solid var(--ss-line);border-radius:12px;
  background:rgba(255,255,255,.05);color:#fff!important;font-size:.78rem;font-weight:850
}
.ss-workspace-action:hover{border-color:rgba(80,214,208,.42);background:rgba(80,214,208,.07)}
.ss-workspace-tabs{
  display:flex;gap:7px;overflow-x:auto;padding:0 clamp(14px,4vw,44px) 11px;
  scrollbar-width:none;-webkit-overflow-scrolling:touch
}
.ss-workspace-tabs::-webkit-scrollbar{display:none}
.ss-workspace-tab{
  flex:0 0 auto;display:flex;align-items:center;gap:7px;padding:9px 12px;border-radius:11px;
  border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.035);
  color:#ddd4e8!important;font-size:.78rem;font-weight:850;white-space:nowrap
}
.ss-workspace-tab:hover{border-color:rgba(80,214,208,.34)}
.ss-workspace-tab.active{
  color:#fff!important;border-color:rgba(80,214,208,.28);
  background:linear-gradient(110deg,rgba(239,61,152,.22),rgba(155,77,204,.24),rgba(80,214,208,.16))
}

/* Shared visual language for the existing editors without changing their forms. */
body .panel,body .card,body .slot,body .library,body .intro-card,body article.media{
  background:rgba(23,16,42,.94)!important;border-color:var(--ss-line)!important;
  color:#fff!important;box-shadow:0 18px 50px rgba(0,0,0,.18)
}
body .wrap{margin-top:20px}
body .muted,body .small,body .intro,body .help,body .note{color:var(--ss-muted)!important}
body input:not([type="checkbox"]):not([type="radio"]),body textarea,body select{
  border:1px solid #49365f!important;border-radius:11px!important;background:var(--ss-panel2)!important;
  color:#fff!important;font:inherit!important;outline:none
}
body input:not([type="checkbox"]):not([type="radio"]):focus,body textarea:focus,body select:focus{
  border-color:var(--ss-teal)!important;box-shadow:0 0 0 3px rgba(80,214,208,.10)!important
}
body button,body .button,body .btn{font-family:inherit}
body article.media .body{background:rgba(16,10,29,.72);color:#fff}
body article.media img{background:#090510}
body .primary{background:linear-gradient(110deg,var(--ss-pink),var(--ss-purple),var(--ss-teal))!important;color:#fff!important}
body .secondary{background:#2a1d3c!important;color:#fff!important}
body .danger{color:#fff!important}
body a{color:inherit}
body .preview,body .nav-panel{top:132px!important}

.ss-workspace-mobile-dock{display:none}
@media(max-width:760px){
  body{padding-bottom:112px!important}
  .ss-workspace-top{min-height:66px;padding:10px 12px;gap:10px}
  .ss-workspace-back{width:40px;height:40px;flex-basis:40px}
  .ss-workspace-heading p{display:none}
  .ss-workspace-actions .ss-open-site{display:none}
  .ss-workspace-action{padding:8px 10px}
  .ss-workspace-tabs{padding:0 12px 10px;gap:6px}
  .ss-workspace-tab{padding:8px 10px;font-size:.73rem}
  body .wrap,body .shell{margin-top:14px!important}
  body .preview,body .nav-panel{top:auto!important}
  body .card,body .panel,body .slot,body .library,body .intro-card{border-radius:18px!important}
  .ss-workspace-mobile-dock{
    position:fixed;display:grid;grid-template-columns:repeat(4,1fr);left:10px;right:10px;bottom:10px;
    z-index:1100;border:1px solid var(--ss-line);background:rgba(10,6,18,.96);
    backdrop-filter:blur(22px);border-radius:17px;padding:6px;box-shadow:0 14px 38px rgba(0,0,0,.36)
  }
  .ss-workspace-mobile-dock a{
    text-align:center;color:var(--ss-muted)!important;font-size:.62rem;padding:5px 2px
  }
  .ss-workspace-mobile-dock b{display:block;color:#fff;font-size:1.08rem;margin-bottom:2px}
}
@media(max-width:460px){
  .ss-workspace-kicker{font-size:.6rem}.ss-workspace-heading h1{font-size:1.05rem}
  .ss-workspace-action{font-size:.72rem}.ss-workspace-action .wide-label{display:none}
}
</style>
"""


def _workspace_markup(path: str) -> str:
    current = WORKSPACE_PAGES[path]
    tabs = []
    icons = {
        "/admin/website/homepage": "🏠",
        "/admin/website/page-text": "✏️",
        "/admin/website/classes": "📄",
        "/admin/website/videos": "🎬",
        "/admin/media": "🖼️",
        "/admin/website/inquiries": "📨",
    }
    for page_path, info in WORKSPACE_PAGES.items():
        active = " active" if page_path == path else ""
        tabs.append(
            f'<a class="ss-workspace-tab{active}" href="{page_path}">'
            f'<span>{icons[page_path]}</span><span>{html.escape(info["label"])}</span></a>'
        )

    return f"""
<header id="ss-website-workspace">
  <div class="ss-workspace-top">
    <div class="ss-workspace-brand">
      <a class="ss-workspace-back" href="/admin#website-management" aria-label="Back to Command Center">←</a>
      <div class="ss-workspace-heading">
        <div class="ss-workspace-kicker">Website Management</div>
        <h1>{current['icon']} {html.escape(current['title'])}</h1>
        <p>{html.escape(current['description'])}</p>
      </div>
    </div>
    <div class="ss-workspace-actions">
      <a class="ss-workspace-action ss-open-site" href="/" target="_blank">↗ <span class="wide-label">Open Website</span></a>
      <a class="ss-workspace-action" href="/admin">◈ <span class="wide-label">Command Center</span></a>
    </div>
  </div>
  <nav class="ss-workspace-tabs" aria-label="Website Management tools">
    {''.join(tabs)}
  </nav>
</header>
<nav class="ss-workspace-mobile-dock" aria-label="Website workspace mobile navigation">
  <a href="/admin"><b>◈</b>Home</a>
  <a href="/admin#website-management"><b>🌐</b>Website</a>
  <a href="/" target="_blank"><b>↗</b>Live Site</a>
  <a href="/admin/logout"><b>↪</b>Log Out</a>
</nav>
"""


def register_website_workspace_polish(app) -> None:
    """Give Website Management tools one consistent shell without changing editor logic."""

    @app.after_request
    def add_website_workspace(response):
        path = request.path.rstrip("/") or "/"
        if path not in WORKSPACE_PAGES or response.mimetype != "text/html":
            return response
        if request.method != "GET" or response.status_code != 200:
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or 'id="ss-website-workspace"' in body:
                return response
            if "</head>" in body:
                body = body.replace("</head>", WORKSPACE_STYLE + "</head>", 1)
            markup = _workspace_markup(path)
            body_start = body.find("<body")
            if body_start >= 0:
                body_close = body.find(">", body_start)
                if body_close >= 0:
                    body = body[: body_close + 1] + markup + body[body_close + 1 :]
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply Website Management workspace UI")
        return response
