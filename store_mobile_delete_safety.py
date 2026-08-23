from __future__ import annotations

from flask import request


STYLE = r"""
<style id="ss-store-delete-safety-style">
form.product + form[action^="/admin/product/"][action$="/delete"]{
  margin-top:18px;
  margin-bottom:30px;
}
@media(max-width:720px){
  form.product > .actions{
    margin-bottom:0!important;
  }
  form.product + form[action^="/admin/product/"][action$="/delete"]{
    margin-top:22px!important;
    margin-bottom:36px!important;
    padding-top:18px;
    border-top:1px solid rgba(255,255,255,.10);
  }
  form.product + form[action^="/admin/product/"][action$="/delete"] .danger{
    min-height:48px;
  }
}
</style>
"""


SCRIPT = r"""
<script id="ss-store-delete-safety-script">
(function(){
  document.querySelectorAll('form[action^="/admin/product/"][action$="/delete"]').forEach(function(form){
    // Replace the older generic inline confirm with one clear product-specific warning.
    form.onsubmit = null;
    form.addEventListener('submit', function(event){
      var editForm = form.previousElementSibling;
      var nameInput = editForm && editForm.querySelector('input[name="name"]');
      var productName = nameInput && nameInput.value.trim() ? nameInput.value.trim() : 'this product';
      var confirmed = window.confirm(
        'Delete "' + productName + '"?\n\nThis permanently removes the product and cannot be undone.'
      );
      if(!confirmed){
        event.preventDefault();
        event.stopPropagation();
      }
    });
  });
})();
</script>
"""


def register_store_mobile_delete_safety(app) -> None:
    @app.after_request
    def store_mobile_delete_safety(response):
        if (
            request.method != "GET"
            or request.path != "/admin/store"
            or response.status_code != 200
            or response.mimetype != "text/html"
        ):
            return response
        try:
            body = response.get_data(as_text=True)
            if "ss-store-delete-safety-style" not in body:
                body = body.replace("</head>", STYLE + "\n</head>", 1)
            if "ss-store-delete-safety-script" not in body:
                body = body.replace("</body>", SCRIPT + "\n</body>", 1)
            response.set_data(body)
        except Exception:
            app.logger.exception("Could not apply Store Manager delete safety polish")
        return response
