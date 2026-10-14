import ctypes
import os
import shutil
import subprocess
import time


# =========================================================
# ALLOWED APPLICATIONS
# =========================================================

ALLOWED_APPS = {
    "notepad": {
        "aliases": [
            "notepad",
            "note pad",
            "windows notepad",
        ],
        "executables": [
            "notepad.exe",
        ],
    },

    "calculator": {
        "aliases": [
            "calculator",
            "calc",
            "windows calculator",
        ],
        "executables": [
            "calc.exe",
        ],
    },

    "paint": {
        "aliases": [
            "paint",
            "mspaint",
            "microsoft paint",
        ],
        "executables": [
            "mspaint.exe",
        ],
    },

    "vscode": {
        "aliases": [
            "vscode",
            "vs code",
            "visual studio code",
            "code",
        ],
        "executables": [
            "code",
            "code.cmd",
            "code.exe",
        ],
    },

    # -----------------------------------------------------
    # New high-value applications
    # -----------------------------------------------------

    "chrome": {
        "aliases": [
            "chrome",
            "google chrome",
            "googlechrome",
        ],
        "executables": [
            "chrome.exe",
            "google-chrome.exe",
        ],
    },

    "edge": {
        "aliases": [
            "edge",
            "microsoft edge",
            "msedge",
        ],
        "executables": [
            "msedge.exe",
        ],
    },

    "explorer": {
        "aliases": [
            "explorer",
            "file explorer",
            "windows explorer",
            "files",
            "file manager",
        ],
        "executables": [
            "explorer.exe",
        ],
    },

    "word": {
        "aliases": [
            "word",
            "microsoft word",
            "ms word",
            "winword",
        ],
        "executables": [
            "WINWORD.EXE",
            "winword.exe",
        ],
    },

    "excel": {
        "aliases": [
            "excel",
            "microsoft excel",
            "ms excel",
        ],
        "executables": [
            "EXCEL.EXE",
            "excel.exe",
        ],
    },

    "powershell": {
        "aliases": [
            "powershell",
            "windows powershell",
            "pwsh",
        ],
        "executables": [
            "powershell.exe",
            "pwsh.exe",
        ],
    },

    "cmd": {
        "aliases": [
            "cmd",
            "command prompt",
            "terminal",
            "command line",
        ],
        "executables": [
            "cmd.exe",
        ],
    },

    "discord": {
        "aliases": ["discord"],
        "executables": ["Discord.exe", "Update.exe"],
    },
    "spotify": {
        "aliases": ["spotify"],
        "executables": ["Spotify.exe"],
    },
    "outlook": {
        "aliases": ["outlook", "microsoft outlook"],
        "executables": ["OUTLOOK.EXE", "outlook.exe"],
    },
    "teams": {
        "aliases": ["teams", "microsoft teams"],
        "executables": ["ms-teams.exe", "Teams.exe"],
    },
}


# =========================================================
# WINDOWS CONSTANTS
# =========================================================

if os.name == "nt":
    SW_RESTORE = 9


# =========================================================
# APPLICATION RESOLUTION
# =========================================================

def _resolve_application(application):
    """
    Convert an application alias into the canonical
    application name.
    """

    requested = str(application).strip().lower()

    for name, config in ALLOWED_APPS.items():

        if requested == name:
            return name

        if requested in config["aliases"]:
            return name

    return None


# =========================================================
# EXECUTABLE RESOLUTION
# =========================================================

def _find_executable(application):
    """
    Find the executable available on the system PATH
    or in common install locations.
    """

    config = ALLOWED_APPS[application]

    for executable in config["executables"]:

        found = shutil.which(executable)

        if found:
            return found

    # Common install locations for browsers and Office
    extra_paths = {
        "chrome": [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ],
        "edge": [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ],
        "word": [
            os.path.expandvars(r"%ProgramFiles%\Microsoft Office\root\Office16\WINWORD.EXE"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft Office\root\Office16\WINWORD.EXE"),
        ],
        "excel": [
            os.path.expandvars(r"%ProgramFiles%\Microsoft Office\root\Office16\EXCEL.EXE"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft Office\root\Office16\EXCEL.EXE"),
        ],
    }

    for path in extra_paths.get(application, []):
        if os.path.isfile(path):
            return path

    return None


# =========================================================
# WINDOW ENUMERATION
# =========================================================

def _get_windows():
    """
    Return visible top-level Windows windows.

    Each result contains:

        hwnd
        pid
        title
    """

    if os.name != "nt":
        return []

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

        buffer = ctypes.create_unicode_buffer(
            length + 1
        )

        user32.GetWindowTextW(
            hwnd,
            buffer,
            length + 1,
        )

        title = buffer.value.strip()

        if not title:
            return True

        process_id = ctypes.c_ulong()

        user32.GetWindowThreadProcessId(
            hwnd,
            ctypes.byref(process_id),
        )

        windows.append(
            {
                "hwnd": int(hwnd),
                "pid": int(process_id.value),
                "title": title,
            }
        )

        return True

    callback_function = EnumWindowsProc(callback)

    user32.EnumWindows(
        callback_function,
        0,
    )

    return windows


# =========================================================
# FIND WINDOW BY PROCESS
# =========================================================

def _find_window_by_pid(pid):
    """
    Find a visible application window belonging
    to a specific process.
    """

    if not pid:
        return None

    windows = _get_windows()

    for window in windows:

        if window["pid"] == pid:
            return window

    return None


# =========================================================
# FIND WINDOW BY APPLICATION NAME
# =========================================================

def _find_application_window(application):
    """
    Try to find an existing window belonging to one
    of the supported applications.
    """

    application = _resolve_application(application)

    if not application:
        return None

    windows = _get_windows()

    if not windows:
        return None

    name = application.lower()

    # -----------------------------------------------------
    # Title-based matching
    # -----------------------------------------------------

    title_keywords = {
        "notepad": [
            "notepad",
        ],
        "calculator": [
            "calculator",
        ],
        "paint": [
            "paint",
        ],
        "vscode": [
            "visual studio code",
            "vs code",
        ],
        "chrome": [
            "google chrome",
            "chrome",
        ],
        "edge": [
            "microsoft edge",
            "edge",
        ],
        "explorer": [
            "file explorer",
            "explorer",
        ],
        "word": [
            "word",
            "microsoft word",
        ],
        "excel": [
            "excel",
            "microsoft excel",
        ],
        "powershell": [
            "powershell",
            "windows powershell",
        ],
        "cmd": [
            "command prompt",
            "cmd.exe",
        ],
    }

    keywords = title_keywords.get(
        name,
        [],
    )

    for window in windows:

        title = window["title"].lower()

        for keyword in keywords:

            if keyword in title:

                return window

    return None


# =========================================================
# FOCUS WINDOW
# =========================================================

def _focus_window(hwnd):
    """
    Force a window to the foreground.

    Uses AttachThreadInput — the reliable way to steal focus
    on modern Windows when another app (e.g. Aethra) currently
    owns the foreground.
    """

    if os.name != "nt":
        return False

    if not hwnd:
        return False

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.1)

        # Bring to top without requiring foreground rights first
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)

        foreground = user32.GetForegroundWindow()
        if foreground == hwnd:
            return True

        # AttachThreadInput trick
        current_thread = kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        foreground_thread = 0
        if foreground:
            foreground_thread = user32.GetWindowThreadProcessId(
                foreground, None
            )

        attached_fg = False
        attached_target = False

        if foreground_thread and foreground_thread != current_thread:
            attached_fg = bool(
                user32.AttachThreadInput(
                    current_thread, foreground_thread, True
                )
            )

        if target_thread and target_thread != current_thread:
            attached_target = bool(
                user32.AttachThreadInput(
                    current_thread, target_thread, True
                )
            )

        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        user32.SetActiveWindow(hwnd)

        time.sleep(0.2)

        # Detach
        if attached_target:
            user32.AttachThreadInput(
                current_thread, target_thread, False
            )
        if attached_fg:
            user32.AttachThreadInput(
                current_thread, foreground_thread, False
            )

        time.sleep(0.1)
        return user32.GetForegroundWindow() == hwnd

    except Exception:
        try:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.15)
            return user32.GetForegroundWindow() == hwnd
        except Exception:
            return False


# =========================================================
# WAIT FOR WINDOW
# =========================================================

def _wait_for_window(
    application,
    pid=None,
    timeout=3.0,
):
    """
    Wait briefly for an application window to appear.
    """

    start_time = time.time()

    while time.time() - start_time < timeout:

        window = None

        if pid:
            window = _find_window_by_pid(pid)

        if window is None:
            window = _find_application_window(
                application
            )

        if window:
            return window

        time.sleep(0.15)

    return None


# =========================================================
# OPEN APPLICATION
# =========================================================

def open_application(application):
    """
    Open an allowlisted desktop application.

    The function verifies the result by looking for an
    actual application window when possible.
    """

    requested = str(
        application
    ).strip().lower()

    resolved = _resolve_application(
        requested
    )

    # -----------------------------------------------------
    # Allowlist verification
    # -----------------------------------------------------

    if not resolved:

        return {
            "success": False,
            "verified": False,
            "error": (
                f"Application '{requested}' "
                "is not allowlisted."
            ),
        }

    # -----------------------------------------------------
    # Check whether it is already open
    # -----------------------------------------------------

    existing_window = _find_application_window(
        resolved
    )

    if existing_window:

        focused = _focus_window(
            existing_window["hwnd"]
        )
        time.sleep(0.3)

        return {
            "success": True,
            "verified": True,
            "application": resolved,
            "already_running": True,
            "window_found": True,
            "window_title": existing_window["title"],
            "window_handle": existing_window["hwnd"],
            "pid": existing_window["pid"],
            "focus_verified": focused,
            "verification_type": "existing_window",
            "message": (
                f"{resolved} was already open and focused "
                "for input."
            ),
        }

    # -----------------------------------------------------
    # Locate executable
    # -----------------------------------------------------

    executable = _find_executable(
        resolved
    )

    if not executable:

        return {
            "success": False,
            "verified": False,
            "application": resolved,
            "error": (
                f"Could not find the executable "
                f"for '{resolved}'."
            ),
        }

    # -----------------------------------------------------
    # Launch
    # -----------------------------------------------------

    try:

        creation_flags = 0

        if hasattr(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
        ):
            creation_flags = (
                subprocess.CREATE_NEW_PROCESS_GROUP
            )

        process = subprocess.Popen(
            [executable],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creation_flags,
        )

    except FileNotFoundError:

        return {
            "success": False,
            "verified": False,
            "application": resolved,
            "executable": executable,
            "error": (
                "The application executable "
                "could not be found."
            ),
        }

    except PermissionError:

        return {
            "success": False,
            "verified": False,
            "application": resolved,
            "executable": executable,
            "error": (
                "Windows denied permission to "
                "start the application."
            ),
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "application": resolved,
            "executable": executable,
            "error": str(exc),
        }

    # -----------------------------------------------------
    # Give the application time to create its window
    # -----------------------------------------------------

    time.sleep(0.6)

    # -----------------------------------------------------
    # Check whether process exited immediately
    # -----------------------------------------------------

    return_code = process.poll()

    # -----------------------------------------------------
    # Look for actual application window
    # -----------------------------------------------------

    window = _wait_for_window(
        resolved,
        pid=process.pid,
        timeout=3.0,
    )

    # -----------------------------------------------------
    # Window successfully detected
    # -----------------------------------------------------

    if window:

        focused = _focus_window(
            window["hwnd"]
        )
        # Extra settle time so the next keystrokes land here
        time.sleep(0.35)

        # Re-check foreground
        try:
            import ctypes
            fg = ctypes.windll.user32.GetForegroundWindow()
            focused = bool(fg == window["hwnd"]) or focused
        except Exception:
            pass

        return {
            "success": True,
            "verified": True,
            "application": resolved,
            "already_running": False,
            "executable": executable,
            "pid": window["pid"],
            "window_found": True,
            "window_title": window["title"],
            "window_handle": window["hwnd"],
            "focus_verified": focused,
            "verification_type": "window_detected",
            "message": (
                f"Opened {resolved}, focused its window, "
                "and waited for it to become ready for input."
            ),
        }

    # -----------------------------------------------------
    # Process still alive but window was not detected
    # -----------------------------------------------------

    if return_code is None:

        return {
            "success": True,
            "verified": True,
            "application": resolved,
            "already_running": False,
            "executable": executable,
            "pid": process.pid,
            "window_found": False,
            "focus_verified": False,
            "verification_type": "process_alive",
            "message": (
                f"{resolved} started successfully, "
                "but its window could not yet be detected."
            ),
        }

    # -----------------------------------------------------
    # Process exited and no window appeared
    # -----------------------------------------------------

    return {
        "success": False,
        "verified": False,
        "application": resolved,
        "executable": executable,
        "pid": process.pid,
        "window_found": False,
        "exit_code": return_code,
        "error": (
            f"{resolved} started but exited before "
            "a usable application window appeared."
        ),
    }


# =========================================================
# FOCUS APPLICATION
# =========================================================

def focus_application(application):
    """
    Find an allowlisted application's window and bring it
    to the foreground.

    This does not launch the application.
    """

    requested = str(
        application
    ).strip().lower()

    resolved = _resolve_application(
        requested
    )

    # -----------------------------------------------------
    # Allowlist verification
    # -----------------------------------------------------

    if not resolved:

        return {
            "success": False,
            "verified": False,
            "error": (
                f"Application '{requested}' "
                "is not allowlisted."
            ),
        }

    # -----------------------------------------------------
    # Find existing window
    # -----------------------------------------------------

    window = _find_application_window(
        resolved
    )

    if not window:

        return {
            "success": False,
            "verified": False,
            "application": resolved,
            "window_found": False,
            "error": (
                f"Could not find an open window "
                f"for {resolved}."
            ),
        }

    # -----------------------------------------------------
    # Focus window
    # -----------------------------------------------------

    focused = _focus_window(
        window["hwnd"]
    )
    time.sleep(0.3)

    if not focused:

        return {
            "success": True,
            "verified": True,
            "application": resolved,
            "window_found": True,
            "window_title": window["title"],
            "window_handle": window["hwnd"],
            "pid": window["pid"],
            "focus_verified": False,
            "verification_type": "window_detected",
            "message": (
                f"Found {resolved}, but Windows "
                "did not confirm foreground focus."
            ),
        }

    return {
        "success": True,
        "verified": True,
        "application": resolved,
        "window_found": True,
        "window_title": window["title"],
        "window_handle": window["hwnd"],
        "pid": window["pid"],
        "focus_verified": True,
        "verification_type": "foreground_window",
        "message": (
            f"{resolved} is now the active window."
        ),
    }


def get_active_window():
    """
    Return information about the currently active Windows window.
    """

    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()

        if not hwnd:
            return {
                "success": False,
                "verified": False,
                "error": "Could not determine the active window."
            }

        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)

        buffer = ctypes.create_unicode_buffer(
            length + 1
        )

        ctypes.windll.user32.GetWindowTextW(
            hwnd,
            buffer,
            length + 1
        )

        title = buffer.value.strip()

        pid = ctypes.c_ulong()

        ctypes.windll.user32.GetWindowThreadProcessId(
            hwnd,
            ctypes.byref(pid)
        )

        return {
            "success": True,
            "verified": True,
            "window_handle": hwnd,
            "window_title": title,
            "pid": pid.value,
            "verification_type": "foreground_window",
            "message": (
                f"Active window: "
                f"{title or 'Untitled window'}"
            )
        }

    except Exception as exc:

        return {
            "success": False,
            "verified": False,
            "error": str(exc)
        }



# =========================================================
# APP DISCOVERY + ARBITRARY EXECUTABLE LAUNCH
# =========================================================

def search_installed_apps(query: str = "", limit: int = 15):
    """
    Search for installed / discoverable applications.

    Sources (best-effort, Windows):
    - Start Menu shortcuts (.lnk)
    - Common install directories
    - Allowlisted apps (always included when matching)

    Returns candidate name + path pairs. Does not launch anything.
    """
    try:
        query = (query or "").strip().lower()
        limit = max(1, min(int(limit or 15), 40))

        candidates = []
        seen_paths = set()

        def _add(name, path, source):
            if not path:
                return
            path_norm = os.path.normcase(os.path.abspath(path))
            if path_norm in seen_paths:
                return
            if not os.path.isfile(path):
                return
            seen_paths.add(path_norm)
            candidates.append({
                "name": name,
                "path": path,
                "source": source,
            })

        # 1) Allowlisted apps first (fast path awareness)
        for app_key, config in ALLOWED_APPS.items():
            if query and query not in app_key and not any(
                query in a for a in config.get("aliases", [])
            ):
                # still try resolve — may match executable name
                pass
            resolved_path = _find_executable(app_key)
            if resolved_path:
                if not query or query in app_key or query in resolved_path.lower():
                    _add(app_key, resolved_path, "allowlist")

        # 2) Start Menu shortcuts
        start_menu_roots = []
        for env in ("PROGRAMDATA", "APPDATA"):
            base = os.environ.get(env)
            if not base:
                continue
            if env == "PROGRAMDATA":
                start_menu_roots.append(
                    os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs")
                )
            else:
                start_menu_roots.append(
                    os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs")
                )

        for root in start_menu_roots:
            if not os.path.isdir(root):
                continue
            for dirpath, _dirnames, filenames in os.walk(root):
                for filename in filenames:
                    if not filename.lower().endswith(".lnk"):
                        continue
                    name = os.path.splitext(filename)[0]
                    if query and query not in name.lower():
                        continue
                    # Resolve .lnk target when possible
                    lnk_path = os.path.join(dirpath, filename)
                    target = _resolve_shortcut(lnk_path)
                    if target and target.lower().endswith(".exe"):
                        _add(name, target, "start_menu")
                if len(candidates) >= limit * 3:
                    break

        # 3) Common install directories (shallow)
        common_dirs = []
        for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base and os.path.isdir(base):
                common_dirs.append(base)

        for root in common_dirs:
            try:
                entries = os.listdir(root)
            except Exception:
                continue
            for entry in entries:
                app_dir = os.path.join(root, entry)
                if not os.path.isdir(app_dir):
                    continue
                if query and query not in entry.lower():
                    continue
                # Look one level for an exe matching the folder name
                try:
                    for filename in os.listdir(app_dir):
                        if not filename.lower().endswith(".exe"):
                            continue
                        if query and query not in filename.lower() and query not in entry.lower():
                            continue
                        # Skip obvious non-app binaries
                        skip = (
                            "uninstall", "update", "crash", "helper",
                            "setup", "installer", "vcredist",
                        )
                        low = filename.lower()
                        if any(s in low for s in skip):
                            continue
                        _add(entry, os.path.join(app_dir, filename), "program_files")
                        break
                except Exception:
                    continue

        # Rank: allowlist first, then start menu, then program files
        source_rank = {"allowlist": 0, "start_menu": 1, "program_files": 2}
        candidates.sort(
            key=lambda c: (
                source_rank.get(c["source"], 9),
                c["name"].lower(),
            )
        )

        results = candidates[:limit]
        return {
            "success": True,
            "verified": True,
            "query": query,
            "count": len(results),
            "apps": results,
            "message": (
                f"Found {len(results)} app candidate(s)"
                + (f" matching '{query}'." if query else ".")
            ),
        }

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }


def _resolve_shortcut(lnk_path: str):
    """
    Resolve a Windows .lnk shortcut to its target path.
    Best-effort; returns None on failure.
    """
    try:
        # PowerShell is reliable for .lnk resolution without extra packages
        import subprocess as sp
        safe = lnk_path.replace("'", "''")
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "$w = New-Object -ComObject WScript.Shell; "
                f"$s = $w.CreateShortcut('{safe}'); "
                "$s.TargetPath"
            ),
        ]
        result = sp.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        target = (result.stdout or "").strip()
        if target and os.path.isfile(target):
            return target
        return None
    except Exception:
        return None


def open_executable(path: str):
    """
    Launch an arbitrary .exe by full path.

    Intended for apps discovered via search_installed_apps
    that are not on the allowlist. Should require user permission
    at the brain/UI layer.
    """
    try:
        path = str(path or "").strip().strip('"')
        if not path:
            return {
                "success": False,
                "verified": False,
                "error": "Executable path is required.",
            }

        path = os.path.abspath(path)

        if not os.path.isfile(path):
            return {
                "success": False,
                "verified": False,
                "error": f"File not found: {path}",
            }

        if not path.lower().endswith(".exe"):
            return {
                "success": False,
                "verified": False,
                "error": "Only .exe files can be launched this way.",
            }

        # Block obvious dangerous locations / names
        low = path.lower()
        blocked_bits = [
            "\\windows\\system32\\",
            "\\windows\\syswow64\\",
        ]
        # Allow system32 only for known safe tools is complex —
        # we allow but still require UI permission. Soft-warn only.
        dangerous_names = [
            "format.exe", "diskpart.exe", "regedit.exe",
            "shutdown.exe", "taskkill.exe",
        ]
        base = os.path.basename(low)
        if base in dangerous_names:
            return {
                "success": False,
                "verified": False,
                "error": (
                    f"Launching '{base}' is blocked for safety. "
                    "Use a more specific system tool flow if needed."
                ),
            }

        process = subprocess.Popen(
            [path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            cwd=os.path.dirname(path) or None,
        )

        time.sleep(0.5)

        if process.poll() is not None and process.returncode not in (0, None):
            return {
                "success": False,
                "verified": False,
                "path": path,
                "error": f"Process exited immediately with code {process.returncode}.",
            }

        return {
            "success": True,
            "verified": True,
            "path": path,
            "pid": process.pid,
            "message": f"Launched executable: {path}",
        }

    except Exception as exc:
        return {
            "success": False,
            "verified": False,
            "error": str(exc),
        }
