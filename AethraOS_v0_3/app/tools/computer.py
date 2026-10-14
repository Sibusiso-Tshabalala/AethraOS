import os
import re
import time
from typing import Any, Dict, Optional

import pyautogui


# =========================================================
# SCREENSHOT
# =========================================================

def take_screenshot() -> Dict[str, Any]:
    """
    Take a screenshot of the current screen.

    The screenshot is saved locally and the result is
    verified by checking that the file exists and
    contains data.
    """

    try:

        screenshot_dir = os.path.join(
            os.getcwd(),
            "data",
            "screenshots"
        )

        os.makedirs(
            screenshot_dir,
            exist_ok=True
        )

        timestamp = time.strftime(
            "%Y%m%d_%H%M%S"
        )

        screenshot_path = os.path.join(
            screenshot_dir,
            f"screenshot_{timestamp}.png"
        )

        screenshot = pyautogui.screenshot()

        screenshot.save(
            screenshot_path
        )

        # Verify that the screenshot was actually written.
        file_exists = os.path.exists(
            screenshot_path
        )

        file_size = (
            os.path.getsize(screenshot_path)
            if file_exists
            else 0
        )

        verified = (
            file_exists
            and file_size > 0
        )

        if not verified:

            return {
                "success": False,
                "verified": False,
                "error": (
                    "Screenshot capture was attempted, "
                    "but the saved file could not be verified."
                ),
                "path": screenshot_path
            }

        return {
            "success": True,
            "verified": True,
            "message": "Screenshot captured and verified successfully.",
            "path": screenshot_path,
            "file_size": file_size
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "error": str(exc)
        }


# =========================================================
# SCREEN TEXT (OCR) – LOCAL ONLY
# =========================================================

def _get_active_window_rect() -> Optional[Dict[str, int]]:
    """
    Return the bounding rectangle of the foreground window
    as {left, top, right, bottom}, or None on failure.
    """
    try:
        import ctypes
        from ctypes import wintypes

        if os.name != "nt":
            return None

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None

        return {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
        }
    except Exception:
        return None


def _configure_tesseract(pytesseract) -> None:
    """Use the usual Windows install path if tesseract is not on PATH."""
    import shutil
    if shutil.which("tesseract"):
        return
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in candidates:
        if os.path.isfile(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return


def get_screen_text(
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Capture the screen (or active window region) and extract
    readable text using local OCR (pytesseract).

    No external APIs are used.

    Parameters
    ----------
    region : str, optional
        "full" (default) or "active" (crops to the
        foreground window when possible).
    """

    try:
        # Lazy import so the rest of the computer tools
        # still work even if OCR dependencies are missing.
        import pytesseract
        from PIL import Image

        _configure_tesseract(pytesseract)

        region = (region or "full").strip().lower()
        used_region = "full"
        crop_box = None

        screenshot = pyautogui.screenshot()

        if region == "active":
            rect = _get_active_window_rect()
            if rect:
                # Clamp to screenshot bounds
                width, height = screenshot.size
                left = max(0, rect["left"])
                top = max(0, rect["top"])
                right = min(width, rect["right"])
                bottom = min(height, rect["bottom"])

                if right > left and bottom > top:
                    crop_box = (left, top, right, bottom)
                    screenshot = screenshot.crop(crop_box)
                    used_region = "active"

        text = pytesseract.image_to_string(screenshot)
        text = text.strip()

        if not text:
            return {
                "success": True,
                "verified": True,
                "text": "",
                "region": used_region,
                "message": (
                    "OCR completed but no readable text "
                    "was detected on the screen."
                ),
                "characters": 0,
            }

        # Keep the payload reasonable for the model context
        max_chars = 4000
        truncated = False

        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[... truncated ...]"
            truncated = True

        result = {
            "success": True,
            "verified": True,
            "text": text,
            "characters": len(text),
            "truncated": truncated,
            "region": used_region,
            "message": (
                "Screen text extracted successfully "
                f"using local OCR ({used_region} region)."
            ),
        }

        if crop_box:
            result["crop_box"] = {
                "left": crop_box[0],
                "top": crop_box[1],
                "right": crop_box[2],
                "bottom": crop_box[3],
            }

        return result

    except ImportError:
        return {
            "success": False,
            "verified": False,
            "error": (
                "OCR dependencies are missing. "
                "Install with: pip install pytesseract pillow\n"
                "Also install the Tesseract binary for your OS."
            ),
        }

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


def get_monitor_info() -> Dict[str, Any]:
    """
    Return basic multi-monitor information.

    Uses PyAutoGUI / system info only — no extra packages.
    """
    try:
        # PyAutoGUI exposes the virtual desktop size
        width, height = pyautogui.size()

        # Best-effort monitor count via Windows API
        monitor_count = 1
        try:
            import ctypes
            if os.name == "nt":
                user32 = ctypes.windll.user32
                # SM_CMONITORS = 80
                monitor_count = int(user32.GetSystemMetrics(80)) or 1
        except Exception:
            monitor_count = 1

        return {
            "success": True,
            "verified": True,
            "monitor_count": monitor_count,
            "virtual_width": width,
            "virtual_height": height,
            "message": (
                f"{monitor_count} monitor(s) detected. "
                f"Virtual desktop: {width}x{height}."
            ),
        }
    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


def get_screen_summary() -> Dict[str, Any]:
    """
    Lightweight screen awareness snapshot.

    Combines:
    - active window title
    - mouse position
    - monitor / virtual desktop size
    - a short OCR sample (first ~800 characters)

    Designed to be cheap enough to call frequently.
    """

    try:
        from app.tools.applications import get_active_window

        window_info = get_active_window()
        mouse_info = get_mouse_position()
        monitor_info = get_monitor_info()

        # Prefer active-window OCR when possible (cheaper + more relevant)
        ocr_result = get_screen_text(region="active")

        summary = {
            "success": True,
            "verified": True,
            "active_window": (
                window_info.get("window_title", "Unknown")
                if isinstance(window_info, dict)
                else "Unknown"
            ),
            "active_pid": (
                window_info.get("pid")
                if isinstance(window_info, dict)
                else None
            ),
            "mouse_x": (
                mouse_info.get("x")
                if isinstance(mouse_info, dict)
                else None
            ),
            "mouse_y": (
                mouse_info.get("y")
                if isinstance(mouse_info, dict)
                else None
            ),
            "monitor_count": (
                monitor_info.get("monitor_count", 1)
                if isinstance(monitor_info, dict)
                else 1
            ),
            "virtual_width": (
                monitor_info.get("virtual_width")
                if isinstance(monitor_info, dict)
                else None
            ),
            "virtual_height": (
                monitor_info.get("virtual_height")
                if isinstance(monitor_info, dict)
                else None
            ),
            "screen_text_sample": "",
            "ocr_available": False,
            "ocr_region": "full",
        }

        if (
            isinstance(ocr_result, dict)
            and ocr_result.get("success")
            and ocr_result.get("text")
        ):
            sample = ocr_result["text"][:800]
            summary["screen_text_sample"] = sample
            summary["ocr_available"] = True
            summary["ocr_characters"] = ocr_result.get("characters", 0)
            summary["ocr_region"] = ocr_result.get("region", "full")

        summary["message"] = (
            "Screen awareness snapshot captured."
        )

        return summary

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


# =========================================================
# MOUSE
# =========================================================

def get_mouse_position() -> Dict[str, Any]:
    """
    Return the current mouse cursor position.
    """

    try:

        x, y = pyautogui.position()

        return {
            "success": True,
            "verified": True,
            "x": x,
            "y": y
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "error": str(exc)
        }


def move_mouse(x: int, y: int) -> Dict[str, Any]:
    """
    Move the mouse cursor to the specified screen coordinates.

    After moving, the cursor position is read again to verify
    that the requested position was actually reached.
    """

    try:

        target_x = int(x)
        target_y = int(y)

        pyautogui.moveTo(
            target_x,
            target_y,
            duration=0.2
        )

        # Read the actual cursor position after moving.
        actual_x, actual_y = pyautogui.position()

        verified = (
            actual_x == target_x
            and actual_y == target_y
        )

        if not verified:

            return {
                "success": False,
                "verified": False,
                "requested_x": target_x,
                "requested_y": target_y,
                "actual_x": actual_x,
                "actual_y": actual_y,
                "error": (
                    "Mouse movement completed, but the cursor "
                    "did not reach the requested coordinates."
                )
            }

        return {
            "success": True,
            "verified": True,
            "message": (
                f"Mouse moved to "
                f"({target_x}, {target_y}) "
                f"and the position was verified."
            ),
            "x": actual_x,
            "y": actual_y
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "error": str(exc)
        }


def click_mouse(button: str = "left") -> Dict[str, Any]:
    """
    Click the mouse.

    Supported buttons:
    - left
    - right
    - middle

    Verification here confirms that PyAutoGUI successfully
    performed the click operation.

    It does NOT claim that the application responded to
    the click, because that requires screen/UI inspection.
    """

    allowed_buttons = {
        "left",
        "right",
        "middle"
    }

    button = str(button).lower()

    if button not in allowed_buttons:

        return {
            "success": False,
            "verified": False,
            "error": (
                f"Unsupported mouse button: {button}. "
                f"Use left, right, or middle."
            )
        }

    try:

        pyautogui.click(
            button=button
        )

        return {
            "success": True,
            "verified": True,
            "verification_type": "input_completed",
            "message": (
                f"{button} mouse click completed successfully."
            )
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "error": str(exc)
        }


def scroll_mouse(amount: int) -> Dict[str, Any]:
    """
    Scroll the mouse wheel.

    The existing safety limit of 20 scroll units per
    tool call is preserved.
    """

    try:

        amount = int(amount)

        # Safety limit for one tool call.
        amount = max(
            -20,
            min(amount, 20)
        )

        pyautogui.scroll(
            amount
        )

        return {
            "success": True,
            "verified": True,
            "amount": amount,
            "message": (
                f"Scrolled {amount} mouse-wheel units "
                f"successfully."
            )
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "error": str(exc)
        }


# =========================================================
# KEYBOARD
# =========================================================

def _click_center_of_foreground_window() -> Dict[str, Any]:
    """
    Click inside the foreground window so the editor/document
    control receives keyboard focus.

    On Windows, SetForegroundWindow alone is often not enough —
    Notepad/VS Code need a click in the client area first.
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"success": False, "error": "No foreground window."}

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return {"success": False, "error": "GetWindowRect failed."}

        left = int(rect.left)
        top = int(rect.top)
        right = int(rect.right)
        bottom = int(rect.bottom)
        width = right - left
        height = bottom - top

        if width < 50 or height < 50:
            return {"success": False, "error": "Window too small to click."}

        # Slightly above vertical center — avoids status bars
        cx = left + width // 2
        cy = top + int(height * 0.40)

        pyautogui.click(cx, cy)
        time.sleep(0.15)

        return {
            "success": True,
            "x": cx,
            "y": cy,
            "window_rect": {
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
            },
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def type_text(
    text: str,
    interval: float = 0.05,
    target_application: str = "",
) -> Dict[str, Any]:
    """
    Type text so the user can watch it appear in the target app.

    If target_application is given (e.g. "notepad"), force-focus
    that window first — even when Aethra currently owns focus.
    Then click the editor area and type slowly.
    """

    try:
        from app.tools.applications import (
            get_active_window,
            focus_application,
            _find_application_window,
            _focus_window,
        )

        text = str(text)
        try:
            interval = float(interval)
        except Exception:
            interval = 0.05
        interval = max(0.02, min(interval, 0.2))

        target_application = (target_application or "").strip().lower()
        focus_result = None

        # Force the target app to the foreground when known
        if target_application:
            focus_result = focus_application(target_application)
            time.sleep(0.25)
        else:
            # If focus is on Aethra, try common targets from open windows
            before_probe = get_active_window()
            probe_title = ""
            if isinstance(before_probe, dict):
                probe_title = (before_probe.get("window_title") or "").lower()
            if "aethra" in probe_title and "notepad" not in probe_title and "visual studio" not in probe_title:
                for candidate in (
                    "notepad", "vscode", "chrome", "edge",
                    "word", "excel", "paint", "cmd", "powershell",
                ):
                    win = _find_application_window(candidate)
                    if win:
                        _focus_window(win["hwnd"])
                        time.sleep(0.25)
                        target_application = candidate
                        break

        before = get_active_window()
        before_title = ""
        if isinstance(before, dict) and before.get("success"):
            before_title = before.get("window_title", "") or ""

        # Still on the Aethra window, not a document that merely contains the word.
        title_l = before_title.lower()
        on_aethra_window = (
            "aethra" in title_l
            and "notepad" not in title_l
            and "visual studio" not in title_l
            and "code" not in title_l
        )
        if on_aethra_window:
            return {
                "success": False,
                "verified": False,
                "error": (
                    "Could not move focus away from Aethra. "
                    "Pass target_application='notepad' (or the app name) "
                    "to type_text, or call focus_application first."
                ),
                "active_window_before": before_title,
                "focus_result": focus_result,
            }

        # Click into the document area
        click_result = _click_center_of_foreground_window()
        time.sleep(0.1)

        pyautogui.write(text, interval=interval)

        time.sleep(0.15)

        after = get_active_window()
        after_title = ""
        if isinstance(after, dict) and after.get("success"):
            after_title = after.get("window_title", "") or ""

        focus_stable = True
        if before_title and after_title:
            before_l = before_title.lower()
            after_l = after_title.lower()
            same_app = (
                before_l[:40] == after_l[:40]
                or before_l in after_l
                or after_l in before_l
                or before_l.split("-")[-1].strip() == after_l.split("-")[-1].strip()
            )
            typed_visible = text.lower()[:12] in after_l if text else False
            focus_stable = same_app or typed_visible

        clicked = bool(click_result.get("success"))

        return {
            "success": True,
            "verified": focus_stable and clicked,
            "verification_type": (
                "clicked_editor_and_typed"
                if clicked
                else "typed_without_editor_click"
            ),
            "characters_requested": len(text),
            "interval": interval,
            "target_application": target_application or None,
            "editor_click": click_result,
            "active_window_before": before_title,
            "active_window_after": after_title,
            "message": (
                f"Focused editor and typed {len(text)} characters "
                f"(interval={interval}s) into '{after_title}'."
            ),
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "error": str(exc)
        }



def press_key(key: str) -> Dict[str, Any]:
    """
    Press a single keyboard key.

    Verification confirms that PyAutoGUI completed
    the key-press operation.
    """

    try:

        key = str(key).lower()

        pyautogui.press(
            key
        )

        return {
            "success": True,
            "verified": True,
            "verification_type": "input_completed",
            "key": key,
            "message": (
                f"Key '{key}' press completed successfully."
            )
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "error": str(exc)
        }


def hotkey(keys) -> Dict[str, Any]:
    """
    Press a keyboard shortcut.

    Example:
        ["ctrl", "c"]

    or:

        ["ctrl", "shift", "s"]

    Verification confirms that PyAutoGUI completed
    the shortcut operation.
    """

    try:

        if not isinstance(keys, list):

            return {
                "success": False,
                "verified": False,
                "error": "keys must be a list."
            }

        if not keys:

            return {
                "success": False,
                "verified": False,
                "error": "No keys supplied."
            }

        keys = [
            str(key).lower()
            for key in keys
        ]

        # Safety limit.
        if len(keys) > 5:

            return {
                "success": False,
                "verified": False,
                "error": "Maximum of 5 keys allowed."
            }

        pyautogui.hotkey(
            *keys
        )

        return {
            "success": True,
            "verified": True,
            "verification_type": "input_completed",
            "keys": keys,
            "message": (
                "Keyboard shortcut executed successfully: "
                f"{' + '.join(keys)}"
            )
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "error": str(exc)
        }


# =========================================================
# CLIPBOARD (local, no extra dependencies)
# =========================================================

def get_clipboard() -> Dict[str, Any]:
    """
    Read the current text content of the Windows clipboard.

    Uses only the Windows API via ctypes — no extra packages.
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CF_UNICODETEXT = 13

        if not user32.OpenClipboard(None):
            return {
                "success": False,
                "verified": False,
                "error": "Could not open the clipboard.",
            }

        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return {
                    "success": True,
                    "verified": True,
                    "text": "",
                    "message": "Clipboard is empty or contains no text.",
                }

            # Lock the global memory and read the Unicode string
            locked = kernel32.GlobalLock(handle)
            if not locked:
                return {
                    "success": False,
                    "verified": False,
                    "error": "Could not lock clipboard data.",
                }

            try:
                text = ctypes.wstring_at(locked)
            finally:
                kernel32.GlobalUnlock(handle)

            # Safety limit for the model context
            max_chars = 8000
            truncated = False
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[... truncated ...]"
                truncated = True

            return {
                "success": True,
                "verified": True,
                "text": text,
                "characters": len(text),
                "truncated": truncated,
                "message": "Clipboard text retrieved successfully.",
            }

        finally:
            user32.CloseClipboard()

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


def set_clipboard(text: str) -> Dict[str, Any]:
    """
    Set the Windows clipboard to the given text.

    Uses only the Windows API via ctypes — no extra packages.
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002

        text = str(text)
        # Include the null terminator
        data = text.encode("utf-16-le") + b"\x00\x00"
        size = len(data)

        if not user32.OpenClipboard(None):
            return {
                "success": False,
                "verified": False,
                "error": "Could not open the clipboard.",
            }

        try:
            user32.EmptyClipboard()

            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not handle:
                return {
                    "success": False,
                    "verified": False,
                    "error": "Could not allocate clipboard memory.",
                }

            locked = kernel32.GlobalLock(handle)
            if not locked:
                kernel32.GlobalFree(handle)
                return {
                    "success": False,
                    "verified": False,
                    "error": "Could not lock clipboard memory.",
                }

            try:
                ctypes.memmove(locked, data, size)
            finally:
                kernel32.GlobalUnlock(handle)

            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                kernel32.GlobalFree(handle)
                return {
                    "success": False,
                    "verified": False,
                    "error": "Could not set clipboard data.",
                }

            # Ownership of the handle is transferred to the system
            return {
                "success": True,
                "verified": True,
                "characters": len(text),
                "message": "Clipboard text set successfully.",
            }

        finally:
            user32.CloseClipboard()

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


# =========================================================
# WINDOW MANAGEMENT
# =========================================================

def list_open_windows() -> Dict[str, Any]:
    """
    Return a list of currently visible top-level windows.

    Each entry contains title, pid and window handle.
    Limited to a reasonable number for the model context.
    """
    try:
        import ctypes

        if os.name != "nt":
            return {
                "success": False,
                "verified": False,
                "error": "Window listing is only supported on Windows.",
            }

        user32 = ctypes.windll.user32
        windows = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )

        def callback(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()

            if not title:
                return True

            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            windows.append({
                "title": title,
                "pid": int(pid.value),
                "hwnd": int(hwnd),
            })
            return True

        user32.EnumWindows(EnumWindowsProc(callback), 0)

        # Keep payload reasonable
        max_windows = 40
        truncated = len(windows) > max_windows
        windows = windows[:max_windows]

        return {
            "success": True,
            "verified": True,
            "windows": windows,
            "count": len(windows),
            "truncated": truncated,
            "message": f"Found {len(windows)} visible windows.",
        }

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


def _find_window_by_title(title_substring: str):
    """
    Find the first visible window whose title contains
    the given substring (case-insensitive).
    """
    result = list_open_windows()
    if not result.get("success"):
        return None

    needle = title_substring.strip().lower()
    if not needle:
        return None

    for window in result.get("windows", []):
        if needle in window["title"].lower():
            return window
    return None


def manage_window(
    action: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Perform a window management action on a window.

    Actions:
        minimize, maximize, restore, close, focus

    If title is omitted, the current foreground window is used.
    """
    try:
        import ctypes

        if os.name != "nt":
            return {
                "success": False,
                "verified": False,
                "error": "Window management is only supported on Windows.",
            }

        user32 = ctypes.windll.user32

        action = str(action).strip().lower()
        allowed = {"minimize", "maximize", "restore", "close", "focus"}
        if action not in allowed:
            return {
                "success": False,
                "verified": False,
                "error": (
                    f"Unsupported action '{action}'. "
                    f"Use one of: {', '.join(sorted(allowed))}."
                ),
            }

        # Resolve target window
        if title:
            window = _find_window_by_title(title)
            if not window:
                return {
                    "success": False,
                    "verified": False,
                    "error": f"No visible window found matching '{title}'.",
                }
            hwnd = window["hwnd"]
            window_title = window["title"]
        else:
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return {
                    "success": False,
                    "verified": False,
                    "error": "Could not determine the active window.",
                }
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            window_title = buffer.value.strip() or "Untitled window"

        # Windows show commands
        SW_MINIMIZE = 6
        SW_MAXIMIZE = 3
        SW_RESTORE = 9

        if action == "minimize":
            user32.ShowWindow(hwnd, SW_MINIMIZE)
            message = f"Minimized window: {window_title}"
        elif action == "maximize":
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
            message = f"Maximized window: {window_title}"
        elif action == "restore":
            user32.ShowWindow(hwnd, SW_RESTORE)
            message = f"Restored window: {window_title}"
        elif action == "close":
            WM_CLOSE = 0x0010
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            message = f"Close requested for window: {window_title}"
        elif action == "focus":
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.12)
            focused = user32.GetForegroundWindow() == hwnd
            return {
                "success": True,
                "verified": focused,
                "action": action,
                "window_title": window_title,
                "hwnd": int(hwnd),
                "focus_verified": focused,
                "message": (
                    f"Focused window: {window_title}"
                    if focused
                    else f"Attempted to focus {window_title}, but focus was not confirmed."
                ),
            }

        return {
            "success": True,
            "verified": True,
            "action": action,
            "window_title": window_title,
            "hwnd": int(hwnd),
            "message": message,
        }

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


# =========================================================
# UI AUTOMATION (named controls)
# =========================================================

def _get_uia_backend():
    """Lazy-load pywinauto. Returns (Desktop, error_message)."""
    try:
        from pywinauto import Desktop
        return Desktop(backend="uia"), None
    except ImportError:
        return None, (
            "UI Automation requires pywinauto. "
            "Install with: pip install pywinauto"
        )
    except Exception as exc:
        return None, str(exc)


def find_ui_elements(name: str = "", control_type: str = "") -> Dict[str, Any]:
    """
    Find visible UI elements in the foreground window by name
    and/or control type (Button, Edit, MenuItem, etc.).
    """
    try:
        desktop, err = _get_uia_backend()
        if err:
            return {"success": False, "verified": False, "error": err}

        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return {
                "success": False,
                "verified": False,
                "error": "No foreground window.",
            }

        window = desktop.window(handle=hwnd)
        name = (name or "").strip()
        control_type = (control_type or "").strip()

        criteria = {}
        if name:
            criteria["title_re"] = f"(?i).*{re.escape(name)}.*"
        if control_type:
            criteria["control_type"] = control_type

        try:
            elements = (
                window.descendants(**criteria)
                if criteria
                else window.descendants()
            )
        except Exception:
            elements = []

        matches = []
        for el in elements[:30]:
            try:
                info = el.element_info
                matches.append({
                    "name": getattr(info, "name", "") or "",
                    "control_type": str(getattr(info, "control_type", "") or ""),
                    "automation_id": getattr(info, "automation_id", "") or "",
                    "class_name": getattr(info, "class_name", "") or "",
                })
            except Exception:
                continue

        return {
            "success": True,
            "verified": True,
            "count": len(matches),
            "elements": matches,
            "message": f"Found {len(matches)} matching UI element(s).",
        }

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


def click_ui_element(
    name: str,
    control_type: str = "",
) -> Dict[str, Any]:
    """
    Click a UI element in the foreground window by accessible name.
    Prefer this over coordinate clicking when a control has a name.
    """
    try:
        desktop, err = _get_uia_backend()
        if err:
            return {"success": False, "verified": False, "error": err}

        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return {
                "success": False,
                "verified": False,
                "error": "No foreground window.",
            }

        window = desktop.window(handle=hwnd)
        name = str(name).strip()
        if not name:
            return {
                "success": False,
                "verified": False,
                "error": "Element name is required.",
            }

        criteria = {"title_re": f"(?i).*{re.escape(name)}.*"}
        if control_type:
            criteria["control_type"] = str(control_type).strip()

        element = window.child_window(**criteria)
        if not element.exists(timeout=1):
            return {
                "success": False,
                "verified": False,
                "error": f"No UI element found matching '{name}'.",
            }

        element.click_input()
        return {
            "success": True,
            "verified": True,
            "name": name,
            "control_type": control_type or "any",
            "message": f"Clicked UI element matching '{name}'.",
        }

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


def type_into_ui_element(
    name: str,
    text: str,
    control_type: str = "Edit",
) -> Dict[str, Any]:
    """Type text into a named edit/input control in the foreground window."""
    try:
        desktop, err = _get_uia_backend()
        if err:
            return {"success": False, "verified": False, "error": err}

        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return {
                "success": False,
                "verified": False,
                "error": "No foreground window.",
            }

        window = desktop.window(handle=hwnd)
        name = str(name).strip()
        text = str(text)

        if not name:
            return {
                "success": False,
                "verified": False,
                "error": "Element name is required.",
            }

        criteria = {"title_re": f"(?i).*{re.escape(name)}.*"}
        if control_type:
            criteria["control_type"] = str(control_type).strip()

        element = window.child_window(**criteria)
        if not element.exists(timeout=1):
            return {
                "success": False,
                "verified": False,
                "error": f"No input element found matching '{name}'.",
            }

        element.set_focus()
        try:
            element.type_keys(text, with_spaces=True, pause=0.02)
        except Exception:
            element.set_focus()
            pyautogui.hotkey("ctrl", "a")
            pyautogui.write(text, interval=0.01)

        return {
            "success": True,
            "verified": True,
            "name": name,
            "characters": len(text),
            "message": f"Typed into UI element matching '{name}'.",
        }

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


# =========================================================
# BROWSER HELPERS
# =========================================================

def open_url(url: str, browser: str = "chrome") -> Dict[str, Any]:
    """
    Open a URL in an allowlisted browser (chrome or edge).
    Only http/https URLs are allowed.
    """
    try:
        import subprocess
        from urllib.parse import urlparse

        url = str(url).strip()
        if not url:
            return {
                "success": False,
                "verified": False,
                "error": "URL cannot be empty.",
            }

        parsed = urlparse(url if "://" in url else "https://" + url)
        if parsed.scheme not in ("http", "https"):
            return {
                "success": False,
                "verified": False,
                "error": "Only http and https URLs are allowed.",
            }
        final_url = parsed.geturl()

        browser = str(browser).strip().lower() or "chrome"
        if browser not in ("chrome", "edge"):
            return {
                "success": False,
                "verified": False,
                "error": "Browser must be 'chrome' or 'edge'.",
            }

        from app.tools.applications import (
            _resolve_application,
            _find_executable,
            open_application,
        )

        resolved = _resolve_application(browser)
        if not resolved:
            return {
                "success": False,
                "verified": False,
                "error": f"Browser '{browser}' is not allowlisted.",
            }

        executable = _find_executable(resolved)
        if not executable:
            open_result = open_application(resolved)
            return {
                "success": open_result.get("success", False),
                "verified": False,
                "error": (
                    f"Could not find {browser} executable to open URL."
                ),
                "open_result": open_result,
            }

        subprocess.Popen(
            [executable, final_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        time.sleep(0.4)

        return {
            "success": True,
            "verified": True,
            "url": final_url,
            "browser": resolved,
            "message": f"Opened {final_url} in {resolved}.",
        }

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }