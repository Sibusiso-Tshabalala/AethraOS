"""
Project self-awareness. Read, explain, propose, back up, restore.
Does not apply patches and does not touch permissions or secrets.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List

SKIP = {".venv", "venv", "__pycache__", ".git", "data"}


def _root() -> str:
    return os.path.abspath(os.getcwd())


def _safe(path: str) -> str:
    target = os.path.abspath(path if os.path.isabs(path) else os.path.join(_root(), path))
    root = _root()
    if not target.startswith(root):
        raise ValueError("Path is outside the project.")
    parts = set(target.split(os.sep))
    if parts & SKIP or target.endswith(".pyc"):
        raise ValueError("That path is skipped.")
    return target


def inventory_project() -> Dict[str, Any]:
    root = _root()
    files: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            files.append({"path": rel.replace("\\", "/"), "bytes": size})
    files.sort(key=lambda item: item["path"])
    return {
        "success": True,
        "verified": True,
        "root": root,
        "count": len(files),
        "files": files[:200],
        "message": f"{len(files)} Python files in the project. Secrets and caches are skipped.",
    }


def read_project_file(path: str, limit: int = 200) -> Dict[str, Any]:
    try:
        target = _safe(path)
    except ValueError as exc:
        return {"success": False, "verified": False, "error": str(exc)}
    if not os.path.isfile(target):
        return {"success": False, "verified": False, "error": "File not found."}
    with open(target, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()[: max(1, min(int(limit or 200), 400))]
    return {
        "success": True,
        "verified": True,
        "path": os.path.relpath(target, _root()),
        "text": "".join(lines)[:6000],
        "message": f"Read {len(lines)} lines.",
    }


def propose_patch(path: str, problem: str, suggestion: str) -> Dict[str, Any]:
    """Record a proposed fix. Does not edit the file."""
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "path": path,
        "problem": problem[:500],
        "suggestion": suggestion[:1500],
        "applied": False,
    }
    _append_history(record)
    return {
        "success": True,
        "verified": True,
        "applied": False,
        "proposal": record,
        "message": "Proposal saved. No file was changed. Approve it yourself before editing.",
    }


def backup_project_file(path: str) -> Dict[str, Any]:
    try:
        target = _safe(path)
    except ValueError as exc:
        return {"success": False, "verified": False, "error": str(exc)}
    if not os.path.isfile(target):
        return {"success": False, "verified": False, "error": "File not found."}
    folder = os.path.join(_root(), "data", "backups")
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(folder, f"{stamp}-{os.path.basename(target)}")
    shutil.copy2(target, dest)
    return {
        "success": True,
        "verified": True,
        "backup": dest,
        "message": f"Backup written to {dest}.",
    }


def restore_backup(backup_path: str, target_path: str) -> Dict[str, Any]:
    try:
        target = _safe(target_path)
        backup = os.path.abspath(backup_path)
        backup_root = os.path.join(_root(), "data", "backups")
        if not backup.startswith(backup_root) or not os.path.isfile(backup):
            return {"success": False, "verified": False, "error": "Backup must be a file under data/backups."}
    except ValueError as exc:
        return {"success": False, "verified": False, "error": str(exc)}
    shutil.copy2(backup, target)
    return {
        "success": True,
        "verified": True,
        "restored": os.path.relpath(target, _root()),
        "message": "Backup restored. Restart Aethra to load it.",
    }


def repair_history(limit: int = 10) -> Dict[str, Any]:
    path = _history_path()
    if not os.path.isfile(path):
        return {"success": True, "verified": True, "items": [], "message": "No repair history yet."}
    with open(path, "r", encoding="utf-8") as handle:
        items = json.load(handle)
    items = items[-max(1, min(int(limit or 10), 30)):] if isinstance(items, list) else []
    return {"success": True, "verified": True, "items": items, "count": len(items)}


def _history_path() -> str:
    folder = os.path.join(_root(), "data")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "repair_history.json")


def _append_history(record: Dict[str, Any]) -> None:
    path = _history_path()
    items: List[Any] = []
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                items = json.load(handle)
        except Exception:
            items = []
    if not isinstance(items, list):
        items = []
    items.append(record)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(items[-100:], handle, indent=2)
