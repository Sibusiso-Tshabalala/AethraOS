"""
Gmail draft-with-approval.

Does not send mail. Stores a local draft and, only after the user
approves, opens a Gmail compose window prefilled with that draft.
The user must press Send in Gmail themselves.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import quote


def _db_path() -> str:
    data = os.path.join(os.getcwd(), "data")
    os.makedirs(data, exist_ok=True)
    return os.path.join(data, "aethra_mail_drafts.db")


class DraftStore:
    def __init__(self):
        self.path = _db_path()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    to_addr TEXT,
                    subject TEXT,
                    body TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def create(self, to_addr: str, subject: str, body: str) -> Dict[str, Any]:
        to_addr = str(to_addr or "").strip()
        subject = str(subject or "").strip()
        body = str(body or "").strip()
        if not body:
            return {"success": False, "verified": False, "error": "Draft body is empty."}
        now = datetime.now().isoformat(timespec="seconds")
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute(
                "INSERT INTO drafts (to_addr, subject, body, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
                (to_addr, subject, body, now),
            )
            conn.commit()
            did = cur.lastrowid
        return {
            "success": True,
            "verified": True,
            "id": did,
            "status": "pending",
            "to": to_addr,
            "subject": subject,
            "body": body,
            "message": (
                f"Draft #{did} saved. Show this to the user. "
                "Do not send. Call open_gmail_draft only after they approve."
            ),
        }

    def get(self, draft_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM drafts WHERE id = ?", (int(draft_id),)).fetchone()
        return dict(row) if row else None

    def list_pending(self) -> Dict[str, Any]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, to_addr, subject, status, created_at FROM drafts WHERE status = 'pending' ORDER BY id DESC LIMIT 10"
            ).fetchall()
        items = [dict(r) for r in rows]
        return {"success": True, "verified": True, "count": len(items), "drafts": items}

    def mark(self, draft_id: int, status: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE drafts SET status = ? WHERE id = ?", (status, int(draft_id)))
            conn.commit()


_store: Optional[DraftStore] = None


def _get() -> DraftStore:
    global _store
    if _store is None:
        _store = DraftStore()
    return _store


def create_gmail_draft(to: str, subject: str, body: str) -> Dict[str, Any]:
    return _get().create(to, subject, body)


def list_gmail_drafts() -> Dict[str, Any]:
    return _get().list_pending()


def open_gmail_draft(id: int, approved: bool = False) -> Dict[str, Any]:
    """
    Open Gmail compose with the draft only if approved is true.
    Never clicks Send.
    """
    if not approved:
        return {
            "success": False,
            "verified": False,
            "error": "User approval is required. Set approved=true only after they confirm the draft text.",
        }
    draft = _get().get(id)
    if not draft:
        return {"success": False, "verified": False, "error": f"No draft #{id}."}
    url = (
        "https://mail.google.com/mail/?view=cm&fs=1"
        f"&to={quote(draft.get('to_addr') or '')}"
        f"&su={quote(draft.get('subject') or '')}"
        f"&body={quote(draft.get('body') or '')}"
    )
    try:
        from app.tools.computer import open_url
        opened = open_url(url, browser="chrome")
    except Exception as exc:
        opened = {"success": False, "error": str(exc)}
    _get().mark(id, "opened_for_review")
    return {
        "success": bool(opened.get("success")),
        "verified": bool(opened.get("success")),
        "draft_id": id,
        "url_opened": True,
        "sent": False,
        "message": (
            "Gmail compose opened with the draft. "
            "Aethra did not send it. The user must press Send."
        ),
        "open_result": opened,
    }