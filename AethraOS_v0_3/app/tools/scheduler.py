"""
Local reminders and alarms for AethraOS.

Fully offline. Stored in SQLite under data/aethra_scheduler.db.
A background checker (UI timer or poll) calls due items and marks them fired.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _db_path() -> str:
    root = os.getcwd()
    data = os.path.join(root, "data")
    os.makedirs(data, exist_ok=True)
    return os.path.join(data, "aethra_scheduler.db")


class SchedulerStore:
    def __init__(self, database_path: Optional[str] = None):
        self.database_path = database_path or _db_path()
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    message TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    fired_at TEXT
                )
                """
            )
            conn.commit()

    # --------------------------------------------------
    # TIME PARSING (simple natural phrases)
    # --------------------------------------------------

    @staticmethod
    def parse_when(when: str, now: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Parse simple time expressions into a datetime.

        Supported examples:
        - in 5 minutes / in 2 hours / in 1 day
        - at 9:00 / at 9am / at 21:30
        - tomorrow at 9am
        - 2026-10-06 14:30
        """
        now = now or datetime.now()
        text = (when or "").strip().lower()
        if not text:
            return {"success": False, "error": "Time expression is empty."}

        # Absolute ISO-like
        for fmt in (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(text, fmt)
                return {"success": True, "due_at": dt, "parsed_from": text}
            except ValueError:
                pass

        # in N units
        m = re.match(
            r"in\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs|day|days|second|seconds|sec|secs)\b",
            text,
        )
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            if unit.startswith("sec"):
                delta = timedelta(seconds=n)
            elif unit.startswith("min"):
                delta = timedelta(minutes=n)
            elif unit.startswith("hour") or unit.startswith("hr"):
                delta = timedelta(hours=n)
            else:
                delta = timedelta(days=n)
            dt = now + delta
            return {"success": True, "due_at": dt, "parsed_from": text}

        tomorrow = text.startswith("tomorrow")
        base = now + timedelta(days=1) if tomorrow else now
        time_part = text
        if tomorrow:
            time_part = re.sub(r"^tomorrow\s*(at\s*)?", "", text).strip()
            if not time_part:
                # tomorrow morning default 9:00
                dt = base.replace(hour=9, minute=0, second=0, microsecond=0)
                return {"success": True, "due_at": dt, "parsed_from": text}

        # at 9 / at 9am / at 9:30 pm
        m = re.match(
            r"(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
            time_part,
        )
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2) or 0)
            ampm = m.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
            if hour > 23 or minute > 59:
                return {"success": False, "error": f"Invalid time: {when}"}
            dt = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if not tomorrow and dt <= now:
                dt = dt + timedelta(days=1)
            return {"success": True, "due_at": dt, "parsed_from": text}

        return {
            "success": False,
            "error": (
                "Could not parse time. Try: 'in 10 minutes', "
                "'at 9:30am', 'tomorrow at 2pm', or '2026-10-06 14:30'."
            ),
        }

    # --------------------------------------------------
    # CRUD
    # --------------------------------------------------

    def add(
        self,
        message: str,
        when: str,
        kind: str = "reminder",
    ) -> Dict[str, Any]:
        message = str(message or "").strip()
        if not message:
            return {
                "success": False,
                "verified": False,
                "error": "Reminder message cannot be empty.",
            }

        kind = (kind or "reminder").strip().lower()
        if kind not in ("reminder", "alarm"):
            kind = "reminder"

        parsed = self.parse_when(when)
        if not parsed.get("success"):
            return {
                "success": False,
                "verified": False,
                "error": parsed.get("error", "Invalid time"),
            }

        due_at: datetime = parsed["due_at"]
        created = datetime.now()

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO reminders (kind, message, due_at, created_at, status)
                VALUES (?, ?, ?, ?, 'scheduled')
                """,
                (
                    kind,
                    message,
                    due_at.isoformat(timespec="seconds"),
                    created.isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
            item_id = cur.lastrowid

        return {
            "success": True,
            "verified": True,
            "id": item_id,
            "kind": kind,
            "message": message,
            "due_at": due_at.isoformat(timespec="seconds"),
            "message_text": (
                f"{kind.title()} set for "
                f"{due_at.strftime('%Y-%m-%d %H:%M')}: {message}"
            ),
        }

    def list_items(
        self,
        include_fired: bool = False,
        limit: int = 20,
    ) -> Dict[str, Any]:
        limit = max(1, min(int(limit or 20), 50))
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if include_fired:
                rows = conn.execute(
                    """
                    SELECT * FROM reminders
                    ORDER BY due_at ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM reminders
                    WHERE status = 'scheduled'
                    ORDER BY due_at ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        items = [dict(r) for r in rows]
        return {
            "success": True,
            "verified": True,
            "count": len(items),
            "items": items,
            "message": f"Found {len(items)} reminder/alarm item(s).",
        }

    def cancel(self, item_id: int) -> Dict[str, Any]:
        try:
            item_id = int(item_id)
        except Exception:
            return {
                "success": False,
                "verified": False,
                "error": "id must be an integer.",
            }

        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE reminders
                SET status = 'cancelled'
                WHERE id = ? AND status = 'scheduled'
                """,
                (item_id,),
            )
            conn.commit()
            if cur.rowcount == 0:
                return {
                    "success": False,
                    "verified": False,
                    "error": f"No scheduled item with id={item_id}.",
                }

        return {
            "success": True,
            "verified": True,
            "id": item_id,
            "message": f"Cancelled item #{item_id}.",
        }

    def get_due(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        now = now or datetime.now()
        now_s = now.isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM reminders
                WHERE status = 'scheduled' AND due_at <= ?
                ORDER BY due_at ASC
                """,
                (now_s,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_fired(self, item_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET status = 'fired', fired_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(timespec="seconds"), int(item_id)),
            )
            conn.commit()


# Module-level helpers for tool calling

_store: Optional[SchedulerStore] = None


def _get_store() -> SchedulerStore:
    global _store
    if _store is None:
        _store = SchedulerStore()
    return _store


def create_reminder(message: str, when: str) -> Dict[str, Any]:
    return _get_store().add(message=message, when=when, kind="reminder")


def create_alarm(message: str, when: str) -> Dict[str, Any]:
    return _get_store().add(message=message, when=when, kind="alarm")


def list_reminders(include_fired: bool = False, limit: int = 20) -> Dict[str, Any]:
    return _get_store().list_items(include_fired=include_fired, limit=limit)


def cancel_reminder(id: int) -> Dict[str, Any]:
    return _get_store().cancel(id)


def check_due_reminders() -> Dict[str, Any]:
    """
    Return due items and mark them fired.
    Called by the UI background timer.
    """
    store = _get_store()
    due = store.get_due()
    fired = []
    for item in due:
        store.mark_fired(item["id"])
        fired.append(item)
    return {
        "success": True,
        "verified": True,
        "count": len(fired),
        "items": fired,
    }