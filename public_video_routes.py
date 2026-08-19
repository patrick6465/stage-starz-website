from __future__ import annotations

import website_video_manager as video_manager


def _decorate_public_html(app, response, page: str):
    """Inject the managed website video before Flask sends the HTML response."""
    response = app.make_response(response)
    if response.status_code != 200 or response.mimetype != "text/html":
        return response

    try:
        # send_from_directory/send_file responses use direct_passthrough=True.
        # Turn that off for these small HTML documents so their markup can be
        # decorated safely before the response is sent to the browser.
        response.direct_passthrough = False
        body = response.get_data(as_text=True)
        if not body:
            return response

        values = video_manager._settings()
        changed = False

        if page == "home":
            # Resolve through the module at request time. persistent_videos patches
            # this helper so database-backed videos stay valid after a Railway
            # restart even before the large file has been materialized to disk.
            video_url = video_manager._valid_video_url(
                values.get("home_performance", "")
            )
            if video_url:
                updated = video_manager._inject_homepage_video(body, video_url)
                if updated != body:
                    body = updated
                    changed = True

        elif page == "competition":
            # The Competition spotlight is part of the page even before a video
            # is assigned. Passing an empty URL intentionally renders the
            # Musical Theater placeholder.
            video_url = video_manager._valid_video_url(
                values.get("competition_musical_theater", "")
            )
            updated = video_manager._inject_competition_video(body, video_url)
            if updated != body:
                body = updated
                changed = True

        if (
            page in {"home", "competition"}
            and 'id="ss-public-video-style"' not in body
            and "</head>" in body
        ):
            body = body.replace(
                "</head>",
                video_manager.PUBLIC_VIDEO_STYLE + "</head>",
                1,
            )
            changed = True

        if changed:
            response.set_data(body)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers.pop("ETag", None)
            response.headers.pop("Last-Modified", None)

    except Exception:
        app.logger.exception("Could not decorate public page with website video")

    return response


def register_public_video_routes(app) -> None:
    """Wrap the existing public page endpoints with deterministic video rendering."""
    home_endpoint = "website_home"
    file_endpoint = "website_file"

    original_home = app.view_functions.get(home_endpoint)
    if original_home and not getattr(original_home, "_ss_video_wrapped", False):
        def website_home_with_video(*args, **kwargs):
            return _decorate_public_html(
                app,
                original_home(*args, **kwargs),
                "home",
            )

        website_home_with_video._ss_video_wrapped = True
        website_home_with_video.__name__ = getattr(original_home, "__name__", home_endpoint)
        app.view_functions[home_endpoint] = website_home_with_video

    original_file = app.view_functions.get(file_endpoint)
    if original_file and not getattr(original_file, "_ss_video_wrapped", False):
        def website_file_with_video(filename: str, *args, **kwargs):
            response = original_file(filename, *args, **kwargs)
            clean = (filename or "").strip("/").lower()
            if clean in {"competition.html", "competition"}:
                return _decorate_public_html(app, response, "competition")
            return response

        website_file_with_video._ss_video_wrapped = True
        website_file_with_video.__name__ = getattr(original_file, "__name__", file_endpoint)
        app.view_functions[file_endpoint] = website_file_with_video
