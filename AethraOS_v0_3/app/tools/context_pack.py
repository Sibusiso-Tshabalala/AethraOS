"""
Cross-app context pack.

Looks at the active window, recent files, memory, calendar, and drafts
so Aethra can relate what the user is doing to a doc or email.
Does not send mail.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List


def _recent_files(limit: int = 8) -> List[Dict[str, str]]:
    home = os.path.expanduser("~")
    folders = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Desktop"),
    ]
    found = []
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        try:
            names = os.listdir(folder)
        except Exception:
            continue
        for name in names:
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            if not name.lower().endswith((".py", ".txt", ".md", ".docx", ".pdf", ".xlsx", ".csv")):
                continue
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                continue
            found.append({"name": name, "path": path, "mtime": mtime, "folder": os.path.basename(folder)})
    found.sort(key=lambda item: item["mtime"], reverse=True)
    out = []
    for item in found[:limit]:
        out.append({
            "name": item["name"],
            "path": item["path"],
            "folder": item["folder"],
            "modified": datetime.fromtimestamp(item["mtime"]).strftime("%Y-%m-%d %H:%M"),
        })
    return out


def build_context_pack(topic: str = "") -> Dict[str, Any]:
    topic = str(topic or "").strip()
    active = {}
    try:
        from app.tools.applications import get_active_window
        active = get_active_window() or {}
    except Exception as exc:
        active = {"error": str(exc)}

    files = _recent_files()
    memories = []
    try:
        from app.agent.memory import MemoryStore
        query = topic or (active.get("window_title") if isinstance(active, dict) else "") or ""
        if query:
            memories = MemoryStore().search(query, limit=5)
    except Exception:
        memories = []

    agenda = {}
    try:
        from app.tools.calendar_local import get_agenda
        agenda = get_agenda("today")
    except Exception as exc:
        agenda = {"error": str(exc)}

    drafts = {}
    try:
        from app.tools.gmail_draft import list_gmail_drafts
        drafts = list_gmail_drafts()
    except Exception as exc:
        drafts = {"error": str(exc)}

    title = ""
    if isinstance(active, dict):
        title = active.get("window_title") or ""

    suggestions = []
    if title:
        suggestions.append(f"Active window: {title}")
    if files:
        suggestions.append(f"Most recent file: {files[0]['name']}")
    if isinstance(drafts, dict) and drafts.get("drafts"):
        suggestions.append("There is a pending mail draft waiting for approval.")
    if isinstance(agenda, dict) and agenda.get("events"):
        suggestions.append(f"{agenda.get('count', 0)} event(s) on today's calendar.")

    return {
        "success": True,
        "verified": True,
        "topic": topic,
        "active_window": title,
        "recent_files": files,
        "memories": memories,
        "today": agenda.get("events", []) if isinstance(agenda, dict) else [],
        "pending_drafts": drafts.get("drafts", []) if isinstance(drafts, dict) else [],
        "suggestions": suggestions,
        "message": "Context pack ready. Use it to open a related file or draft mail. Do not send mail.",
    }