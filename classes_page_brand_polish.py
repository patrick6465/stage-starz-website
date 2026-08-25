from __future__ import annotations

from flask import request


CLASSES_BRAND_STYLE = r"""
<style id="ss-classes-brand-polish">
/* Stage Starz branded visual pass for the public Classes landing page only. */
body{
  background:
    radial-gradient(circle at 8% 18%,rgba(236,63,169,.18),transparent 28rem),
    radial-gradient(circle at 94% 34%,rgba(36,200,216,.14),transparent 30rem),
    radial-gradient(circle at 50% 78%,rgba(126,50,255,.14),transparent 34rem),
    linear-gradient(180deg,#0b0715 0%,#120a20 48%,#090711 100%)!important;
  color:#f8f4ff!important;
}
.header{
  background:rgba(10,7,18,.94)!important;
  border-bottom:1px solid rgba(123,216,209,.20)!important;
  box-shadow:0 12px 34px rgba(0,0,0,.26);
}
.logo,.nav-links{color:#fff!important}
.nav-links>a:not(.btn):hover{color:#65e2de!important}
.menu{color:#fff!important}

.trust{
  background:linear-gradient(120deg,rgba(27,15,43,.98),rgba(11,25,36,.98))!important;
  border-top:1px solid rgba(236,63,169,.16)!important;
  border-bottom:1px solid rgba(36,200,216,.18)!important;
  box-shadow:0 18px 42px rgba(0,0,0,.16);
}
.trust-item{color:#fff!important}
.trust-icon{
  color:#fff!important;
  background:linear-gradient(135deg,#8b3cff,#ec3fa9 58%,#24c8d8)!important;
  box-shadow:0 10px 24px rgba(126,50,255,.25);
}

main>.section{position:relative}
.section-head h2,.section-head h3{color:#fff!important}
.section-head p,.lead{color:#c9c1d4!important}
.section-head .eyebrow,.eyebrow{color:#62e3de!important}

#programs{
  padding-top:88px!important;
  padding-bottom:82px!important;
}
#programs:before{
  content:"";
  position:absolute;
  inset:30px 10px 24px;
  z-index:-1;
  border-radius:44px;
  background:
    radial-gradient(circle at 8% 12%,rgba(236,63,169,.11),transparent 23rem),
    radial-gradient(circle at 92% 88%,rgba(36,200,216,.10),transparent 24rem),
    rgba(255,255,255,.018);
  border:1px solid rgba(255,255,255,.05);
}
.program-grid{gap:22px!important}
.program-card{
  isolation:isolate;
  color:#fff!important;
  background:
    radial-gradient(circle at 88% 7%,rgba(36,200,216,.13),transparent 14rem),
    radial-gradient(circle at 7% 100%,rgba(236,63,169,.16),transparent 16rem),
    linear-gradient(145deg,rgba(29,17,48,.98),rgba(13,10,25,.98))!important;
  border:1px solid rgba(152,112,255,.28)!important;
  box-shadow:0 24px 55px rgba(0,0,0,.34),inset 0 1px 0 rgba(255,255,255,.04)!important;
}
.program-card:hover{
  transform:translateY(-6px)!important;
  border-color:rgba(80,214,208,.58)!important;
  box-shadow:0 30px 70px rgba(0,0,0,.42),0 0 28px rgba(126,50,255,.15)!important;
}
.program-card:after{
  height:6px!important;
  background:linear-gradient(90deg,#8b3cff,#f33fa8 52%,#24c8d8)!important;
}
.program-card h3{color:#fff!important}
.program-card p{color:#c8bfd2!important}
.program-card .age{color:#65e2de!important}
.styles span{
  color:#f7f1ff!important;
  background:rgba(255,255,255,.065)!important;
  border-color:rgba(255,255,255,.12)!important;
}
.card-link{color:#ff82c4!important}

.photo-card{
  border:1px solid rgba(255,255,255,.10)!important;
  box-shadow:0 25px 65px rgba(0,0,0,.38)!important;
}
.photo-card:after{
  background:linear-gradient(to top,rgba(8,7,18,.96),rgba(8,7,18,.04) 70%)!important;
}
.photo-copy strong{color:#fff}
.photo-copy span{color:#d8cfdf!important}

.finder{
  border:1px solid rgba(80,214,208,.22)!important;
  background:
    radial-gradient(circle at 8% 12%,rgba(236,63,169,.22),transparent 18rem),
    radial-gradient(circle at 92% 88%,rgba(36,200,216,.16),transparent 20rem),
    linear-gradient(135deg,#11091f,#18102b)!important;
  box-shadow:0 28px 70px rgba(0,0,0,.38)!important;
}
.finder p{color:#d1c8da!important}

.steps{gap:20px!important}
.step{
  position:relative;
  overflow:hidden;
  color:#fff!important;
  background:linear-gradient(145deg,rgba(28,17,46,.98),rgba(13,10,24,.98))!important;
  border:1px solid rgba(152,112,255,.24)!important;
  box-shadow:0 20px 48px rgba(0,0,0,.30)!important;
}
.step:after{
  content:"";
  position:absolute;
  width:130px;
  height:130px;
  right:-58px;
  bottom:-72px;
  border-radius:50%;
  background:radial-gradient(circle,rgba(36,200,216,.18),transparent 70%);
}
.step h3{color:#fff!important}
.step p{color:#c8bfd2!important}
.step-number{
  background:linear-gradient(135deg,#8b3cff,#ec3fa9 58%,#24c8d8)!important;
  box-shadow:0 10px 28px rgba(236,63,169,.23);
}

.local-card,.help-card{
  color:#fff!important;
  border:1px solid rgba(255,255,255,.10)!important;
  box-shadow:0 24px 58px rgba(0,0,0,.32)!important;
}
.local-card{
  background:
    radial-gradient(circle at 10% 5%,rgba(236,63,169,.17),transparent 17rem),
    linear-gradient(145deg,#1b102e,#0e0b1b)!important;
}
.help-card{
  background:
    radial-gradient(circle at 92% 8%,rgba(36,200,216,.18),transparent 17rem),
    linear-gradient(145deg,#15102b,#0b1b24)!important;
}
.local-card h2,.help-card h2{color:#fff!important}
.local-card p,.help-card p{color:#c9c1d4!important}
.area-list span{
  color:#fff!important;
  background:rgba(255,255,255,.06)!important;
  border-color:rgba(255,255,255,.12)!important;
}
.help-card .btn.ghost{
  color:#fff!important;
  background:transparent!important;
  border-color:#65e2de!important;
}

.footer{border-top:1px solid rgba(80,214,208,.12)}

@media(max-width:920px){
  .nav-links{
    background:#120b20!important;
    border-color:rgba(152,112,255,.25)!important;
    color:#fff!important;
    box-shadow:0 22px 60px rgba(0,0,0,.42)!important;
  }
}
@media(max-width:640px){
  #programs{padding-top:64px!important;padding-bottom:58px!important}
  #programs:before{inset:18px 7px 16px;border-radius:30px}
  .program-card,.step{border-radius:24px!important}
  .program-card{padding:24px!important;min-height:270px!important}
  .photo-card{border-radius:24px!important}
  .finder{border-radius:28px!important}
  .local-card,.help-card{border-radius:26px!important}
}
</style>
"""


def register_classes_page_brand_polish(app) -> None:
    """Give the public Classes landing page a richer Stage Starz visual treatment."""

    @app.after_request
    def polish_classes_page(response):
        if request.method != "GET" or response.status_code != 200:
            return response
        if response.mimetype != "text/html":
            return response
        path = request.path.rstrip("/") or "/"
        if path != "/classes.html":
            return response
        try:
            response.direct_passthrough = False
            body = response.get_data(as_text=True)
            if not body or 'id="ss-classes-brand-polish"' in body:
                return response
            if "</head>" not in body:
                return response
            body = body.replace("</head>", CLASSES_BRAND_STYLE + "</head>", 1)
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
            response.headers.pop("Last-Modified", None)
        except Exception:
            app.logger.exception("Could not apply Classes page brand polish")
        return response
