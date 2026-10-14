"""Simple local calendar. Offline SQLite. No Google/Outlook yet."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.tools.scheduler import SchedulerStore


def _db_path() -> str:
    root = os.getcwd()
    data = os.path.join(root, "data")
    os.makedirs(data, exist_ok=True)
    return os.path.join(data, "aethra_calendar.db")


class LocalCalendar:
    def __init__(self, database_path: Optional[str] = None):
        self.database_path = database_path or _db_path()
        self._init()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _init(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    notes TEXT,
                    start_at TEXT NOT NULL,
                    end_at TEXT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled'
                )
                """
            )
            conn.commit()

    def add_event(self, title: str, when: str, notes: str = "", duration_minutes: int = 60) -> Dict[str, Any]:
        title = str(title or "").strip()
        if not title:
            return {"success": False, "verified": False, "error": "Event title is required."}
        parsed = SchedulerStore.parse_when(when)
        if not parsed.get("success"):
            return {"success": False, "verified": False, "error": parsed.get("error")}
        start = parsed["due_at"]
        try:
            minutes = int(duration_minutes or 60)
        except Exception:
            minutes = 60
        end = start + timedelta(minutes=max(15, minutes))
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO events (title, notes, start_at, end_at, created_at, status)
                VALUES (?, ?, ?, ?, ?, 'scheduled')
                """,
                (title, notes or "", start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), now),
            )
            conn.commit()
            eid = cur.lastrowid
        return {
            "success": True,
            "verified": True,
            "id": eid,
            "title": title,
            "start_at": start.isoformat(timespec="seconds"),
            "end_at": end.isoformat(timespec="seconds"),
            "message": f"Event '{title}' added for {start.strftime('%Y-%m-%d %H:%M')}.",
        }

    def agenda(self, day: str = "today") -> Dict[str, Any]:
        now = datetime.now()
        day = (day or "today").strip().lower()
        if day == "tomorrow":
            start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE status = 'scheduled' AND start_at >= ? AND start_at < ?
                ORDER BY start_at ASC
                """,
                (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
            ).fetchall()
        items = [dict(r) for r in rows]
        return {
            "success": True,
            "verified": True,
            "day": day,
            "count": len(items),
            "events": items,
            "message": f"{len(items)} event(s) on {day}.",
        }

    def cancel_event(self, event_id: int) -> Dict[str, Any]:
        try:
            event_id = int(event_id)
        except Exception:
            return {"success": False, "verified": False, "error": "id must be an integer."}
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE events SET status = 'cancelled' WHERE id = ? AND status = 'scheduled'",
                (event_id,),
            )
            conn.commit()
        if cur.rowcount == 0:
            return {"success": False, "verified": False, "error": f"No event id={event_id}."}
        return {"success": True, "verified": True, "id": event_id, "message": f"Cancelled event #{event_id}."}


_cal: Optional[LocalCalendar] = None


def _store() -> LocalCalendar:
    global _cal
    if _cal is None:
        _cal = LocalCalendar()
    return _cal


def add_calendar_event(title: str, when: str, notes: str = "", duration_minutes: int = 60) -> Dict[str, Any]:
    return _store().add_event(title, when, notes, duration_minutes)


def get_agenda(day: str = "today") -> Dict[str, Any]:
    return _store().agenda(day)


def cancel_calendar_event(id: int) -> Dict[str, Any]:
    return _store().cancel_event(id)