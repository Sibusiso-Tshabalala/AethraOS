"""Poll a folder for new files. Safe default is Downloads. No deletes."""

from __future__ import annotations

import json
import os
from typing import Any, Dict


def _state_path() -> str:
    folder = os.path.join(os.getcwd(), "data")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "watch_state.json")


def watch_folder(folder: str = "", workflow: str = "") -> Dict[str, Any]:
    target = folder or os.path.join(os.path.expanduser("~"), "Downloads")
    target = os.path.abspath(target)
    home = os.path.abspath(os.path.expanduser("~"))
    if not target.startswith(home) or not os.path.isdir(target):
        return {"success": False, "verified": False, "error": "Folder must exist inside your user profile."}
    state = {"folder": target, "workflow": workflow or "", "seen": sorted(os.listdir(target))[:200]}
    with open(_state_path(), "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    return {"success": True, "verified": True, "folder": target, "message": f"Watching {target}."}


def poll_watch() -> Dict[str, Any]:
    path = _state_path()
    if not os.path.isfile(path):
        return {"success": True, "verified": True, "new_files": [], "message": "No folder is being watched."}
    with open(path, "r", encoding="utf-8") as handle:
        state = json.load(handle)
    folder = state.get("folder") or ""
    if not os.path.isdir(folder):
        return {"success": False, "verified": False, "error": "Watched folder is missing."}
    current = set(os.listdir(folder))
    seen = set(state.get("seen") or [])
    new_files = sorted(current - seen)[:20]
    state["seen"] = sorted(current)[:200]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    return {
        "success": True,
        "verified": True,
        "new_files": new_files,
        "workflow": state.get("workflow") or "",
        "message": f"{len(new_files)} new file(s)." if new_files else "No new files.",
    }
