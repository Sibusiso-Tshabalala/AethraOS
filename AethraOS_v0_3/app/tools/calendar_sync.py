"""
Calendar sync into the local Aethra calendar.

Supported without extra accounts:
- Import a Google or Outlook .ics file (secret address or exported file)
- Read the local Outlook desktop calendar if pywin32 is installed

Does not upload events. Does not require Google OAuth in this version.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List

from app.tools.calendar_local import add_calendar_event


def _unfold_ics(text: str) -> str:
    return text.replace("\r\n ", "").replace("\n ", "").replace("\r\n\t", "")


def _parse_ics_datetime(value: str):
    value = (value or "").strip()
    if value.endswith("Z"):
        value = value[:-1]
    value = value.split(";")[0]
    for fmt, size in (("%Y%m%dT%H%M%S", 15), ("%Y%m%dT%H%M", 13), ("%Y%m%d", 8)):
        try:
            return datetime.strptime(value[:size], fmt)
        except Exception:
            continue
    return None


def import_ics(path: str, limit: int = 30) -> Dict[str, Any]:
    """Import VEVENT items from an .ics file into the local calendar."""
    path = str(path or "").strip().strip('"')
    if not path or not os.path.isfile(path):
        return {"success": False, "verified": False, "error": f"ICS file not found: {path}"}
    try:
        raw = open(path, "r", encoding="utf-8", errors="ignore").read()
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}

    text = _unfold_ics(raw)
    blocks = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, flags=re.S | re.I)
    imported = []
    for block in blocks[: max(1, min(int(limit or 30), 100))]:
        summary = ""
        start = ""
        notes = ""
        sm = re.search(r"SUMMARY:(.+)", block)
        dt = re.search(r"DTSTART[^:]*:(.+)", block)
        desc = re.search(r"DESCRIPTION:(.+)", block)
        if sm:
            summary = sm.group(1).strip()
        if dt:
            start = dt.group(1).strip()
        if desc:
            notes = desc.group(1).strip()[:300]
        parsed = _parse_ics_datetime(start) if start else None
        if not summary or not parsed:
            continue
        when = parsed.strftime("%Y-%m-%d %H:%M")
        result = add_calendar_event(summary, when, notes=notes or "Imported from ICS")
        if result.get("success"):
            imported.append({"title": summary, "when": when, "id": result.get("id")})
    return {
        "success": True,
        "verified": True,
        "imported": len(imported),
        "events": imported,
        "message": f"Imported {len(imported)} event(s) from {os.path.basename(path)} into the local calendar.",
    }


def sync_outlook_desktop(days_ahead: int = 7, limit: int = 20) -> Dict[str, Any]:
    """
    Read upcoming appointments from the local Outlook desktop app.
    Requires Outlook installed and pywin32. Does not touch Outlook.com directly.
    """
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return {
            "success": False,
            "verified": False,
            "error": "pywin32 is not installed, or this is not Windows. pip install pywin32, then open Outlook once.",
        }
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        calendar = outlook.GetDefaultFolder(9)  # olFolderCalendar
        items = calendar.Items
        items.Sort("[Start]")
        items.IncludeRecurrences = True
        now = datetime.now()
        end = datetime.now().replace(hour=23, minute=59)
        imported: List[Dict[str, Any]] = []
        count = 0
        for item in items:
            if count >= limit:
                break
            try:
                start = item.Start
                start_dt = datetime(start.year, start.month, start.day, start.hour, start.minute)
            except Exception:
                continue
            if start_dt < now:
                continue
            if (start_dt - now).days > int(days_ahead or 7):
                break
            title = str(getattr(item, "Subject", "") or "Outlook event")
            when = start_dt.strftime("%Y-%m-%d %H:%M")
            result = add_calendar_event(title, when, notes="Synced from Outlook desktop")
            if result.get("success"):
                imported.append({"title": title, "when": when, "id": result.get("id")})
                count += 1
        return {
            "success": True,
            "verified": True,
            "imported": len(imported),
            "events": imported,
            "message": f"Synced {len(imported)} Outlook desktop event(s) into the local calendar.",
        }
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}