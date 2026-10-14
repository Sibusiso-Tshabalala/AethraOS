"""
Local screen vision that does not rely only on a screenshot.

Primary path: Windows UI Automation tree of visible windows
(text, names, control types). Optional OCR sample is included
when pytesseract is available.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List


def _ocr_sample(max_chars: int = 600) -> str:
    try:
        from app.tools.computer import get_screen_text
        result = get_screen_text(region="active")
        if isinstance(result, dict) and result.get("success"):
            return (result.get("text") or "")[:max_chars]
    except Exception:
        return ""
    return ""


def see_screen(include_ocr: bool = True, max_windows: int = 8) -> Dict[str, Any]:
    """
    Read the current desktop from the accessibility tree.

    Returns window titles plus named controls (buttons, edits, text)
    so the model can "see" the screen without only looking at pixels.
    """
    windows: List[Dict[str, Any]] = []
    error = None

    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        count = 0
        for win in desktop.windows():
            if count >= max_windows:
                break
            try:
                if not win.is_visible():
                    continue
                title = (win.window_text() or "").strip()
                if not title:
                    continue
                controls = []
                try:
                    for el in win.descendants()[:40]:
                        try:
                            name = (el.window_text() or "").strip()
                            if not name:
                                continue
                            info = el.element_info
                            controls.append({
                                "name": name[:120],
                                "type": str(getattr(info, "control_type", "") or ""),
                            })
                        except Exception:
                            continue
                        if len(controls) >= 15:
                            break
                except Exception:
                    controls = []
                windows.append({
                    "title": title[:160],
                    "controls": controls,
                })
                count += 1
            except Exception:
                continue
    except ImportError:
        error = "pywinauto is not installed. pip install pywinauto"
    except Exception as exc:
        error = str(exc)

    # Fallback: open window titles only
    if not windows:
        try:
            from app.tools.computer import list_open_windows
            listed = list_open_windows()
            for w in (listed.get("windows") or [])[:max_windows]:
                windows.append({
                    "title": w.get("title", ""),
                    "controls": [],
                })
        except Exception:
            pass

    ocr = _ocr_sample() if include_ocr else ""
    return {
        "success": True,
        "verified": bool(windows or ocr),
        "source": "ui_automation" if windows and not error else "windows_plus_ocr",
        "window_count": len(windows),
        "windows": windows,
        "ocr_sample": ocr,
        "note": error,
        "message": (
            f"Read {len(windows)} visible window(s) from the UI tree"
            + (" plus an OCR sample." if ocr else ".")
        ),
    }