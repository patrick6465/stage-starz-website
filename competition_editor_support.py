from __future__ import annotations

import re

from flask import request

import class_content_editor as class_editor


COMPETITION_PAGES = {
    "mini_competition": {
        "label": "Mini Competition Team",
        "filename": "mini-competition-team.html",
        "audience": "Ages 5–7",
        "built_in_hero_image": "/assets/images/full-team-picture.jpg",
    },
    "petite_competition": {
        "label": "Petite Competition Team",
        "filename": "petite-competition-team.html",
        "audience": "Ages 6–8",
        "built_in_hero_image": "/assets/images/full-team-picture.jpg",
    },
    "juniorettes_competition": {
        "label": "Juniorettes Competition Team",
        "filename": "juniorettes-competition-team.html",
        "audience": "Ages 7–10",
        "built_in_hero_image": "/assets/images/full-team-picture.jpg",
    },
    "junior_competition": {
        "label": "Junior Competition Team",
        "filename": "junior-competition-team.html",
        "audience": "Competition team",
        "built_in_hero_image": "/assets/images/full-team-picture.jpg",
    },
}


def _ensure_details_wrapper(source: str) -> str:
    """Give compact competition pages the same editable details block as class pages."""
    if re.search(r'<div\s+class="copied-content">', source, flags=re.IGNORECASE):
        return source

    pattern = re.compile(
        r'(?P<start><div\s+class="info-card"[^>]*>.*?<h2[^>]*>.*?</h2>)'
        r'(?P<details>.*?)'
        r'(?P<end></div>\s*</section>)',
        flags=re.IGNORECASE | re.DOTALL,
    )

    def wrap(match: re.Match) -> str:
        details = match.group("details")
        if not details.strip():
            return match.group(0)
        return (
            match.group("start")
            + '<div class="copied-content">'
            + details
            + "</div>"
            + match.group("end")
        )

    return pattern.sub(wrap, source, count=1)


def install_competition_editor_support(app) -> None:
    """Put every competition team in the yearly text/photo editor."""
    class_editor.CLASS_PAGES.update(COMPETITION_PAGES)

    original_read = class_editor._read_source
    original_apply = class_editor._apply_saved_content

    def read_source(filename: str) -> str:
        return _ensure_details_wrapper(original_read(filename))

    def apply_saved_content(source: str, saved: dict[str, str]) -> str:
        return original_apply(_ensure_details_wrapper(source), saved)

    # _extract_original_content calls _read_source at runtime, so replacing the
    # module helper makes the editor see the competition details as editable text.
    class_editor._read_source = read_source
    class_editor._apply_saved_content = apply_saved_content

    @app.after_request
    def show_competition_builtin_photos_in_editor(response):
        if request.path != "/admin/website/classes" or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            if 'id="ss-competition-editor-photo-defaults"' in body:
                return response

            defaults = {
                key: page["built_in_hero_image"]
                for key, page in COMPETITION_PAGES.items()
            }
            pairs = ",".join(
                f'"{key}":"{url}"' for key, url in defaults.items()
            )
            script = f"""
<script id="ss-competition-editor-photo-defaults">
(function(){{
  var defaults={{{pairs}}};
  function setup(){{
    Object.keys(defaults).forEach(function(key){{
      var hidden=document.getElementById('hero-image-'+key);
      var img=document.getElementById('image-preview-'+key);
      var wrap=document.getElementById('image-wrap-'+key);
      if(!hidden||!img||hidden.value) return;
      img.src=defaults[key];
      img.hidden=false;
      if(wrap){{
        var note=wrap.querySelector('.built-in-note');
        if(note) note.remove();
      }}
    }});
  }}
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',setup);
  else setup();
}})();
</script>
"""
            body = body.replace("</body>", script + "</body>", 1)
            response.set_data(body)
        except Exception:
            app.logger.exception("Could not add competition photo defaults to editor")
        return response
