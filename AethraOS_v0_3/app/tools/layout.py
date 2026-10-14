"""Place two windows side by side. Does not send mail."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def arrange_windows(left_title: str, right_title: str) -> Dict[str, Any]:
    if os.name != "nt":
        return {"success": False, "verified": False, "error": "Split screen is only implemented on Windows."}
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        half = width // 2

        def find(fragment: str) -> Optional[int]:
            found = {"hwnd": None}
            needle = fragment.lower()

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def callback(hwnd, lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if needle in buf.value.lower():
                    found["hwnd"] = hwnd
                    return False
                return True

            user32.EnumWindows(callback, 0)
            return found["hwnd"]

        left = find(left_title)
        right = find(right_title)
        if not left or not right:
            return {
                "success": False,
                "verified": False,
                "error": f"Could not find both windows ({left_title!r}, {right_title!r}). Open them first.",
            }
        SW_RESTORE = 9
        user32.ShowWindow(left, SW_RESTORE)
        user32.ShowWindow(right, SW_RESTORE)
        user32.MoveWindow(left, 0, 0, half, height - 40, True)
        user32.MoveWindow(right, half, 0, width - half, height - 40, True)
        return {
            "success": True,
            "verified": True,
            "message": f"Placed '{left_title}' on the left and '{right_title}' on the right.",
        }
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}