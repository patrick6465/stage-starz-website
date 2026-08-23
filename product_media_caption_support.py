from __future__ import annotations

from flask import has_request_context, request

from database import get_db
import product_media_gallery as gallery


PHOTO_SLOTS = (
    ("photo_2", "Photo 2", "product_image_2", "remove_product_image_2"),
    ("photo_3", "Photo 3", "product_image_3", "remove_product_image_3"),
    ("photo_4", "Photo 4", "product_image_4", "remove_product_image_4"),
)

CAPTION_FIELDS = {
    "photo_2": "product_caption_2",
    "photo_3": "product_caption_3",
    "photo_4": "product_caption_4",
}

DEFAULT_LABELS = {
    "photo_2": "Photo 2",
    "photo_3": "Photo 3",
    "photo_4": "Photo 4",
    "video": "Product video",
}

_original_ensure_schema = gallery.ensure_product_media_schema
_schema_ready = False


def _row_value(row, key: str, index: int = 0):
    try:
        return row[key]
    except (TypeError, KeyError, IndexError):
        return row[index]


def ensure_caption_schema() -> None:
    """Add one optional caption column without disturbing existing product media."""
    global _schema_ready
    if _schema_ready:
        return

    _original_ensure_schema()
    connection = get_db()
    try:
        if getattr(connection, "backend", "sqlite") == "postgresql":
            exists = connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='product_media' AND column_name='caption'
                """
            ).fetchone()
            has_caption = bool(exists)
        else:
            rows = connection.execute("PRAGMA table_info(product_media)").fetchall()
            has_caption = any(str(_row_value(row, "name", 1)) == "caption" for row in rows)

        if not has_caption:
            connection.execute(
                "ALTER TABLE product_media ADD COLUMN caption TEXT NOT NULL DEFAULT ''"
            )
        connection.commit()
        _schema_ready = True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _media_for_product(product_id: int) -> dict[str, dict[str, str]]:
    ensure_caption_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT slot, media_type, media_url, caption FROM product_media WHERE product_id=?",
        (product_id,),
    ).fetchall()
    connection.close()

    result: dict[str, dict[str, str]] = {}
    for row in rows:
        item = dict(row)
        result[str(item["slot"])] = {
            "type": str(item["media_type"] or ""),
            "url": str(item["media_url"] or ""),
            "caption": str(item.get("caption") or ""),
        }
    return result


def _all_media() -> dict[int, dict[str, dict[str, str]]]:
    ensure_caption_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT product_id, slot, media_type, media_url, caption FROM product_media ORDER BY product_id, slot"
    ).fetchall()
    connection.close()

    result: dict[int, dict[str, dict[str, str]]] = {}
    for row in rows:
        item = dict(row)
        product_id = int(item["product_id"])
        result.setdefault(product_id, {})[str(item["slot"])] = {
            "type": str(item["media_type"] or ""),
            "url": str(item["media_url"] or ""),
            "caption": str(item.get("caption") or ""),
        }
    return result


def _caption_from_request(slot: str, current: str = "") -> str:
    if not has_request_context():
        return current
    field = CAPTION_FIELDS.get(slot)
    if not field or field not in request.form:
        return current
    return request.form.get(field, "").strip()[:120]


def _set_media(product_id: int, slot: str, media_type: str, media_url: str) -> None:
    """Store media while preserving or accepting its optional editable caption."""
    ensure_caption_schema()
    connection = get_db()
    if media_url:
        existing = connection.execute(
            "SELECT caption FROM product_media WHERE product_id=? AND slot=?",
            (product_id, slot),
        ).fetchone()
        current_caption = str(_row_value(existing, "caption", 0) or "") if existing else ""
        caption = _caption_from_request(slot, current_caption)
        connection.execute(
            """
            INSERT INTO product_media (
                product_id, slot, media_type, media_url, caption, updated_at
            ) VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(product_id, slot) DO UPDATE SET
                media_type=excluded.media_type,
                media_url=excluded.media_url,
                caption=excluded.caption,
                updated_at=CURRENT_TIMESTAMP
            """,
            (product_id, slot, media_type, media_url, caption),
        )
    else:
        connection.execute(
            "DELETE FROM product_media WHERE product_id=? AND slot=?",
            (product_id, slot),
        )
    connection.commit()
    connection.close()


def _attach_product_media(products: list[dict]) -> list[dict]:
    media_map = _all_media()
    for product in products:
        product_id = int(product.get("id") or 0)
        slots = media_map.get(product_id, {})
        items: list[dict[str, str]] = []

        primary = str(product.get("image_url") or "").strip()
        if primary:
            items.append(
                {
                    "slot": "photo_1",
                    "type": "image",
                    "label": "Main photo",
                    "url": primary,
                }
            )

        for slot, _label, _field, _remove in PHOTO_SLOTS:
            entry = slots.get(slot) or {}
            url = str(entry.get("url") or "").strip()
            if url:
                caption = str(entry.get("caption") or "").strip()
                items.append(
                    {
                        "slot": slot,
                        "type": "image",
                        "label": caption or DEFAULT_LABELS[slot],
                        "url": url,
                    }
                )

        video = slots.get("video") or {}
        video_url = str(video.get("url") or "").strip()
        if video_url:
            items.append(
                {
                    "slot": "video",
                    "type": "video",
                    "label": DEFAULT_LABELS["video"],
                    "url": video_url,
                }
            )

        product["media_items"] = items
        product["image_urls"] = [item["url"] for item in items if item["type"] == "image"]
        product["video_url"] = video_url
        product["media_count"] = len(items)
    return products


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
      <div class="ss-product-media-head"><strong>Product Media Gallery</strong><span>Add up to three more photos plus one optional video. Photos 2–4 can be anything you need; give each one a caption such as Size Chart, Back View, or Detail.</span></div>
      <div class="ss-product-media-grid">
        <div class="ss-product-media-slot" data-media-slot="photo_2">
          <label>Photo 2</label><div class="ss-product-media-existing" data-existing></div>
          <input name="product_image_2" type="file" accept="image/*">
          <label class="ss-product-media-caption-label">Caption</label>
          <input class="ss-product-media-caption-field" data-caption name="product_caption_2" type="text" maxlength="120" placeholder="Example: Size Chart">
          <label class="ss-product-media-remove" data-remove><input name="remove_product_image_2" type="checkbox"> Remove existing Photo 2</label>
        </div>
        <div class="ss-product-media-slot" data-media-slot="photo_3">
          <label>Photo 3</label><div class="ss-product-media-existing" data-existing></div>
          <input name="product_image_3" type="file" accept="image/*">
          <label class="ss-product-media-caption-label">Caption</label>
          <input class="ss-product-media-caption-field" data-caption name="product_caption_3" type="text" maxlength="120" placeholder="Example: Back View">
          <label class="ss-product-media-remove" data-remove><input name="remove_product_image_3" type="checkbox"> Remove existing Photo 3</label>
        </div>
        <div class="ss-product-media-slot" data-media-slot="photo_4">
          <label>Photo 4</label><div class="ss-product-media-existing" data-existing></div>
          <input name="product_image_4" type="file" accept="image/*">
          <label class="ss-product-media-caption-label">Caption</label>
          <input class="ss-product-media-caption-field" data-caption name="product_caption_4" type="text" maxlength="120" placeholder="Example: Sleeve Detail">
          <label class="ss-product-media-remove" data-remove><input name="remove_product_image_4" type="checkbox"> Remove existing Photo 4</label>
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
          const box=editor.querySelector('[data-media-slot="'+slot+'"]');
          if(!box)return;
          const caption=box.querySelector('[data-caption]');
          if(caption&&item)caption.value=item.caption||'';
          if(!item||!item.url)return;
          const existing=box.querySelector('[data-existing]');
          const remove=box.querySelector('[data-remove]');
          existing.classList.add('show');
          if(item.type==='video'){
            const video=document.createElement('video');video.src=item.url;video.muted=true;video.preload='metadata';existing.appendChild(video);
          }else{
            const img=document.createElement('img');img.src=item.url;img.alt=item.caption||'Existing product photo';existing.appendChild(img);
          }
          const text=document.createElement('span');text.textContent=item.caption?('Currently saved — '+item.caption):'Currently saved';existing.appendChild(text);
          if(remove)remove.classList.add('show');
        });
      }).catch(()=>{});
  }
  document.querySelectorAll('form[action="/admin/product/save"]').forEach(buildEditor);
})();
</script>
"""


def _save_existing_caption_edits(response):
    """Persist caption-only edits even when the image file itself was not replaced."""
    if (
        request.method != "POST"
        or request.path != "/admin/product/save"
        or response.status_code >= 400
    ):
        return response

    product_id_value = request.form.get("id", "").strip()
    if not product_id_value:
        return response

    try:
        product_id = int(product_id_value)
    except (TypeError, ValueError):
        return response

    ensure_caption_schema()
    connection = get_db()
    try:
        for slot, field in CAPTION_FIELDS.items():
            if field not in request.form:
                continue
            caption = request.form.get(field, "").strip()[:120]
            connection.execute(
                """
                UPDATE product_media
                SET caption=?, updated_at=CURRENT_TIMESTAMP
                WHERE product_id=? AND slot=?
                """,
                (caption, product_id, slot),
            )
        connection.commit()
    except Exception:
        connection.rollback()
    finally:
        connection.close()
    return response


def install_product_media_captions(app) -> None:
    """Make Photo 2–4 generic and give each saved gallery photo an editable caption."""
    ensure_caption_schema()

    gallery.PHOTO_SLOTS = PHOTO_SLOTS
    gallery.ensure_product_media_schema = ensure_caption_schema
    gallery._media_for_product = _media_for_product
    gallery._all_media = _all_media
    gallery._set_media = _set_media
    gallery._attach_product_media = _attach_product_media
    gallery.ADMIN_SCRIPT = ADMIN_SCRIPT
    gallery.ADMIN_STYLE = gallery.ADMIN_STYLE.replace(
        "</style>",
        """
.ss-product-media-caption-label{display:block!important;margin:10px 0 5px!important;color:#cfc5dc!important;font-size:.7rem!important;font-weight:800!important}
body .ss-product-media-editor input.ss-product-media-caption-field{width:100%!important;box-sizing:border-box!important;margin:0!important;padding:9px 10px!important;border:1px solid rgba(255,255,255,.14)!important;border-radius:9px!important;background:rgba(255,255,255,.055)!important;color:#fff!important;font:inherit!important;font-size:.78rem!important}
body .ss-product-media-editor input.ss-product-media-caption-field::placeholder{color:#8f849e!important}
</style>""",
        1,
    )

    app.after_request(_save_existing_caption_edits)
