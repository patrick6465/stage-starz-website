from __future__ import annotations

import re

from flask import request


COMPETITION_HTML_PATHS = {
    "/competition.html",
    "/competition-auditions.html",
    "/mini-competition-team.html",
    "/petite-competition-team.html",
    "/juniorettes-competition-team.html",
    "/junior-competition-team.html",
    "/teen-competition-team.html",
    "/team-only.html",
}

TEAM_LINKS = """<div><h3>Competition</h3>
<a href=\"competition.html\">Team Overview</a>
<a href=\"competition-auditions.html\">Auditions</a>
<a href=\"mini-competition-team.html\">Mini Team</a>
<a href=\"petite-competition-team.html\">Petite Team</a>
<a href=\"juniorettes-competition-team.html\">Juniorettes Team</a>
<a href=\"junior-competition-team.html\">Junior Team</a>
<a href=\"teen-competition-team.html\">Teen Team</a></div>"""

TEEN_LABEL_FIX = """<script id=\"ss-teen-team-label-fix\">
document.querySelectorAll('a[href=\"teen-competition-team.html\"] h3').forEach(function(h){h.textContent='Teen Competition Team';});
</script>"""


def register_competition_site_fixes(app) -> None:
    """Keep competition-team navigation consistent across all public team pages."""

    @app.after_request
    def normalize_competition_team_links(response):
        if request.path not in COMPETITION_HTML_PATHS or response.mimetype != "text/html":
            return response

        try:
            body = response.get_data(as_text=True)

            # Remove the legacy Teen/Senior label everywhere it can still surface.
            body = body.replace("Teen / Senior Competition Team", "Teen Competition Team")
            body = body.replace("Teen & Senior Competition Team", "Teen Competition Team")
            body = body.replace("Teen / Senior Team", "Teen Team")

            # Every competition footer should expose the same complete team list.
            footer_pattern = re.compile(
                r'<div><h3>Competition</h3>.*?</div>',
                flags=re.IGNORECASE | re.DOTALL,
            )
            body = footer_pattern.sub(TEAM_LINKS, body, count=1)

            # site-refinements.js historically renamed Teen to Teen/Senior on the overview.
            # Run this tiny correction after that script so the current team name wins.
            if request.path == "/competition.html" and 'id="ss-teen-team-label-fix"' not in body:
                body = body.replace("</body>", TEEN_LABEL_FIX + "</body>", 1)

            response.set_data(body)
        except Exception:
            app.logger.exception("Could not normalize competition-team links")
        return response
