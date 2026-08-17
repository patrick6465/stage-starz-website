"""Small public-video behavior refinements for Stage Starz pages."""

from flask import request


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
    """Hide the descriptive video tag while a public website video is playing."""

    @app.after_request
    def polish_public_video_player(response):
        if request.path not in {"/", "/competition.html"}:
            return response
        if response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            if (
                body
                and 'id="ss-video-player-polish-style"' not in body
                and "</head>" in body
            ):
                body = body.replace("</head>", PLAYER_POLISH + "</head>", 1)
                response.set_data(body)
                response.headers.pop("ETag", None)
        except Exception:
            app.logger.exception("Could not apply public video player polish")
        return response
