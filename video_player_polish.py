"""Public-video behavior and resilient placement refinements for Stage Starz pages."""

from flask import request

from website_video_manager import (
    PUBLIC_VIDEO_STYLE,
    _inject_competition_video,
    _settings,
    _valid_video_url,
)


PLAYER_POLISH = r"""
<style id="ss-video-player-polish-style">
.ss-video-caption{
  transition:opacity .22s ease,visibility .22s ease;
}
.ss-video-stage.ss-video-playing .ss-video-caption{
  opacity:0!important;
  visibility:hidden!important;
}
</style>
<script id="ss-video-player-polish-script">
(function(){
  function bindStageStarzVideos(){
    document.querySelectorAll('.ss-video-stage video').forEach(function(video){
      if(video.dataset.ssCaptionBound==='1')return;
      video.dataset.ssCaptionBound='1';
      var stage=video.closest('.ss-video-stage');
      if(!stage)return;
      function syncCaption(){
        stage.classList.toggle('ss-video-playing',!video.paused&&!video.ended);
      }
      video.addEventListener('play',syncCaption);
      video.addEventListener('playing',syncCaption);
      video.addEventListener('pause',syncCaption);
      video.addEventListener('ended',syncCaption);
      video.addEventListener('emptied',syncCaption);
      syncCaption();
    });
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',bindStageStarzVideos);
  }else{
    bindStageStarzVideos();
  }
})();
</script>
"""


def register_video_player_polish(app) -> None:
    """Keep public video placement reliable and hide captions during playback."""

    @app.after_request
    def polish_public_video_player(response):
        if response.mimetype != "text/html":
            return response

        try:
            body = response.get_data(as_text=True)
            if not body:
                return response

            changed = False
            is_home = request.path == "/" or "ss-home-performance-video" in body
            is_competition = (
                '<section class="competition-hero">' in body
                or 'class="competition-hero"' in body
                or request.path.rstrip("/").lower() in {"/competition", "/competition.html"}
            )

            # The main video manager historically keyed this placement to the exact
            # /competition.html path. Detect the page from its hero markup as a
            # fallback so rewritten/normalized URLs still receive the spotlight.
            if is_competition and "ss-musical-theater-spotlight" not in body:
                values = _settings()
                competition_video = _valid_video_url(
                    values.get("competition_musical_theater", "")
                )
                updated = _inject_competition_video(body, competition_video)
                if updated != body:
                    body = updated
                    changed = True

            # If this fallback performed the placement on a rewritten URL, the main
            # manager may not add its shared player CSS/JS. Ensure it exists here.
            if (
                (is_home or is_competition)
                and 'id="ss-public-video-style"' not in body
                and "</head>" in body
            ):
                body = body.replace("</head>", PUBLIC_VIDEO_STYLE + "</head>", 1)
                changed = True

            if (
                (is_home or is_competition)
                and 'id="ss-video-player-polish-style"' not in body
                and "</head>" in body
            ):
                body = body.replace("</head>", PLAYER_POLISH + "</head>", 1)
                changed = True

            if changed:
                response.set_data(body)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply public video player polish")
        return response
