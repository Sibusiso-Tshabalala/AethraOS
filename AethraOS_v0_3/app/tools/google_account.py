"""
Google sign-in and in-thread drafts.

Place the OAuth desktop client file at data/google_credentials.json.
Aethra stores the token at data/google_token.json.
Drafts are created in the real Gmail thread. Nothing is sent.
"""

from __future__ import annotations

import base64
import os
from email.mime.text import MIMEText
from typing import Any, Dict, List

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _paths():
    data = os.path.join(os.getcwd(), "data")
    os.makedirs(data, exist_ok=True)
    return (
        os.path.join(data, "google_credentials.json"),
        os.path.join(data, "google_token.json"),
    )


def connect_google() -> Dict[str, Any]:
    cred_path, token_path = _paths()
    if not os.path.isfile(cred_path):
        return {
            "success": False,
            "verified": False,
            "error": (
                "Missing data/google_credentials.json. "
                "In Google Cloud, create an OAuth desktop client and download that file."
            ),
        }
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        return {
            "success": False,
            "verified": False,
            "error": "pip install google-api-python-client google-auth-oauthlib google-auth-httplib2",
        }
    creds = None
    if os.path.isfile(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as handle:
            handle.write(creds.to_json())
    return {"success": True, "verified": True, "message": "Google account connected. Token saved locally."}


def _service(name: str, version: str):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    _, token_path = _paths()
    if not os.path.isfile(token_path):
        raise RuntimeError("Google is not connected. Call connect_google first.")
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    return build(name, version, credentials=creds)


def list_google_threads(limit: int = 5) -> Dict[str, Any]:
    try:
        service = _service("gmail", "v1")
        result = service.users().threads().list(userId="me", maxResults=max(1, min(int(limit or 5), 10))).execute()
        threads = []
        for item in result.get("threads", []):
            full = service.users().threads().get(userId="me", id=item["id"], format="metadata").execute()
            messages = full.get("messages", [])
            headers = {h["name"]: h["value"] for h in messages[-1].get("payload", {}).get("headers", [])} if messages else {}
            threads.append({
                "thread_id": item["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "snippet": full.get("snippet", ""),
            })
        return {"success": True, "verified": True, "threads": threads, "count": len(threads)}
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}


def reply_in_gmail_thread(thread_id: str, body: str) -> Dict[str, Any]:
    """Create a draft reply inside the Gmail thread. Does not send."""
    try:
        service = _service("gmail", "v1")
        thread = service.users().threads().get(userId="me", id=thread_id, format="metadata").execute()
        last = thread["messages"][-1]
        headers = {h["name"]: h["value"] for h in last.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        to_addr = headers.get("Reply-To") or headers.get("From", "")
        message = MIMEText(body or "")
        message["to"] = to_addr
        message["subject"] = subject
        if headers.get("Message-ID"):
            message["In-Reply-To"] = headers["Message-ID"]
            message["References"] = headers["Message-ID"]
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw, "threadId": thread_id}},
        ).execute()
        return {
            "success": True,
            "verified": True,
            "sent": False,
            "draft_id": draft.get("id"),
            "thread_id": thread_id,
            "to": to_addr,
            "subject": subject,
            "message": "Draft reply created inside the Gmail thread. It was not sent.",
        }
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}


def list_google_events(limit: int = 5) -> Dict[str, Any]:
    try:
        service = _service("calendar", "v3")
        result = service.events().list(
            calendarId="primary",
            maxResults=max(1, min(int(limit or 5), 10)),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = []
        for item in result.get("items", []):
            events.append({
                "summary": item.get("summary", ""),
                "start": (item.get("start") or {}).get("dateTime") or (item.get("start") or {}).get("date"),
            })
        return {"success": True, "verified": True, "events": events, "count": len(events)}
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}


def reply_in_outlook_thread(subject: str, body: str) -> Dict[str, Any]:
    """Open a reply on the matching Outlook message. Does not send."""
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return {"success": False, "verified": False, "error": "pywin32 is not installed."}
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)
        needle = (subject or "").lower()
        for item in items:
            found = str(getattr(item, "Subject", "") or "")
            if needle and needle not in found.lower():
                continue
            reply = item.Reply()
            reply.Body = (body or "") + "\n\n" + str(reply.Body or "")
            reply.Display()
            return {
                "success": True,
                "verified": True,
                "sent": False,
                "subject": found,
                "message": "Outlook reply window opened in the thread. It was not sent.",
            }
        return {"success": False, "verified": False, "error": "No matching Outlook message."}
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}


def send_gmail_draft(draft_id: str, approved: bool = False) -> Dict[str, Any]:
    """Send a Gmail API draft only after explicit approval."""
    if not approved:
        return {
            "success": False,
            "verified": False,
            "sent": False,
            "error": "Send blocked. Call again with approved=true only after the user confirms the exact text.",
        }
    try:
        service = _service("gmail", "v1")
        sent = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
        return {
            "success": True,
            "verified": True,
            "sent": True,
            "id": sent.get("id"),
            "message": "Gmail draft sent after confirmation.",
        }
    except Exception as exc:
        return {"success": False, "verified": False, "sent": False, "error": str(exc)}
