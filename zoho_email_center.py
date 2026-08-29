"""Private Zoho mailbox client for the Stage Starz Command Center.\n\nIncoming/folder access uses Zoho IMAP. Outbound delivery uses the existing\nZeptoMail HTTPS API so Railway does not need outbound SMTP access.\n"""

from __future__ import annotations

import base64
import imaplib
import mimetypes
import os
import re
import secrets
import smtplib
import ssl
import urllib.parse
from datetime import datetime, timezone
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import formataddr, getaddresses, make_msgid, parsedate_to_datetime
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

from zeptomail_sender import send_zeptomail_message

IMAP_HOST = (os.getenv("ZOHO_IMAP_HOST") or "imap.zoho.com").strip()
IMAP_PORT = int((os.getenv("ZOHO_IMAP_PORT") or "993").strip())


class ZohoMailError(RuntimeError):
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
        lines = [" ".join(line.split()) for line in "".join(self.parts).replace("\r", "").split("\n")]
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


def _configured_email() -> str:
    return (os.getenv("ZOHO_EMAIL_ADDRESS") or "office@stagestarzdance.com").strip()


def _password() -> str:
    return (os.getenv("ZOHO_APP_PASSWORD") or "").strip()


def _decode_header_text(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _addresses(value: str | None) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    if not value:
        return result
    for name, email in getaddresses([value]):
        email = (email or "").strip()
        if not email:
            continue
        result.append({"name": _decode_header_text(name).strip(), "email": email})
    return result


def _iso_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
        if dt is None:
            return value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return value


def _message_text(msg: Message) -> str:
    text_parts: list[str] = []
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            disposition = (part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue
            ctype = part.get_content_type()
            try:
                content = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                content = payload.decode(charset, errors="replace")
            if ctype == "text/plain":
                text_parts.append(str(content))
            elif ctype == "text/html":
                html_parts.append(str(content))
    else:
        try:
            content = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
        if msg.get_content_type() == "text/html":
            html_parts.append(str(content))
        else:
            text_parts.append(str(content))
    if text_parts:
        return "\n\n".join(part.strip() for part in text_parts if part.strip()).strip()
    if html_parts:
        return _html_to_text("\n".join(html_parts))
    return ""


def _attachments(msg: Message) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for idx, part in enumerate(msg.walk()):
        if part.is_multipart():
            continue
        filename = part.get_filename()
        disposition = (part.get_content_disposition() or "").lower()
        if not filename and disposition != "attachment":
            continue
        filename = _decode_header_text(filename) or "attachment"
        payload = part.get_payload(decode=True) or b""
        result.append(
            {
                "blobId": str(idx),
                "name": filename,
                "size": len(payload),
                "type": part.get_content_type() or "application/octet-stream",
            }
        )
    return result


def _message_id_token(folder: str, uid: str) -> str:
    encoded = base64.urlsafe_b64encode(folder.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{encoded}.{uid}"


def _decode_message_id(token: str) -> tuple[str, str]:
    try:
        encoded, uid = token.rsplit(".", 1)
        padding = "=" * (-len(encoded) % 4)
        folder = base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8")
        if not folder or not uid.isdigit():
            raise ValueError
        return folder, uid
    except Exception as exc:
        raise ZohoMailError("That email reference is invalid.") from exc


def _imap_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parse_flags(fetch_meta: bytes | str) -> set[str]:
    text = fetch_meta.decode("utf-8", errors="replace") if isinstance(fetch_meta, bytes) else str(fetch_meta)
    match = re.search(r"FLAGS \(([^)]*)\)", text, re.I)
    if not match:
        return set()
    return {flag for flag in match.group(1).split() if flag}


def _parse_size(fetch_meta: bytes | str) -> int:
    text = fetch_meta.decode("utf-8", errors="replace") if isinstance(fetch_meta, bytes) else str(fetch_meta)
    match = re.search(r"RFC822\.SIZE\s+(\d+)", text, re.I)
    return int(match.group(1)) if match else 0


def _role_for(flags: set[str], name: str) -> str | None:
    lowered_flags = {flag.lower() for flag in flags}
    lowered = name.strip().lower()
    flag_map = {
        "\\inbox": "inbox",
        "\\sent": "sent",
        "\\drafts": "drafts",
        "\\junk": "junk",
        "\\trash": "trash",
        "\\archive": "archive",
        "\\all": "all",
    }
    for flag, role in flag_map.items():
        if flag in lowered_flags:
            return role
    if lowered == "inbox":
        return "inbox"
    name_map = {
        "sent": "sent",
        "sent mail": "sent",
        "sent messages": "sent",
        "draft": "drafts",
        "drafts": "drafts",
        "spam": "junk",
        "junk": "junk",
        "trash": "trash",
        "deleted": "trash",
        "archive": "archive",
        "all mail": "all",
        "all messages": "all",
    }
    return name_map.get(lowered)


def _parse_list_line(raw: bytes) -> tuple[set[str], str] | None:
    text = raw.decode("utf-8", errors="replace").strip()
    match = re.match(r'^\((.*?)\)\s+(?:"[^"]*"|NIL)\s+(.+)$', text)
    if not match:
        return None
    flags = {item for item in match.group(1).split() if item}
    name = match.group(2).strip()
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return flags, name


class ZohoMailClient:
    def __init__(self) -> None:
        self.email = _configured_email()
        self.password = _password()
        if not self.password:
            raise ZohoMailError("ZOHO_APP_PASSWORD is not configured in Railway.")
        if not self.email:
            raise ZohoMailError("ZOHO_EMAIL_ADDRESS is not configured in Railway.")

    def _connect(self) -> imaplib.IMAP4_SSL:
        try:
            client = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=25)
            client.login(self.email, self.password)
            return client
        except imaplib.IMAP4.error as exc:
            raise ZohoMailError(
                "Zoho IMAP login failed. Verify the app password and make sure IMAP access is enabled for office@stagestarzdance.com in Zoho Mail."
            ) from exc
        except OSError as exc:
            raise ZohoMailError(f"Could not reach Zoho IMAP: {exc}") from exc

    def mailboxes(self) -> list[dict[str, Any]]:
        client = self._connect()
        try:
            status, data = client.list()
            if status != "OK":
                raise ZohoMailError("Zoho did not return the mailbox list.")
            result: list[dict[str, Any]] = []
            for raw in data or []:
                if not raw:
                    continue
                parsed = _parse_list_line(raw)
                if not parsed:
                    continue
                flags, name = parsed
                if any(flag.lower() == "\\noselect" for flag in flags):
                    continue
                total = 0
                unread = 0
                try:
                    st, details = client.status(_imap_quote(name), "(MESSAGES UNSEEN)")
                    if st == "OK" and details and details[0]:
                        line = details[0].decode("utf-8", errors="replace")
                        m_total = re.search(r"MESSAGES\s+(\d+)", line, re.I)
                        m_unread = re.search(r"UNSEEN\s+(\d+)", line, re.I)
                        total = int(m_total.group(1)) if m_total else 0
                        unread = int(m_unread.group(1)) if m_unread else 0
                except Exception:
                    pass
                role = _role_for(flags, name)
                result.append(
                    {
                        "id": name,
                        "name": name.split("/")[-1],
                        "role": role,
                        "sortOrder": 0,
                        "totalEmails": total,
                        "unreadEmails": unread,
                    }
                )
            role_order = {"inbox": 0, "sent": 1, "drafts": 2, "archive": 3, "junk": 4, "trash": 5, "all": 6}
            result.sort(key=lambda item: (role_order.get(item.get("role"), 20), item.get("name", "").lower()))
            return result
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def _find_role(self, mailboxes: list[dict[str, Any]], role: str) -> dict[str, Any] | None:
        for mailbox in mailboxes:
            if (mailbox.get("role") or "").lower() == role.lower():
                return mailbox
        return None

    def ensure_role(self, mailboxes: list[dict[str, Any]], role: str) -> dict[str, Any]:
        existing = self._find_role(mailboxes, role)
        if existing:
            return existing
        preferred = {
            "archive": "Archive",
            "junk": "Spam",
            "trash": "Trash",
            "drafts": "Drafts",
            "sent": "Sent",
            "inbox": "INBOX",
        }.get(role, role.title())
        client = self._connect()
        try:
            if role == "inbox":
                return {"id": "INBOX", "name": "INBOX", "role": "inbox"}
            status, _ = client.create(_imap_quote(preferred))
            if status not in {"OK", "NO"}:
                raise ZohoMailError(f"Zoho could not create the {preferred} folder.")
        finally:
            try:
                client.logout()
            except Exception:
                pass
        return {"id": preferred, "name": preferred, "role": role}

    def _fetch_raw(self, client: imaplib.IMAP4_SSL, uid: str, peek: bool = True) -> tuple[bytes, set[str], int]:
        item = "BODY.PEEK[]" if peek else "RFC822"
        status, data = client.uid("fetch", uid, f"(FLAGS RFC822.SIZE {item})")
        if status != "OK" or not data:
            raise ZohoMailError("That email could not be found.")
        raw = b""
        flags: set[str] = set()
        size = 0
        for part in data:
            if isinstance(part, tuple):
                flags |= _parse_flags(part[0])
                size = max(size, _parse_size(part[0]))
                if isinstance(part[1], bytes):
                    raw += part[1]
        if not raw:
            raise ZohoMailError("Zoho returned an empty email.")
        return raw, flags, size or len(raw)

    def _summary(self, folder: str, uid: str, raw: bytes, flags: set[str], size: int) -> dict[str, Any]:
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        body = _message_text(msg)
        keywords: dict[str, bool] = {}
        lowered = {flag.lower() for flag in flags}
        if "\\seen" in lowered:
            keywords["$seen"] = True
        if "\\flagged" in lowered:
            keywords["$flagged"] = True
        if "\\answered" in lowered:
            keywords["$answered"] = True
        stamp = _iso_date(msg.get("Date"))
        return {
            "id": _message_id_token(folder, uid),
            "threadId": "",
            "mailboxIds": {folder: True},
            "keywords": keywords,
            "from": _addresses(msg.get("From")),
            "to": _addresses(msg.get("To")),
            "subject": _decode_header_text(msg.get("Subject")) or "",
            "receivedAt": stamp,
            "sentAt": stamp,
            "hasAttachment": bool(_attachments(msg)),
            "preview": " ".join(body.split())[:240],
            "size": size,
        }

    def list_messages(
        self,
        mailbox_id: str | None,
        query_text: str,
        position: int,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        folder = mailbox_id or "INBOX"
        client = self._connect()
        try:
            status, _ = client.select(_imap_quote(folder), readonly=True)
            if status != "OK":
                raise ZohoMailError(f"Zoho could not open the {folder} folder.")
            if query_text:
                safe = query_text.replace("\\", "\\\\").replace('"', '\\"')
                status, data = client.uid("search", None, "TEXT", f'"{safe}"')
            else:
                status, data = client.uid("search", None, "ALL")
            if status != "OK":
                raise ZohoMailError("Zoho mail search failed.")
            uids = (data[0] or b"").decode("ascii", errors="ignore").split()
            uids = list(reversed(uids))
            total = len(uids)
            selected = uids[position: position + limit]
            messages: list[dict[str, Any]] = []
            for uid in selected:
                try:
                    raw, flags, size = self._fetch_raw(client, uid, peek=True)
                    messages.append(self._summary(folder, uid, raw, flags, size))
                except ZohoMailError:
                    continue
            return messages, total
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def get_message(self, email_id: str) -> dict[str, Any]:
        folder, uid = _decode_message_id(email_id)
        client = self._connect()
        try:
            status, _ = client.select(_imap_quote(folder))
            if status != "OK":
                raise ZohoMailError(f"Zoho could not open the {folder} folder.")
            raw, flags, size = self._fetch_raw(client, uid, peek=True)
            msg = BytesParser(policy=policy.default).parsebytes(raw)
            body = _message_text(msg)
            result = self._summary(folder, uid, raw, flags, size)
            result.update(
                {
                    "cc": _addresses(msg.get("Cc")),
                    "bcc": _addresses(msg.get("Bcc")),
                    "replyTo": _addresses(msg.get("Reply-To")),
                    "messageId": [str(msg.get("Message-ID") or "").strip("<>")] if msg.get("Message-ID") else [],
                    "inReplyTo": [str(msg.get("In-Reply-To") or "").strip("<>")] if msg.get("In-Reply-To") else [],
                    "attachments": _attachments(msg),
                    "displayBody": body,
                }
            )
            return result
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def set_flag(self, email_id: str, flag: str, enabled: bool) -> None:
        folder, uid = _decode_message_id(email_id)
        client = self._connect()
        try:
            status, _ = client.select(_imap_quote(folder))
            if status != "OK":
                raise ZohoMailError(f"Zoho could not open the {folder} folder.")
            command = "+FLAGS.SILENT" if enabled else "-FLAGS.SILENT"
            status, _ = client.uid("store", uid, command, f"({flag})")
            if status != "OK":
                raise ZohoMailError("Zoho could not update that email.")
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def move_email(self, email_id: str, target_folder: str) -> None:
        folder, uid = _decode_message_id(email_id)
        client = self._connect()
        try:
            status, _ = client.select(_imap_quote(folder))
            if status != "OK":
                raise ZohoMailError(f"Zoho could not open the {folder} folder.")
            status, _ = client.uid("copy", uid, _imap_quote(target_folder))
            if status != "OK":
                raise ZohoMailError(f"Zoho could not move the email to {target_folder}.")
            client.uid("store", uid, "+FLAGS.SILENT", "(\\Deleted)")
            client.expunge()
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def destroy_email(self, email_id: str) -> None:
        folder, uid = _decode_message_id(email_id)
        client = self._connect()
        try:
            status, _ = client.select(_imap_quote(folder))
            if status != "OK":
                raise ZohoMailError(f"Zoho could not open the {folder} folder.")
            client.uid("store", uid, "+FLAGS.SILENT", "(\\Deleted)")
            client.expunge()
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def append_raw(self, folder: str, raw: bytes, flags: str | None = None) -> None:
        client = self._connect()
        try:
            flag_text = f"({flags})" if flags else None
            internal_date = imaplib.Time2Internaldate(datetime.now(timezone.utc))
            status, _ = client.append(_imap_quote(folder), flag_text, internal_date, raw)
            if status != "OK":
                raise ZohoMailError(f"Zoho could not save the email in {folder}.")
        except ZohoMailError:
            raise
        except Exception as exc:
            raise ZohoMailError(f"Zoho could not save the email in {folder}: {exc}") from exc
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def send_raw(self, raw: bytes) -> None:
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        to_recipients = getaddresses([msg.get("To") or ""])
        cc_recipients = getaddresses([msg.get("Cc") or ""])
        bcc_recipients = getaddresses([msg.get("Bcc") or ""])
        text_body = _message_text(msg)

        api_attachments: list[dict[str, Any]] = []
        for part in msg.walk():
            if part.is_multipart():
                continue
            filename = part.get_filename()
            disposition = (part.get_content_disposition() or "").lower()
            if not filename and disposition != "attachment":
                continue
            data = part.get_payload(decode=True) or b""
            api_attachments.append({
                "name": _decode_header_text(filename) or "attachment",
                "mime_type": part.get_content_type() or "application/octet-stream",
                "data": data,
            })

        headers: dict[str, str] = {}
        if msg.get("In-Reply-To"):
            headers["In-Reply-To"] = str(msg.get("In-Reply-To"))
        if msg.get("References"):
            headers["References"] = str(msg.get("References"))

        ok, detail = send_zeptomail_message(
            to_recipients,
            _decode_header_text(msg.get("Subject")) or "(No subject)",
            cc_recipients=cc_recipients,
            bcc_recipients=bcc_recipients,
            text_body=text_body or " ",
            attachments=api_attachments,
            from_name="Stage Starz Academy of Dance",
            mime_headers=headers,
            client_reference="stage-starz-email-center",
        )
        if not ok:
            raise ZohoMailError(f"ZeptoMail could not send the email: {detail}")

    def download_attachment(self, email_id: str, blob_id: str) -> tuple[bytes, str, str]:
        folder, uid = _decode_message_id(email_id)
        client = self._connect()
        try:
            status, _ = client.select(_imap_quote(folder), readonly=True)
            if status != "OK":
                raise ZohoMailError(f"Zoho could not open the {folder} folder.")
            raw, _flags, _size = self._fetch_raw(client, uid, peek=True)
            msg = BytesParser(policy=policy.default).parsebytes(raw)
            try:
                target_index = int(blob_id)
            except ValueError as exc:
                raise ZohoMailError("Attachment reference is invalid.") from exc
            for idx, part in enumerate(msg.walk()):
                if idx != target_index:
                    continue
                filename = _decode_header_text(part.get_filename()) or "attachment"
                payload = part.get_payload(decode=True) or b""
                return payload, part.get_content_type() or "application/octet-stream", filename
            raise ZohoMailError("Attachment not found.")
        finally:
            try:
                client.logout()
            except Exception:
                pass


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
        raise ZohoMailError("The form expired. Please reload the Email Center and try again.")


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
        return _find_role(mailboxes, "all") or _find_role(mailboxes, "inbox")
    by_role = _find_role(mailboxes, key)
    if by_role:
        return by_role
    for mailbox in mailboxes:
        if mailbox.get("id") == key:
            return mailbox
    return _find_role(mailboxes, "inbox")


def _folder_label(mailbox: dict[str, Any] | None, key: str) -> str:
    if key == "all" and mailbox and mailbox.get("role") == "all":
        return "All Mail"
    if key == "all":
        return "Inbox"
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
        raise ZohoMailError("Enter at least one recipient.")

    msg = EmailMessage(policy=policy.SMTP)
    msg["From"] = formataddr(("Stage Starz Academy of Dance", sender_email))
    if to_addresses:
        msg["To"] = ", ".join(formataddr(pair) if pair[0] else pair[1] for pair in to_addresses)
    if cc_addresses:
        msg["Cc"] = ", ".join(formataddr(pair) if pair[0] else pair[1] for pair in cc_addresses)
    if bcc_addresses:
        msg["Bcc"] = ", ".join(formataddr(pair) if pair[0] else pair[1] for pair in bcc_addresses)
    msg["Subject"] = " ".join((subject or "").replace("\r", " ").replace("\n", " ").split())[:500]
    msg["Message-ID"] = make_msgid(domain=sender_email.split("@", 1)[-1])
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
        if len(data) > 10 * 1024 * 1024 or total_size > 10 * 1024 * 1024:
            raise ZohoMailError("Attachments are limited to 10 MB total in the Stage Starz Email Center.")
        guessed = upload.mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, subtype = guessed.split("/", 1) if "/" in guessed else ("application", "octet-stream")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg.as_bytes()


def register_zoho_email_center(app, permission_required) -> None:
    if "zoho_email_center" in app.view_functions:
        return

    email_permission = permission_required("notifications")

    @app.get("/email", endpoint="stage_starz_email_shortcut")
    @email_permission
    def stage_starz_email_shortcut():
        return redirect(url_for("zoho_email_center"))

    @app.after_request
    def zoho_email_no_cache(response):
        if request.path.startswith("/admin/email"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    @app.get("/admin/email", endpoint="zoho_email_center")
    @email_permission
    def zoho_email_center():
        try:
            client = ZohoMailClient()
            mailboxes = client.mailboxes()
            folder_key = (request.args.get("folder") or "inbox").strip()
            selected = _mailbox_for_key(mailboxes, folder_key)
            if not selected:
                raise ZohoMailError("Zoho Inbox could not be located.")
            if folder_key != "all":
                folder_key = selected.get("role") or selected.get("id")
            q = (request.args.get("q") or "").strip()[:200]
            try:
                page = max(1, int(request.args.get("page") or "1"))
            except ValueError:
                page = 1
            limit = 50
            position = (page - 1) * limit
            messages, total = client.list_messages(selected.get("id"), q, position, limit)
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
        except ZohoMailError as exc:
            return render_template(
                "fastmail_email_center.html",
                mode="error",
                configured=False,
                error=str(exc),
                account_email=_configured_email(),
                mailboxes=[],
                csrf_token=_csrf(),
            ), 503

    @app.get("/admin/email/message/<email_id>", endpoint="zoho_email_message")
    @email_permission
    def zoho_email_message(email_id: str):
        try:
            client = ZohoMailClient()
            mailboxes = client.mailboxes()
            message = client.get_message(email_id)
            if "$seen" not in (message.get("keywords") or {}):
                try:
                    client.set_flag(email_id, "\\Seen", True)
                    message.setdefault("keywords", {})["$seen"] = True
                except ZohoMailError:
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
        except ZohoMailError as exc:
            flash(str(exc), "error")
            return redirect(url_for("zoho_email_center"))

    @app.route("/admin/email/compose", methods=["GET", "POST"], endpoint="zoho_email_compose")
    @email_permission
    def zoho_email_compose():
        try:
            client = ZohoMailClient()
            mailboxes = client.mailboxes()
            drafts = _find_role(mailboxes, "drafts") or client.ensure_role(mailboxes, "drafts")
            sent = _find_role(mailboxes, "sent") or client.ensure_role(mailboxes, "sent")

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

            if action == "draft":
                client.append_raw(drafts["id"], raw, "\\Draft")
                if old_draft_id:
                    try:
                        client.destroy_email(old_draft_id)
                    except ZohoMailError:
                        pass
                flash("Draft saved in Zoho Mail.", "success")
                return redirect(url_for("zoho_email_center", folder="drafts"))

            client.send_raw(raw)
            sent_copy_saved = True
            try:
                client.append_raw(sent["id"], raw, "\\Seen")
            except ZohoMailError:
                sent_copy_saved = False
            if old_draft_id:
                try:
                    client.destroy_email(old_draft_id)
                except ZohoMailError:
                    pass
            if reply_to_id:
                try:
                    client.set_flag(reply_to_id, "\\Answered", True)
                except ZohoMailError:
                    pass
            if sent_copy_saved:
                flash("Email sent from office@stagestarzdance.com and saved in Zoho Sent.", "success")
                return redirect(url_for("zoho_email_center", folder="sent"))
            flash("Email was sent successfully, but Zoho could not save the Sent copy.", "error")
            return redirect(url_for("zoho_email_center", folder="inbox"))
        except ZohoMailError as exc:
            flash(str(exc), "error")
            if request.method == "POST":
                return redirect(url_for("zoho_email_compose"))
            return redirect(url_for("zoho_email_center"))

    @app.post("/admin/email/message/<email_id>/action", endpoint="zoho_email_action")
    @email_permission
    def zoho_email_action(email_id: str):
        try:
            _check_csrf()
            client = ZohoMailClient()
            mailboxes = client.mailboxes()
            action = (request.form.get("action") or "").strip().lower()
            if action in {"archive", "trash", "junk", "inbox"}:
                target = _find_role(mailboxes, action)
                if not target:
                    target = client.ensure_role(mailboxes, action)
                client.move_email(email_id, target["id"])
            elif action == "unread":
                client.set_flag(email_id, "\\Seen", False)
            elif action == "read":
                client.set_flag(email_id, "\\Seen", True)
            elif action == "flag":
                client.set_flag(email_id, "\\Flagged", True)
            elif action == "unflag":
                client.set_flag(email_id, "\\Flagged", False)
            elif action == "delete":
                client.destroy_email(email_id)
            else:
                raise ZohoMailError("Unknown email action.")
            flash("Email updated.", "success")
        except ZohoMailError as exc:
            flash(str(exc), "error")
        return redirect(url_for("zoho_email_center", folder=request.form.get("return_folder") or "inbox"))

    @app.get(
        "/admin/email/attachment/<email_id>/<blob_id>/<path:filename>",
        endpoint="zoho_email_attachment",
    )
    @email_permission
    def zoho_email_attachment(email_id: str, blob_id: str, filename: str):
        try:
            client = ZohoMailClient()
            data, content_type, actual_name = client.download_attachment(email_id, blob_id)
            safe_name = os.path.basename(actual_name or filename or "attachment")
            response = Response(data, mimetype=content_type)
            encoded = urllib.parse.quote(safe_name)
            response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded}"
            return response
        except ZohoMailError as exc:
            flash(str(exc), "error")
            return redirect(url_for("zoho_email_message", email_id=email_id))
