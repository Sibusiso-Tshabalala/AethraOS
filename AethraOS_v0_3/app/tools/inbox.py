"""
Read inbox without sending mail.

- Outlook desktop via COM if Outlook and pywin32 are installed
- Gmail via IMAP only if GMAIL_USER and GMAIL_APP_PASSWORD are set

Drafts still go through create_gmail_draft. Nothing here sends.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List


def read_outlook_inbox(limit: int = 5) -> Dict[str, Any]:
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return {
            "success": False,
            "verified": False,
            "error": "pywin32 is not installed. pip install pywin32 and open Outlook once.",
        }
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)  # olFolderInbox
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)
        messages: List[Dict[str, Any]] = []
        count = 0
        for item in items:
            if count >= max(1, min(int(limit or 5), 15)):
                break
            try:
                messages.append({
                    "from": str(getattr(item, "SenderName", "") or ""),
                    "subject": str(getattr(item, "Subject", "") or ""),
                    "received": str(getattr(item, "ReceivedTime", "") or ""),
                    "preview": str(getattr(item, "Body", "") or "")[:500],
                    "unread": bool(getattr(item, "UnRead", False)),
                })
                count += 1
            except Exception:
                continue
        return {
            "success": True,
            "verified": True,
            "source": "outlook_desktop",
            "count": len(messages),
            "messages": messages,
            "message": f"Read {len(messages)} Outlook message(s). Do not send a reply without approval.",
        }
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}


def read_gmail_inbox(limit: int = 5) -> Dict[str, Any]:
    user = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not user or not password:
        return {
            "success": False,
            "verified": False,
            "error": (
                "Gmail is not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD "
                "(Google app password) in the environment, or use read_outlook_inbox."
            ),
        }
    try:
        import imaplib
        import email
        from email.header import decode_header

        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, password)
        mail.select("inbox")
        status, data = mail.search(None, "ALL")
        ids = (data[0] or b"").split()
        ids = ids[-max(1, min(int(limit or 5), 15)):]
        messages = []
        for mid in reversed(ids):
            status, msg_data = mail.fetch(mid, "(RFC822)")
            raw = msg_data[0][1]
            parsed = email.message_from_bytes(raw)
            subject = parsed.get("Subject", "")
            decoded = decode_header(subject)[0]
            if isinstance(decoded[0], bytes):
                subject = decoded[0].decode(decoded[1] or "utf-8", errors="ignore")
            else:
                subject = str(decoded[0])
            body = ""
            if parsed.is_multipart():
                for part in parsed.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                payload = parsed.get_payload(decode=True)
                body = payload.decode(errors="ignore") if payload else ""
            messages.append({
                "from": parsed.get("From", ""),
                "subject": subject,
                "preview": body[:500],
            })
        mail.logout()
        return {
            "success": True,
            "verified": True,
            "source": "gmail_imap",
            "count": len(messages),
            "messages": messages,
            "message": f"Read {len(messages)} Gmail message(s). Draft a reply; do not send.",
        }
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}