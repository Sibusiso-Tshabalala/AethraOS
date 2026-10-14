"""Saved workflows. A named list of tool steps. Does not send mail."""

from __future__ import annotations

import json
import os
from typing import Any, Dict


def _path() -> str:
    folder = os.path.join(os.getcwd(), "data")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "workflows.json")


def _load() -> Dict[str, Any]:
    path = _path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def save_workflow(name: str, steps: list) -> Dict[str, Any]:
    name = str(name or "").strip()
    if not name or not isinstance(steps, list) or not steps:
        return {"success": False, "verified": False, "error": "Name and a list of steps are required."}
    clean = []
    for step in steps[:12]:
        if not isinstance(step, dict) or not step.get("tool"):
            continue
        clean.append({"tool": step["tool"], "arguments": step.get("arguments") or {}})
    data = _load()
    data[name] = clean
    with open(_path(), "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return {"success": True, "verified": True, "name": name, "steps": len(clean), "message": f"Saved workflow {name}."}


def list_workflows() -> Dict[str, Any]:
    ensure_default_workflows()
    data = _load()
    return {"success": True, "verified": True, "workflows": list(data.keys()), "count": len(data)}


def get_workflow(name: str) -> Dict[str, Any]:
    ensure_default_workflows()
    data = _load()
    steps = data.get(name)
    if not steps:
        return {"success": False, "verified": False, "error": f"No workflow named {name}."}
    return {"success": True, "verified": True, "name": name, "steps": steps}


def ensure_default_workflows() -> Dict[str, Any]:
    data = _load()
    defaults = {
        "Morning": [
            {"tool": "poll_inbox", "arguments": {}},
            {"tool": "news_brief", "arguments": {"topic": "tech"}},
            {"tool": "get_system_health", "arguments": {}},
        ],
        "Project": [
            {"tool": "create_project", "arguments": {"name": "scratch", "language": "python"}},
            {"tool": "open_in_vscode", "arguments": {"project_path": ""}},
        ],
    }
    added = []
    for name, steps in defaults.items():
        if name not in data:
            data[name] = steps
            added.append(name)
    if added:
        with open(_path(), "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    return {"success": True, "verified": True, "added": added, "message": "Default workflows ready."}
