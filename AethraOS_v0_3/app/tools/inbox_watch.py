"""Notice new Outlook mail. Suggest a plan. Do not open apps or send."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


def _path() -> str:
    folder = os.path.join(os.getcwd(), "data")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "inbox_seen.json")


def poll_inbox() -> Dict[str, Any]:
    from AethraOS_v0_3.app.tools.inbox import read_outlook_inbox

    result = read_outlook_inbox(limit=5)
    if not result.get("success"):
        return result
    messages = result.get("messages") or []
    seen = []
    if os.path.isfile(_path()):
        try:
            with open(_path(), "r", encoding="utf-8") as handle:
                seen = json.load(handle)
        except Exception:
            seen = []
    seen_keys = set(seen if isinstance(seen, list) else [])
    fresh: List[Dict[str, Any]] = []
    keys = []
    for item in messages:
        key = f"{item.get('from','')}|{item.get('subject','')}|{item.get('received','')}"
        keys.append(key)
        if key not in seen_keys:
            fresh.append(item)
    with open(_path(), "w", encoding="utf-8") as handle:
        json.dump(keys, handle, indent=2)
    plans = []
    for item in fresh:
        plans.append(
            f"New mail from {item.get('from')}: {item.get('subject')}. "
            "I can open VS Code, read the file you name, and draft the documentation. I will not send or push."
        )
    return {
        "success": True,
        "verified": True,
        "new_messages": fresh,
        "plans": plans,
        "message": f"{len(fresh)} new message(s)." if fresh else "No new mail.",
    }