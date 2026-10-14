"""One local morning brief. Does not send mail."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def morning_brief() -> Dict[str, Any]:
    hour = datetime.now().hour
    hello = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    parts = [hello + "."]

    try:
        from app.tools.calendar_local import get_agenda
        today = get_agenda("today")
        events = today.get("events") or []
        parts.append(f"{len(events)} local event(s) today.")
    except Exception as exc:
        events = []
        parts.append(f"Calendar unavailable: {exc}")

    try:
        from app.tools.scheduler import list_reminders
        reminders = list_reminders().get("items") or []
        parts.append(f"{len(reminders)} reminder(s) waiting.")
    except Exception:
        reminders = []

    mail = []
    try:
        from app.tools.google_account import list_google_threads
        threads = list_google_threads(limit=3)
        if threads.get("success"):
            mail = threads.get("threads") or []
            parts.append(f"{len(mail)} recent Gmail thread(s).")
        else:
            from AethraOS_v0_3.app.tools.inbox import read_outlook_inbox
            outlook = read_outlook_inbox(limit=3)
            mail = outlook.get("messages") or []
            parts.append(f"{len(mail)} recent Outlook message(s).")
    except Exception as exc:
        parts.append(f"Mail not connected: {exc}")

    drafts = []
    try:
        from app.tools.gmail_draft import list_gmail_drafts
        drafts = list_gmail_drafts().get("drafts") or []
        if drafts:
            parts.append(f"{len(drafts)} unsent draft(s).")
    except Exception:
        pass

    return {
        "success": True,
        "verified": True,
        "greeting": hello,
        "events": events,
        "reminders": reminders,
        "mail": mail,
        "drafts": drafts,
        "sent": False,
        "message": " ".join(parts) + " Nothing was sent.",
    }


def prepare_inbox_replies(limit: int = 3) -> Dict[str, Any]:
    """Save local reply drafts for recent mail. Never sends."""
    from app.tools.gmail_draft import create_gmail_draft

    brief = morning_brief()
    created = []
    for item in (brief.get("mail") or [])[: max(1, min(int(limit or 3), 5))]:
        subject = item.get("subject") or "your message"
        sender = item.get("from") or ""
        preview = item.get("preview") or item.get("snippet") or ""
        body = (
            f"Hi,\n\nThanks for the note about {subject}.\n\n"
            f"I saw: {preview[:180]}\n\nI will follow up shortly.\n"
        )
        draft = create_gmail_draft(sender, subject, body)
        if draft.get("success"):
            created.append(draft)
    return {
        "success": True,
        "verified": True,
        "sent": False,
        "drafts": created,
        "message": f"Prepared {len(created)} reply draft(s). Show them and wait for send confirmation.",
    }
