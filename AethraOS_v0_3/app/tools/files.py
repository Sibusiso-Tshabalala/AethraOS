from pathlib import Path
import re
from app.config import settings

def _downloads():
    p = Path(settings.downloads_dir).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p

def list_downloads():
    p = _downloads()
    items = [{"name": x.name, "type": "folder" if x.is_dir() else "file"}
             for x in sorted(p.iterdir(), key=lambda x: x.name.lower())]
    return {"success": True, "folder": str(p), "items": items[:100], "truncated": len(items)>100}

def create_text_file(filename, content):
    name = Path(str(filename)).name.strip()
    if not name:
        return {"success": False, "error": "Filename cannot be empty."}
    if not name.lower().endswith(".txt"):
        name += ".txt"
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    target = _downloads()/name
    try:
        target.write_text(str(content), encoding="utf-8")
        return {"success": True, "message": f"Created {target.name}.", "path": str(target)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
