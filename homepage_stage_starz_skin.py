from __future__ import annotations

from flask import request


HOMEPAGE_STAGE_STARZ_STYLE = r"""
<style id="ss-homepage-stage-starz-skin">
/* Homepage top-section Stage Starz visual skin. Content, links and editor hooks remain unchanged. */
body{
  background:#080713!important;
}

/* Carry the dark Stage Starz identity through the sticky navigation. */
.header{
  background:rgba(8,7,19,.94)!important;
  border-bottom:1px solid rgba(255,255,255,.11)!important;
  box-shadow:0 12px 34px rgba(0,0,0,.24)!important;
}
.logo,.nav-links>a:not(.btn),.menu{
  color:#fff!important;
}
.nav-links>a:not(.btn):hover{
  color:#67e5df!important;
}
.nav-links .btn.dark{
  background:linear-gradient(110deg,#ef3d98,#9b4dcc,#35cfc5)!important;
  box-shadow:0 10px 24px rgba(155,77,204,.24)!important;
}

/* Blend the hero naturally into the darker homepage rather than into a white page. */
.hero{
  box-shadow:inset 0 -48px 58px -38px rgba(8,7,19,.96)!important;
}

/* On desktop, give the full dancer more vertical room before the shop banner begins. */
@media(min-width:981px){
  .hero{
    min-height:clamp(760px,92vh,940px)!important;
  }
}

/* Studio highlights become a compact dark-glass bridge into the content. */
.trust-strip{
  position:relative!important;
  background:
    radial-gradient(circle at 8% 10%,rgba(239,61,152,.13),transparent 22rem),
    radial-gradient(circle at 92% 20%,rgba(53,207,197,.12),transparent 23rem),
    #0b0815!important;
  border-top:1px solid rgba(255,255,255,.08)!important;
  border-bottom:1px solid rgba(255,255,255,.10)!important;
  color:#fff!important;
}
.trust-inner{
  padding-top:25px!important;
  padding-bottom:25px!important;
}
.trust-item{
  padding:13px 14px!important;
  border:1px solid rgba(255,255,255,.10)!important;
  border-radius:17px!important;
  background:linear-gradient(135deg,rgba(155,77,204,.10),rgba(53,207,197,.055))!important;
  color:#f8f4ff!important;
  box-shadow:0 10px 28px rgba(0,0,0,.16)!important;
}
.trust-icon{
  color:#fff!important;
  background:linear-gradient(135deg,#9b4dcc,#ef3d98 55%,#35cfc5)!important;
  box-shadow:0 7px 18px rgba(155,77,204,.22)!important;
}

/* Programs: replace the large white field with a branded dark editorial section. */
#programs{
  position:relative!important;
  isolation:isolate!important;
  width:100%!important;
  max-width:none!important;
  padding-left:max(22px,calc((100vw - 1180px)/2))!important;
  padding-right:max(22px,calc((100vw - 1180px)/2))!important;
  color:#fff!important;
  background:
    radial-gradient(circle at 9% 12%,rgba(239,61,152,.15),transparent 30rem),
    radial-gradient(circle at 94% 22%,rgba(53,207,197,.13),transparent 31rem),
    linear-gradient(180deg,#0b0815 0%,#110b1f 55%,#080713 100%)!important;
  overflow:hidden!important;
}
#programs:before{
  content:"";
  position:absolute;
  z-index:-1;
  width:460px;
  height:460px;
  right:-230px;
  bottom:-180px;
  border-radius:50%;
  border:1px solid rgba(53,207,197,.10);
  box-shadow:0 0 0 70px rgba(155,77,204,.025),0 0 0 140px rgba(239,61,152,.018);
  pointer-events:none;
}
#programs .section-head,
#programs .program-grid{
  width:100%!important;
  max-width:1180px!important;
  margin-left:auto!important;
  margin-right:auto!important;
}
#programs .eyebrow{
  color:#62ddd7!important;
}
#programs h2{
  color:#fff!important;
  text-shadow:0 0 28px rgba(155,77,204,.12)!important;
}
#programs .lead{
  color:#c9bed6!important;
}
#programs .section-head>.btn.dark{
  color:#fff!important;
  border:1px solid rgba(53,207,197,.42)!important;
  background:rgba(53,207,197,.08)!important;
  box-shadow:0 9px 26px rgba(0,0,0,.20)!important;
}
#programs .section-head>.btn.dark:hover{
  background:linear-gradient(110deg,#8f42c8,#c53c9c,#249fa9)!important;
  border-color:transparent!important;
}
#programs .program{
  border:1px solid rgba(255,255,255,.12)!important;
  box-shadow:0 20px 48px rgba(0,0,0,.30)!important;
  transition:transform .22s ease,box-shadow .22s ease,border-color .22s ease!important;
}
#programs .program:hover{
  transform:translateY(-5px)!important;
  border-color:rgba(103,229,223,.42)!important;
  box-shadow:0 26px 58px rgba(0,0,0,.38),0 0 24px rgba(155,77,204,.08)!important;
}

@media(max-width:980px){
  .nav-links{
    background:rgba(15,10,27,.98)!important;
    border-color:rgba(255,255,255,.12)!important;
    box-shadow:0 18px 46px rgba(0,0,0,.34)!important;
  }
  .nav-links>a:not(.btn){color:#fff!important}
}

@media(max-width:640px){
  .trust-inner{gap:10px!important;padding:16px!important}
  .trust-item{padding:11px 12px!important}

  /* Replace the bright local-proof block with a compact Stage Starz dark panel. */
  .ss-local-proof{
    background:
      radial-gradient(circle at 8% 12%,rgba(239,61,152,.16),transparent 20rem),
      radial-gradient(circle at 94% 85%,rgba(53,207,197,.14),transparent 22rem),
      linear-gradient(160deg,#0b0815 0%,#17102a 58%,#08171b 100%)!important;
    border-top:1px solid rgba(255,255,255,.08)!important;
    border-bottom:1px solid rgba(103,229,223,.12)!important;
  }
  .ss-local-proof-inner{
    gap:12px!important;
    padding:30px 18px 34px!important;
  }
  .ss-local-proof-copy{
    padding:0 8px 6px!important;
  }
  .ss-local-proof-copy strong{
    color:#fff!important;
  }
  .ss-local-proof-copy span{
    color:#c9bed6!important;
  }
  .ss-local-proof-item{
    padding:15px 14px!important;
    border:1px solid rgba(255,255,255,.10)!important;
    border-radius:17px!important;
    background:linear-gradient(135deg,rgba(155,77,204,.11),rgba(53,207,197,.065))!important;
    color:#f8f4ff!important;
    box-shadow:0 10px 28px rgba(0,0,0,.16)!important;
  }
  .ss-local-proof-item small{
    color:#bdb2c9!important;
  }

  /* Keep the mobile quick actions useful without covering so much page content. */
  .ss-mobile-cta{
    left:10px!important;
    right:10px!important;
    bottom:max(7px,env(safe-area-inset-bottom))!important;
    gap:6px!important;
    padding:5px!important;
    border-radius:16px!important;
  }
  .ss-mobile-cta a{
    min-height:0!important;
    height:52px!important;
    padding:0 12px!important;
    border-radius:11px!important;
    font-size:.88rem!important;
    line-height:1.1!important;
  }
  body[data-homepage="true"]{
    padding-bottom:72px!important;
  }
  body[data-homepage="true"] .hero .actions{
    margin-bottom:66px!important;
  }

  /* The quick-action bar stays completely out of the way until the hero has left the viewport. */
  body[data-homepage="true"]:not(.ss-past-hero) .ss-mobile-cta{
    opacity:0!important;
    transform:translateY(22px)!important;
    pointer-events:none!important;
    visibility:hidden!important;
  }
  body[data-homepage="true"].ss-past-hero .ss-mobile-cta{
    opacity:1!important;
    transform:translateY(0)!important;
    pointer-events:auto!important;
    visibility:visible!important;
    transition:opacity .22s ease,transform .22s ease,visibility .22s ease!important;
  }

  #programs{
    padding-left:16px!important;
    padding-right:16px!important;
    padding-top:64px!important;
    padding-bottom:70px!important;
  }
  #programs .section-head{
    margin-bottom:28px!important;
  }
  #programs .section-head>.btn.dark{
    width:100%!important;
  }
}
</style>
"""

HOMEPAGE_MOBILE_CTA_SCRIPT = r"""
<script id="ss-homepage-mobile-cta-visibility">
(function(){
  function init(){
    var body=document.body;
    var hero=document.querySelector('.hero');
    if(!body||!hero){return;}

    function update(){
      if(window.innerWidth>640){
        body.classList.add('ss-past-hero');
        return;
      }
      body.classList.toggle('ss-past-hero',hero.getBoundingClientRect().bottom<=0);
    }

    update();
    window.addEventListener('scroll',update,{passive:true});
    window.addEventListener('resize',update,{passive:true});
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',init,{once:true});
  }else{
    init();
  }
})();
</script>
"""


def register_homepage_stage_starz_skin(app) -> None:
    """Apply the Stage Starz dark visual skin to the top of the public homepage."""

    @app.after_request
    def add_homepage_stage_starz_skin(response):
        if (
            request.method != "GET"
            or request.path not in {"/", "/index.html", "/index-new.html"}
            or response.status_code != 200
            or response.mimetype != "text/html"
        ):
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if body and 'id="ss-homepage-stage-starz-skin"' not in body and "</head>" in body:
                body = body.replace(
                    "</head>",
                    HOMEPAGE_STAGE_STARZ_STYLE + "\n" + HOMEPAGE_MOBILE_CTA_SCRIPT + "\n</head>",
                    1,
                )
                body = body.replace(
                    'src="assets/js/site-refinements.js"',
                    'src="assets/js/site-refinements.js?v=20260825-cta2"',
                    1,
                )
                body = body.replace(
                    'src="/assets/js/site-refinements.js"',
                    'src="/assets/js/site-refinements.js?v=20260825-cta2"',
                    1,
                )
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply Stage Starz homepage skin")
        return response
