from __future__ import annotations

import html
import re

from flask import request


STORE_SECTIONS = [
    {
        "key": "products",
        "path": "/admin/store",
        "label": "Products",
        "title": "Store Manager",
        "icon": "🛍️",
        "description": "Products, pricing, photos, options, store settings and availability.",
    },
    {
        "key": "orders",
        "path": "/admin/orders",
        "label": "Orders",
        "title": "Orders",
        "icon": "🧾",
        "description": "Customer orders, payment status, fulfillment status and order details.",
    },
    {
        "key": "inventory",
        "path": "/admin/inventory",
        "label": "Inventory",
        "title": "Inventory",
        "icon": "📦",
        "description": "Stock levels, low-stock items, variants and inventory adjustments.",
    },
    {
        "key": "fulfillment",
        "path": "/admin/packing-slips",
        "label": "Fulfillment",
        "title": "Fulfillment",
        "icon": "🚚",
        "description": "Packing slips and order preparation for pickup or shipping.",
    },
    {
        "key": "reports",
        "path": "/admin/reports",
        "label": "Reports",
        "title": "Store Reports",
        "icon": "📊",
        "description": "Sales, orders, products, customers, payments and revenue reporting.",
    },
]


STORE_STYLE = r"""
<style id="ss-store-workspace-style">
:root{
  --ss-store-night:#090510;--ss-store-night2:#17102a;--ss-store-panel:#17102a;
  --ss-store-panel2:#100a1d;--ss-store-line:rgba(255,255,255,.13);
  --ss-store-muted:#b8adca;--ss-store-pink:#ef3d98;--ss-store-purple:#9b4dcc;
  --ss-store-teal:#50d6d0;--ss-store-success:#62e6aa;--ss-store-warn:#ffc867;
}
html{scroll-behavior:smooth}
body{
  min-height:100vh!important;color:#fff!important;
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif!important;
  background:
    radial-gradient(circle at 6% 0%,rgba(239,61,152,.17),transparent 28rem),
    radial-gradient(circle at 95% 4%,rgba(80,214,208,.12),transparent 30rem),
    linear-gradient(145deg,var(--ss-store-night),var(--ss-store-night2))!important;
  padding-bottom:30px;
}
body > header:not(#ss-store-workspace){display:none!important}
#ss-store-workspace{
  display:block!important;width:100%!important;box-sizing:border-box!important;
  position:sticky;top:0;z-index:1000;background:rgba(9,5,16,.96);
  border-bottom:1px solid var(--ss-store-line);backdrop-filter:blur(22px);
  box-shadow:0 10px 34px rgba(0,0,0,.22)
}
.ss-store-top{
  width:100%;box-sizing:border-box;min-height:72px;padding:12px clamp(14px,4vw,44px);
  display:flex!important;align-items:center;justify-content:space-between;gap:18px
}
.ss-store-brand{display:flex;align-items:center;gap:12px;min-width:0}
.ss-store-back{
  width:42px;height:42px;flex:0 0 42px;display:grid;place-items:center;border-radius:13px;
  border:1px solid var(--ss-store-line);background:rgba(255,255,255,.055);font-size:1.15rem;
  color:#fff!important;text-decoration:none!important
}
.ss-store-heading{min-width:0}.ss-store-kicker{
  color:var(--ss-store-teal);font-size:.68rem;font-weight:950;text-transform:uppercase;
  letter-spacing:.12em;margin-bottom:2px
}
.ss-store-heading h1{margin:0;font-size:clamp(1.12rem,3vw,1.5rem);line-height:1.15;color:#fff!important}
.ss-store-heading p{margin:4px 0 0;color:var(--ss-store-muted);font-size:.78rem;line-height:1.35}
.ss-store-actions{display:flex;gap:8px;align-items:center;flex:0 0 auto}
.ss-store-action{
  display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:40px;
  padding:9px 12px;border:1px solid var(--ss-store-line);border-radius:12px;
  background:rgba(255,255,255,.05);color:#fff!important;text-decoration:none!important;
  font-size:.78rem;font-weight:850
}
.ss-store-action:hover{border-color:rgba(80,214,208,.42);background:rgba(80,214,208,.07)}
.ss-store-tabs{
  width:100%;box-sizing:border-box;display:flex!important;gap:7px;overflow-x:auto;
  padding:0 clamp(14px,4vw,44px) 11px;scrollbar-width:none;-webkit-overflow-scrolling:touch
}
.ss-store-tabs::-webkit-scrollbar{display:none}
.ss-store-tab{
  flex:0 0 auto;display:flex;align-items:center;gap:7px;padding:9px 12px;border-radius:11px;
  border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.035);
  color:#ddd4e8!important;text-decoration:none!important;font-size:.78rem;font-weight:850;white-space:nowrap
}
.ss-store-tab.active{
  color:#fff!important;border-color:rgba(80,214,208,.30);
  background:linear-gradient(110deg,rgba(239,61,152,.20),rgba(155,77,204,.25),rgba(80,214,208,.15))
}
body .wrap{margin-top:20px!important;margin-bottom:40px!important}
body .card,body .panel,body .section,body .stat,body .toolbar,body .table-wrap,body .product{
  border-color:var(--ss-store-line)!important
}
body .card,body .panel,body .section,body .stat{
  background:rgba(23,16,42,.94)!important;color:#fff!important;
  box-shadow:0 18px 50px rgba(0,0,0,.16)
}
body h1,body h2,body h3,body h4,body strong,body label{color:#fff!important}
body .muted,body .small,body .helper,body .note{color:var(--ss-store-muted)!important}
body input:not([type="checkbox"]):not([type="radio"]),body textarea,body select{
  border:1px solid #49365f!important;border-radius:11px!important;background:var(--ss-store-panel2)!important;
  color:#fff!important;font:inherit!important;outline:none
}
body input:not([type="checkbox"]):not([type="radio"]):focus,body textarea:focus,body select:focus{
  border-color:var(--ss-store-teal)!important;box-shadow:0 0 0 3px rgba(80,214,208,.10)!important
}
body input[type="checkbox"],body input[type="radio"]{accent-color:var(--ss-store-pink)}
body button,body .button,body .btn{font-family:inherit}
body .primary,body button.primary,body .button.primary,body .btn.primary{
  background:linear-gradient(110deg,var(--ss-store-pink),var(--ss-store-purple),var(--ss-store-teal))!important;
  color:#fff!important
}
body .secondary{background:rgba(255,255,255,.08)!important;color:#fff!important}
body .danger{color:#fff!important}
body table{background:rgba(23,16,42,.95)!important;color:#fff!important}
body th{color:#d8cfdf!important}body td,body th{border-color:rgba(255,255,255,.10)!important}
body .table,body .table-wrap{max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}
body a{color:inherit}
.ss-store-mobile-dock{display:none}
@media(max-width:760px){
  body{padding-bottom:112px!important}
  #ss-store-workspace{display:block!important;width:100%!important}
  .ss-store-top{width:100%!important;min-height:66px;padding:10px 12px;gap:10px}
  .ss-store-brand{flex:1 1 auto;min-width:0}.ss-store-back{width:40px;height:40px;flex-basis:40px}
  .ss-store-heading p{display:none}.ss-store-actions{flex:0 0 auto}
  .ss-store-actions .ss-store-action:first-child{display:none!important}
  .ss-store-action{padding:8px 10px;min-width:40px}.ss-store-tabs{padding:0 12px 10px;gap:6px}
  .ss-store-tab{padding:8px 10px;font-size:.73rem}
  body .wrap{width:calc(100% - 28px)!important;margin-top:14px!important}
  body .grid{grid-template-columns:1fr!important}
  body .full{grid-column:auto!important}
  body .card,body .panel,body .section,body .stat,body .table-wrap{border-radius:18px!important}
  body table{min-width:700px}
  .ss-store-mobile-dock{
    position:fixed;display:grid;grid-template-columns:repeat(5,1fr);left:10px;right:10px;bottom:10px;
    z-index:1100;border:1px solid var(--ss-store-line);background:rgba(10,6,18,.97);
    backdrop-filter:blur(22px);border-radius:17px;padding:6px;box-shadow:0 14px 38px rgba(0,0,0,.36)
  }
  .ss-store-mobile-dock a{text-align:center;text-decoration:none;color:var(--ss-store-muted)!important;font-size:.58rem;padding:5px 1px;border-radius:12px}
  .ss-store-mobile-dock a.active{background:linear-gradient(110deg,rgba(239,61,152,.23),rgba(155,77,204,.28),rgba(80,214,208,.15));color:#fff!important}
  .ss-store-mobile-dock b{display:block;color:#fff;font-size:1.05rem;margin-bottom:2px}
}
@media(max-width:430px){
  .ss-store-kicker{font-size:.6rem}.ss-store-heading h1{font-size:1.02rem}
  .ss-store-action{font-size:.72rem}.ss-store-action .wide-label{display:none}
  .ss-store-mobile-dock a{font-size:.54rem}
}
@media print{
  #ss-store-workspace,.ss-store-mobile-dock{display:none!important}
}
</style>
<script id="ss-store-workspace-script">
document.addEventListener('DOMContentLoaded',function(){
  var nav=document.querySelector('.ss-store-tabs');
  var active=nav&&nav.querySelector('.ss-store-tab.active');
  if(nav&&active){nav.scrollLeft=Math.max(0,active.offsetLeft-(nav.clientWidth-active.offsetWidth)/2)}
});
</script>
"""


def _section_for_path(path: str):
    if path == "/admin/store":
        return dict(STORE_SECTIONS[0])
    if path == "/admin/orders" or path.startswith("/admin/orders/"):
        current = dict(STORE_SECTIONS[1])
        if path != "/admin/orders":
            current["title"] = "Order Details"
            current["description"] = "Order items, customer information, payment and fulfillment controls."
        return current
    if path == "/admin/inventory":
        return dict(STORE_SECTIONS[2])
    if path == "/admin/variants":
        current = dict(STORE_SECTIONS[2])
        current["title"] = "Variant Inventory"
        current["description"] = "Stock by product size and color, with variant-level inventory controls."
        return current
    if path == "/admin/packing-slips":
        return dict(STORE_SECTIONS[3])
    if path == "/admin/reports":
        return dict(STORE_SECTIONS[4])
    return None


def _workspace_markup(current: dict) -> str:
    tabs = []
    for item in STORE_SECTIONS:
        active = " active" if item["key"] == current["key"] else ""
        tabs.append(
            f'<a class="ss-store-tab{active}" href="{item["path"]}">'
            f'<span>{item["icon"]}</span><span>{html.escape(item["label"])}</span></a>'
        )

    dock_items = [
        ("home", "/admin", "◈", "Home"),
        ("products", "/admin/store", "🛍️", "Products"),
        ("orders", "/admin/orders", "🧾", "Orders"),
        ("inventory", "/admin/inventory", "📦", "Stock"),
        ("reports", "/admin/reports", "📊", "Reports"),
    ]
    dock = []
    for key, href, icon, label in dock_items:
        active = " active" if key == current["key"] else ""
        dock.append(f'<a class="{active.strip()}" href="{href}"><b>{icon}</b>{label}</a>')

    return f"""
<header id="ss-store-workspace">
  <div class="ss-store-top">
    <div class="ss-store-brand">
      <a class="ss-store-back" href="/admin#store-orders" aria-label="Back to Command Center">←</a>
      <div class="ss-store-heading">
        <div class="ss-store-kicker">Store &amp; Orders</div>
        <h1>{current['icon']} {html.escape(current['title'])}</h1>
        <p>{html.escape(current['description'])}</p>
      </div>
    </div>
    <div class="ss-store-actions">
      <a class="ss-store-action" href="/store" target="_blank">↗ <span class="wide-label">Open Store</span></a>
      <a class="ss-store-action" href="/admin">◈ <span class="wide-label">Command Center</span></a>
    </div>
  </div>
  <nav class="ss-store-tabs" aria-label="Store and Orders tools">{''.join(tabs)}</nav>
</header>
<nav class="ss-store-mobile-dock" aria-label="Store and Orders mobile navigation">{''.join(dock)}</nav>
"""


def register_store_workspace_polish(app) -> None:
    """Unify Store Manager, orders, inventory, fulfillment and store reports."""

    @app.after_request
    def add_store_workspace(response):
        path = request.path.rstrip("/") or "/"
        current = _section_for_path(path)
        if not current or request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html":
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or 'id="ss-store-workspace"' in body:
                return response
            if "</head>" in body:
                body = body.replace("</head>", STORE_STYLE + "</head>", 1)
            markup = _workspace_markup(current)
            match = re.search(r"<body[^>]*>", body, flags=re.I)
            if match:
                body = body[: match.end()] + markup + body[match.end() :]
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply Store & Orders workspace UI")
        return response
