from __future__ import annotations

import html
import os
import uuid
from pathlib import Path

from flask import (
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.utils import secure_filename

from config import BASE_DIR, VOLUME_MOUNT_PATH
from database import get_db


VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "m4v"}
MAX_VIDEO_BYTES = 250 * 1024 * 1024
MAX_REQUEST_BYTES = 260 * 1024 * 1024

VIDEO_FOLDER = Path(
    os.environ.get(
        "VIDEO_FOLDER",
        str(
            (Path(VOLUME_MOUNT_PATH) / "videos")
            if VOLUME_MOUNT_PATH
            else (BASE_DIR / "data" / "videos")
        ),
    )
)
VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)

VIDEO_SLOTS = {
    "home_performance": {
        "label": "Homepage Performance Video",
        "description": (
            "Plays inside the existing Competition • Recital • Community Performances "
            "container on the homepage."
        ),
        "page_url": "/",
    },
    "competition_musical_theater": {
        "label": "Competition Musical Theater Video",
        "description": (
            "Plays in the Musical Theater Production spotlight near the top of the "
            "Competition page."
        ),
        "page_url": "/competition.html",
    },
}

PUBLIC_VIDEO_STYLE = r"""
<style id="ss-public-video-style">
.ss-video-stage{
  position:relative;
  overflow:hidden;
  background:#05050c;
  border-radius:inherit;
}
.ss-video-stage video{
  display:block;
  width:100%;
  height:100%;
  object-fit:cover;
  background:#05050c;
}
.ss-video-fullscreen{
  position:absolute;
  top:14px;
  right:14px;
  z-index:5;
  border:1px solid rgba(255,255,255,.42);
  border-radius:999px;
  padding:9px 13px;
  background:rgba(5,5,12,.72);
  color:#fff;
  font:inherit;
  font-size:.78rem;
  font-weight:900;
  cursor:pointer;
  backdrop-filter:blur(12px);
  box-shadow:0 8px 22px rgba(0,0,0,.28);
}
.ss-video-fullscreen:hover{background:rgba(5,5,12,.92)}
.ss-video-caption{
  position:absolute;
  left:18px;
  bottom:54px;
  z-index:4;
  max-width:calc(100% - 36px);
  padding:9px 12px;
  border-radius:999px;
  background:rgba(5,5,12,.68);
  color:#fff;
  font-size:.78rem;
  font-weight:900;
  backdrop-filter:blur(10px);
  pointer-events:none;
}
.ss-home-performance-video.performance-art{
  background:#05050c!important;
  padding:0!important;
}
.ss-home-performance-video.performance-art:before,
.ss-home-performance-video.performance-art:after{display:none!important;content:none!important}
.ss-home-performance-video video{min-height:500px}

.ss-musical-theater-spotlight{padding-top:58px!important;padding-bottom:58px!important}
.ss-musical-theater-card{
  display:grid;
  grid-template-columns:minmax(0,.88fr) minmax(420px,1.12fr);
  gap:34px;
  align-items:center;
  padding:34px;
  border:1px solid rgba(255,255,255,.14);
  border-radius:32px;
  background:
    radial-gradient(circle at 8% 10%,rgba(181,59,212,.24),transparent 23rem),
    radial-gradient(circle at 96% 88%,rgba(32,200,199,.14),transparent 25rem),
    linear-gradient(145deg,rgba(23,16,42,.96),rgba(8,7,15,.96));
  box-shadow:0 28px 80px rgba(0,0,0,.40);
}
.ss-musical-theater-copy .kicker{margin-bottom:10px}
.ss-musical-theater-copy h2{
  margin:0 0 14px;
  font-size:clamp(2.35rem,4.8vw,4.5rem);
}
.ss-musical-theater-copy p{color:#c8bed4;margin:0 0 18px}
.ss-musical-theater-tags{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 0}
.ss-musical-theater-tags span{
  padding:7px 11px;
  border:1px solid rgba(255,255,255,.14);
  border-radius:999px;
  background:rgba(255,255,255,.055);
  color:#ebe4f1;
  font-size:.78rem;
  font-weight:850;
}
.ss-musical-theater-video{
  aspect-ratio:16/9;
  border:1px solid rgba(255,255,255,.15);
  border-radius:24px;
  padding:8px;
  background:linear-gradient(145deg,rgba(181,59,212,.22),rgba(32,200,199,.10));
  box-shadow:0 22px 60px rgba(0,0,0,.38);
}
.ss-musical-theater-video .ss-video-stage{width:100%;height:100%;border-radius:17px}
.ss-video-placeholder{
  min-height:100%;
  display:grid;
  place-items:center;
  padding:36px;
  text-align:center;
  color:#e8dff0;
  background:
    radial-gradient(circle at 35% 30%,rgba(255,255,255,.13),transparent 12rem),
    linear-gradient(145deg,#35145a,#142a43);
  font-weight:900;
}
.ss-video-placeholder span{display:block;color:#bfb2ca;font-size:.85rem;font-weight:700;margin-top:7px}
@media(max-width:920px){
  .ss-musical-theater-card{grid-template-columns:1fr;padding:26px}
  .ss-home-performance-video video{min-height:380px}
}
@media(max-width:640px){
  .ss-musical-theater-spotlight{padding-top:34px!important;padding-bottom:34px!important}
  .ss-musical-theater-card{padding:20px;border-radius:25px}
  .ss-musical-theater-video{border-radius:20px;padding:6px}
  .ss-video-caption{bottom:50px;left:10px;font-size:.68rem}
  .ss-video-fullscreen{top:9px;right:9px;padding:8px 10px}
}
</style>
<script id="ss-public-video-script">
function ssExpandVideo(button){
  var stage=button.closest('.ss-video-stage');
  var video=stage&&stage.querySelector('video');
  if(!video)return;
  if(video.requestFullscreen){video.requestFullscreen();}
  else if(video.webkitEnterFullscreen){video.webkitEnterFullscreen();}
  else if(video.webkitRequestFullscreen){video.webkitRequestFullscreen();}
}
</script>
"""


def ensure_video_schema() -> None:
    connection = get_db()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS website_video_settings (
            slot TEXT PRIMARY KEY,
            video_url TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()


def _settings() -> dict[str, str]:
    ensure_video_schema()
    connection = get_db()
    rows = connection.execute(
        "SELECT slot, video_url FROM website_video_settings"
    ).fetchall()
    connection.close()
    values = {key: "" for key in VIDEO_SLOTS}
    for row in rows:
        try:
            slot, url = row["slot"], row["video_url"]
        except (TypeError, KeyError, IndexError):
            slot, url = row[0], row[1]
        if slot in values:
            values[slot] = url or ""
    return values


def _set_slot(slot: str, video_url: str) -> None:
    ensure_video_schema()
    connection = get_db()
    connection.execute(
        """
        INSERT INTO website_video_settings (slot, video_url, updated_at)
        VALUES (?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(slot) DO UPDATE SET
            video_url=excluded.video_url,
            updated_at=CURRENT_TIMESTAMP
        """,
        (slot, video_url),
    )
    connection.commit()
    connection.close()


def _video_path_from_url(video_url: str) -> Path | None:
    prefix = "/media/videos/"
    if not video_url.startswith(prefix):
        return None
    filename = Path(video_url[len(prefix):]).name
    if not filename:
        return None
    return VIDEO_FOLDER / filename


def _valid_video_url(video_url: str) -> str:
    path = _video_path_from_url(video_url)
    if path is None or not path.exists() or not path.is_file():
        return ""
    return f"/media/videos/{path.name}"


def _list_videos() -> list[dict[str, str]]:
    videos: list[dict[str, str]] = []
    if not VIDEO_FOLDER.exists():
        return videos
    for path in VIDEO_FOLDER.iterdir():
        if not path.is_file() or path.suffix.lower().lstrip(".") not in VIDEO_EXTENSIONS:
            continue
        size = path.stat().st_size
        videos.append(
            {
                "name": path.name,
                "url": f"/media/videos/{path.name}",
                "size_mb": f"{size / (1024 * 1024):.1f}",
            }
        )
    return sorted(videos, key=lambda item: item["name"].lower())


def _save_video(file_storage) -> str:
    if not file_storage or not file_storage.filename:
        return ""
    original = secure_filename(file_storage.filename) or "stage-starz-video.mp4"
    if "." not in original:
        raise ValueError("Choose an MP4, WEBM, MOV, or M4V video.")
    extension = original.rsplit(".", 1)[1].lower()
    if extension not in VIDEO_EXTENSIONS:
        raise ValueError("Choose an MP4, WEBM, MOV, or M4V video. MP4 is recommended.")

    VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)
    stem = Path(original).stem[:70] or "stage-starz-video"
    filename = f"{stem}-{uuid.uuid4().hex[:10]}.{extension}"
    target = VIDEO_FOLDER / filename

    try:
        file_storage.save(target)
    except Exception as exc:
        if target.exists():
            target.unlink()
        raise ValueError("The video could not be saved. Please choose it again.") from exc

    size = target.stat().st_size if target.exists() else 0
    if size <= 0:
        if target.exists():
            target.unlink()
        raise ValueError("That video file is empty. Please choose another video.")
    if size > MAX_VIDEO_BYTES:
        target.unlink()
        raise ValueError("That video is larger than 250 MB. Please use a smaller file.")

    return f"/media/videos/{filename}"


def _video_markup(video_url: str, caption: str, extra_class: str = "") -> str:
    safe_url = html.escape(video_url, quote=True)
    safe_caption = html.escape(caption)
    return (
        f'<div class="ss-video-stage {extra_class}">'
        f'<video controls playsinline preload="metadata" src="{safe_url}">'
        "Your browser does not support HTML5 video."
        "</video>"
        '<button class="ss-video-fullscreen" type="button" '
        'onclick="ssExpandVideo(this)" aria-label="Expand video to full screen">⛶ Full screen</button>'
        f'<div class="ss-video-caption">{safe_caption}</div>'
        "</div>"
    )


def _inject_homepage_video(body: str, video_url: str) -> str:
    if "ss-home-performance-video" in body:
        return body
    marker = '<div class="performance-art" aria-label="Abstract dance performance artwork"></div>'
    if marker not in body:
        return body
    video = _video_markup(
        video_url,
        "Competition • Recital • Community Performances",
    )
    replacement = (
        '<div class="performance-art ss-home-performance-video" '
        'aria-label="Stage Starz performance video">'
        + video
        + "</div>"
    )
    return body.replace(marker, replacement, 1)


def _musical_theater_section(video_url: str) -> str:
    if video_url:
        media = _video_markup(video_url, "Stage Starz Musical Theater Competition Production")
    else:
        media = (
            '<div class="ss-video-stage"><div class="ss-video-placeholder">'
            '<div>Musical Theater Production Video<span>Performance spotlight coming soon.</span></div>'
            "</div></div>"
        )
    return f"""
<section class="section ss-musical-theater-spotlight" aria-labelledby="musical-theater-title">
  <div class="ss-musical-theater-card">
    <div class="ss-musical-theater-copy">
      <p class="kicker">A Stage Starz favorite</p>
      <h2 id="musical-theater-title">Musical Theater Competition Production</h2>
      <p>One of our most popular competition experiences brings dancers of multiple ages together in one large-scale production. Musical theater combines dance, character, storytelling, performance quality, and the energy of a full cast on the competition stage.</p>
      <p>The mixed-age format gives dancers the chance to perform as part of something bigger than a traditional group routine while building stage presence, teamwork, and theatrical confidence.</p>
      <div class="ss-musical-theater-tags"><span>Mixed-age cast</span><span>Large production</span><span>Storytelling &amp; character</span><span>Competition performance</span></div>
      <div class="hero-actions" style="justify-content:flex-start;margin-top:26px"><a class="btn primary" href="competition-auditions.html">Audition Information</a><a class="btn ghost" href="contact.html">Ask About Musical Theater</a></div>
    </div>
    <div class="ss-musical-theater-video">{media}</div>
  </div>
</section>
"""


def _inject_competition_video(body: str, video_url: str) -> str:
    if "ss-musical-theater-spotlight" in body:
        return body
    hero_start = body.find('<section class="competition-hero">')
    if hero_start < 0:
        return body
    hero_end = body.find("</section>", hero_start)
    if hero_end < 0:
        return body
    hero_end += len("</section>")
    return body[:hero_end] + _musical_theater_section(video_url) + body[hero_end:]


def register_website_video_manager(app, permission_required, log_activity=None) -> None:
    """Add persistent large-video uploads and two editable public video placements."""
    ensure_video_schema()
    VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)

    # Images still enforce their own 25 MB source limit. The larger request cap is
    # needed only so the dedicated video uploader can receive production videos.
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

    @app.errorhandler(413)
    def website_media_too_large(_error):
        flash(
            "That upload is too large. Website videos can be up to 250 MB; photos can be up to 25 MB.",
            "error",
        )
        return redirect(request.referrer or "/admin")

    @app.route("/media/videos/<path:filename>")
    def website_video_file(filename: str):
        clean = Path(filename).name
        if clean != filename or clean.rsplit(".", 1)[-1].lower() not in VIDEO_EXTENSIONS:
            abort(404)
        target = VIDEO_FOLDER / clean
        if not target.exists() or not target.is_file():
            abort(404)
        response = send_from_directory(
            VIDEO_FOLDER,
            clean,
            conditional=True,
            as_attachment=False,
        )
        response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["Accept-Ranges"] = "bytes"
        return response

    @app.route("/admin/website/videos")
    @permission_required("website")
    def website_video_editor():
        values = _settings()
        slots = []
        for key, info in VIDEO_SLOTS.items():
            current = _valid_video_url(values.get(key, ""))
            slots.append(
                {
                    "key": key,
                    "label": info["label"],
                    "description": info["description"],
                    "page_url": info["page_url"],
                    "video_url": current,
                }
            )
        return render_template(
            "website_video_editor.html",
            slots=slots,
            video_files=_list_videos(),
            max_video_mb=250,
        )

    @app.route("/admin/website/videos/save", methods=["POST"])
    @permission_required("website")
    def save_website_video():
        slot = request.form.get("slot", "").strip()
        if slot not in VIDEO_SLOTS:
            flash("That video location could not be found.", "error")
            return redirect("/admin/website/videos")

        action = request.form.get("action", "save").strip()
        if action == "clear":
            _set_slot(slot, "")
            flash(f"{VIDEO_SLOTS[slot]['label']} was removed from the page.", "success")
            if log_activity:
                try:
                    log_activity("Website video cleared", VIDEO_SLOTS[slot]["label"])
                except Exception:
                    app.logger.exception("Could not log website video clear")
            return redirect(f"/admin/website/videos#slot-{slot}")

        selected = request.form.get("video_url", "").strip()
        uploaded = request.files.get("video_upload")
        if uploaded and uploaded.filename:
            try:
                selected = _save_video(uploaded)
            except ValueError as error:
                flash(str(error), "error")
                return redirect(f"/admin/website/videos#slot-{slot}")

        selected = _valid_video_url(selected)
        if not selected:
            flash("Choose or upload a video before publishing.", "error")
            return redirect(f"/admin/website/videos#slot-{slot}")

        _set_slot(slot, selected)
        flash(f"{VIDEO_SLOTS[slot]['label']} is now published.", "success")
        if log_activity:
            try:
                log_activity("Website video published", VIDEO_SLOTS[slot]["label"])
            except Exception:
                app.logger.exception("Could not log website video update")
        return redirect(f"/admin/website/videos#slot-{slot}")

    @app.route("/admin/website/videos/delete", methods=["POST"])
    @permission_required("website")
    def delete_website_video():
        video_url = request.form.get("video_url", "").strip()
        path = _video_path_from_url(video_url)
        if path is None or not path.exists() or not path.is_file():
            flash("That video could not be found.", "error")
            return redirect("/admin/website/videos")

        values = _settings()
        for slot, current in values.items():
            if _valid_video_url(current) == f"/media/videos/{path.name}":
                _set_slot(slot, "")
        path.unlink()
        flash("Video deleted from the Video Library.", "success")
        if log_activity:
            try:
                log_activity("Website video deleted", path.name)
            except Exception:
                app.logger.exception("Could not log website video deletion")
        return redirect("/admin/website/videos")

    @app.after_request
    def render_website_videos(response):
        if response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            if not body:
                return response

            values = _settings()
            changed = False

            if request.path == "/":
                home_video = _valid_video_url(values.get("home_performance", ""))
                if home_video:
                    updated = _inject_homepage_video(body, home_video)
                    changed = updated != body
                    body = updated

            elif request.path == "/competition.html":
                competition_video = _valid_video_url(
                    values.get("competition_musical_theater", "")
                )
                updated = _inject_competition_video(body, competition_video)
                changed = updated != body
                body = updated

            elif request.path == "/admin":
                desktop_link = '<a href="/admin/website/videos">🎬 Website Videos</a>'
                class_link = '<a href="/admin/website/classes">✏️ Class Page Editor</a>'
                homepage_link = '<a href="/admin/website/homepage">🏠 Homepage Editor</a>'
                if desktop_link not in body:
                    if class_link in body:
                        body = body.replace(class_link, class_link + desktop_link, 1)
                        changed = True
                    elif homepage_link in body:
                        body = body.replace(homepage_link, homepage_link + desktop_link, 1)
                        changed = True

            if request.path in {"/", "/competition.html"} and 'id="ss-public-video-style"' not in body:
                body = body.replace("</head>", PUBLIC_VIDEO_STYLE + "</head>", 1)
                changed = True

            if changed:
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not render website video content")
        return response
