from __future__ import annotations

from flask import request


MOBILE_POLISH = r"""
<style id="ss-command-center-mobile-polish">
@media(max-width:940px){
  #command-center-v3 .main{padding-bottom:165px!important}
  #command-center-v3 .modules{gap:10px!important}
  #command-center-v3 .module-card.mobile-collapsible{padding:0!important;overflow:hidden}
  #command-center-v3 .module-card.mobile-collapsible .module-head{
    margin:0!important;padding:16px;align-items:center;cursor:pointer;user-select:none
  }
  #command-center-v3 .module-card.mobile-collapsible .module-head:active{background:rgba(255,255,255,.035)}
  #command-center-v3 .module-card.mobile-collapsible .mobile-toggle-indicator{
    margin-left:auto;flex:0 0 34px;width:34px;height:34px;border-radius:11px;
    display:grid;place-items:center;border:1px solid rgba(255,255,255,.11);
    background:rgba(255,255,255,.045);font-size:1rem;color:#d9d0e4;
    transition:transform .18s ease,background .18s ease
  }
  #command-center-v3 .module-card.mobile-collapsible .tool-list{
    display:none!important;padding:0 16px 16px
  }
  #command-center-v3 .module-card.mobile-collapsible.mobile-open .tool-list{display:grid!important}
  #command-center-v3 .module-card.mobile-collapsible.mobile-open .module-head{
    border-bottom:1px solid rgba(255,255,255,.08);margin-bottom:14px!important
  }
  #command-center-v3 .module-card.mobile-collapsible.mobile-open .mobile-toggle-indicator{
    transform:rotate(180deg);background:rgba(80,214,208,.09);color:#8ff0eb
  }
  #command-center-v3 .content-grid:last-of-type{margin-bottom:28px}
}
@media(min-width:941px){
  #command-center-v3 .mobile-toggle-indicator{display:none!important}
}
</style>
<script id="ss-command-center-mobile-polish-script">
(function(){
  var root=document.getElementById('command-center-v3');
  if(!root)return;
  var mobile=window.matchMedia('(max-width: 940px)');
  var cards=Array.prototype.slice.call(document.querySelectorAll('.module-card'));

  function sync(card){
    var head=card.querySelector('.module-head');
    var indicator=card.querySelector('.mobile-toggle-indicator');
    if(!head)return;
    if(mobile.matches){
      head.setAttribute('role','button');
      head.setAttribute('tabindex','0');
      head.setAttribute('aria-expanded',card.classList.contains('mobile-open')?'true':'false');
      if(indicator)indicator.setAttribute('aria-hidden','true');
    }else{
      head.removeAttribute('role');
      head.removeAttribute('tabindex');
      head.removeAttribute('aria-expanded');
    }
  }

  function setOpen(card,open,exclusive){
    if(exclusive&&open){
      cards.forEach(function(other){
        if(other!==card){other.classList.remove('mobile-open');sync(other);}
      });
    }
    card.classList.toggle('mobile-open',!!open);
    sync(card);
  }

  cards.forEach(function(card){
    var head=card.querySelector('.module-head');
    var tools=card.querySelector('.tool-list');
    if(!head||!tools)return;
    card.classList.add('mobile-collapsible');

    var indicator=document.createElement('span');
    indicator.className='mobile-toggle-indicator';
    indicator.textContent='⌄';
    head.appendChild(indicator);

    if(card.id==='website-management')card.classList.add('mobile-open');
    else card.classList.remove('mobile-open');

    function toggle(){
      if(!mobile.matches)return;
      setOpen(card,!card.classList.contains('mobile-open'),true);
    }
    head.addEventListener('click',function(event){
      if(event.target.closest('a,button,input,select,textarea'))return;
      toggle();
    });
    head.addEventListener('keydown',function(event){
      if(!mobile.matches)return;
      if(event.key==='Enter'||event.key===' '){event.preventDefault();toggle();}
    });
    sync(card);
  });

  function revealHash(){
    if(!mobile.matches||!location.hash)return;
    var id=location.hash.slice(1);
    var card=document.getElementById(id);
    if(!card||!card.classList.contains('mobile-collapsible'))return;
    setOpen(card,true,true);
    window.setTimeout(function(){card.scrollIntoView({behavior:'smooth',block:'start'});},40);
  }

  window.addEventListener('hashchange',revealHash);
  if(mobile.addEventListener){mobile.addEventListener('change',function(){cards.forEach(sync);revealHash();});}
  else if(mobile.addListener){mobile.addListener(function(){cards.forEach(sync);revealHash();});}
  revealHash();
})();
</script>
"""


LEGACY_PORTAL_LINKS = (
    '<a class="tool-link external" href="/parent-hub.html" target="_blank"><span class="tool-icon">↗</span><span>Open Parent Hub</span></a>',
    '<a class="tool-link external" href="/portal.html" target="_blank"><span class="tool-icon">↗</span><span>Open Dancer Portal</span></a>',
)


def register_command_center_mobile_polish(app) -> None:
    """Keep the Command Center compact on phones and hide retired portal shortcuts."""

    @app.after_request
    def polish_command_center_mobile(response):
        if request.path != "/admin" or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            if 'id="command-center-v3"' not in body:
                return response

            changed = False
            for legacy_link in LEGACY_PORTAL_LINKS:
                if legacy_link in body:
                    body = body.replace(legacy_link, "")
                    changed = True

            if 'id="ss-command-center-mobile-polish"' not in body and "</body>" in body:
                body = body.replace("</body>", MOBILE_POLISH + "</body>", 1)
                changed = True

            if changed:
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not add mobile Command Center polish")
        return response
