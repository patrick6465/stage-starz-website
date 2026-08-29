"""SEO and legacy-URL launch layer for the Stage Starz Railway site.

This module intentionally wraps the existing launch_app without changing any
approved public design. Railway starts this module instead of launch_app so the
existing application receives migration redirects, crawl controls, canonical
metadata, social metadata, a sitemap, and local-business structured data.
"""

from __future__ import annotations

import json
import re
from flask import Response, redirect, request

from config import BASE_DIR
from email_access_polish import register_email_access_polish
from website_traffic_analytics import register_website_traffic
from zoho_email_center import register_zoho_email_center
from routes_email import register_email_routes
from launch_app import app
from app import permission_required

register_email_routes(app)
register_zoho_email_center(app, permission_required)
register_email_access_polish(app)
register_website_traffic(app, permission_required)

CANONICAL_ORIGIN = "https://www.stagestarzdance.com"
SITE_NAME = "Stage Starz Academy of Dance"
DEFAULT_SOCIAL_IMAGE = f"{CANONICAL_ORIGIN}/assets/images/audriana-homepage-hero.jpg"


GOOGLE_ADS_TAG = r"""
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=AW-18417496467"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'AW-18417496467');
</script>
"""


def _inject_google_ads_tag(html_text: str) -> str:
    """Install the Stage Starz Google Ads base tag on public HTML responses."""
    if "AW-18417496467" in html_text:
        return html_text
    if not re.search(r"<head(?:\s[^>]*)?>", html_text, flags=re.I):
        return html_text
    return re.sub(
        r"(<head(?:\s[^>]*)?>)",
        r"\1\n" + GOOGLE_ADS_TAG,
        html_text,
        count=1,
        flags=re.I,
    )


STAGE_STARZ_MEDIA_PROTECTION = r"""
<style id="stage-starz-media-protection-style">
img,video{
  -webkit-user-drag:none;
  -webkit-user-select:none;
  user-select:none;
  -webkit-touch-callout:none;
}
</style>
<script id="stage-starz-media-protection-script">
(function(){
  'use strict';

  function protectMedia(root){
    var scope=root&&root.querySelectorAll?root:document;
    scope.querySelectorAll('img').forEach(function(img){
      img.setAttribute('draggable','false');
    });
    scope.querySelectorAll('video').forEach(function(video){
      video.setAttribute('controlsList','nodownload noremoteplayback');
      video.setAttribute('disablePictureInPicture','');
      video.setAttribute('disableRemotePlayback','');
      video.disablePictureInPicture=true;
      video.disableRemotePlayback=true;
      video.setAttribute('draggable','false');
      try{
        if(video.controlsList){
          video.controlsList.add('nodownload');
          video.controlsList.add('noremoteplayback');
        }
      }catch(_error){}
    });
  }

  document.addEventListener('contextmenu',function(event){
    var target=event.target;
    if(target&&target.closest&&target.closest('img,video')){
      event.preventDefault();
    }
  },true);

  document.addEventListener('dragstart',function(event){
    var target=event.target;
    if(target&&target.closest&&target.closest('img,video')){
      event.preventDefault();
    }
  },true);

  function start(){
    protectMedia(document);
    if('MutationObserver' in window){
      new MutationObserver(function(records){
        records.forEach(function(record){
          record.addedNodes.forEach(function(node){
            if(node&&node.nodeType===1){
              if(node.matches&&node.matches('img,video')){
                protectMedia(node.parentNode||document);
              }else{
                protectMedia(node);
              }
            }
          });
        });
      }).observe(document.documentElement,{childList:true,subtree:true});
    }
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',start,{once:true});
  }else{
    start();
  }
})();
</script>
"""


def _protect_public_media(html_text: str) -> str:
    """Deter casual downloading/saving of public images and videos.

    Browser-delivered media can never be made impossible to copy, but this removes
    native video download/PiP controls and blocks normal image/video context menus
    and drag-saving without changing the public page design.
    """
    if "stage-starz-media-protection-script" in html_text:
        return html_text
    if not re.search(r"</head\\s*>", html_text, flags=re.I):
        return html_text
    return re.sub(
        r"</head\\s*>",
        STAGE_STARZ_MEDIA_PROTECTION + "</head>",
        html_text,
        count=1,
        flags=re.I,
    )

# Wix URLs and other historical aliases that may still exist in Google, ads,
# bookmarks, social posts, or customer emails. Query strings are preserved.
LEGACY_REDIRECTS = {
    "/home": "/",
    "/index.html": "/",
    "/index-new.html": "/",
    "/about-us": "/about.html",
    "/whychooseus": "/about.html",
    "/teachersandstaff": "/about.html",
    "/contact-us": "/contact.html",
    "/classes": "/classes.html",
    "/preschool": "/preschool-class-registration.html",
    "/preschool-class-registration": "/preschool-class-registration.html",
    "/primary": "/primary-class-registration.html",
    "/primary-class-registration": "/primary-class-registration.html",
    "/elementary-class-registration": "/elementary-class-registration.html",
    "/int1-2thruadvancedregistration": "/intermediate-advanced-registration.html",
    "/intermediate-advanced-registration": "/intermediate-advanced-registration.html",
    "/specializedclasses": "/specialized-class-registration.html",
    "/specialized-class-registration": "/specialized-class-registration.html",
    "/musicaltheater": "/specialized-class-registration.html",
    "/performanceopportunities": "/events.html",
    "/bringafriend": "/events.html",
    "/intensives": "/classes.html",
    "/recital": "/recital-2027.html",
    "/recital-2026.html": "/recital-2027.html",
    "/auditions": "/competition.html",
    "/competition-auditions.html": "/competition.html",
    "/auditions-1": "/competition.html",
    "/preregister": "/competition.html",
    "/preregister-1": "/competition.html",
    "/competition-team": "/competition.html",
    "/petitecomp": "/petite-competition-team.html",
    "/petitecomp-1": "/petite-competition-team.html",
    "/petitecomp-1-1": "/petite-competition-team.html",
    "/mini-competition-team": "/mini-competition-team.html",
    "/junior-competition-team": "/junior-competition-team.html",
    "/teen": "/teen-competition-team.html",
    "/online-store": "/store",
    "/shop": "/store",
    "/shop-1": "/store",
    "/file-downloads": "/parent-hub.html",
    "/blank": "/",
    "/blank-1": "/",
    "/blank-2": "/",
    "/test": "/",
}

# Only stable, customer-facing pages belong in Google's sitemap. Old audition,
# private portal, admin, and operational pages are intentionally excluded.
SITEMAP_PATHS = (
    "/",
    "/classes.html",
    "/dance-classes-toledo",
    "/class-finder.html",
    "/about.html",
    "/contact.html",
    "/preschool-class-registration.html",
    "/primary-class-registration.html",
    "/elementary-class-registration.html",
    "/intermediate-advanced-registration.html",
    "/specialized-class-registration.html",
    "/competition.html",
    "/petite-competition-team.html",
    "/juniorettes-competition-team.html",
    "/mini-competition-team.html",
    "/junior-competition-team.html",
    "/teen-competition-team.html",
    "/events.html",
    "/recital-2027.html",
    "/store",
)

PRIVATE_PREFIXES = (
    "/admin",
    "/api/",
    "/staff",
    "/customer",
    "/parent",
    "/login",
    "/health",
    "/uploads/",
    "/ticketing",
    "/production",
    "/workflow",
    "/reports",
    "/inventory",
    "/packing",
)
PRIVATE_EXACT = {
    "/portal.html",
    "/parent-hub.html",
    "/team-only.html",
    "/portal",
    "/team-only",
}

LOCAL_BUSINESS_SCHEMA = {
    "@context": "https://schema.org",
    "@type": ["LocalBusiness", "EducationalOrganization"],
    "name": SITE_NAME,
    "url": f"{CANONICAL_ORIGIN}/",
    "logo": f"{CANONICAL_ORIGIN}/assets/images/stage-starz-logo.png",
    "image": DEFAULT_SOCIAL_IMAGE,
    "telephone": "+1-734-497-3740",
    "email": "stagestarzdance@aol.com",
    "address": {
        "@type": "PostalAddress",
        "streetAddress": "6800 Lewis Ave",
        "addressLocality": "Temperance",
        "addressRegion": "MI",
        "postalCode": "48182",
        "addressCountry": "US",
    },
    "areaServed": [
        {"@type": "City", "name": "Temperance"},
        {"@type": "City", "name": "Toledo"},
    ],
}


def _normalized_path(path: str) -> str:
    if path == "/":
        return "/"
    return path.rstrip("/") or "/"


def _is_private(path: str) -> bool:
    normalized = _normalized_path(path).lower()
    if normalized in PRIVATE_EXACT:
        return True
    return any(normalized.startswith(prefix) for prefix in PRIVATE_PREFIXES)


def _with_query(destination: str) -> str:
    if not request.query_string:
        return destination
    return f"{destination}?{request.query_string.decode('utf-8', errors='ignore')}"


@app.before_request
def stage_starz_legacy_url_redirects():
    """301 old Wix and duplicate URLs to their approved Railway destinations."""
    if request.method not in {"GET", "HEAD"}:
        return None
    normalized = _normalized_path(request.path)
    target = LEGACY_REDIRECTS.get(normalized)
    if not target:
        return None
    return redirect(_with_query(f"{CANONICAL_ORIGIN}{target}"), code=301)


@app.route("/dance-classes-toledo", methods=["GET", "HEAD"])
def stage_starz_toledo_landing():
    page_path = BASE_DIR / "dance-classes-toledo.html"
    if not page_path.exists():
        return ("Page not found", 404)
    return app.response_class(page_path.read_text(encoding="utf-8"), mimetype="text/html")


@app.route("/robots.txt", methods=["GET", "HEAD"])
def stage_starz_robots_txt():
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin",
            "Disallow: /api/",
            "Disallow: /staff",
            "Disallow: /customer",
            "Disallow: /parent",
            "Disallow: /portal",
            "Disallow: /team-only",
            "Disallow: /uploads/",
            "Disallow: /health",
            f"Sitemap: {CANONICAL_ORIGIN}/sitemap.xml",
            "",
        ]
    )
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml", methods=["GET", "HEAD"])
def stage_starz_sitemap_xml():
    urls = "\n".join(
        f"  <url><loc>{CANONICAL_ORIGIN}{path}</loc></url>" for path in SITEMAP_PATHS
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    return Response(body, mimetype="application/xml")


def _extract_title(html_text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.I | re.S)
    if not match:
        return SITE_NAME
    return re.sub(r"\s+", " ", match.group(1)).strip() or SITE_NAME


def _extract_description(html_text: str) -> str:
    patterns = (
        r'<meta\s+[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\'][^>]*>',
        r'<meta\s+[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\'][^>]*>',
    )
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.I | re.S)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def _canonical_for(path: str) -> str:
    normalized = _normalized_path(path)
    if normalized in {"/index.html", "/index-new.html"}:
        normalized = "/"
    return f"{CANONICAL_ORIGIN}{normalized}"


def _seo_tags(html_text: str, path: str) -> str:
    canonical = _canonical_for(path)
    title = _extract_title(html_text)
    description = _extract_description(html_text)
    tags: list[str] = []

    if not re.search(r'<link\s+[^>]*rel=["\']canonical["\']', html_text, flags=re.I):
        tags.append(f'<link rel="canonical" href="{canonical}">')
    if not re.search(r'<meta\s+[^>]*property=["\']og:site_name["\']', html_text, flags=re.I):
        tags.append(f'<meta property="og:site_name" content="{SITE_NAME}">')
    if not re.search(r'<meta\s+[^>]*property=["\']og:type["\']', html_text, flags=re.I):
        tags.append('<meta property="og:type" content="website">')
    if not re.search(r'<meta\s+[^>]*property=["\']og:url["\']', html_text, flags=re.I):
        tags.append(f'<meta property="og:url" content="{canonical}">')
    if not re.search(r'<meta\s+[^>]*property=["\']og:title["\']', html_text, flags=re.I):
        safe_title = title.replace("&", "&amp;").replace('"', "&quot;")
        tags.append(f'<meta property="og:title" content="{safe_title}">')
    if description and not re.search(r'<meta\s+[^>]*property=["\']og:description["\']', html_text, flags=re.I):
        safe_description = description.replace("&", "&amp;").replace('"', "&quot;")
        tags.append(f'<meta property="og:description" content="{safe_description}">')
    if not re.search(r'<meta\s+[^>]*property=["\']og:image["\']', html_text, flags=re.I):
        tags.append(f'<meta property="og:image" content="{DEFAULT_SOCIAL_IMAGE}">')
    if not re.search(r'<meta\s+[^>]*name=["\']twitter:card["\']', html_text, flags=re.I):
        tags.append('<meta name="twitter:card" content="summary_large_image">')

    if _normalized_path(path) == "/" and "StageStarzLocalBusinessSchema" not in html_text:
        schema = json.dumps(LOCAL_BUSINESS_SCHEMA, separators=(",", ":"))
        tags.append(
            '<script id="StageStarzLocalBusinessSchema" type="application/ld+json">'
            f"{schema}</script>"
        )

    if not tags or not re.search(r"</head\s*>", html_text, flags=re.I):
        return html_text
    block = "\n  " + "\n  ".join(tags) + "\n"
    return re.sub(r"</head\s*>", f"{block}</head>", html_text, count=1, flags=re.I)


def stage_starz_seo_finalize(response):
    """Apply crawl policy and final SEO markup after all other launch polish."""
    path = request.path

    # Search engines should never index private/operational application screens.
    if _is_private(path):
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    if response.status_code == 404:
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        if request.method in {"GET", "HEAD"} and "text/html" in response.content_type.lower():
            branded_404 = BASE_DIR / "site" / "404.html"
            if branded_404.exists():
                response.set_data(branded_404.read_text(encoding="utf-8"))
                response.content_type = "text/html; charset=utf-8"
        return response

    if request.method != "GET" or response.status_code != 200:
        return response
    if "text/html" not in response.content_type.lower():
        return response

    if response.direct_passthrough:
        response.direct_passthrough = False

    try:
        html_text = response.get_data(as_text=True)
    except (RuntimeError, UnicodeDecodeError):
        return response

    html_text = _inject_google_ads_tag(html_text)
    html_text = _protect_public_media(html_text)
    response.set_data(_seo_tags(html_text, path))
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


# Flask executes after_request handlers in reverse registration order. Put this
# handler at the beginning so it executes LAST, after every existing visual/content
# launch hook has finished its response transformations.
app.after_request(stage_starz_seo_finalize)
_handlers = app.after_request_funcs.setdefault(None, [])
if stage_starz_seo_finalize in _handlers:
    _handlers.remove(stage_starz_seo_finalize)
    _handlers.insert(0, stage_starz_seo_finalize)
