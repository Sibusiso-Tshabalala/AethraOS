"""Read a text file inside the user profile. No writes."""

import os
from typing import Any, Dict


def read_user_file(path: str, limit: int = 200) -> Dict[str, Any]:
    target = os.path.abspath(str(path or "").strip().strip('"'))
    home = os.path.abspath(os.path.expanduser("~"))
    if not target.startswith(home) or not os.path.isfile(target):
        return {"success": False, "verified": False, "error": "File must exist inside your user profile."}
    if os.path.getsize(target) > 200_000:
        return {"success": False, "verified": False, "error": "File is too large to read here."}
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[: max(1, min(int(limit or 200), 400))]
        return {
            "success": True,
            "verified": True,
            "path": target,
            "text": "".join(lines)[:4000],
            "message": f"Read {len(lines)} lines from {target}.",
        }
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}