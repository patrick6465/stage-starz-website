"""ZeptoMail REST delivery for Stage Starz transactional email."""

from __future__ import annotations

import base64
import json
import os
from typing import Any
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


def _recipient_entries(values) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for item in values or []:
        name = ""
        address = ""
        if isinstance(item, str):
            address = item.strip()
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            name = str(item[0] or "").strip()
            address = str(item[1] or "").strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            address = str(item.get("address") or item.get("email") or "").strip()
        if not address:
            continue
        email_address: dict[str, str] = {"address": address}
        if name:
            email_address["name"] = name
        entries.append({"email_address": email_address})
    return entries


def send_zeptomail_message(
    to_recipients,
    subject: str,
    *,
    cc_recipients=None,
    bcc_recipients=None,
    html_body: str = "",
    text_body: str = "",
    attachments: list[dict[str, Any]] | None = None,
    from_name: str = "Stage Starz Academy of Dance",
    reply_to: str = "",
    reply_to_name: str = "",
    client_reference: str = "",
    mime_headers: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Send a transactional message through ZeptoMail's HTTPS API."""

    subject = (subject or "").strip()
    to_entries = _recipient_entries(to_recipients)
    cc_entries = _recipient_entries(cc_recipients)
    bcc_entries = _recipient_entries(bcc_recipients)

    if not (to_entries or cc_entries or bcc_entries):
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
        "subject": subject,
        "track_clicks": False,
        "track_opens": False,
    }
    if to_entries:
        payload["to"] = to_entries
    if cc_entries:
        payload["cc"] = cc_entries
    if bcc_entries:
        payload["bcc"] = bcc_entries

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

    prepared_attachments: list[dict[str, str]] = []
    for item in attachments or []:
        name = str(item.get("name") or "attachment")[:180]
        mime_type = str(item.get("mime_type") or item.get("type") or "application/octet-stream")
        raw = item.get("data")
        content = item.get("content")
        if isinstance(raw, (bytes, bytearray)):
            content = base64.b64encode(bytes(raw)).decode("ascii")
        if not content:
            continue
        prepared_attachments.append({
            "content": str(content),
            "mime_type": mime_type,
            "name": name,
        })
    if prepared_attachments:
        payload["attachments"] = prepared_attachments

    if mime_headers:
        payload["mime_headers"] = {
            str(key): str(value)
            for key, value in mime_headers.items()
            if key and value
        }

    client_reference = (client_reference or "").strip()
    if client_reference:
        payload["client_reference"] = client_reference[:200]

    endpoint = (os.environ.get("ZEPTOMAIL_API_URL") or DEFAULT_ZEPTOMAIL_ENDPOINT).strip()
    req = Request(
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
        with urlopen(req, timeout=20) as response:
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
    """Backward-compatible single-recipient helper used by website forms."""
    return send_zeptomail_message(
        [recipient],
        subject,
        html_body=html_body,
        text_body=text_body,
        from_name=from_name,
        reply_to=reply_to,
        reply_to_name=reply_to_name,
        client_reference=client_reference,
    )
