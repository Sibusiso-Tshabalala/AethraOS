"""
Side mail draft.

Opens the related thread in the browser and saves a draft.
Does not send. Safe to run while the user keeps coding.
"""

from __future__ import annotations

from typing import Any, Dict
from urllib.parse import quote


def draft_reply_on_side(to: str, subject: str, body: str, source: str = "gmail") -> Dict[str, Any]:
    from app.tools.gmail_draft import create_gmail_draft

    draft = create_gmail_draft(to, subject if subject.lower().startswith("re:") else f"Re: {subject}", body)
    if not draft.get("success"):
        return draft
    query = quote(subject or "")
    if (source or "gmail").lower().startswith("outlook"):
        url = f"https://outlook.office.com/mail/search?q={query}"
    else:
        url = f"https://mail.google.com/mail/u/0/#search/{query}"
    opened = {"success": False}
    try:
        from app.tools.computer import open_url
        opened = open_url(url, browser="chrome")
    except Exception as exc:
        opened = {"success": False, "error": str(exc)}
    return {
        "success": True,
        "verified": True,
        "sent": False,
        "draft": draft,
        "thread_opened": bool(opened.get("success")),
        "message": "Thread search opened and draft saved. Nothing was sent. Show the draft and wait for approval.",
    }


def import_google_calendar_url(url: str, limit: int = 30) -> Dict[str, Any]:
    """Download a secret Google/Outlook ICS URL into the local calendar."""
    import os
    import tempfile
    import urllib.request
    from app.tools.calendar_sync import import_ics

    url = str(url or "").strip()
    if not url.startswith("https://") or not url.endswith(".ics") and "ical" not in url and ".ics" not in url:
        return {"success": False, "verified": False, "error": "Provide an https secret iCal address."}
    try:
        fd, path = tempfile.mkstemp(suffix=".ics")
        os.close(fd)
        urllib.request.urlretrieve(url, path)
        result = import_ics(path, limit=limit)
        os.remove(path)
        result["source"] = "calendar_url"
        return result
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}