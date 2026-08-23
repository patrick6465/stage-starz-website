from __future__ import annotations

from pathlib import Path

from flask import flash, jsonify, redirect, request, url_for

from database import get_db
from persistent_videos import _store_video, delete_persistent_video
from website_video_manager import _save_video, _video_path_from_url


PHOTO_SLOTS = (
    ("photo_2", "Photo 2 — Back", "product_image_2", "remove_product_image_2"),
    ("photo_3", "Photo 3 — Size chart", "product_image_3", "remove_product_image_3"),
    ("photo_4", "Photo 4 — Extra / detail", "product_image_4", "remove_product_image_4"),
)
VIDEO_SLOT = "video"


def ensure_product_media_schema() -> None:
    connection = get_db()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS product_media (
            product_id INTEGER NOT NULL,
            slot TEXT NOT NULL,
            media_type TEXT NOT NULL,
            media_url TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (product_id, slot),
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        )
        """
    )
    connection.commit()
    connection.close()


def _media_for_product(product_id: int) -> dict[str, dict[str, str]]:
    ensure_product_media_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT slot, media_type, media_url FROM product_media WHERE product_id=?",
        (product_id,),
    ).fetchall()
    connection.close()
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        item = dict(row)
        result[str(item["slot"])] = {
            "type": str(item["media_type"] or ""),
            "url": str(item["media_url"] or ""),
        }
    return result


def _all_media() -> dict[int, dict[str, dict[str, str]]]:
    ensure_product_media_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT product_id, slot, media_type, media_url FROM product_media ORDER BY product_id, slot"
    ).fetchall()
    connection.close()
    result: dict[int, dict[str, dict[str, str]]] = {}
    for row in rows:
        item = dict(row)
        product_id = int(item["product_id"])
        result.setdefault(product_id, {})[str(item["slot"])] = {
            "type": str(item["media_type"] or ""),
            "url": str(item["media_url"] or ""),
        }
    return result


def _set_media(product_id: int, slot: str, media_type: str, media_url: str) -> None:
    ensure_product_media_schema()
    connection = get_db()
    if media_url:
        connection.execute(
            """
            INSERT INTO product_media (product_id, slot, media_type, media_url, updated_at)
            VALUES (?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(product_id, slot) DO UPDATE SET
                media_type=excluded.media_type,
                media_url=excluded.media_url,
                updated_at=CURRENT_TIMESTAMP
            """,
            (product_id, slot, media_type, media_url),
        )
    else:
        connection.execute(
            "DELETE FROM product_media WHERE product_id=? AND slot=?",
            (product_id, slot),
        )
    connection.commit()
    connection.close()


def _image_reference_count(image_url: str) -> int:
    if not image_url:
        return 0
    connection = get_db()
    product_count = connection.execute(
        "SELECT COUNT(*) AS count FROM products WHERE image_url=?",
        (image_url,),
    ).fetchone()["count"]
    media_count = connection.execute(
        "SELECT COUNT(*) AS count FROM product_media WHERE media_type='image' AND media_url=?",
        (image_url,),
    ).fetchone()["count"]
    connection.close()
    return int(product_count or 0) + int(media_count or 0)


def _video_reference_count(video_url: str) -> int:
    if not video_url:
        return 0
    connection = get_db()
    count = connection.execute(
        "SELECT COUNT(*) AS count FROM product_media WHERE media_type='video' AND media_url=?",
        (video_url,),
    ).fetchone()["count"]
    connection.close()
    return int(count or 0)


def _cleanup_image_if_unused(image_url: str, delete_image) -> None:
    if image_url and _image_reference_count(image_url) == 0:
        try:
            delete_image(image_url)
        except Exception:
            pass


def _cleanup_video_if_unused(video_url: str) -> None:
    if not video_url or _video_reference_count(video_url) != 0:
        return
    try:
        delete_persistent_video(video_url)
    except Exception:
        pass
    try:
        path = _video_path_from_url(video_url)
        if path and path.exists() and path.is_file():
            path.unlink()
    except Exception:
        pass


def _as_float(value, default=0.0):
    try:
        return float(value) if str(value or "").strip() else default
    except (TypeError, ValueError):
        return default


def _as_int(value, default=0):
    try:
        return int(float(value)) if str(value or "").strip() else default
    except (TypeError, ValueError):
        return default


def _attach_product_media(products: list[dict]) -> list[dict]:
    media_map = _all_media()
    labels = {
        "photo_2": "Back",
        "photo_3": "Size chart",
        "photo_4": "Extra / detail",
        "video": "Product video",
    }
    for product in products:
        product_id = int(product.get("id") or 0)
        slots = media_map.get(product_id, {})
        items: list[dict[str, str]] = []
        primary = str(product.get("image_url") or "").strip()
        if primary:
            items.append({
                "slot": "photo_1",
                "type": "image",
                "label": "Front / main",
                "url": primary,
            })
        for slot, _label, _field, _remove in PHOTO_SLOTS:
            entry = slots.get(slot) or {}
            url = str(entry.get("url") or "").strip()
            if url:
                items.append({
                    "slot": slot,
                    "type": "image",
                    "label": labels[slot],
                    "url": url,
                })
        video = slots.get(VIDEO_SLOT) or {}
        video_url = str(video.get("url") or "").strip()
        if video_url:
            items.append({
                "slot": VIDEO_SLOT,
                "type": "video",
                "label": labels[VIDEO_SLOT],
                "url": video_url,
            })
        product["media_items"] = items
        product["image_urls"] = [item["url"] for item in items if item["type"] == "image"]
        product["video_url"] = video_url
        product["media_count"] = len(items)
    return products


ADMIN_STYLE = r"""
<style id="ss-product-media-admin-style">
.ss-product-media-editor{grid-column:1/-1;margin-top:2px;padding:15px;border:1px solid rgba(80,214,208,.24);border-radius:14px;background:rgba(80,214,208,.055)}
.ss-product-media-head{margin-bottom:12px}.ss-product-media-head strong{display:block;color:#fff!important;font-size:.9rem}.ss-product-media-head span{display:block;color:#b8adca!important;font-size:.78rem;line-height:1.45;margin-top:3px}
.ss-product-media-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.ss-product-media-slot{padding:12px;border:1px solid rgba(255,255,255,.11);border-radius:12px;background:rgba(16,10,29,.68);min-width:0}
body .ss-product-media-editor label,body .ss-product-media-editor strong{color:#fff!important}.ss-product-media-slot>label{display:block;margin:0 0 7px;font-size:.76rem;font-weight:900}.ss-product-media-slot input[type=file]{width:100%}.ss-product-media-note{display:block;color:#b8adca!important;font-size:.7rem;line-height:1.4;margin-top:6px}
.ss-product-media-existing{display:none;align-items:center;gap:9px;margin:0 0 9px;padding:8px;border:1px solid rgba(255,255,255,.09);border-radius:10px;background:rgba(255,255,255,.035)}.ss-product-media-existing.show{display:flex}.ss-product-media-existing img,.ss-product-media-existing video{width:58px;height:58px;border-radius:8px;object-fit:cover;background:#080611}.ss-product-media-existing span{color:#d9d0e4!important;font-size:.7rem;overflow-wrap:anywhere}
.ss-product-media-remove{display:none!important;align-items:center!important;gap:7px!important;margin-top:8px!important;color:#ddd4e8!important;font-size:.72rem!important}.ss-product-media-remove.show{display:flex!important}.ss-product-media-remove input{width:auto!important;margin:0!important}
@media(max-width:720px){.ss-product-media-grid{grid-template-columns:1fr}.ss-product-media-editor{grid-column:auto;padding:12px}}
</style>
"""


ADMIN_SCRIPT = r"""
<script id="ss-product-media-admin-script">
(function(){
  function buildEditor(form){
    if(form.dataset.ssProductMediaReady==='1')return;
    form.dataset.ssProductMediaReady='1';
    const primary=form.querySelector('input[name="product_image"]');
    if(!primary)return;
    const primaryWrap=primary.closest('div');
    const primaryLabel=primaryWrap&&primaryWrap.querySelector('label');
    if(primaryLabel)primaryLabel.textContent='Photo 1 — Main / front';

    const editor=document.createElement('div');
    editor.className='ss-product-media-editor';
    editor.innerHTML=`
      <div class="ss-product-media-head"><strong>Product Media Gallery</strong><span>Add up to three more photos plus one optional video. The main/front photo above remains the store-card image.</span></div>
      <div class="ss-product-media-grid">
        <div class="ss-product-media-slot" data-media-slot="photo_2">
          <label>Photo 2 — Back</label><div class="ss-product-media-existing" data-existing></div>
          <input name="product_image_2" type="file" accept="image/*">
          <label class="ss-product-media-remove" data-remove><input name="remove_product_image_2" type="checkbox"> Remove existing back photo</label>
        </div>
        <div class="ss-product-media-slot" data-media-slot="photo_3">
          <label>Photo 3 — Size chart</label><div class="ss-product-media-existing" data-existing></div>
          <input name="product_image_3" type="file" accept="image/*">
          <label class="ss-product-media-remove" data-remove><input name="remove_product_image_3" type="checkbox"> Remove existing size chart</label>
        </div>
        <div class="ss-product-media-slot" data-media-slot="photo_4">
          <label>Photo 4 — Extra / detail</label><div class="ss-product-media-existing" data-existing></div>
          <input name="product_image_4" type="file" accept="image/*">
          <label class="ss-product-media-remove" data-remove><input name="remove_product_image_4" type="checkbox"> Remove existing extra photo</label>
        </div>
        <div class="ss-product-media-slot" data-media-slot="video">
          <label>Product video — Optional</label><div class="ss-product-media-existing" data-existing></div>
          <input name="product_video" type="file" accept="video/mp4,video/webm,video/quicktime,.mov,.m4v">
          <span class="ss-product-media-note">MP4 recommended. Up to 250 MB. Video does not autoplay in the store.</span>
          <label class="ss-product-media-remove" data-remove><input name="remove_product_video" type="checkbox"> Remove existing product video</label>
        </div>
      </div>`;
    if(primaryWrap)primaryWrap.insertAdjacentElement('afterend',editor);

    const idInput=form.querySelector('input[name="id"]');
    const productId=idInput&&idInput.value.trim();
    if(!productId){
      editor.querySelectorAll('[data-remove]').forEach(el=>el.remove());
      return;
    }
    fetch('/admin/product-media/'+encodeURIComponent(productId),{credentials:'same-origin'})
      .then(r=>r.ok?r.json():null)
      .then(data=>{
        if(!data)return;
        ['photo_2','photo_3','photo_4','video'].forEach(slot=>{
          const item=data[slot];
          if(!item||!item.url)return;
          const box=editor.querySelector('[data-media-slot="'+slot+'"]');
          if(!box)return;
          const existing=box.querySelector('[data-existing]');
          const remove=box.querySelector('[data-remove]');
          existing.classList.add('show');
          if(item.type==='video'){
            const video=document.createElement('video');video.src=item.url;video.muted=true;video.preload='metadata';existing.appendChild(video);
          }else{
            const img=document.createElement('img');img.src=item.url;img.alt='Existing product photo';existing.appendChild(img);
          }
          const text=document.createElement('span');text.textContent='Currently saved';existing.appendChild(text);
          if(remove)remove.classList.add('show');
        });
      }).catch(()=>{});
  }
  document.querySelectorAll('form[action="/admin/product/save"]').forEach(buildEditor);
})();
</script>
"""


STORE_STYLE = r"""
<style id="ss-product-media-store-style">
.media.ss-has-product-media{position:relative;cursor:pointer}.ss-product-media-badge{position:absolute;right:10px;bottom:10px;z-index:3;border:0;border-radius:999px;padding:7px 10px;background:rgba(32,34,52,.84);color:#fff;font:inherit;font-size:.72rem;font-weight:900;box-shadow:0 7px 20px rgba(0,0,0,.18);backdrop-filter:blur(8px)}
.ss-product-media-modal{position:fixed;inset:0;z-index:90;display:none;place-items:center;padding:20px;background:rgba(8,6,15,.76)}.ss-product-media-modal.open{display:grid}.ss-product-media-dialog{width:min(900px,96vw);max-height:92vh;overflow:auto;border-radius:22px;background:#fff;box-shadow:0 28px 90px rgba(0,0,0,.34)}
.ss-product-media-modal-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:16px 18px;border-bottom:1px solid #e5deee}.ss-product-media-modal-head strong{font-size:1.05rem}.ss-product-media-close{width:38px;height:38px;border:0;border-radius:50%;background:#eee;font-size:1.25rem}
.ss-product-media-stage-wrap{position:relative;background:#f4f0f8}.ss-product-media-stage{min-height:440px;display:grid;place-items:center;padding:16px}.ss-product-media-stage img,.ss-product-media-stage video{display:block;max-width:100%;width:auto;max-height:68vh;border-radius:14px;object-fit:contain;background:#0a0810}.ss-product-media-stage video{width:100%;aspect-ratio:16/9}
.ss-product-media-nav{position:absolute;top:50%;transform:translateY(-50%);width:42px;height:42px;border:0;border-radius:50%;background:rgba(32,34,52,.78);color:#fff;font-size:1.6rem;display:none;place-items:center}.ss-product-media-nav.show{display:grid}.ss-product-media-prev{left:12px}.ss-product-media-next{right:12px}
.ss-product-media-caption{text-align:center;padding:0 16px 12px;color:#6d7180;font-size:.82rem;font-weight:800}.ss-product-media-thumbs{display:flex;gap:9px;overflow-x:auto;padding:13px 16px 17px;border-top:1px solid #e5deee}.ss-product-media-thumb{flex:0 0 82px;height:70px;border:2px solid transparent;border-radius:11px;overflow:hidden;background:#eee;padding:0;position:relative}.ss-product-media-thumb.active{border-color:#6f35c5}.ss-product-media-thumb img{width:100%;height:100%;object-fit:cover}.ss-product-media-video-thumb{display:grid;place-items:center;background:linear-gradient(135deg,#5b2aa0,#1699aa);color:#fff;font-size:1.55rem}.ss-product-media-video-thumb span{position:absolute;bottom:4px;left:4px;right:4px;font-size:.55rem;font-weight:900;text-align:center}
@media(max-width:700px){.ss-product-media-modal{padding:9px}.ss-product-media-dialog{width:100%;border-radius:18px}.ss-product-media-stage{min-height:300px;padding:10px}.ss-product-media-stage img,.ss-product-media-stage video{max-height:62vh}.ss-product-media-nav{width:38px;height:38px}.ss-product-media-thumb{flex-basis:70px;height:60px}}
</style>
"""


STORE_MODAL = r"""
<div id="ssProductMediaModal" class="ss-product-media-modal" onclick="if(event.target===this)ssCloseProductMedia()" aria-hidden="true">
  <section class="ss-product-media-dialog" role="dialog" aria-modal="true" aria-labelledby="ssProductMediaTitle">
    <div class="ss-product-media-modal-head"><strong id="ssProductMediaTitle">Product media</strong><button class="ss-product-media-close" type="button" onclick="ssCloseProductMedia()" aria-label="Close">×</button></div>
    <div class="ss-product-media-stage-wrap">
      <div id="ssProductMediaStage" class="ss-product-media-stage"></div>
      <button id="ssProductMediaPrev" class="ss-product-media-nav ss-product-media-prev" type="button" onclick="ssProductMediaMove(-1)" aria-label="Previous media">‹</button>
      <button id="ssProductMediaNext" class="ss-product-media-nav ss-product-media-next" type="button" onclick="ssProductMediaMove(1)" aria-label="Next media">›</button>
    </div>
    <div id="ssProductMediaCaption" class="ss-product-media-caption"></div>
    <div id="ssProductMediaThumbs" class="ss-product-media-thumbs"></div>
  </section>
</div>
"""


STORE_SCRIPT = r"""
<script id="ss-product-media-store-script">
(function(){
  let activeItems=[],activeIndex=0;
  function productById(id){try{return products.find(p=>Number(p.id)===Number(id));}catch(e){return null;}}
  function cardProductId(card){const size=card.querySelector('select[id^="size-"]');return size?Number(size.id.replace('size-','')):0;}
  function itemsFor(product){return Array.isArray(product&&product.media_items)?product.media_items.filter(x=>x&&x.url):[];}
  function enhance(){
    document.querySelectorAll('#grid .card').forEach(card=>{
      const id=cardProductId(card);if(!id)return;
      const p=productById(id);const items=itemsFor(p);const hasExtra=items.length>1||(items.length===1&&items[0].type==='video');
      if(!hasExtra)return;
      const media=card.querySelector('.media');if(!media||media.classList.contains('ss-has-product-media'))return;
      media.classList.add('ss-has-product-media');media.setAttribute('role','button');media.setAttribute('tabindex','0');media.setAttribute('aria-label','View product photos and video');
      media.addEventListener('click',e=>{if(e.target.closest('.ss-product-media-badge'))return;ssOpenProductMedia(id);});
      media.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();ssOpenProductMedia(id);}});
      const badge=document.createElement('button');badge.type='button';badge.className='ss-product-media-badge';
      const photos=items.filter(x=>x.type==='image').length;const video=items.some(x=>x.type==='video');
      badge.textContent='📷 '+photos+(video?'  ▶':'');badge.title='View photos'+(video?' and video':'');badge.addEventListener('click',e=>{e.stopPropagation();ssOpenProductMedia(id);});media.appendChild(badge);
    });
  }
  window.ssOpenProductMedia=function(id){
    const p=productById(id);activeItems=itemsFor(p);if(!activeItems.length)return;activeIndex=0;
    document.getElementById('ssProductMediaTitle').textContent=p.name||'Product media';
    const thumbs=document.getElementById('ssProductMediaThumbs');thumbs.innerHTML='';
    activeItems.forEach((item,index)=>{
      const button=document.createElement('button');button.type='button';button.className='ss-product-media-thumb';button.setAttribute('aria-label','View '+(item.label||'media'));
      if(item.type==='video'){button.classList.add('ss-product-media-video-thumb');button.innerHTML='▶<span>VIDEO</span>';}
      else{const img=document.createElement('img');img.src=item.url;img.alt=item.label||'Product photo';button.appendChild(img);}
      button.addEventListener('click',()=>ssShowProductMedia(index));thumbs.appendChild(button);
    });
    const modal=document.getElementById('ssProductMediaModal');modal.classList.add('open');modal.setAttribute('aria-hidden','false');document.body.style.overflow='hidden';ssShowProductMedia(0);
  };
  window.ssShowProductMedia=function(index){
    if(!activeItems.length)return;activeIndex=(index+activeItems.length)%activeItems.length;const item=activeItems[activeIndex];
    const stage=document.getElementById('ssProductMediaStage');stage.innerHTML='';
    if(item.type==='video'){const video=document.createElement('video');video.src=item.url;video.controls=true;video.playsInline=true;video.preload='metadata';stage.appendChild(video);}
    else{const img=document.createElement('img');img.src=item.url;img.alt=item.label||'Product photo';stage.appendChild(img);}
    document.getElementById('ssProductMediaCaption').textContent=item.label||'';
    document.querySelectorAll('#ssProductMediaThumbs .ss-product-media-thumb').forEach((thumb,i)=>thumb.classList.toggle('active',i===activeIndex));
    const showNav=activeItems.length>1;document.getElementById('ssProductMediaPrev').classList.toggle('show',showNav);document.getElementById('ssProductMediaNext').classList.toggle('show',showNav);
  };
  window.ssProductMediaMove=function(delta){ssShowProductMedia(activeIndex+delta);};
  window.ssCloseProductMedia=function(){
    const modal=document.getElementById('ssProductMediaModal');const video=modal.querySelector('video');if(video)video.pause();modal.classList.remove('open');modal.setAttribute('aria-hidden','true');document.body.style.overflow='';
  };
  document.addEventListener('keydown',e=>{const modal=document.getElementById('ssProductMediaModal');if(!modal.classList.contains('open'))return;if(e.key==='Escape')ssCloseProductMedia();else if(e.key==='ArrowLeft')ssProductMediaMove(-1);else if(e.key==='ArrowRight')ssProductMediaMove(1);});
  const grid=document.getElementById('grid');if(grid)new MutationObserver(enhance).observe(grid,{childList:true,subtree:true});setTimeout(enhance,0);
})();
</script>
"""


def register_product_media_gallery(
    app,
    permission_required,
    save_image,
    delete_image,
    log_activity=None,
) -> None:
    """Add a four-photo product gallery and one optional uploaded product video."""
    ensure_product_media_schema()

    @app.route("/admin/product-media/<int:product_id>")
    @permission_required("store")
    def admin_product_media(product_id: int):
        return jsonify(_media_for_product(product_id))

    original_api = app.view_functions.get("api_products")
    if original_api:
        def api_products_with_media():
            response = original_api()
            response = app.make_response(response)
            data = response.get_json(silent=True)
            if isinstance(data, list):
                _attach_product_media(data)
                response.set_data(app.json.dumps(data))
                response.mimetype = "application/json"
            return response
        app.view_functions["api_products"] = api_products_with_media

    @permission_required("store")
    def save_product_with_media():
        form = request.form
        product_id_value = form.get("id", "").strip()
        existing_image_url = form.get("existing_image_url", "").strip()
        image_url = "" if form.get("remove_image") == "on" else existing_image_url
        new_primary = ""

        try:
            uploaded_primary = request.files.get("product_image")
            if uploaded_primary and uploaded_primary.filename:
                new_primary = save_image(uploaded_primary)
                if new_primary:
                    image_url = new_primary
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("store_manager"))

        values = (
            form.get("name", "").strip(),
            form.get("category", "").strip(),
            form.get("description", "").strip(),
            _as_float(form.get("price"), 0.0),
            _as_float(form.get("sale_price"), 0.0) if form.get("sale_price", "").strip() else None,
            _as_float(form.get("fulfillment_fee"), 0.0),
            _as_int(form.get("stock"), 0),
            form.get("sizes", "").strip(),
            form.get("colors", "Default").strip() or "Default",
            1 if form.get("show_color") == "on" else 0,
            1 if form.get("allow_name") == "on" else 0,
            1 if form.get("active") == "on" else 0,
            image_url,
            form.get("emoji", "⭐").strip() or "⭐",
        )

        connection = get_db()
        try:
            if product_id_value:
                product_id = int(product_id_value)
                connection.execute(
                    """UPDATE products SET name=?, category=?, description=?, price=?, sale_price=?, fulfillment_fee=?, stock=?, sizes=?, colors=?, show_color=?, allow_name=?, active=?, image_url=?, emoji=? WHERE id=?""",
                    values + (product_id,),
                )
            else:
                sql = """INSERT INTO products (name, category, description, price, sale_price, fulfillment_fee, stock, sizes, colors, show_color, allow_name, active, image_url, emoji) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                if connection.backend == "postgresql":
                    sql += " RETURNING id"
                cursor = connection.execute(sql, values)
                product_id = int(cursor.fetchone()["id"]) if connection.backend == "postgresql" else int(cursor.lastrowid)
            connection.commit()
        except Exception:
            connection.rollback()
            connection.close()
            if new_primary:
                try: delete_image(new_primary)
                except Exception: pass
            app.logger.exception("Product save failed while product media gallery was enabled")
            flash("The product could not be saved. Please try again.", "error")
            return redirect(url_for("store_manager"))
        connection.close()

        media_errors: list[str] = []
        for slot, label, upload_field, remove_field in PHOTO_SLOTS:
            old = (_media_for_product(product_id).get(slot) or {}).get("url", "")
            upload = request.files.get(upload_field)
            try:
                if upload and upload.filename:
                    new_url = save_image(upload)
                    if new_url:
                        try:
                            _set_media(product_id, slot, "image", new_url)
                        except Exception:
                            try: delete_image(new_url)
                            except Exception: pass
                            raise
                        if old and old != new_url:
                            _cleanup_image_if_unused(old, delete_image)
                elif form.get(remove_field) == "on" and old:
                    _set_media(product_id, slot, "image", "")
                    _cleanup_image_if_unused(old, delete_image)
            except ValueError as error:
                media_errors.append(f"{label}: {error}")
            except Exception:
                app.logger.exception("Could not save %s for product %s", slot, product_id)
                media_errors.append(f"{label} could not be saved.")

        old_video = (_media_for_product(product_id).get(VIDEO_SLOT) or {}).get("url", "")
        video_upload = request.files.get("product_video")
        try:
            if video_upload and video_upload.filename:
                new_video = _save_video(video_upload)
                path = _video_path_from_url(new_video)
                if path is None or not _store_video(path):
                    if path and path.exists():
                        path.unlink()
                    raise ValueError("The product video could not be backed up to persistent storage.")
                try:
                    _set_media(product_id, VIDEO_SLOT, "video", new_video)
                except Exception:
                    delete_persistent_video(new_video)
                    if path and path.exists():
                        path.unlink()
                    raise
                if old_video and old_video != new_video:
                    _cleanup_video_if_unused(old_video)
            elif form.get("remove_product_video") == "on" and old_video:
                _set_media(product_id, VIDEO_SLOT, "video", "")
                _cleanup_video_if_unused(old_video)
        except ValueError as error:
            media_errors.append(f"Product video: {error}")
        except Exception:
            app.logger.exception("Could not save product video for product %s", product_id)
            media_errors.append("Product video could not be saved.")

        if existing_image_url and existing_image_url != image_url:
            _cleanup_image_if_unused(existing_image_url, delete_image)

        action = "updated" if product_id_value else "added"
        if log_activity:
            try:
                log_activity(f"Product {action}", values[0])
            except Exception:
                app.logger.exception("Could not log product media save")
        if media_errors:
            flash(f"Product {action}, but " + " ".join(media_errors), "error")
        else:
            flash(f"Product {action}.", "success")
        return redirect(url_for("store_manager"))

    if "save_product" in app.view_functions:
        app.view_functions["save_product"] = save_product_with_media

    original_delete = app.view_functions.get("delete_product")
    if original_delete:
        def delete_product_with_media(product_id: int):
            captured = _media_for_product(product_id)
            response = original_delete(product_id)
            response = app.make_response(response)
            if response.status_code < 400:
                connection = get_db()
                exists = connection.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone()
                connection.close()
                if not exists:
                    for item in captured.values():
                        url = item.get("url", "")
                        if item.get("type") == "video":
                            _cleanup_video_if_unused(url)
                        else:
                            _cleanup_image_if_unused(url, delete_image)
            return response
        app.view_functions["delete_product"] = delete_product_with_media

    @app.after_request
    def product_media_ui(response):
        if request.method != "GET" or response.status_code != 200 or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            if request.path == "/admin/store" and "ss-product-media-admin-script" not in body:
                body = body.replace("</head>", ADMIN_STYLE + "\n</head>", 1)
                body = body.replace("</body>", ADMIN_SCRIPT + "\n</body>", 1)
                response.set_data(body)
            elif request.path == "/store" and "ss-product-media-store-script" not in body:
                body = body.replace("</head>", STORE_STYLE + "\n</head>", 1)
                body = body.replace("</body>", STORE_MODAL + STORE_SCRIPT + "\n</body>", 1)
                response.set_data(body)
        except Exception:
            app.logger.exception("Could not inject product media gallery UI")
        return response
