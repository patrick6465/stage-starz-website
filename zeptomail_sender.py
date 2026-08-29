"""ZeptoMail REST delivery for Stage Starz transactional email."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_ZEPTOMAIL_ENDPOINT = "https://api.zeptomail.com/v1.1/email"
DEFAULT_FROM_EMAIL = "office@stagestarzdance.com"


def _token() -> str:
    return (os.environ.get("ZEPTOMAIL_API_TOKEN") or "").strip()


def _authorization_header() -> str:
    token = _token()
    if not token:
        return ""
    if token.lower().startswith("zoho-enczapikey "):
        return token
    return f"Zoho-enczapikey {token}"


def zeptomail_from_email() -> str:
    return (os.environ.get("ZEPTOMAIL_FROM_EMAIL") or DEFAULT_FROM_EMAIL).strip()


def is_zeptomail_configured() -> bool:
    return bool(_token() and zeptomail_from_email())


def send_zeptomail(
    recipient: str,
    subject: str,
    *,
    html_body: str = "",
    text_body: str = "",
    from_name: str = "Stage Starz Academy of Dance",
    reply_to: str = "",
    reply_to_name: str = "",
    client_reference: str = "",
) -> tuple[bool, str]:
    """Send one transactional message through ZeptoMail's HTTPS API."""

    recipient = (recipient or "").strip()
    subject = (subject or "").strip()
    if not recipient:
        return False, "Recipient is missing."
    if not subject:
        return False, "Subject is missing."
    if not html_body and not text_body:
        return False, "Email body is missing."

    auth = _authorization_header()
    from_address = zeptomail_from_email()
    if not auth or not from_address:
        return False, "ZeptoMail is not configured."

    payload: dict[str, object] = {
        "from": {
            "address": from_address,
            "name": (from_name or "Stage Starz Academy of Dance").strip(),
        },
        "to": [
            {
                "email_address": {
                    "address": recipient,
                }
            }
        ],
        "subject": subject,
        "track_clicks": False,
        "track_opens": False,
    }

    # ZeptoMail documents the body as either htmlbody or textbody. Prefer HTML
    # whenever callers provide it and use plain text only as a fallback.
    if html_body:
        payload["htmlbody"] = html_body
    else:
        payload["textbody"] = text_body

    reply_to = (reply_to or "").strip()
    if reply_to:
        reply: dict[str, str] = {"address": reply_to}
        reply_to_name = (reply_to_name or "").strip()
        if reply_to_name:
            reply["name"] = reply_to_name
        payload["reply_to"] = [reply]

    client_reference = (client_reference or "").strip()
    if client_reference:
        payload["client_reference"] = client_reference[:200]

    endpoint = (os.environ.get("ZEPTOMAIL_API_URL") or DEFAULT_ZEPTOMAIL_ENDPOINT).strip()
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": auth,
            "User-Agent": "StageStarzRailway/1.0",
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            status = int(getattr(response, "status", 200) or 200)
            response_body = response.read().decode("utf-8", errors="replace")
            if 200 <= status < 300:
                detail = response_body[:700] or f"ZeptoMail HTTP {status} success"
                return True, detail
            return False, f"ZeptoMail HTTP {status}: {response_body[:700]}"
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        detail = body[:700] or str(exc)
        return False, f"ZeptoMail HTTP {exc.code}: {detail}"
    except URLError as exc:
        return False, f"ZeptoMail connection error: {exc.reason}"
    except Exception as exc:
        return False, f"ZeptoMail error: {exc}"
