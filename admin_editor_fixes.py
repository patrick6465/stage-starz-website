from __future__ import annotations

from pathlib import Path

from flask import flash, redirect, request, session, url_for


CLASS_EDITOR_MOBILE_FIX = r"""
<style id="ss-class-editor-mobile-fix">
@media(max-width:780px){
  .page-nav button{min-height:58px;border-color:rgba(255,255,255,.08)!important}
  .page-nav button.active{border-color:#50d6d0!important;box-shadow:0 0 0 2px rgba(80,214,208,.12)!important}
  .ss-mobile-page-picker{display:block;margin:0 0 14px}
  .ss-mobile-page-picker label{display:block;margin:0 0 7px;font-size:.82rem;font-weight:900;color:#fff}
  .ss-mobile-page-picker select{width:100%;padding:14px;border-radius:12px;border:1px solid #50d6d0;background:#100a1d;color:#fff;font:inherit;font-weight:800}
}
@media(min-width:781px){.ss-mobile-page-picker{display:none}}
</style>
<script id="ss-class-editor-mobile-script">
(function(){
  function setup(){
    var nav=document.querySelector('.page-nav');
    var buttons=Array.from(document.querySelectorAll('.page-nav button[data-page]'));
    if(!nav||!buttons.length) return;

    var picker=document.getElementById('ss-mobile-page-picker-select');
    if(!picker){
      var wrap=document.createElement('div');
      wrap.className='ss-mobile-page-picker';
      wrap.innerHTML='<label for="ss-mobile-page-picker-select">Choose a class or team to edit</label><select id="ss-mobile-page-picker-select"></select>';
      nav.parentNode.insertBefore(wrap,nav);
      picker=wrap.querySelector('select');
      buttons.forEach(function(button){
        var option=document.createElement('option');
        option.value=button.dataset.page||'';
        option.textContent=(button.textContent||'').replace(/\s+/g,' ').trim();
        picker.appendChild(option);
      });
    }

    function currentKey(){
      var active=document.querySelector('.page-nav button.active[data-page]');
      return active ? active.dataset.page : ((location.hash||'').replace('#page-','') || (buttons[0]&&buttons[0].dataset.page));
    }

    function goTo(key,scroll){
      if(!key) return;
      if(typeof window.showPage==='function') window.showPage(key);
      if(picker) picker.value=key;
      if(scroll && window.matchMedia('(max-width:780px)').matches){
        window.setTimeout(function(){
          var card=document.getElementById('page-'+key);
          if(card) card.scrollIntoView({behavior:'smooth',block:'start'});
        },80);
      }
    }

    buttons.forEach(function(button){
      button.addEventListener('click',function(){goTo(button.dataset.page,true);});
    });
    if(picker){
      picker.value=currentKey();
      picker.addEventListener('change',function(){goTo(this.value,true);});
    }
    window.addEventListener('hashchange',function(){
      var key=(location.hash||'').replace('#page-','');
      if(key) goTo(key,false);
    });
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',setup);
  else setup();
})();
</script>
"""

MEDIA_LIBRARY_MOBILE_FIX = r"""
<style id="ss-media-mobile-fix">
.ss-upload-status{margin:12px 0 0;padding:11px 12px;border-radius:10px;background:#f2ecff;color:#4d1f91;font-weight:800;font-size:.88rem;display:none}
.ss-upload-status.show{display:block}
.ss-upload-status.error{background:#fff0f2;color:#a42337}
@media(max-width:640px){
  header{align-items:flex-start;gap:10px;flex-direction:column}
  header div{line-height:1.8}
  .wrap{width:min(100% - 20px,1200px);margin-top:14px}
  .card{padding:16px}
  input[type=file]{font-size:16px;max-width:100%}
  .actions{display:grid;grid-template-columns:1fr}
  .actions button,.actions .button{width:100%;text-align:center}
}
</style>
<script id="ss-media-mobile-script">
(function(){
  function setup(){
    var form=document.querySelector('form[action="/admin/media/upload"]');
    if(!form) return;
    var input=form.querySelector('input[type="file"][name="image"]');
    var button=form.querySelector('button.primary');
    if(!input||!button) return;

    var status=document.createElement('div');
    status.className='ss-upload-status';
    status.setAttribute('role','status');
    form.insertBefore(status,form.querySelector('.actions'));

    var heading=form.closest('.card');
    var note=heading ? heading.querySelector('p') : null;
    if(note) note.textContent='Choose a JPG, PNG, WEBP, HEIC, or HEIF photo. Upload starts automatically. Maximum original size: 25 MB.';

    input.addEventListener('change',function(){
      var file=input.files&&input.files[0];
      if(!file) return;
      var mb=file.size/1024/1024;
      status.className='ss-upload-status show';
      status.textContent='Selected: '+file.name+' ('+mb.toFixed(1)+' MB). Uploading and optimizing…';
      if(file.size>25*1024*1024){
        status.className='ss-upload-status show error';
        status.textContent='That photo is larger than 25 MB. Please choose a smaller image.';
        input.value='';
        return;
      }
      button.disabled=true;
      button.textContent='Uploading…';
      window.setTimeout(function(){
        if(form.requestSubmit) form.requestSubmit();
        else form.submit();
      },120);
    });
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',setup);
  else setup();
})();
</script>
"""


def register_admin_editor_fixes(app, upload_folder, save_uploaded_image, log_activity) -> None:
    """Make the mobile class editor navigation and Media Library uploads reliable."""

    @app.before_request
    def reliable_media_upload():
        if request.path != "/admin/media/upload" or request.method != "POST":
            return None
        if not session.get("admin_logged_in"):
            return None

        upload_folder.mkdir(parents=True, exist_ok=True)
        image = request.files.get("image")
        if not image or not image.filename:
            flash("Choose an image before uploading.", "error")
            return redirect(url_for("media_library"))

        try:
            image_url = save_uploaded_image(image)
            if not image_url:
                flash("Choose an image before uploading.", "error")
            else:
                log_activity("Image uploaded", Path(image_url).name)
                flash(f"{Path(image_url).name} uploaded and saved permanently.", "success")
        except ValueError as error:
            flash(str(error), "error")
        except Exception:
            app.logger.exception("Media Library upload failed")
            flash("That photo could not be uploaded. Please try it again or choose another image.", "error")
        return redirect(url_for("media_library"))

    @app.after_request
    def improve_admin_mobile_pages(response):
        if response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            if request.path == "/admin/website/classes":
                # The Teen team's built-in image is a sharper bundled WEBP. Keep the
                # editor preview aligned with the public page without changing custom uploads.
                body = body.replace(
                    "/assets/images/teen-competition-team.jpg",
                    "/assets/images/teen-competition-team.webp",
                )
                if 'id="ss-class-editor-mobile-fix"' not in body:
                    body = body.replace("</body>", CLASS_EDITOR_MOBILE_FIX + "</body>", 1)
                response.set_data(body)
            elif request.path == "/admin/media":
                if 'id="ss-media-mobile-fix"' not in body:
                    body = body.replace("</body>", MEDIA_LIBRARY_MOBILE_FIX + "</body>", 1)
                response.set_data(body)
        except Exception:
            app.logger.exception("Could not apply admin mobile fixes")
        return response