from __future__ import annotations

import html
import json
import re

from flask import flash, jsonify, redirect, request, url_for

from database import get_db


SPIRIT = "spirit"
EVERYDAY = "everyday"
VALID_SHOP_TYPES = {SPIRIT, EVERYDAY}


def _row_value(row, key: str, index: int = 0):
    try:
        return row[key]
    except (TypeError, KeyError, IndexError):
        return row[index]


def ensure_two_shop_schema() -> None:
    """Add product shop classification and persistent seasonal-store settings."""
    connection = get_db()
    try:
        if getattr(connection, "backend", "sqlite") == "postgresql":
            connection.execute(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS shop_type TEXT NOT NULL DEFAULT 'spirit'"
            )
        else:
            columns = connection.execute("PRAGMA table_info(products)").fetchall()
            names = {str(_row_value(row, "name", 1)) for row in columns}
            if "shop_type" not in names:
                connection.execute(
                    "ALTER TABLE products ADD COLUMN shop_type TEXT NOT NULL DEFAULT 'spirit'"
                )

        connection.execute(
            "UPDATE products SET shop_type='spirit' WHERE shop_type IS NULL OR TRIM(shop_type)=''"
        )
        defaults = (
            ("spirit_wear_open", "1"),
            (
                "spirit_wear_window_note",
                "Limited ordering windows are announced by Stage Starz.",
            ),
        )
        for key, value in defaults:
            connection.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (key, value),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _shop_settings() -> dict[str, str]:
    ensure_two_shop_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT key, value FROM settings WHERE key IN ('spirit_wear_open','spirit_wear_window_note')"
    ).fetchall()
    connection.close()
    values = {
        "spirit_wear_open": "1",
        "spirit_wear_window_note": "Limited ordering windows are announced by Stage Starz.",
    }
    for row in rows:
        values[str(_row_value(row, "key", 0))] = str(_row_value(row, "value", 1) or "")
    return values


def _product_shop_types() -> dict[int, str]:
    ensure_two_shop_schema()
    connection = get_db()
    rows = connection.execute("SELECT id, shop_type FROM products").fetchall()
    connection.close()
    result: dict[int, str] = {}
    for row in rows:
        product_id = int(_row_value(row, "id", 0))
        shop_type = str(_row_value(row, "shop_type", 1) or SPIRIT).strip().lower()
        result[product_id] = shop_type if shop_type in VALID_SHOP_TYPES else SPIRIT
    return result


def _normalize_shop_type(value: str) -> str:
    value = str(value or "").strip().lower()
    return value if value in VALID_SHOP_TYPES else SPIRIT


def _save_shop_type(product_id: int, shop_type: str) -> None:
    ensure_two_shop_schema()
    connection = get_db()
    connection.execute(
        "UPDATE products SET shop_type=? WHERE id=?",
        (_normalize_shop_type(shop_type), int(product_id)),
    )
    connection.commit()
    connection.close()


def _max_product_id() -> int:
    connection = get_db()
    row = connection.execute("SELECT COALESCE(MAX(id),0) AS max_id FROM products").fetchone()
    connection.close()
    return int(_row_value(row, "max_id", 0) or 0)


def _new_product_id_after(previous_max: int, name: str) -> int | None:
    connection = get_db()
    row = connection.execute(
        """
        SELECT id FROM products
        WHERE id>? AND name=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (int(previous_max), str(name or "").strip()),
    ).fetchone()
    connection.close()
    if not row:
        return None
    return int(_row_value(row, "id", 0))


ADMIN_STYLE = r"""
<style id="ss-two-shop-admin-style">
.ss-shop-availability{
  border:1px solid rgba(83,215,210,.27)!important;
  background:
    radial-gradient(circle at 96% 0%,rgba(28,190,196,.13),transparent 22rem),
    radial-gradient(circle at 0% 100%,rgba(181,59,212,.14),transparent 24rem),
    rgba(19,12,34,.92)!important;
}
.ss-shop-availability h2{color:#fff!important;margin-bottom:6px!important}
.ss-shop-availability .ss-shop-admin-intro{color:#c8bdd5!important;line-height:1.55;margin:0 0 16px}
.ss-shop-admin-status{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 16px}
.ss-shop-admin-pill{display:inline-flex;align-items:center;gap:7px;padding:8px 11px;border-radius:999px;font-size:.75rem;font-weight:900;border:1px solid rgba(255,255,255,.12);color:#f8f5fb!important;background:rgba(255,255,255,.055)}
.ss-shop-admin-pill.open{border-color:rgba(61,216,174,.42);background:rgba(61,216,174,.11)}
.ss-shop-admin-pill.year{border-color:rgba(83,215,210,.38);background:rgba(83,215,210,.09)}
.ss-shop-availability-grid{display:grid;grid-template-columns:minmax(0,.8fr) minmax(260px,1.2fr);gap:14px;align-items:end}
.ss-shop-availability .ss-shop-open-toggle{display:flex!important;align-items:center!important;gap:9px!important;min-height:42px;margin:0!important;padding:10px 12px;border:1px solid rgba(255,255,255,.12);border-radius:10px;background:rgba(255,255,255,.045);color:#fff!important}
.ss-shop-availability .ss-shop-open-toggle input{width:19px!important;height:19px!important;margin:0!important;accent-color:#35cfc5}
.ss-shop-availability label{color:#fff!important}
.ss-shop-availability input[type=text]{background:rgba(255,255,255,.065)!important;color:#fff!important;border-color:rgba(255,255,255,.15)!important}
.ss-shop-availability input[type=text]::placeholder{color:#8f849e!important}
.ss-product-shop-type{min-width:0}
.ss-product-shop-type label{display:block!important}
.ss-product-shop-type select{width:100%!important}
.ss-product-shop-type .ss-shop-type-help{display:block;color:#a99db8!important;font-size:.7rem;line-height:1.4;margin-top:5px}
@media(max-width:720px){
  .ss-shop-availability-grid{grid-template-columns:1fr}
  .ss-shop-availability .actions button{width:100%;min-height:46px}
}
</style>
"""


ADMIN_SCRIPT = r"""
<script id="ss-two-shop-admin-script">
(function(){
  const savedTypes = window.ssProductShopTypes || {};
  function addShopType(form){
    if(form.dataset.ssShopTypeReady==='1')return;
    form.dataset.ssShopTypeReady='1';
    const category=form.querySelector('input[name="category"]');
    if(!category)return;
    const idInput=form.querySelector('input[name="id"]');
    const id=idInput&&idInput.value.trim();
    const selected=(id&&savedTypes[id])||'spirit';
    const wrap=document.createElement('div');
    wrap.className='ss-product-shop-type';
    wrap.innerHTML=`
      <label>Shop</label>
      <select name="shop_type">
        <option value="spirit">Official Spirit Wear — Seasonal</option>
        <option value="everyday">Everyday Shop — Year-Round</option>
      </select>
      <span class="ss-shop-type-help">Spirit Wear follows the seasonal ordering switch. Everyday Shop items stay available year-round.</span>`;
    wrap.querySelector('select').value=selected==='everyday'?'everyday':'spirit';
    const categoryWrap=category.closest('div');
    if(categoryWrap)categoryWrap.insertAdjacentElement('afterend',wrap);
  }
  document.querySelectorAll('form[action="/admin/product/save"]').forEach(addShopType);
})();
</script>
"""


PUBLIC_STYLE = r"""
<style id="ss-two-shop-public-style">
:root{--ss-deep:#0c0714;--ss-panel:#171023;--ss-purple:#9d4edd;--ss-teal:#35cfc5;--ss-pink:#f14fa9}
body{
  background:
    radial-gradient(circle at 8% 3%,rgba(157,78,221,.14),transparent 28rem),
    radial-gradient(circle at 94% 18%,rgba(53,207,197,.10),transparent 26rem),
    linear-gradient(180deg,#120b1c 0,#181020 300px,#f7f4fb 760px)!important;
}
body>header{
  background:rgba(11,7,18,.94)!important;
  border-bottom:1px solid rgba(255,255,255,.10);
  box-shadow:0 10px 35px rgba(0,0,0,.22);
  backdrop-filter:blur(18px);
}
body>header>a,body>header div,body>header span{color:#fff}
.ss-shop-hero{
  position:relative;overflow:hidden;width:min(1180px,calc(100% - 28px));margin:28px auto 18px;padding:48px 48px 44px;border-radius:30px;color:#fff;
  background:
    radial-gradient(circle at 80% 18%,rgba(53,207,197,.26),transparent 20rem),
    radial-gradient(circle at 7% 94%,rgba(241,79,169,.22),transparent 22rem),
    linear-gradient(135deg,#2f1351 0%,#6a2ba3 48%,#124d61 100%);
  box-shadow:0 26px 70px rgba(16,8,27,.34);
}
.ss-shop-hero:after{content:'★';position:absolute;right:34px;top:2px;font-size:12rem;line-height:1;color:rgba(255,255,255,.055);transform:rotate(10deg);pointer-events:none}
.ss-shop-kicker{display:inline-flex;align-items:center;gap:8px;padding:7px 11px;border-radius:999px;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.09);font-size:.72rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase}
.ss-shop-hero h2{position:relative;z-index:1;font-size:clamp(2.5rem,7vw,4.8rem)!important;line-height:.98;margin:15px 0 13px!important;letter-spacing:-.045em}
.ss-shop-hero p{position:relative;z-index:1;max-width:720px;color:#eee6f5!important;font-size:1.02rem;line-height:1.65!important}
.ss-shop-choices{width:min(1180px,calc(100% - 28px));margin:0 auto 24px;display:grid;grid-template-columns:1fr 1fr;gap:16px}
.ss-shop-choice{position:relative;text-align:left;border:1px solid rgba(255,255,255,.16);border-radius:22px;padding:20px 21px;color:#fff;background:rgba(20,13,31,.94);box-shadow:0 14px 38px rgba(0,0,0,.18);cursor:pointer;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}
.ss-shop-choice:hover{transform:translateY(-2px);border-color:rgba(83,215,210,.48)}
.ss-shop-choice.active{border-color:rgba(83,215,210,.75);box-shadow:0 0 0 2px rgba(83,215,210,.10),0 18px 45px rgba(0,0,0,.22)}
.ss-shop-choice .ss-choice-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.ss-shop-choice strong{display:block;font-size:1.12rem}.ss-shop-choice p{margin:7px 0 0;color:#bfb3cb;line-height:1.45;font-size:.84rem}
.ss-shop-status{flex:0 0 auto;padding:6px 9px;border-radius:999px;font-size:.66rem;font-weight:950;letter-spacing:.04em;text-transform:uppercase;background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.12)}
.ss-shop-status.open{background:rgba(44,202,151,.12);border-color:rgba(44,202,151,.42);color:#8ff0cb}
.ss-shop-status.closed{background:rgba(241,164,72,.11);border-color:rgba(241,164,72,.38);color:#ffd18f}
.ss-shop-status.year{background:rgba(53,207,197,.10);border-color:rgba(53,207,197,.38);color:#8de9e3}
main{background:transparent!important}
.toolbar{padding:13px;border-radius:16px;background:rgba(255,255,255,.96);box-shadow:0 10px 30px rgba(31,18,49,.10)}
.ss-shop-results-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin:26px 0 14px;padding:0 2px}
.ss-shop-results-head h2{margin:0;color:#20172b;font-size:clamp(1.45rem,3vw,2.05rem)}
.ss-shop-results-head p{margin:5px 0 0;color:#746a7f;font-size:.88rem;line-height:1.45}
.ss-shop-window-banner{margin:0 0 18px;padding:14px 16px;border-radius:14px;border:1px solid #dfd5eb;background:#fff;color:#554a60;font-size:.86rem;line-height:1.5;box-shadow:0 8px 22px rgba(44,25,67,.07)}
.ss-shop-window-banner.open{border-color:#b7ead9;background:#f1fff9;color:#275f4f}
.ss-shop-window-banner.closed{border-color:#f0d5b6;background:#fff8ef;color:#78501f}
.grid .card{border-radius:22px!important;border:1px solid #e4daec!important;box-shadow:0 14px 32px rgba(44,25,67,.09)!important;transition:transform .18s ease,box-shadow .18s ease}
.grid .card:hover{transform:translateY(-2px);box-shadow:0 18px 42px rgba(44,25,67,.13)!important}
.grid .card .media{height:235px!important;background:linear-gradient(145deg,#f3edfb,#e9fbfb)!important}
.grid .card .category{display:inline-flex;padding:5px 8px;border-radius:999px;background:#effcfb;color:#148e91!important;letter-spacing:.035em}
.ss-product-shop-badge{display:inline-flex;margin:0 0 7px;padding:5px 8px;border-radius:999px;font-size:.64rem;font-weight:950;text-transform:uppercase;letter-spacing:.045em;background:#f3edfb;color:#6f35c5}
.ss-product-shop-badge.everyday{background:#eafaf8;color:#167f82}
.grid .card .add{min-height:46px;border-radius:12px!important;background:linear-gradient(110deg,#843fd0,#c13ca6,#199fab)!important;box-shadow:0 9px 22px rgba(111,53,197,.18)}
.grid .card .add[disabled]{cursor:not-allowed;background:#ded8e3!important;color:#766d7d!important;box-shadow:none!important}
.ss-shop-empty{grid-column:1/-1;padding:36px 22px;text-align:center;border:1px dashed #d8cce3;border-radius:20px;background:rgba(255,255,255,.8);color:#746a7f}
@media(max-width:700px){
  body{background:linear-gradient(180deg,#120b1c 0,#171020 420px,#f7f4fb 900px)!important}
  .ss-shop-hero{padding:34px 24px 30px;border-radius:24px;margin-top:18px}
  .ss-shop-hero:after{right:-18px;top:24px;font-size:8rem}
  .ss-shop-choices{grid-template-columns:1fr;gap:11px}
  .ss-shop-choice{padding:17px}
  .ss-shop-results-head{display:block}
  .grid .card .media{height:230px!important}
}
</style>
"""


PUBLIC_SCRIPT = r"""
<script id="ss-two-shop-public-script">
(function(){
  let ssSelectedShop='spirit';
  const experience=window.ssShopExperienceSettings||{};
  function spiritIsOpen(){
    const value=(settings&&settings.spirit_wear_open!==undefined)?settings.spirit_wear_open:experience.spirit_wear_open;
    return String(value===undefined?'1':value)==='1';
  }
  function spiritNote(){
    return String((settings&&settings.spirit_wear_window_note)||experience.spirit_wear_window_note||'Limited ordering windows are announced by Stage Starz.');
  }
  function shopType(p){return String((p&&p.shop_type)||'spirit').toLowerCase()==='everyday'?'everyday':'spirit';}
  function filteredProducts(){return products.filter(p=>shopType(p)===ssSelectedShop);}
  function syncChoiceState(){
    document.querySelectorAll('[data-shop-choice]').forEach(button=>button.classList.toggle('active',button.dataset.shopChoice===ssSelectedShop));
    const spiritStatus=document.getElementById('ssSpiritStatus');
    if(spiritStatus){
      const open=spiritIsOpen();
      spiritStatus.textContent=open?'Ordering Open':'Ordering Closed';
      spiritStatus.className='ss-shop-status '+(open?'open':'closed');
    }
    const spiritCount=document.getElementById('ssSpiritCount');
    const everydayCount=document.getElementById('ssEverydayCount');
    if(spiritCount)spiritCount.textContent=products.filter(p=>shopType(p)==='spirit').length+' items';
    if(everydayCount)everydayCount.textContent=products.filter(p=>shopType(p)==='everyday').length+' items';
  }
  function syncCategoryOptions(){
    const select=document.getElementById('category');if(!select)return;
    const available=filteredProducts();
    const categories=[...new Set(available.map(p=>p.category).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    const current=select.value;
    select.innerHTML='<option value="">All categories</option>'+categories.map(c=>`<option>${c}</option>`).join('');
    select.value=categories.includes(current)?current:'';
  }
  function updateResultsHeading(){
    const title=document.getElementById('ssShopResultsTitle');
    const copy=document.getElementById('ssShopResultsCopy');
    const banner=document.getElementById('ssShopWindowBanner');
    if(ssSelectedShop==='spirit'){
      if(title)title.textContent='Official Spirit Wear';
      if(copy)copy.textContent='Team and studio apparel offered during limited Stage Starz ordering windows.';
      if(banner){
        const open=spiritIsOpen();
        banner.className='ss-shop-window-banner '+(open?'open':'closed');
        banner.innerHTML=open?'<strong>Spirit Wear ordering is open.</strong> Place seasonal orders while this window is active.':'<strong>Spirit Wear ordering is currently closed.</strong> '+spiritNote();
        banner.style.display='block';
      }
      const search=document.getElementById('search');if(search)search.placeholder='Search Spirit Wear';
    }else{
      if(title)title.textContent='Everyday Stage Starz Shop';
      if(copy)copy.textContent='Year-round Stage Starz merchandise you can shop anytime.';
      if(banner){banner.style.display='none';}
      const search=document.getElementById('search');if(search)search.placeholder='Search Everyday Shop';
    }
  }
  window.ssSelectShop=function(type){
    ssSelectedShop=type==='everyday'?'everyday':'spirit';
    const search=document.getElementById('search');if(search)search.value='';
    syncChoiceState();syncCategoryOptions();updateResultsHeading();render();
    const main=document.querySelector('main');if(main)main.scrollIntoView({behavior:'smooth',block:'start'});
  };

  render=function(){
    syncChoiceState();updateResultsHeading();syncCategoryOptions();
    const q=document.getElementById('search').value.toLowerCase();
    const cat=document.getElementById('category').value;
    const open=spiritIsOpen();
    const list=filteredProducts().filter(p=>(!cat||p.category===cat)&&(`${p.name} ${p.description}`.toLowerCase().includes(q)));
    const grid=document.getElementById('grid');
    if(!list.length){
      grid.innerHTML=`<div class="ss-shop-empty"><strong>${ssSelectedShop==='spirit'?'No Spirit Wear matches your search.':'Everyday Shop products are coming soon.'}</strong><br><span>${ssSelectedShop==='spirit'?'Try another search or category.':'Check back as new Stage Starz items are added.'}</span></div>`;
      return;
    }
    grid.innerHTML=list.map(p=>{
      const seasonal=shopType(p)==='spirit';
      const purchasable=!seasonal||open;
      return `
      <article class="card ${purchasable?'':'ss-ordering-closed'}">
        <div class="media">${p.image_url?`<img src="${p.image_url}" alt="${p.name}">`:p.emoji}</div>
        <div class="body">
          <div class="ss-product-shop-badge ${seasonal?'':'everyday'}">${seasonal?'Seasonal Spirit Wear':'Available Year-Round'}</div>
          <div class="category">${p.category}</div>
          <h3>${p.name}</h3>
          <div class="desc-wrap">
            <p class="desc collapsed" id="desc-${p.id}">${p.description}</p>
            ${(p.description||'').length>120?`<button type="button" class="desc-toggle" aria-expanded="false" onclick="toggleDescription(${p.id},this)">More</button>`:''}
          </div>
          <div><span class="price">${money(p.sale_price??p.price)}</span>${p.sale_price?`<span class="old">${money(p.price)}</span>`:''}</div>
          <p class="meta">Fulfillment fee: ${money(p.fulfillment_fee)} per item<br>Stock: ${p.stock}</p>
          <div class="field"><label>Size</label><select id="size-${p.id}">${p.sizes.map(x=>`<option>${x}</option>`).join('')}</select></div>
          ${p.show_color?`<div class="field"><label>Color</label><select id="color-${p.id}">${p.colors.map(x=>`<option>${x}</option>`).join('')}</select></div>`:''}
          ${p.allow_name?`
            <div class="field"><label>Add a name? (+${money(Number(settings.name_fee||10))})</label>
              <select id="add-name-${p.id}" onchange="toggleName(${p.id})"><option value="no">No</option><option value="yes">Yes</option></select>
            </div>
            <div class="field name-wrap" id="name-wrap-${p.id}"><label>Name exactly as desired</label><input id="name-${p.id}" maxlength="30"></div>`:''}
          <button class="add" ${purchasable?'':'disabled'} onclick="addToCart(${p.id})">${purchasable?'Add to Cart':'Ordering Currently Closed'}</button>
        </div>
      </article>`;
    }).join('');
  };

  addToCart=function(id){
    const p=products.find(x=>x.id===id);if(!p)return;
    if(shopType(p)==='spirit'&&!spiritIsOpen()){
      alert('Spirit Wear ordering is currently closed. '+spiritNote());return;
    }
    const addName=p.allow_name&&document.getElementById(`add-name-${id}`).value==='yes';
    const requestedName=addName?document.getElementById(`name-${id}`).value.trim():'';
    if(addName&&!requestedName){alert('Please enter the name you want added.');return}
    cart.push({
      id:p.id,name:p.name,price:Number(p.sale_price??p.price),
      fulfillmentFee:Number(p.fulfillment_fee||0),
      nameFee:addName?Number(settings.name_fee||10):0,
      requestedName,size:document.getElementById(`size-${id}`).value,
      showColor:Boolean(p.show_color),
      color:p.show_color?document.getElementById(`color-${id}`).value:'',
      shopType:shopType(p)
    });
    renderCart();toggleCart(true);
  };
})();
</script>
"""


def _admin_panel(settings: dict[str, str]) -> str:
    is_open = settings.get("spirit_wear_open", "1") == "1"
    note = html.escape(settings.get("spirit_wear_window_note", ""), quote=True)
    status = "OPEN" if is_open else "CLOSED"
    status_class = "open" if is_open else ""
    checked = " checked" if is_open else ""
    return f"""
<section class="card ss-shop-availability" id="shop-availability">
  <h2>Shop Availability</h2>
  <p class="ss-shop-admin-intro">Keep Official Spirit Wear visible year-round while controlling when families can order it. Everyday Shop products remain available all year.</p>
  <div class="ss-shop-admin-status">
    <span class="ss-shop-admin-pill {status_class}">Spirit Wear: {status}</span>
    <span class="ss-shop-admin-pill year">Everyday Shop: ALWAYS OPEN</span>
  </div>
  <form method="post" action="/admin/shop-availability/save">
    <div class="ss-shop-availability-grid">
      <label class="ss-shop-open-toggle"><input type="checkbox" name="spirit_wear_open"{checked}> Accept Spirit Wear orders now</label>
      <div><label>Closed-window message</label><input type="text" name="spirit_wear_window_note" maxlength="200" value="{note}" placeholder="Example: Our next order window opens in October."></div>
    </div>
    <div class="actions"><button class="primary" type="submit">Save Shop Availability</button></div>
  </form>
</section>
"""


def _public_shell(settings: dict[str, str]) -> str:
    is_open = settings.get("spirit_wear_open", "1") == "1"
    spirit_text = "Ordering Open" if is_open else "Ordering Closed"
    spirit_class = "open" if is_open else "closed"
    return f"""
<section class="ss-shop-hero">
  <span class="ss-shop-kicker">★ Stage Starz Academy of Dance</span>
  <h2>Stage Starz Shop</h2>
  <p>Shop official seasonal Spirit Wear or browse Stage Starz merchandise available year-round. Choose a shop below to get started.</p>
</section>
<section class="ss-shop-choices" aria-label="Choose a Stage Starz shop">
  <button type="button" class="ss-shop-choice active" data-shop-choice="spirit" onclick="ssSelectShop('spirit')">
    <div class="ss-choice-top"><strong>Official Spirit Wear</strong><span id="ssSpiritStatus" class="ss-shop-status {spirit_class}">{spirit_text}</span></div>
    <p>Team and studio apparel offered during limited ordering windows. <span id="ssSpiritCount"></span></p>
  </button>
  <button type="button" class="ss-shop-choice" data-shop-choice="everyday" onclick="ssSelectShop('everyday')">
    <div class="ss-choice-top"><strong>Everyday Stage Starz Shop</strong><span class="ss-shop-status year">Year-Round</span></div>
    <p>Stage Starz merchandise available anytime. <span id="ssEverydayCount"></span></p>
  </button>
</section>
"""


def register_two_shop_experience(app, permission_required, log_activity=None) -> None:
    """Separate seasonal Spirit Wear from year-round products and brand the public shop."""
    ensure_two_shop_schema()

    @app.route("/admin/shop-availability/save", methods=["POST"])
    @permission_required("store")
    def save_shop_availability():
        is_open = "1" if request.form.get("spirit_wear_open") == "on" else "0"
        note = request.form.get("spirit_wear_window_note", "").strip()[:200]
        if not note:
            note = "Limited ordering windows are announced by Stage Starz."
        connection = get_db()
        for key, value in (
            ("spirit_wear_open", is_open),
            ("spirit_wear_window_note", note),
        ):
            connection.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )
        connection.commit()
        connection.close()
        if log_activity:
            try:
                log_activity(
                    "Spirit Wear ordering updated",
                    "Open" if is_open == "1" else "Closed",
                )
            except Exception:
                app.logger.exception("Could not log Spirit Wear availability change")
        flash(
            "Spirit Wear ordering is now open." if is_open == "1" else "Spirit Wear ordering is now closed. Products remain visible in the shop.",
            "success",
        )
        return redirect(url_for("store_manager"))

    original_save_product = app.view_functions.get("save_product")
    if original_save_product:
        @permission_required("store")
        def save_product_with_shop_type():
            desired = _normalize_shop_type(request.form.get("shop_type", SPIRIT))
            product_id_value = request.form.get("id", "").strip()
            previous_max = _max_product_id() if not product_id_value else 0
            response = original_save_product()
            response = app.make_response(response)
            try:
                product_id = int(product_id_value) if product_id_value else _new_product_id_after(
                    previous_max, request.form.get("name", "")
                )
                if product_id:
                    _save_shop_type(product_id, desired)
            except Exception:
                app.logger.exception("Could not save product shop type")
            return response
        app.view_functions["save_product"] = save_product_with_shop_type

    original_create_order = app.view_functions.get("create_order")
    if original_create_order:
        def create_order_with_seasonal_guard():
            settings = _shop_settings()
            if settings.get("spirit_wear_open", "1") != "1":
                data = request.get_json(silent=True) or {}
                items = data.get("items") or []
                product_ids: list[int] = []
                for item in items:
                    try:
                        product_ids.append(int(item.get("id")))
                    except (TypeError, ValueError, AttributeError):
                        continue
                if product_ids:
                    placeholders = ",".join("?" for _ in product_ids)
                    connection = get_db()
                    rows = connection.execute(
                        f"SELECT id, shop_type FROM products WHERE id IN ({placeholders})",
                        tuple(product_ids),
                    ).fetchall()
                    connection.close()
                    if any(
                        _normalize_shop_type(str(_row_value(row, "shop_type", 1) or SPIRIT)) == SPIRIT
                        for row in rows
                    ):
                        return jsonify(
                            {
                                "error": (
                                    "Spirit Wear ordering is currently closed. "
                                    + settings.get("spirit_wear_window_note", "")
                                ).strip()
                            }
                        ), 409
            return original_create_order()
        app.view_functions["create_order"] = create_order_with_seasonal_guard

    @app.after_request
    def two_shop_ui(response):
        if (
            request.method != "GET"
            or response.status_code != 200
            or response.mimetype != "text/html"
            or request.path not in {"/admin/store", "/store"}
        ):
            return response
        try:
            body = response.get_data(as_text=True)
            values = _shop_settings()
            if request.path == "/admin/store":
                if "ss-two-shop-admin-style" not in body:
                    body = body.replace("</head>", ADMIN_STYLE + "\n</head>", 1)
                if "ss-shop-availability" not in body:
                    marker = '<section class="card" id="new-product">'
                    body = body.replace(marker, _admin_panel(values) + "\n" + marker, 1)
                if "ss-two-shop-admin-script" not in body:
                    mapping = {str(key): value for key, value in _product_shop_types().items()}
                    data_script = (
                        "<script>window.ssProductShopTypes="
                        + json.dumps(mapping).replace("</", "<\\/")
                        + ";</script>"
                    )
                    body = body.replace(
                        "</body>", data_script + ADMIN_SCRIPT + "\n</body>", 1
                    )
            else:
                if "ss-two-shop-public-style" not in body:
                    body = body.replace("</head>", PUBLIC_STYLE + "\n</head>", 1)
                if "ss-shop-choices" not in body:
                    body = re.sub(
                        r'<section class="hero">.*?</section>',
                        _public_shell(values),
                        body,
                        count=1,
                        flags=re.DOTALL,
                    )
                    results_head = """
  <div class="ss-shop-results-head"><div><h2 id="ssShopResultsTitle">Official Spirit Wear</h2><p id="ssShopResultsCopy">Team and studio apparel offered during limited Stage Starz ordering windows.</p></div></div>
  <div id="ssShopWindowBanner" class="ss-shop-window-banner"></div>
"""
                    body = body.replace(
                        '<section id="grid" class="grid"></section>',
                        results_head + '<section id="grid" class="grid"></section>',
                        1,
                    )
                if "ss-two-shop-public-script" not in body:
                    client_settings = {
                        "spirit_wear_open": values.get("spirit_wear_open", "1"),
                        "spirit_wear_window_note": values.get(
                            "spirit_wear_window_note", ""
                        ),
                    }
                    data_script = (
                        "<script>window.ssShopExperienceSettings="
                        + json.dumps(client_settings).replace("</", "<\\/")
                        + ";</script>"
                    )
                    body = body.replace(
                        "</body>", data_script + PUBLIC_SCRIPT + "\n</body>", 1
                    )
            response.set_data(body)
        except Exception:
            app.logger.exception("Could not apply two-shop Store experience")
        return response
