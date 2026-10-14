"""Open a project folder in VS Code and check local setup."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict


def open_in_vscode(project_path: str) -> Dict[str, Any]:
    project_path = os.path.abspath(str(project_path or "").strip().strip('"'))
    home = os.path.abspath(os.path.expanduser("~"))
    if not project_path.startswith(home) or not os.path.isdir(project_path):
        return {"success": False, "verified": False, "error": "Path must be an existing folder in your user profile."}
    candidates = [
        shutil.which("code"),
        shutil.which("code.cmd"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "bin", "code.cmd"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft VS Code", "Code.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft VS Code", "bin", "code.cmd"),
    ]
    code = next((path for path in candidates if path and os.path.isfile(path)), "")
    if not code:
        return {"success": False, "verified": False, "error": "VS Code was not found in the user or Program Files install path."}
    try:
        subprocess.Popen([code, project_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "verified": True, "path": project_path, "message": f"Opened {project_path} in VS Code."}
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}


def health_check() -> Dict[str, Any]:
    checks = {}
    try:
        from app.config import settings
        import urllib.request
        base = settings.ai_base_url or "http://localhost:1234/v1"
        urllib.request.urlopen(base.rstrip("/") + "/models", timeout=2)
        checks["lm_studio"] = "reachable"
    except Exception as exc:
        checks["lm_studio"] = f"not reachable ({exc})"
    tess = shutil.which("tesseract")
    if not tess:
        for path in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ):
            if os.path.isfile(path):
                tess = path
                break
    checks["tesseract"] = "found" if tess else "not found — install from https://github.com/UB-Mannheim/tesseract/wiki"
    checks["pywinauto"] = "installed" if shutil.which("python") else "unknown"
    try:
        import pywinauto  # noqa: F401
        checks["pywinauto"] = "installed"
    except Exception:
        checks["pywinauto"] = "not installed"
    try:
        import sounddevice  # noqa: F401
        checks["microphone_library"] = "installed"
    except Exception:
        checks["microphone_library"] = "not installed"
    try:
        import win32com.client  # type: ignore
        win32com.client.Dispatch("Outlook.Application")
        checks["outlook"] = "available"
    except Exception:
        checks["outlook"] = "not available"
    checks["gmail"] = "configured" if os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD") else "not configured"
    return {"success": True, "verified": True, "checks": checks, "message": "Health check finished."}