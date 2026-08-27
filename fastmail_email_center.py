"""Private Fastmail/JMAP email client for the Stage Starz Command Center."""

from __future__ import annotations

import html
import json
import mimetypes
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.utils import formataddr, getaddresses
from html.parser import HTMLParser
from typing import Any

from flask import (
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

CORE = "urn:ietf:params:jmap:core"
MAIL = "urn:ietf:params:jmap:mail"
SUBMISSION = "urn:ietf:params:jmap:submission"
SESSION_URL = "https://api.fastmail.com/jmap/session"

_SESSION_CACHE: dict[str, Any] = {"token": None, "expires": 0.0, "data": None}
_SESSION_LOCK = threading.Lock()


class FastmailError(RuntimeError):
    pass


class _HTMLToText(HTMLParser):
    BLOCKS = {
        "p", "div", "br", "li", "tr", "table", "section", "article",
        "header", "footer", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def text(self) -> str:
        raw = html.unescape("".join(self.parts)).replace("\r", "")
        lines = [" ".join(line.split()) for line in raw.split("\n")]
        cleaned: list[str] = []
        blank = False
        for line in lines:
            if line:
                cleaned.append(line)
                blank = False
            elif cleaned and not blank:
                cleaned.append("")
                blank = True
        return "\n".join(cleaned).strip()


def _html_to_text(value: str) -> str:
    parser = _HTMLToText()
    try:
        parser.feed(value or "")
        parser.close()
        return parser.text()
    except Exception:
        return " ".join((value or "").replace("<", " <").split())


def _token() -> str:
    return (os.getenv("FASTMAIL_API_TOKEN") or "").strip()


def _configured_email() -> str:
    return (os.getenv("FASTMAIL_EMAIL_ADDRESS") or "office@stagestarzdance.com").strip()


def _json_http(
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 25,
) -> dict[str, Any]:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "StageStarzEmailCenter/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise FastmailError(f"Fastmail returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise FastmailError(f"Could not reach Fastmail: {exc.reason}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise FastmailError("Fastmail returned an invalid response.") from exc


def _session_data(token: str) -> dict[str, Any]:
    now = time.monotonic()
    with _SESSION_LOCK:
        if (
            _SESSION_CACHE.get("token") == token
            and _SESSION_CACHE.get("data")
            and float(_SESSION_CACHE.get("expires") or 0) > now
        ):
            return _SESSION_CACHE["data"]
    data = _json_http(SESSION_URL, token)
    if not data.get("apiUrl"):
        raise FastmailError("Fastmail JMAP session did not provide an API URL.")
    with _SESSION_LOCK:
        _SESSION_CACHE.update(token=token, data=data, expires=now + 300)
    return data


def _replace_template(template: str, **values: str) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", urllib.parse.quote(str(value), safe=""))
    return result


class FastmailClient:
    def __init__(self) -> None:
        self.token = _token()
        if not self.token:
            raise FastmailError("FASTMAIL_API_TOKEN is not configured in Railway.")
        self.session = _session_data(self.token)
        primary = self.session.get("primaryAccounts") or {}
        self.mail_account = primary.get(MAIL)
        self.submission_account = primary.get(SUBMISSION) or self.mail_account
        if not self.mail_account:
            raise FastmailError("This Fastmail token does not have Email access.")
        if not self.submission_account:
            raise FastmailError("This Fastmail token does not have Email Submission access.")

    def call(self, calls: list[list[Any]], using: list[str] | None = None) -> list[list[Any]]:
        payload = {
            "using": using or [CORE, MAIL],
            "methodCalls": calls,
        }
        data = _json_http(self.session["apiUrl"], self.token, payload)
        responses = data.get("methodResponses") or []
        for item in responses:
            if item and item[0] == "error":
                info = item[1] if len(item) > 1 else {}
                description = info.get("description") or info.get("type") or "Unknown JMAP error"
                raise FastmailError(str(description))
        return responses

    def mailboxes(self) -> list[dict[str, Any]]:
        responses = self.call(
            [[
                "Mailbox/get",
                {
                    "accountId": self.mail_account,
                    "ids": None,
                    "properties": [
                        "id", "name", "parentId", "role", "sortOrder",
                        "totalEmails", "unreadEmails",
                    ],
                },
                "m",
            ]]
        )
        for name, data, _tag in responses:
            if name == "Mailbox/get":
                return data.get("list") or []
        return []

    def identities(self) -> list[dict[str, Any]]:
        responses = self.call(
            [[
                "Identity/get",
                {
                    "accountId": self.submission_account,
                    "ids": None,
                    "properties": ["id", "name", "email", "replyTo", "bcc"],
                },
                "i",
            ]],
            [CORE, MAIL, SUBMISSION],
        )
        for name, data, _tag in responses:
            if name == "Identity/get":
                return data.get("list") or []
        return []

    def list_messages(
        self,
        mailbox_id: str | None,
        query_text: str,
        position: int,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[dict[str, Any]] = []
        if mailbox_id:
            conditions.append({"inMailbox": mailbox_id})
        if query_text:
            conditions.append({"text": query_text})
        if not conditions:
            filter_value: dict[str, Any] = {}
        elif len(conditions) == 1:
            filter_value = conditions[0]
        else:
            filter_value = {"operator": "AND", "conditions": conditions}

        calls = [
            [
                "Email/query",
                {
                    "accountId": self.mail_account,
                    "filter": filter_value,
                    "sort": [{"property": "receivedAt", "isAscending": False}],
                    "collapseThreads": False,
                    "position": position,
                    "limit": limit,
                    "calculateTotal": True,
                },
                "q",
            ],
            [
                "Email/get",
                {
                    "accountId": self.mail_account,
                    "#ids": {"resultOf": "q", "name": "Email/query", "path": "/ids"},
                    "properties": [
                        "id", "threadId", "mailboxIds", "keywords", "from", "to",
                        "subject", "receivedAt", "sentAt", "hasAttachment",
                        "preview", "size",
                    ],
                },
                "g",
            ],
        ]
        responses = self.call(calls)
        total = 0
        messages: list[dict[str, Any]] = []
        for name, data, _tag in responses:
            if name == "Email/query":
                total = int(data.get("total") or 0)
            elif name == "Email/get":
                messages = data.get("list") or []
        order: dict[str, int] = {}
        for name, data, _tag in responses:
            if name == "Email/query":
                order = {email_id: idx for idx, email_id in enumerate(data.get("ids") or [])}
        messages.sort(key=lambda item: order.get(item.get("id"), 999999))
        return messages, total

    def get_message(self, email_id: str) -> dict[str, Any]:
        responses = self.call(
            [[
                "Email/get",
                {
                    "accountId": self.mail_account,
                    "ids": [email_id],
                    "properties": [
                        "id", "blobId", "threadId", "mailboxIds", "keywords",
                        "from", "to", "cc", "bcc", "replyTo", "subject",
                        "receivedAt", "sentAt", "messageId", "inReplyTo",
                        "hasAttachment", "preview", "textBody", "htmlBody",
                        "attachments", "bodyValues",
                    ],
                    "bodyProperties": [
                        "partId", "blobId", "size", "name", "type",
                        "charset", "disposition", "cid",
                    ],
                    "fetchTextBodyValues": True,
                    "fetchHTMLBodyValues": True,
                    "maxBodyValueBytes": 500000,
                },
                "g",
            ]]
        )
        for name, data, _tag in responses:
            if name == "Email/get":
                rows = data.get("list") or []
                if rows:
                    message = rows[0]
                    message["displayBody"] = self._message_body(message)
                    return message
        raise FastmailError("That email could not be found.")

    @staticmethod
    def _message_body(message: dict[str, Any]) -> str:
        values = message.get("bodyValues") or {}
        text_parts: list[str] = []
        for part in message.get("textBody") or []:
            part_id = part.get("partId")
            if part_id and part_id in values:
                value = values[part_id].get("value") or ""
                if value:
                    text_parts.append(value)
        if text_parts:
            return "\n\n".join(text_parts).strip()

        html_parts: list[str] = []
        for part in message.get("htmlBody") or []:
            part_id = part.get("partId")
            if part_id and part_id in values:
                value = values[part_id].get("value") or ""
                if value:
                    html_parts.append(_html_to_text(value))
        if html_parts:
            return "\n\n".join(part for part in html_parts if part).strip()
        return message.get("preview") or "(No message body.)"

    def update_email(self, email_id: str, patch: dict[str, Any]) -> None:
        responses = self.call(
            [[
                "Email/set",
                {"accountId": self.mail_account, "update": {email_id: patch}},
                "u",
            ]]
        )
        for name, data, _tag in responses:
            if name == "Email/set" and (data.get("notUpdated") or {}).get(email_id):
                problem = data["notUpdated"][email_id]
                raise FastmailError(problem.get("description") or problem.get("type") or "Email update failed.")

    def destroy_email(self, email_id: str) -> None:
        responses = self.call(
            [[
                "Email/set",
                {"accountId": self.mail_account, "destroy": [email_id]},
                "d",
            ]]
        )
        for name, data, _tag in responses:
            if name == "Email/set" and (data.get("notDestroyed") or {}).get(email_id):
                problem = data["notDestroyed"][email_id]
                raise FastmailError(problem.get("description") or problem.get("type") or "Email delete failed.")

    def upload_raw_message(self, raw: bytes) -> str:
        upload_url = _replace_template(
            self.session["uploadUrl"],
            accountId=self.mail_account,
        )
        req = urllib.request.Request(
            upload_url,
            data=raw,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "message/rfc822",
                "Accept": "application/json",
                "User-Agent": "StageStarzEmailCenter/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise FastmailError(f"Fastmail upload failed ({exc.code}): {detail}") from exc
        except Exception as exc:
            raise FastmailError(f"Fastmail upload failed: {exc}") from exc
        blob_id = result.get("blobId")
        if not blob_id:
            raise FastmailError("Fastmail did not return a blob ID for the draft.")
        return blob_id

    def import_draft(self, blob_id: str, drafts_id: str) -> str:
        responses = self.call(
            [[
                "Email/import",
                {
                    "accountId": self.mail_account,
                    "emails": {
                        "draft": {
                            "blobId": blob_id,
                            "mailboxIds": {drafts_id: True},
                            "keywords": {"$seen": True, "$draft": True},
                            "receivedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        }
                    },
                },
                "imp",
            ]]
        )
        for name, data, _tag in responses:
            if name == "Email/import":
                created = data.get("created") or {}
                if created.get("draft", {}).get("id"):
                    return created["draft"]["id"]
                problem = (data.get("notCreated") or {}).get("draft") or {}
                raise FastmailError(problem.get("description") or problem.get("type") or "Draft creation failed.")
        raise FastmailError("Fastmail did not create the draft.")

    def send_draft(
        self,
        email_id: str,
        identity_id: str,
        drafts_id: str,
        sent_id: str,
    ) -> None:
        responses = self.call(
            [[
                "EmailSubmission/set",
                {
                    "accountId": self.submission_account,
                    "create": {
                        "send": {
                            "identityId": identity_id,
                            "emailId": email_id,
                        }
                    },
                    "onSuccessUpdateEmail": {
                        "#send": {
                            f"mailboxIds/{drafts_id}": None,
                            f"mailboxIds/{sent_id}": True,
                            "keywords/$draft": None,
                        }
                    },
                },
                "send",
            ]],
            [CORE, MAIL, SUBMISSION],
        )
        for name, data, _tag in responses:
            if name == "EmailSubmission/set":
                problem = (data.get("notCreated") or {}).get("send")
                if problem:
                    raise FastmailError(problem.get("description") or problem.get("type") or "Email could not be sent.")
                if (data.get("created") or {}).get("send"):
                    return
        raise FastmailError("Fastmail did not confirm email submission.")

    def download_attachment(self, blob_id: str, name: str, content_type: str) -> tuple[bytes, str]:
        download_url = _replace_template(
            self.session["downloadUrl"],
            accountId=self.mail_account,
            blobId=blob_id,
            name=name,
            type=content_type,
        )
        req = urllib.request.Request(
            download_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "StageStarzEmailCenter/1.0",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read(), response.headers.get_content_type()
        except Exception as exc:
            raise FastmailError(f"Attachment download failed: {exc}") from exc


def _csrf() -> str:
    token = session.get("_stage_starz_email_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_stage_starz_email_csrf"] = token
    return token


def _check_csrf() -> None:
    supplied = request.form.get("_csrf") or ""
    expected = session.get("_stage_starz_email_csrf") or ""
    if not expected or not secrets.compare_digest(supplied, expected):
        raise FastmailError("The form expired. Please reload the Email Center and try again.")


def _address_text(addresses: list[dict[str, Any]] | None) -> str:
    result = []
    for item in addresses or []:
        name = (item.get("name") or "").strip()
        email = (item.get("email") or "").strip()
        if not email:
            continue
        result.append(formataddr((name, email)) if name else email)
    return ", ".join(result)


def _first_address(addresses: list[dict[str, Any]] | None) -> str:
    for item in addresses or []:
        email = (item.get("email") or "").strip()
        if email:
            name = (item.get("name") or "").strip()
            return formataddr((name, email)) if name else email
    return ""


def _parse_addresses(raw: str) -> list[tuple[str, str]]:
    raw = (raw or "").replace(";", ",").strip()
    addresses: list[tuple[str, str]] = []
    for name, email in getaddresses([raw]):
        name = " ".join((name or "").replace("\r", " ").replace("\n", " ").split())
        email = (email or "").replace("\r", "").replace("\n", "").strip()
        if not email or "@" not in email:
            continue
        addresses.append((name, email))
    return addresses


def _subject_reply(subject: str) -> str:
    subject = (subject or "").strip()
    return subject if subject.lower().startswith("re:") else f"Re: {subject or '(no subject)'}"


def _subject_forward(subject: str) -> str:
    subject = (subject or "").strip()
    return subject if subject.lower().startswith(("fwd:", "fw:")) else f"Fwd: {subject or '(no subject)'}"


def _find_role(mailboxes: list[dict[str, Any]], role: str) -> dict[str, Any] | None:
    for mailbox in mailboxes:
        if (mailbox.get("role") or "").lower() == role.lower():
            return mailbox
    return None


def _mailbox_for_key(mailboxes: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    if key == "all":
        return None
    by_role = _find_role(mailboxes, key)
    if by_role:
        return by_role
    for mailbox in mailboxes:
        if mailbox.get("id") == key:
            return mailbox
    return _find_role(mailboxes, "inbox")


def _folder_label(mailbox: dict[str, Any] | None, key: str) -> str:
    if key == "all":
        return "All Mail"
    if mailbox:
        return mailbox.get("name") or (mailbox.get("role") or "Mailbox").title()
    return "Inbox"


def _build_message(
    sender_email: str,
    to_text: str,
    cc_text: str,
    bcc_text: str,
    subject: str,
    body: str,
    attachments,
    original: dict[str, Any] | None = None,
) -> bytes:
    to_addresses = _parse_addresses(to_text)
    cc_addresses = _parse_addresses(cc_text)
    bcc_addresses = _parse_addresses(bcc_text)
    if not to_addresses and not cc_addresses and not bcc_addresses:
        raise FastmailError("Enter at least one recipient.")

    msg = EmailMessage(policy=policy.SMTP)
    msg["From"] = formataddr(("Stage Starz Academy of Dance", sender_email))
    if to_addresses:
        msg["To"] = ", ".join(formataddr(pair) if pair[0] else pair[1] for pair in to_addresses)
    if cc_addresses:
        msg["Cc"] = ", ".join(formataddr(pair) if pair[0] else pair[1] for pair in cc_addresses)
    if bcc_addresses:
        msg["Bcc"] = ", ".join(formataddr(pair) if pair[0] else pair[1] for pair in bcc_addresses)
    msg["Subject"] = " ".join((subject or "").replace("\r", " ").replace("\n", " ").split())[:500]
    if original:
        message_ids = original.get("messageId") or []
        if message_ids:
            original_id = str(message_ids[0]).strip("<>")
            msg["In-Reply-To"] = f"<{original_id}>"
            msg["References"] = f"<{original_id}>"
    msg.set_content(body or "")

    total_size = 0
    for upload in attachments:
        if not upload or not getattr(upload, "filename", ""):
            continue
        filename = os.path.basename(upload.filename)[:180] or "attachment"
        data = upload.read()
        total_size += len(data)
        if len(data) > 15 * 1024 * 1024 or total_size > 20 * 1024 * 1024:
            raise FastmailError("Attachments are limited to 15 MB each and 20 MB total in the Stage Starz Email Center.")
        guessed = upload.mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, subtype = guessed.split("/", 1) if "/" in guessed else ("application", "octet-stream")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg.as_bytes()


def register_fastmail_email_center(app, permission_required) -> None:
    if "fastmail_email_center" in app.view_functions:
        return

    email_permission = permission_required("notifications")

    @app.after_request
    def fastmail_email_no_cache(response):
        if request.path.startswith("/admin/email"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    @app.get("/admin/email", endpoint="fastmail_email_center")
    @email_permission
    def fastmail_email_center():
        try:
            client = FastmailClient()
            mailboxes = client.mailboxes()
            folder_key = (request.args.get("folder") or "inbox").strip()
            selected = _mailbox_for_key(mailboxes, folder_key)
            if folder_key != "all" and selected:
                folder_key = selected.get("role") or selected.get("id")
            q = (request.args.get("q") or "").strip()[:200]
            try:
                page = max(1, int(request.args.get("page") or "1"))
            except ValueError:
                page = 1
            limit = 50
            position = (page - 1) * limit
            messages, total = client.list_messages(
                selected.get("id") if selected else None,
                q,
                position,
                limit,
            )
            role = (selected.get("role") or "") if selected else "all"
            return render_template(
                "fastmail_email_center.html",
                mode="list",
                configured=True,
                account_email=_configured_email(),
                mailboxes=mailboxes,
                selected_mailbox=selected,
                folder=folder_key,
                folder_role=role,
                folder_label=_folder_label(selected, folder_key),
                messages=messages,
                total=total,
                page=page,
                limit=limit,
                q=q,
                csrf_token=_csrf(),
                address_text=_address_text,
            )
        except FastmailError as exc:
            return render_template(
                "fastmail_email_center.html",
                mode="error",
                configured=False,
                error=str(exc),
                account_email=_configured_email(),
                mailboxes=[],
                csrf_token=_csrf(),
            ), 503

    @app.get("/admin/email/message/<email_id>", endpoint="fastmail_email_message")
    @email_permission
    def fastmail_email_message(email_id: str):
        try:
            client = FastmailClient()
            mailboxes = client.mailboxes()
            message = client.get_message(email_id)
            if "$seen" not in (message.get("keywords") or {}):
                try:
                    client.update_email(email_id, {"keywords/$seen": True})
                    message.setdefault("keywords", {})["$seen"] = True
                except FastmailError:
                    pass
            return render_template(
                "fastmail_email_center.html",
                mode="message",
                configured=True,
                account_email=_configured_email(),
                mailboxes=mailboxes,
                message=message,
                folder=request.args.get("folder") or "inbox",
                csrf_token=_csrf(),
                address_text=_address_text,
            )
        except FastmailError as exc:
            flash(str(exc), "error")
            return redirect(url_for("fastmail_email_center"))

    @app.route("/admin/email/compose", methods=["GET", "POST"], endpoint="fastmail_email_compose")
    @email_permission
    def fastmail_email_compose():
        try:
            client = FastmailClient()
            mailboxes = client.mailboxes()
            drafts = _find_role(mailboxes, "drafts")
            sent = _find_role(mailboxes, "sent")
            if not drafts or not sent:
                raise FastmailError("Fastmail Drafts or Sent mailbox could not be located.")

            if request.method == "GET":
                values = {"to": "", "cc": "", "bcc": "", "subject": "", "body": "", "reply_to_id": "", "draft_id": ""}
                reply_id = (request.args.get("reply") or "").strip()
                forward_id = (request.args.get("forward") or "").strip()
                draft_id = (request.args.get("draft") or "").strip()
                original = None
                if reply_id:
                    original = client.get_message(reply_id)
                    values["to"] = _first_address(original.get("replyTo") or original.get("from"))
                    values["subject"] = _subject_reply(original.get("subject") or "")
                    stamp = original.get("sentAt") or original.get("receivedAt") or ""
                    sender = _address_text(original.get("from"))
                    quoted = "\n".join("> " + line for line in (original.get("displayBody") or "").splitlines())
                    values["body"] = f"\n\nOn {stamp}, {sender} wrote:\n{quoted}"
                    values["reply_to_id"] = reply_id
                elif forward_id:
                    original = client.get_message(forward_id)
                    values["subject"] = _subject_forward(original.get("subject") or "")
                    values["body"] = (
                        "\n\n---------- Forwarded message ----------\n"
                        f"From: {_address_text(original.get('from'))}\n"
                        f"Date: {original.get('sentAt') or original.get('receivedAt') or ''}\n"
                        f"Subject: {original.get('subject') or ''}\n"
                        f"To: {_address_text(original.get('to'))}\n\n"
                        f"{original.get('displayBody') or ''}"
                    )
                elif draft_id:
                    original = client.get_message(draft_id)
                    values.update(
                        to=_address_text(original.get("to")),
                        cc=_address_text(original.get("cc")),
                        bcc=_address_text(original.get("bcc")),
                        subject=original.get("subject") or "",
                        body=original.get("displayBody") or "",
                        draft_id=draft_id,
                    )
                return render_template(
                    "fastmail_email_center.html",
                    mode="compose",
                    configured=True,
                    account_email=_configured_email(),
                    mailboxes=mailboxes,
                    values=values,
                    csrf_token=_csrf(),
                )

            _check_csrf()
            action = request.form.get("compose_action") or "send"
            to_text = request.form.get("to") or ""
            cc_text = request.form.get("cc") or ""
            bcc_text = request.form.get("bcc") or ""
            subject = request.form.get("subject") or ""
            body = request.form.get("body") or ""
            reply_to_id = (request.form.get("reply_to_id") or "").strip()
            old_draft_id = (request.form.get("draft_id") or "").strip()
            original = client.get_message(reply_to_id) if reply_to_id else None
            raw = _build_message(
                _configured_email(),
                to_text,
                cc_text,
                bcc_text,
                subject,
                body,
                request.files.getlist("attachments"),
                original=original,
            )
            blob_id = client.upload_raw_message(raw)
            new_draft_id = client.import_draft(blob_id, drafts["id"])

            if old_draft_id and old_draft_id != new_draft_id:
                try:
                    client.destroy_email(old_draft_id)
                except FastmailError:
                    pass

            if action == "draft":
                flash("Draft saved in Fastmail.", "success")
                return redirect(url_for("fastmail_email_center", folder="drafts"))

            identities = client.identities()
            configured = _configured_email().lower()
            identity = next(
                (item for item in identities if (item.get("email") or "").lower() == configured),
                identities[0] if identities else None,
            )
            if not identity:
                raise FastmailError("Fastmail did not provide a sending identity.")
            client.send_draft(new_draft_id, identity["id"], drafts["id"], sent["id"])
            if reply_to_id:
                try:
                    client.update_email(reply_to_id, {"keywords/$answered": True})
                except FastmailError:
                    pass
            flash("Email sent from office@stagestarzdance.com.", "success")
            return redirect(url_for("fastmail_email_center", folder="sent"))
        except FastmailError as exc:
            flash(str(exc), "error")
            if request.method == "POST":
                return redirect(url_for("fastmail_email_compose"))
            return redirect(url_for("fastmail_email_center"))

    @app.post("/admin/email/message/<email_id>/action", endpoint="fastmail_email_action")
    @email_permission
    def fastmail_email_action(email_id: str):
        try:
            _check_csrf()
            client = FastmailClient()
            mailboxes = client.mailboxes()
            action = (request.form.get("action") or "").strip().lower()
            if action in {"archive", "trash", "junk", "inbox"}:
                role = "junk" if action == "junk" else action
                target = _find_role(mailboxes, role)
                if not target:
                    raise FastmailError(f"Fastmail {role.title()} mailbox could not be located.")
                client.update_email(email_id, {"mailboxIds": {target["id"]: True}})
            elif action == "unread":
                client.update_email(email_id, {"keywords/$seen": None})
            elif action == "read":
                client.update_email(email_id, {"keywords/$seen": True})
            elif action == "flag":
                client.update_email(email_id, {"keywords/$flagged": True})
            elif action == "unflag":
                client.update_email(email_id, {"keywords/$flagged": None})
            elif action == "delete":
                client.destroy_email(email_id)
            else:
                raise FastmailError("Unknown email action.")
            flash("Email updated.", "success")
        except FastmailError as exc:
            flash(str(exc), "error")
        return redirect(url_for("fastmail_email_center", folder=request.form.get("return_folder") or "inbox"))

    @app.get(
        "/admin/email/attachment/<email_id>/<blob_id>/<path:filename>",
        endpoint="fastmail_email_attachment",
    )
    @email_permission
    def fastmail_email_attachment(email_id: str, blob_id: str, filename: str):
        try:
            client = FastmailClient()
            message = client.get_message(email_id)
            attachment = next(
                (
                    item for item in (message.get("attachments") or [])
                    if item.get("blobId") == blob_id
                ),
                None,
            )
            if not attachment:
                raise FastmailError("Attachment not found.")
            safe_name = os.path.basename(attachment.get("name") or filename or "attachment")
            content_type = attachment.get("type") or "application/octet-stream"
            data, returned_type = client.download_attachment(blob_id, safe_name, content_type)
            response = Response(data, mimetype=returned_type or content_type)
            encoded = urllib.parse.quote(safe_name)
            response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded}"
            return response
        except FastmailError as exc:
            flash(str(exc), "error")
            return redirect(url_for("fastmail_email_message", email_id=email_id))
