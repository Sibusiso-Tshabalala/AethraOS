"""
Project folders and a restricted runner.

Creates a project under the user profile (Documents, Desktop, Downloads,
or any folder inside the user home). Runs only the project entry file
with a known interpreter. No arbitrary shell.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List

LANGS = {
    "python": {"ext": ".py", "file": "main.py", "cmd": ["python"]},
    "javascript": {"ext": ".js", "file": "main.js", "cmd": ["node"]},
    "typescript": {"ext": ".ts", "file": "main.ts", "cmd": ["npx", "ts-node"]},
    "html": {"ext": ".html", "file": "index.html", "cmd": []},
    "csharp": {"ext": ".cs", "file": "Program.cs", "cmd": ["dotnet", "run"]},
    "java": {"ext": ".java", "file": "Main.java", "cmd": []},
    "cpp": {"ext": ".cpp", "file": "main.cpp", "cmd": []},
    "go": {"ext": ".go", "file": "main.go", "cmd": ["go", "run", "main.go"]},
}


def _home() -> str:
    return os.path.abspath(os.path.expanduser("~"))


def _safe_dir(folder: str) -> str:
    folder = (folder or "Documents").strip().strip('"')
    home = _home()
    named = {
        "documents": os.path.join(home, "Documents"),
        "desktop": os.path.join(home, "Desktop"),
        "downloads": os.path.join(home, "Downloads"),
        "home": home,
    }
    if folder.lower() in named:
        target = named[folder.lower()]
    else:
        target = folder if os.path.isabs(folder) else os.path.join(home, folder)
    target = os.path.abspath(target)
    if not target.startswith(home):
        raise ValueError("Projects can only be created inside your user folder.")
    blocked = ("\\windows\\", "\\program files", "\\programdata\\")
    low = target.lower()
    if any(bit in low for bit in blocked):
        raise ValueError("That folder is not allowed.")
    return target


def create_project(name: str, language: str = "python", folder: str = "Documents", files: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    name = "".join(ch for ch in str(name or "project").strip() if ch.isalnum() or ch in ("-", "_", " ")).strip()
    if not name:
        return {"success": False, "verified": False, "error": "Project name is empty."}
    language = (language or "python").strip().lower()
    spec = LANGS.get(language, LANGS["python"])
    try:
        base = _safe_dir(folder)
        os.makedirs(base, exist_ok=True)
        project = os.path.join(base, name.replace(" ", "-"))
        os.makedirs(project, exist_ok=True)
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}

    written = []
    payload = files or [{
        "filename": spec["file"],
        "content": _starter(language, name),
    }]
    for item in payload:
        filename = os.path.basename(str(item.get("filename") or spec["file"]))
        if not filename or ".." in filename:
            continue
        path = os.path.join(project, filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(item.get("content") or ""))
        written.append(path)
    return {
        "success": True,
        "verified": True,
        "language": language,
        "project_path": project,
        "files": written,
        "message": f"Created {language} project at {project}.",
    }


def _starter(language: str, name: str) -> str:
    if language == "python":
        return (
            "def average(marks):\n"
            "    return sum(marks) / len(marks) if marks else 0\n\n"
            "if __name__ == '__main__':\n"
            "    marks = [70, 85, 90]\n"
            "    print('Student marks project:', average(marks))\n"
        )
    if language == "javascript":
        return "const marks = [70, 85, 90];\nconst avg = marks.reduce((a,b)=>a+b,0)/marks.length;\nconsole.log('Student marks project:', avg);\n"
    if language == "html":
        return f"<!doctype html><title>{name}</title><h1>{name}</h1>\n"
    return f"// {name}\n"


def run_project(project_path: str, language: str = "python", timeout: int = 20) -> Dict[str, Any]:
    project_path = os.path.abspath(str(project_path or "").strip().strip('"'))
    try:
        home = _home()
        if not project_path.startswith(home) or not os.path.isdir(project_path):
            return {"success": False, "verified": False, "error": "Project path must be an existing folder in your user profile."}
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}
    language = (language or "python").strip().lower()
    spec = LANGS.get(language)
    if not spec or not spec["cmd"]:
        return {"success": False, "verified": False, "error": f"No runner for {language}. Open it in VS Code instead."}
    entry = os.path.join(project_path, spec["file"])
    if language != "csharp" and not os.path.isfile(entry):
        return {"success": False, "verified": False, "error": f"Missing {spec['file']} in {project_path}."}
    cmd = spec["cmd"] + ([entry] if language in ("python", "javascript") else [])
    if language == "go":
        cmd = ["go", "run", "main.go"]
    try:
        completed = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=max(5, min(int(timeout or 20), 60)),
            shell=False,
        )
        return {
            "success": completed.returncode == 0,
            "verified": completed.returncode == 0,
            "return_code": completed.returncode,
            "stdout": (completed.stdout or "")[:2000],
            "stderr": (completed.stderr or "")[:2000],
            "message": "Program finished." if completed.returncode == 0 else "Program failed.",
        }
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}