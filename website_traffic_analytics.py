"""Privacy-conscious first-party website traffic analytics for Stage Starz."""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from flask import render_template, request, session

from database import get_db


STUDIO_TZ = ZoneInfo("America/New_York")
VISITOR_COOKIE = "_ss_vid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365
SESSION_GAP = timedelta(minutes=30)

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
BOT_PATTERN = re.compile(
    r"bot|crawler|spider|slurp|bingpreview|facebookexternalhit|"
    r"headless|phantom|selenium|monitoring|uptime|preview",
    re.I,
)
VALID_VISITOR = re.compile(r"^[A-Za-z0-9_-]{20,100}$")


def _now_local() -> datetime:
    return datetime.now(STUDIO_TZ)


def ensure_traffic_schema() -> None:
    connection = get_db()
    id_column = (
        "SERIAL PRIMARY KEY"
        if getattr(connection, "backend", "sqlite") == "postgresql"
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    try:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS website_traffic (
                id {id_column},
                occurred_at TEXT NOT NULL,
                event_day TEXT NOT NULL,
                visitor_id TEXT NOT NULL,
                path TEXT NOT NULL,
                referrer_source TEXT NOT NULL DEFAULT 'Direct',
                device_type TEXT NOT NULL DEFAULT 'Desktop',
                utm_source TEXT NOT NULL DEFAULT '',
                utm_medium TEXT NOT NULL DEFAULT '',
                utm_campaign TEXT NOT NULL DEFAULT '',
                is_entry INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS website_visitors (
                visitor_id TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                total_views INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        for statement in (
            "CREATE INDEX IF NOT EXISTS idx_website_traffic_day ON website_traffic(event_day)",
            "CREATE INDEX IF NOT EXISTS idx_website_traffic_visitor ON website_traffic(visitor_id)",
            "CREATE INDEX IF NOT EXISTS idx_website_traffic_path ON website_traffic(path)",
        ):
            connection.execute(statement)
        connection.commit()
    finally:
        connection.close()


def _should_track(response) -> bool:
    if request.method != "GET" or response.status_code != 200:
        return False
    if response.mimetype != "text/html":
        return False
    path = request.path.rstrip("/") or "/"
    if any(path.startswith(prefix) for prefix in PRIVATE_PREFIXES):
        return False
    if session.get("admin_user_id"):
        return False
    if request.headers.get("DNT") == "1" or request.headers.get("Sec-GPC") == "1":
        return False
    user_agent = request.headers.get("User-Agent", "")
    if not user_agent or BOT_PATTERN.search(user_agent):
        return False
    return True


def _visitor_id() -> tuple[str, bool]:
    existing = (request.cookies.get(VISITOR_COOKIE) or "").strip()
    if existing and VALID_VISITOR.match(existing):
        return existing, False
    return secrets.token_urlsafe(24), True


def _device_type(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if any(token in ua for token in ("ipad", "tablet", "kindle", "silk/")):
        return "Tablet"
    if any(token in ua for token in ("iphone", "android", "mobile", "windows phone")):
        return "Mobile"
    return "Desktop"


def _source_from_referrer(referrer: str) -> str:
    if not referrer:
        return "Direct"
    try:
        host = (urlparse(referrer).hostname or "").lower().removeprefix("www.")
    except Exception:
        return "Direct"
    if not host:
        return "Direct"
    if host.endswith("stagestarzdance.com") or host.endswith("stagestarzdance.net"):
        return "Internal"
    if "google." in host:
        return "Google"
    if host.endswith("bing.com"):
        return "Bing"
    if host.endswith("facebook.com"):
        return "Facebook"
    if host.endswith("instagram.com"):
        return "Instagram"
    if host in {"x.com", "twitter.com", "t.co"} or host.endswith(".twitter.com"):
        return "X / Twitter"
    if "duckduckgo.com" in host:
        return "DuckDuckGo"
    if host.endswith("yahoo.com"):
        return "Yahoo"
    return host[:120]


def _clean_campaign(value: str, limit: int) -> str:
    return " ".join((value or "").replace("\r", " ").replace("\n", " ").split())[:limit]


def _record_page_view(visitor_id: str) -> None:
    now = _now_local()
    occurred_at = now.isoformat(timespec="seconds")
    event_day = now.date().isoformat()
    path = (request.path or "/")[:300]
    source = _source_from_referrer(request.headers.get("Referer", ""))
    device = _device_type(request.headers.get("User-Agent", ""))
    utm_source = _clean_campaign(request.args.get("utm_source", ""), 120)
    utm_medium = _clean_campaign(request.args.get("utm_medium", ""), 120)
    utm_campaign = _clean_campaign(request.args.get("utm_campaign", ""), 160)

    connection = get_db()
    try:
        last = connection.execute(
            """
            SELECT occurred_at
            FROM website_traffic
            WHERE visitor_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (visitor_id,),
        ).fetchone()

        is_entry = 1
        if last and last["occurred_at"]:
            try:
                previous = datetime.fromisoformat(str(last["occurred_at"]))
                if previous.tzinfo is None:
                    previous = previous.replace(tzinfo=STUDIO_TZ)
                if now - previous.astimezone(STUDIO_TZ) <= SESSION_GAP:
                    is_entry = 0
            except (TypeError, ValueError):
                pass

        connection.execute(
            """
            INSERT INTO website_traffic (
                occurred_at,event_day,visitor_id,path,referrer_source,
                device_type,utm_source,utm_medium,utm_campaign,is_entry
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                occurred_at,
                event_day,
                visitor_id,
                path,
                source,
                device,
                utm_source,
                utm_medium,
                utm_campaign,
                is_entry,
            ),
        )
        connection.execute(
            """
            INSERT INTO website_visitors (
                visitor_id,first_seen,last_seen,total_views
            ) VALUES (?,?,?,1)
            ON CONFLICT(visitor_id) DO UPDATE SET
                last_seen=excluded.last_seen,
                total_views=website_visitors.total_views+1
            """,
            (visitor_id, occurred_at, occurred_at),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _counts(connection, start_day: str, end_day: str | None = None) -> dict[str, int]:
    if end_day:
        row = connection.execute(
            """
            SELECT COUNT(*) AS views, COUNT(DISTINCT visitor_id) AS visitors
            FROM website_traffic
            WHERE event_day>=? AND event_day<=?
            """,
            (start_day, end_day),
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT COUNT(*) AS views, COUNT(DISTINCT visitor_id) AS visitors
            FROM website_traffic
            WHERE event_day=?
            """,
            (start_day,),
        ).fetchone()
    return {
        "views": int(row["views"] or 0),
        "visitors": int(row["visitors"] or 0),
    }


def traffic_summary() -> dict:
    today = _now_local().date()
    today_text = today.isoformat()
    yesterday_text = (today - timedelta(days=1)).isoformat()
    seven_start = (today - timedelta(days=6)).isoformat()
    thirty_start = (today - timedelta(days=29)).isoformat()

    connection = get_db()
    try:
        today_counts = _counts(connection, today_text)
        yesterday_counts = _counts(connection, yesterday_text)
        seven_counts = _counts(connection, seven_start, today_text)
        thirty_counts = _counts(connection, thirty_start, today_text)
        first = connection.execute(
            "SELECT MIN(occurred_at) AS first_seen FROM website_traffic"
        ).fetchone()

        change = None
        if yesterday_counts["visitors"] > 0:
            change = round(
                ((today_counts["visitors"] - yesterday_counts["visitors"])
                 / yesterday_counts["visitors"]) * 100
            )
        elif today_counts["visitors"] > 0:
            change = 100

        return {
            "today_visitors": today_counts["visitors"],
            "today_views": today_counts["views"],
            "yesterday_visitors": yesterday_counts["visitors"],
            "seven_visitors": seven_counts["visitors"],
            "seven_views": seven_counts["views"],
            "thirty_visitors": thirty_counts["visitors"],
            "thirty_views": thirty_counts["views"],
            "visitor_change": change,
            "tracking_since": str(first["first_seen"] or "")[:10],
        }
    finally:
        connection.close()


def _daily_series(connection, start: date, end: date) -> list[dict]:
    rows = connection.execute(
        """
        SELECT event_day, COUNT(*) AS views, COUNT(DISTINCT visitor_id) AS visitors
        FROM website_traffic
        WHERE event_day>=? AND event_day<=?
        GROUP BY event_day
        ORDER BY event_day
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    by_day = {
        str(row["event_day"]): {
            "views": int(row["views"] or 0),
            "visitors": int(row["visitors"] or 0),
        }
        for row in rows
    }
    result = []
    cursor = start
    max_visitors = max([item["visitors"] for item in by_day.values()] or [1])
    while cursor <= end:
        key = cursor.isoformat()
        counts = by_day.get(key, {"views": 0, "visitors": 0})
        result.append(
            {
                "day": key,
                "label": cursor.strftime("%b %d"),
                "views": counts["views"],
                "visitors": counts["visitors"],
                "bar": round((counts["visitors"] / max_visitors) * 100) if max_visitors else 0,
            }
        )
        cursor += timedelta(days=1)
    return result


def traffic_report(days: int) -> dict:
    today = _now_local().date()
    start = today - timedelta(days=days - 1)
    start_text = start.isoformat()
    today_text = today.isoformat()

    connection = get_db()
    try:
        today_counts = _counts(connection, today_text)
        period_counts = _counts(connection, start_text, today_text)

        top_pages = [
            {
                "path": row["path"],
                "views": int(row["views"] or 0),
                "visitors": int(row["visitors"] or 0),
            }
            for row in connection.execute(
                """
                SELECT path, COUNT(*) AS views, COUNT(DISTINCT visitor_id) AS visitors
                FROM website_traffic
                WHERE event_day>=? AND event_day<=?
                GROUP BY path
                ORDER BY views DESC, visitors DESC
                LIMIT 12
                """,
                (start_text, today_text),
            ).fetchall()
        ]

        landing_pages = [
            {
                "path": row["path"],
                "visits": int(row["visits"] or 0),
            }
            for row in connection.execute(
                """
                SELECT path, COUNT(*) AS visits
                FROM website_traffic
                WHERE event_day>=? AND event_day<=? AND is_entry=1
                GROUP BY path
                ORDER BY visits DESC
                LIMIT 10
                """,
                (start_text, today_text),
            ).fetchall()
        ]

        sources = [
            {
                "source": row["referrer_source"],
                "views": int(row["views"] or 0),
                "visitors": int(row["visitors"] or 0),
            }
            for row in connection.execute(
                """
                SELECT referrer_source, COUNT(*) AS views,
                       COUNT(DISTINCT visitor_id) AS visitors
                FROM website_traffic
                WHERE event_day>=? AND event_day<=?
                GROUP BY referrer_source
                ORDER BY visitors DESC, views DESC
                LIMIT 12
                """,
                (start_text, today_text),
            ).fetchall()
        ]

        devices = [
            {
                "device": row["device_type"],
                "views": int(row["views"] or 0),
                "visitors": int(row["visitors"] or 0),
            }
            for row in connection.execute(
                """
                SELECT device_type, COUNT(*) AS views,
                       COUNT(DISTINCT visitor_id) AS visitors
                FROM website_traffic
                WHERE event_day>=? AND event_day<=?
                GROUP BY device_type
                ORDER BY visitors DESC
                """,
                (start_text, today_text),
            ).fetchall()
        ]

        campaigns = [
            {
                "source": row["utm_source"] or "—",
                "medium": row["utm_medium"] or "—",
                "campaign": row["utm_campaign"] or "—",
                "views": int(row["views"] or 0),
                "visitors": int(row["visitors"] or 0),
            }
            for row in connection.execute(
                """
                SELECT utm_source,utm_medium,utm_campaign,
                       COUNT(*) AS views,
                       COUNT(DISTINCT visitor_id) AS visitors
                FROM website_traffic
                WHERE event_day>=? AND event_day<=?
                  AND (utm_source!='' OR utm_medium!='' OR utm_campaign!='')
                GROUP BY utm_source,utm_medium,utm_campaign
                ORDER BY visitors DESC, views DESC
                LIMIT 12
                """,
                (start_text, today_text),
            ).fetchall()
        ]

        new_row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM website_visitors
            WHERE SUBSTR(first_seen,1,10)>=? AND SUBSTR(first_seen,1,10)<=?
            """,
            (start_text, today_text),
        ).fetchone()
        new_visitors = min(
            int(new_row["count"] or 0),
            period_counts["visitors"],
        )
        returning_visitors = max(period_counts["visitors"] - new_visitors, 0)

        first = connection.execute(
            "SELECT MIN(occurred_at) AS first_seen FROM website_traffic"
        ).fetchone()

        return {
            "days": days,
            "start": start_text,
            "end": today_text,
            "today": today_counts,
            "period": period_counts,
            "daily": _daily_series(connection, start, today),
            "top_pages": top_pages,
            "landing_pages": landing_pages,
            "sources": sources,
            "devices": devices,
            "campaigns": campaigns,
            "new_visitors": new_visitors,
            "returning_visitors": returning_visitors,
            "tracking_since": str(first["first_seen"] or "")[:10],
        }
    finally:
        connection.close()


def register_website_traffic(app, permission_required) -> None:
    ensure_traffic_schema()

    @app.context_processor
    def website_traffic_dashboard_context():
        if request.path.rstrip("/") != "/admin":
            return {}
        try:
            return {"traffic_stats": traffic_summary()}
        except Exception:
            app.logger.exception("Could not load Website Traffic summary")
            return {
                "traffic_stats": {
                    "today_visitors": 0,
                    "today_views": 0,
                    "seven_visitors": 0,
                    "seven_views": 0,
                    "thirty_visitors": 0,
                    "thirty_views": 0,
                    "visitor_change": None,
                    "tracking_since": "",
                }
            }

    @app.route("/admin/traffic", endpoint="website_traffic_dashboard")
    @app.route("/admin/analytics")
    @permission_required("website")
    def website_traffic_dashboard():
        try:
            days = int(request.args.get("days", "30"))
        except ValueError:
            days = 30
        if days not in {1, 7, 30, 90}:
            days = 30
        return render_template(
            "website_traffic.html",
            report=traffic_report(days),
        )

    @app.after_request
    def track_public_website_traffic(response):
        if not _should_track(response):
            return response
        visitor_id, is_new_cookie = _visitor_id()
        try:
            _record_page_view(visitor_id)
        except Exception:
            app.logger.exception("Could not record website traffic")
        if is_new_cookie:
            response.set_cookie(
                VISITOR_COOKIE,
                visitor_id,
                max_age=COOKIE_MAX_AGE,
                secure=True,
                httponly=True,
                samesite="Lax",
            )
        return response
