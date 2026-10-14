"""What did I miss? Local digest of reminders, calendar, windows, drafts."""

from __future__ import annotations

from typing import Any, Dict


def what_did_i_miss() -> Dict[str, Any]:
    parts = []

    try:
        from app.tools.scheduler import list_reminders
        reminders = list_reminders(include_fired=False, limit=8)
        parts.append({"reminders": reminders.get("items", [])})
    except Exception as exc:
        parts.append({"reminders_error": str(exc)})

    try:
        from app.tools.calendar_local import get_agenda
        today = get_agenda("today")
        tomorrow = get_agenda("tomorrow")
        parts.append({
            "today": today.get("events", []),
            "tomorrow": tomorrow.get("events", []),
        })
    except Exception as exc:
        parts.append({"calendar_error": str(exc)})

    try:
        from app.tools.gmail_draft import list_gmail_drafts
        drafts = list_gmail_drafts()
        parts.append({"pending_drafts": drafts.get("drafts", [])})
    except Exception as exc:
        parts.append({"drafts_error": str(exc)})

    try:
        from app.tools.computer import list_open_windows
        windows = list_open_windows()
        titles = [w.get("title") for w in (windows.get("windows") or [])[:12]]
        parts.append({"open_windows": titles})
    except Exception as exc:
        parts.append({"windows_error": str(exc)})

    return {
        "success": True,
        "verified": True,
        "digest": parts,
        "message": "Local catch-up digest ready. Summarize this for the user in plain language.",
    }