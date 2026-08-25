from __future__ import annotations

from flask import request


PRODUCT_ACCORDION_STYLE = r"""
<style id="ss-store-product-accordion-style">
.ss-product-groups{display:grid;gap:18px;margin-top:16px}
.ss-product-group{border:1px solid rgba(255,255,255,.12);border-radius:18px;background:rgba(10,6,18,.34);overflow:hidden}
.ss-product-group-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:16px 18px;border-bottom:1px solid rgba(255,255,255,.10);background:linear-gradient(110deg,rgba(239,61,152,.10),rgba(155,77,204,.12),rgba(80,214,208,.08))}
.ss-product-group-title{min-width:0}.ss-product-group-title h3{margin:0!important;color:#fff!important;font-size:1rem!important}.ss-product-group-title p{margin:4px 0 0;color:#b8adca!important;font-size:.74rem;line-height:1.4}
.ss-product-count{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:30px;padding:0 10px;border-radius:999px;border:1px solid rgba(80,214,208,.26);background:rgba(80,214,208,.08);color:#9ce9e5;font-size:.72rem;font-weight:900}
.ss-product-list{display:grid;gap:1px;background:rgba(255,255,255,.08)}
.ss-product-empty{padding:18px;color:#b8adca;background:rgba(18,11,31,.94);font-size:.82rem}
.ss-admin-product-item{background:rgba(18,11,31,.96)}
.ss-admin-product-summary{width:100%;display:grid;grid-template-columns:72px minmax(0,1fr) auto;align-items:center;gap:14px;padding:13px 15px;border:0!important;border-radius:0!important;background:transparent!important;color:#fff!important;text-align:left;cursor:pointer}
.ss-admin-product-summary:hover{background:rgba(255,255,255,.035)!important}
.ss-admin-product-item.open>.ss-admin-product-summary{background:linear-gradient(90deg,rgba(239,61,152,.08),rgba(80,214,208,.05))!important;border-bottom:1px solid rgba(255,255,255,.10)!important}
.ss-admin-product-thumb{width:72px;height:72px;border-radius:13px;overflow:hidden;display:grid;place-items:center;background:linear-gradient(145deg,rgba(155,77,204,.18),rgba(80,214,208,.12));border:1px solid rgba(255,255,255,.10);font-size:1.7rem}
.ss-admin-product-thumb img{width:100%;height:100%;display:block;object-fit:contain;background:#0d0916}
.ss-admin-product-main{min-width:0}.ss-admin-product-name{display:block;color:#fff;font-size:.94rem;font-weight:900;line-height:1.3;overflow-wrap:anywhere}.ss-admin-product-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:7px;color:#b8adca;font-size:.7rem}
.ss-admin-product-pill{display:inline-flex;align-items:center;min-height:25px;padding:4px 8px;border:1px solid rgba(255,255,255,.11);border-radius:999px;background:rgba(255,255,255,.045);color:#d8cfe4;font-weight:800}.ss-admin-product-pill.active{border-color:rgba(98,230,170,.28);background:rgba(98,230,170,.08);color:#9aefc5}.ss-admin-product-pill.hidden{border-color:rgba(255,200,103,.25);background:rgba(255,200,103,.07);color:#ffd58c}
.ss-admin-product-toggle{display:flex;align-items:center;gap:8px;color:#9ce9e5;font-size:.74rem;font-weight:900;white-space:nowrap}.ss-admin-product-chevron{font-size:1rem;transition:transform .18s ease}.ss-admin-product-item.open .ss-admin-product-chevron{transform:rotate(180deg)}
.ss-product-details{padding:18px;background:rgba(12,7,22,.76)}.ss-product-details[hidden]{display:none!important}.ss-product-details .product{border-top:0!important;margin:0!important;padding:0!important}.ss-product-details .product>img{object-fit:contain!important;background:#0d0916!important}
.ss-product-details form[action$="/delete"]{margin-top:18px;padding-top:18px;border-top:1px solid rgba(255,255,255,.10)}
.ss-product-close-row{display:flex;justify-content:flex-end;margin-top:14px}.ss-product-close{border:1px solid rgba(80,214,208,.30)!important;background:rgba(80,214,208,.07)!important;color:#b8f2ee!important;min-height:40px}
@media(max-width:720px){
  .ss-product-groups{gap:15px}.ss-product-group{border-radius:16px}.ss-product-group-head{padding:14px}
  .ss-admin-product-summary{grid-template-columns:60px minmax(0,1fr);gap:11px;padding:12px}
  .ss-admin-product-thumb{width:60px;height:60px;border-radius:11px}
  .ss-admin-product-toggle{grid-column:2;justify-self:start;margin-top:-2px}.ss-admin-product-main{align-self:end}
  .ss-product-details{padding:14px 12px 16px}.ss-product-close{width:100%}
}
@media(max-width:420px){
  .ss-admin-product-name{font-size:.88rem}.ss-admin-product-meta{gap:5px}.ss-admin-product-pill{font-size:.65rem;padding:3px 7px}.ss-product-group-title p{font-size:.68rem}
}
</style>
"""


PRODUCT_ACCORDION_SCRIPT = r"""
<script id="ss-store-product-accordion-script">
(function(){
  function money(value){
    const number=Number(value);
    return Number.isFinite(number)?'$'+number.toFixed(2):'$0.00';
  }

  function directProductForms(section){
    return Array.from(section.children).filter(function(node){
      return node.tagName==='FORM' && node.classList.contains('product');
    });
  }

  function closeItem(item,scroll){
    const details=item.querySelector(':scope > .ss-product-details');
    const button=item.querySelector(':scope > .ss-admin-product-summary');
    if(details)details.hidden=true;
    item.classList.remove('open');
    if(button)button.setAttribute('aria-expanded','false');
    if(scroll&&button)button.scrollIntoView({behavior:'smooth',block:'center'});
  }

  function openItem(item){
    document.querySelectorAll('.ss-admin-product-item.open').forEach(function(other){
      if(other!==item)closeItem(other,false);
    });
    const details=item.querySelector(':scope > .ss-product-details');
    const button=item.querySelector(':scope > .ss-admin-product-summary');
    if(details)details.hidden=false;
    item.classList.add('open');
    if(button)button.setAttribute('aria-expanded','true');
  }

  function makeGroup(title,description){
    const group=document.createElement('section');
    group.className='ss-product-group';
    group.innerHTML='<div class="ss-product-group-head"><div class="ss-product-group-title"><h3></h3><p></p></div><span class="ss-product-count">0</span></div><div class="ss-product-list"></div>';
    group.querySelector('h3').textContent=title;
    group.querySelector('p').textContent=description;
    return group;
  }

  function makeSummary(form,shopType){
    const idInput=form.querySelector('input[name="id"]');
    const productId=idInput?idInput.value.trim():'';
    const nameInput=form.querySelector('input[name="name"]');
    const priceInput=form.querySelector('input[name="price"]');
    const saleInput=form.querySelector('input[name="sale_price"]');
    const stockInput=form.querySelector('input[name="stock"]');
    const imageInput=form.querySelector('input[name="existing_image_url"]');
    const emojiInput=form.querySelector('input[name="emoji"]');
    const activeInput=form.querySelector('input[name="active"]');

    const name=(nameInput&&nameInput.value.trim())||'Untitled Product';
    const price=(saleInput&&saleInput.value.trim())||((priceInput&&priceInput.value.trim())||'0');
    const stock=(stockInput&&stockInput.value.trim())||'0';
    const imageUrl=(imageInput&&imageInput.value.trim())||'';
    const emoji=(emojiInput&&emojiInput.value.trim())||'⭐';
    const isActive=!!(activeInput&&activeInput.checked);

    const button=document.createElement('button');
    button.type='button';
    button.className='ss-admin-product-summary';
    button.setAttribute('aria-expanded','false');
    button.setAttribute('aria-controls','ss-product-details-'+productId);

    const thumb=document.createElement('span');
    thumb.className='ss-admin-product-thumb';
    if(imageUrl){
      const img=document.createElement('img');
      img.src=imageUrl;img.alt='';img.loading='lazy';
      thumb.appendChild(img);
    }else{
      thumb.textContent=emoji;
    }

    const main=document.createElement('span');
    main.className='ss-admin-product-main';
    const productName=document.createElement('span');
    productName.className='ss-admin-product-name';productName.textContent=name;
    const meta=document.createElement('span');meta.className='ss-admin-product-meta';
    [money(price),'Stock '+stock,shopType==='everyday'?'Year-Round':'Spirit Wear'].forEach(function(text){
      const pill=document.createElement('span');pill.className='ss-admin-product-pill';pill.textContent=text;meta.appendChild(pill);
    });
    const status=document.createElement('span');
    status.className='ss-admin-product-pill '+(isActive?'active':'hidden');
    status.textContent=isActive?'Shown in Store':'Hidden';meta.appendChild(status);
    main.appendChild(productName);main.appendChild(meta);

    const toggle=document.createElement('span');toggle.className='ss-admin-product-toggle';
    const label=document.createElement('span');label.textContent='Edit Product';
    const chevron=document.createElement('span');chevron.className='ss-admin-product-chevron';chevron.textContent='⌄';
    toggle.appendChild(label);toggle.appendChild(chevron);

    button.appendChild(thumb);button.appendChild(main);button.appendChild(toggle);
    return button;
  }

  function init(){
    if(document.getElementById('ss-product-groups'))return;
    const section=Array.from(document.querySelectorAll('.card')).find(function(card){
      const heading=card.querySelector('h2');
      return heading&&heading.textContent.trim()==='Existing Products';
    });
    if(!section)return;

    const forms=directProductForms(section);
    if(!forms.length)return;

    const mappings=window.ssProductShopTypes||{};
    const shell=document.createElement('div');shell.id='ss-product-groups';shell.className='ss-product-groups';
    const spirit=makeGroup('Official Spirit Wear','Seasonal products shown together for faster review and editing.');
    const everyday=makeGroup('Everyday Shop — Year-Round','Products available year-round, separate from seasonal Spirit Wear.');
    shell.appendChild(spirit);shell.appendChild(everyday);

    const firstForm=forms[0];
    section.insertBefore(shell,firstForm);
    let spiritCount=0,everydayCount=0;

    forms.forEach(function(form){
      const idInput=form.querySelector('input[name="id"]');
      const productId=idInput?idInput.value.trim():'';
      const shopType=String(mappings[productId]||'spirit').toLowerCase()==='everyday'?'everyday':'spirit';
      const deleteForm=form.nextElementSibling&&form.nextElementSibling.tagName==='FORM'&&/\/delete$/.test(form.nextElementSibling.getAttribute('action')||'')?form.nextElementSibling:null;

      const item=document.createElement('article');item.className='ss-admin-product-item';item.dataset.productId=productId;
      const summary=makeSummary(form,shopType);
      const details=document.createElement('div');details.className='ss-product-details';details.id='ss-product-details-'+productId;details.hidden=true;

      summary.addEventListener('click',function(){
        if(item.classList.contains('open'))closeItem(item,false);else openItem(item);
      });

      const list=(shopType==='everyday'?everyday:spirit).querySelector('.ss-product-list');
      list.appendChild(item);item.appendChild(summary);item.appendChild(details);details.appendChild(form);
      if(deleteForm)details.appendChild(deleteForm);

      const closeRow=document.createElement('div');closeRow.className='ss-product-close-row';
      const closeButton=document.createElement('button');closeButton.type='button';closeButton.className='ss-product-close';closeButton.textContent='Close Product Editor';
      closeButton.addEventListener('click',function(){closeItem(item,true);});
      closeRow.appendChild(closeButton);details.appendChild(closeRow);

      if(shopType==='everyday')everydayCount+=1;else spiritCount+=1;
    });

    spirit.querySelector('.ss-product-count').textContent=String(spiritCount);
    everyday.querySelector('.ss-product-count').textContent=String(everydayCount);
    if(!spiritCount){const empty=document.createElement('div');empty.className='ss-product-empty';empty.textContent='No Official Spirit Wear products yet.';spirit.querySelector('.ss-product-list').appendChild(empty);}
    if(!everydayCount){const empty=document.createElement('div');empty.className='ss-product-empty';empty.textContent='No Everyday Shop products yet.';everyday.querySelector('.ss-product-list').appendChild(empty);}
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',function(){setTimeout(init,0);});
  }else{
    setTimeout(init,0);
  }
})();
</script>
"""


def register_store_product_accordion(app) -> None:
    """Group saved products by shop and collapse each editor into a compact summary row."""

    @app.after_request
    def add_store_product_accordion(response):
        if (
            request.method != "GET"
            or request.path != "/admin/store"
            or response.status_code != 200
            or response.mimetype != "text/html"
        ):
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body:
                return response
            if 'id="ss-store-product-accordion-style"' not in body:
                body = body.replace("</head>", PRODUCT_ACCORDION_STYLE + "\n</head>", 1)
            if 'id="ss-store-product-accordion-script"' not in body:
                body = body.replace("</body>", PRODUCT_ACCORDION_SCRIPT + "\n</body>", 1)
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply compact Store Manager product accordion")
        return response
