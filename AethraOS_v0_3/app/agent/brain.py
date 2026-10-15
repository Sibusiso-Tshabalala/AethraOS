import json
from typing import Any, Dict, Optional

from openai import OpenAI

from app.config import settings
from app.agent.task_engine import TaskEngine
from app.agent.coordinator import AgentCoordinator
from app.agent.memory import MemoryStore

from app.tools.system import get_system_info, get_system_health
from app.tools.applications import (
    open_application,
    focus_application,
    get_active_window,
    search_installed_apps,
    open_executable,
)
from app.tools.files import list_downloads, create_text_file
from app.tools.scheduler import (
    create_reminder,
    create_alarm,
    list_reminders,
    cancel_reminder,
)
from app.tools.vision import see_screen
from app.tools.calendar_local import (
    add_calendar_event,
    get_agenda,
    cancel_calendar_event,
)
from app.tools.gmail_draft import (
    create_gmail_draft,
    list_gmail_drafts,
    open_gmail_draft,
)
from app.tools.digest import what_did_i_miss
from app.tools.calendar_sync import import_ics, sync_outlook_desktop
from app.tools.context_pack import build_context_pack
from app.tools.inbox import read_outlook_inbox, read_gmail_inbox
from app.tools.vision_model import ask_vision
from app.tools.projects import create_project, run_project
from app.tools.layout import arrange_windows
from app.tools.workspace import open_in_vscode, health_check
from app.tools.mail_side import draft_reply_on_side, import_google_calendar_url
from app.tools.google_account import (
    connect_google,
    list_google_threads,
    reply_in_gmail_thread,
    list_google_events,
    reply_in_outlook_thread,
    send_gmail_draft,
)
from app.tools.morning_brief import morning_brief, prepare_inbox_replies
from app.tools.workflows import save_workflow, list_workflows, get_workflow
from app.tools.watcher import watch_folder, poll_watch
from app.tools.inbox_watch import poll_inbox
from app.tools.read_file_tool import read_user_file
from app.tools.web_search import search_web, news_brief
from app.tools.self_aware import (
    inventory_project,
    read_project_file,
    propose_patch,
    backup_project_file,
    restore_backup,
    repair_history,
)

from app.tools.computer import (
    take_screenshot,
    get_screen_text,
    get_screen_summary,
    get_monitor_info,
    get_clipboard,
    set_clipboard,
    list_open_windows,
    manage_window,
    find_ui_elements,
    click_ui_element,
    type_into_ui_element,
    open_url,
    get_mouse_position,
    move_mouse,
    click_mouse,
    scroll_mouse,
    type_text,
    press_key,
    hotkey,
)


class PermissionRequired(Exception):
    def __init__(self, tool_name: str, arguments: Dict[str, Any]):
        self.tool_name = tool_name
        self.arguments = arguments
        super().__init__(f"Permission required for {tool_name}")


class AethraBrain:

    def _life_tools(self):
        return [
            {
                "type": "function",
                "name": "see_screen",
                "description": (
                    "Read the live desktop from the UI Automation tree "
                    "(window titles and control text), plus an optional OCR sample. "
                    "Use this to see the screen, not only a screenshot."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_ocr": {"type": "boolean"},
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "add_calendar_event",
                "description": "Add a local calendar event. when uses the same phrases as reminders.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "when": {"type": "string"},
                        "notes": {"type": "string"},
                        "duration_minutes": {"type": "integer"},
                    },
                    "required": ["title", "when"],
                },
            },
            {
                "type": "function",
                "name": "get_agenda",
                "description": "List local calendar events for today or tomorrow.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "day": {"type": "string", "enum": ["today", "tomorrow"]},
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "cancel_calendar_event",
                "description": "Cancel a local calendar event by id.",
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "integer"}},
                    "required": ["id"],
                },
            },
            {
                "type": "function",
                "name": "create_gmail_draft",
                "description": (
                    "Save a Gmail reply draft locally. Never sends. "
                    "Show the draft to the user and wait for approval."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["body"],
                },
            },
            {
                "type": "function",
                "name": "list_gmail_drafts",
                "description": "List pending Gmail drafts waiting for approval.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "type": "function",
                "name": "open_gmail_draft",
                "description": (
                    "Open Gmail compose with a saved draft ONLY after the user approved it. "
                    "Does not press Send."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "approved": {"type": "boolean"},
                    },
                    "required": ["id", "approved"],
                },
            },
            {
                "type": "function",
                "name": "what_did_i_miss",
                "description": (
                    "Catch-up digest: reminders, today's calendar, pending drafts, open windows."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "type": "function",
                "name": "import_ics",
                "description": (
                    "Import a Google or Outlook .ics calendar file into the local calendar. "
                    "Does not upload anything."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["path"],
                },
            },
            {
                "type": "function",
                "name": "sync_outlook_desktop",
                "description": (
                    "Read upcoming events from the local Outlook desktop app into the local calendar. "
                    "Requires Outlook and pywin32."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days_ahead": {"type": "integer"},
                        "limit": {"type": "integer"},
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "build_context_pack",
                "description": (
                    "Build a cross-app context pack from the active window, recent files, "
                    "memory, today's calendar, and pending drafts. Use when the user is coding "
                    "and wants the related doc or email."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "read_outlook_inbox",
                "description": "Read recent Outlook desktop inbox messages. Does not send mail.",
                "parameters": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer"}},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "read_gmail_inbox",
                "description": (
                    "Read recent Gmail messages via IMAP if GMAIL_USER and "
                    "GMAIL_APP_PASSWORD are set. Does not send mail."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer"}},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "ask_vision",
                "description": (
                    "Ask the local vision model what is on screen, including icons and dialogs. "
                    "Falls back to UI Automation and OCR if the model cannot see images."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "create_project",
                "description": (
                    "Create a project folder inside the user profile. folder can be Documents, "
                    "Desktop, Downloads, or any path under the user home. language can be python, "
                    "javascript, typescript, html, csharp, java, cpp, or go."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "language": {"type": "string"},
                        "folder": {"type": "string"},
                        "files": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "filename": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": ["name"],
                },
            },
            {
                "type": "function",
                "name": "run_project",
                "description": (
                    "Run a project Aethra created, only inside the user profile. "
                    "Supports python, javascript, typescript, csharp, and go. No arbitrary shell."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string"},
                        "language": {"type": "string"},
                    },
                    "required": ["project_path", "language"],
                },
            },
            {
                "type": "function",
                "name": "arrange_windows",
                "description": "Put two open windows side by side, left and right.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "left_title": {"type": "string"},
                        "right_title": {"type": "string"},
                    },
                    "required": ["left_title", "right_title"],
                },
            },
            {
                "type": "function",
                "name": "open_in_vscode",
                "description": "Open a project folder in VS Code.",
                "parameters": {
                    "type": "object",
                    "properties": {"project_path": {"type": "string"}},
                    "required": ["project_path"],
                },
            },
            {
                "type": "function",
                "name": "health_check",
                "description": "Check LM Studio, Tesseract, pywinauto, microphone library, Outlook, and Gmail config.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "type": "function",
                "name": "draft_reply_on_side",
                "description": (
                    "While the user codes, open the related Gmail or Outlook thread search "
                    "and save a reply draft. Never sends."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "source": {"type": "string"},
                    },
                    "required": ["subject", "body"],
                },
            },
            {
                "type": "function",
                "name": "import_google_calendar_url",
                "description": "Import a secret Google or Outlook iCal https URL into the local calendar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["url"],
                },
            },
            {
                "type": "function",
                "name": "connect_google",
                "description": "Start Google OAuth using data/google_credentials.json. Does not send mail.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "type": "function",
                "name": "list_google_threads",
                "description": "List recent Gmail threads after Google is connected.",
                "parameters": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer"}},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "reply_in_gmail_thread",
                "description": "Create a draft reply inside a real Gmail thread. Never sends.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "thread_id": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["thread_id", "body"],
                },
            },
            {
                "type": "function",
                "name": "list_google_events",
                "description": "List upcoming Google Calendar events after Google is connected.",
                "parameters": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer"}},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "reply_in_outlook_thread",
                "description": "Open an Outlook reply in the matching message thread. Never sends.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["subject", "body"],
                },
            },
            {
                "type": "function",
                "name": "queue_side_task",
                "description": (
                    "Start mail or calendar work in parallel while the desktop task continues. "
                    "kind is draft, outlook_inbox, agenda, or gmail_threads. Does not send mail."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string"},
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["kind"],
                },
            },
            {
                "type": "function",
                "name": "morning_brief",
                "description": "Morning brief: greeting, today's calendar, reminders, recent mail, unsent drafts. Does not send.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "type": "function",
                "name": "prepare_inbox_replies",
                "description": "Draft replies for recent mail and wait. Never sends.",
                "parameters": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer"}},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "send_gmail_draft",
                "description": "Send a Gmail API draft only after the user confirms the exact text. approved must be true.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "draft_id": {"type": "string"},
                        "approved": {"type": "boolean"},
                    },
                    "required": ["draft_id", "approved"],
                },
            },
            {
                "type": "function",
                "name": "save_workflow",
                "description": "Save a named workflow of tool steps. Does not run it.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "steps": {"type": "array"},
                    },
                    "required": ["name", "steps"],
                },
            },
            {
                "type": "function",
                "name": "list_workflows",
                "description": "List saved workflow names.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "type": "function",
                "name": "watch_folder",
                "description": "Watch a user folder, default Downloads, for new files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "folder": {"type": "string"},
                        "workflow": {"type": "string"},
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "poll_inbox",
                "description": "Check Outlook for new mail and suggest a plan. Does not open apps or send.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "type": "function",
                "name": "read_user_file",
                "description": "Read a text file inside the user profile so a fix or document can be suggested.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["path"],
                },
            },
            {
                "type": "function",
                "name": "search_web",
                "description": "Search the web for a short answer and links.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "type": "function",
                "name": "news_brief",
                "description": "Headlines for world, tech, or business.",
                "parameters": {
                    "type": "object",
                    "properties": {"topic": {"type": "string"}},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "run_workflow",
                "description": "Run a saved workflow step by step without asking the user to steer. High-risk steps still ask.",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
            {
                "type": "function",
                "name": "inventory_project",
                "description": "List Aethra's own Python files. Skips secrets, caches, and virtualenvs.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "type": "function",
                "name": "read_project_file",
                "description": "Read one of Aethra's own source files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["path"],
                },
            },
            {
                "type": "function",
                "name": "propose_patch",
                "description": "Save a proposed code fix. Does not edit any file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "problem": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["path", "problem", "suggestion"],
                },
            },
            {
                "type": "function",
                "name": "backup_project_file",
                "description": "Copy a project file into data/backups before any manual edit.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
            {
                "type": "function",
                "name": "restore_backup",
                "description": "Restore a file from data/backups. High risk. Requires approval.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "backup_path": {"type": "string"},
                        "target_path": {"type": "string"},
                    },
                    "required": ["backup_path", "target_path"],
                },
            },
            {
                "type": "function",
                "name": "repair_history",
                "description": "Show saved repair proposals. None of them are applied automatically.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        ]

    def __init__(
        self,
        permission_callback=None,
        task_progress_callback=None,
        failure_callback=None,
        side_callback=None,
    ):
        self.permission_callback = permission_callback
        self.task_progress_callback = task_progress_callback
        self.failure_callback = failure_callback
        self.side_callback = side_callback

        self.task_engine = TaskEngine()
        self.memory = MemoryStore()
        self.coordinator = AgentCoordinator()
        self.chat_history = self._load_chat_history()

        provider = settings.ai_provider.lower()

        if provider == "lmstudio":
            base_url = settings.ai_base_url or "http://localhost:1234/v1"
            self.client = OpenAI(
                base_url=base_url,
                api_key=settings.ai_api_key or "lm-studio",
            )
        else:
            self.client = OpenAI(api_key=settings.ai_api_key)

        self.model = self._resolve_model()

        self.tools = [
            {
                "type": "function",
                "name": "get_system_info",
                "description": "Get information about the user's computer.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "get_system_health",
                "description": "Short PC verdict: ok, tight, or hot. Includes RAM, disk, NVIDIA GPU, and the heaviest process.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            {
                "type": "function",
                "name": "open_application",
                "description": (
                    "Open an allowlisted desktop application "
                    "(notepad, chrome, vscode, etc.). Fast path."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "application": {"type": "string"},
                    },
                    "required": ["application"],
                },
            },
            {
                "type": "function",
                "name": "search_installed_apps",
                "description": (
                    "Search the PC for installed applications "
                    "(Start Menu, common install folders, allowlist). "
                    "Use when the app is not on the allowlist. "
                    "Does not launch anything."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "App name fragment, e.g. discord",
                        },
                        "limit": {"type": "integer"},
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "open_executable",
                "description": (
                    "Launch an arbitrary .exe by full path. "
                    "Use only after search_installed_apps. "
                    "Requires user permission."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Full path to the .exe",
                        },
                    },
                    "required": ["path"],
                },
            },
            {
                "type": "function",
                "name": "focus_application",
                "description": (
                    "Find an already-open allowed application "
                    "and bring its window to the foreground. "
                    "Use this before typing or interacting with "
                    "an application when necessary."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "application": {"type": "string"},
                    },
                    "required": ["application"],
                },
            },
            {
                "type": "function",
                "name": "get_active_window",
                "description": (
                    "Check which application window is currently "
                    "active and in the foreground."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "list_downloads",
                "description": "List files in the user's Downloads folder.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "create_text_file",
                "description": "Create a text file in the Downloads folder.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["filename", "content"],
                },
            },
            {
                "type": "function",
                "name": "take_screenshot",
                "description": "Take a screenshot of the user's screen.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "get_screen_text",
                "description": (
                    "Capture the screen and extract readable text "
                    "using local OCR. Use this when you need to "
                    "understand what is currently visible on the "
                    "user's screen."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string",
                            "description": (
                                "Optional. 'full' (default) or 'active'."
                            ),
                        },
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "get_screen_summary",
                "description": (
                    "Get a lightweight snapshot of current screen "
                    "awareness: active window title, mouse position, "
                    "monitor info, and a short sample of on-screen text."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "get_monitor_info",
                "description": (
                    "Get multi-monitor information: number of monitors "
                    "and virtual desktop size."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "get_clipboard",
                "description": (
                    "Read the current text content of the system clipboard."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "set_clipboard",
                "description": (
                    "Set the system clipboard to the given text."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to place on the clipboard.",
                        },
                    },
                    "required": ["text"],
                },
            },
            {
                "type": "function",
                "name": "list_open_windows",
                "description": (
                    "List currently visible top-level windows "
                    "(title, pid, handle)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "manage_window",
                "description": (
                    "Perform a window action: minimize, maximize, "
                    "restore, close, or focus. "
                    "If title is omitted, the current foreground "
                    "window is used."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "minimize",
                                "maximize",
                                "restore",
                                "close",
                                "focus",
                            ],
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Optional substring of the window title "
                                "to target. Case-insensitive."
                            ),
                        },
                    },
                    "required": ["action"],
                },
            },
            {
                "type": "function",
                "name": "find_ui_elements",
                "description": (
                    "Find UI elements in the foreground window by "
                    "accessible name and/or control type "
                    "(Button, Edit, MenuItem, etc.)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "control_type": {"type": "string"},
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "click_ui_element",
                "description": (
                    "Click a named UI element in the foreground window. "
                    "Prefer this over coordinate clicking when the "
                    "control has a name (e.g. Save, OK, Cancel)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "control_type": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            {
                "type": "function",
                "name": "type_into_ui_element",
                "description": (
                    "Type text into a named input/edit control "
                    "in the foreground window."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "text": {"type": "string"},
                        "control_type": {
                            "type": "string",
                            "description": "Defaults to Edit.",
                        },
                    },
                    "required": ["name", "text"],
                },
            },
            {
                "type": "function",
                "name": "open_url",
                "description": (
                    "Open an http/https URL in Chrome or Edge."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "browser": {
                            "type": "string",
                            "enum": ["chrome", "edge"],
                        },
                    },
                    "required": ["url"],
                },
            },

            {
                "type": "function",
                "name": "create_reminder",
                "description": (
                    "Create a local reminder. "
                    "when examples: 'in 10 minutes', 'at 9:30am', "
                    "'tomorrow at 2pm', '2026-10-06 14:30'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "when": {"type": "string"},
                    },
                    "required": ["message", "when"],
                },
            },
            {
                "type": "function",
                "name": "create_alarm",
                "description": (
                    "Create a local alarm (same time parsing as reminders)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "when": {"type": "string"},
                    },
                    "required": ["message", "when"],
                },
            },
            {
                "type": "function",
                "name": "list_reminders",
                "description": "List scheduled local reminders and alarms.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_fired": {"type": "boolean"},
                        "limit": {"type": "integer"},
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "cancel_reminder",
                "description": "Cancel a scheduled reminder/alarm by id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                    },
                    "required": ["id"],
                },
            },
            {
                "type": "function",
                "name": "get_mouse_position",
                "description": "Get the current mouse position.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "move_mouse",
                "description": "Move the mouse cursor to a screen position.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                    },
                    "required": ["x", "y"],
                },
            },
            {
                "type": "function",
                "name": "click_mouse",
                "description": "Click the mouse at its current screen position.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "middle"],
                        },
                    },
                    "required": [],
                },
            },
            {
                "type": "function",
                "name": "scroll_mouse",
                "description": "Scroll the mouse wheel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "integer"},
                    },
                    "required": ["amount"],
                },
            },
            {
                "type": "function",
                "name": "type_text",
                "description": (
                    "Type text slowly so the user can watch it. "
                    "ALWAYS pass target_application when the user named "
                    "an app (e.g. notepad, vscode) so focus can be forced "
                    "even if Aethra currently owns the foreground."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "interval": {
                            "type": "number",
                            "description": (
                                "Seconds between characters. "
                                "Default 0.05 (visible)."
                            ),
                        },
                        "target_application": {
                            "type": "string",
                            "description": (
                                "App to force-focus before typing, "
                                "e.g. notepad, vscode, chrome."
                            ),
                        },
                    },
                    "required": ["text"],
                },
            },
            {
                "type": "function",
                "name": "press_key",
                "description": "Press a keyboard key.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                    },
                    "required": ["key"],
                },
            },
            {
                "type": "function",
                "name": "hotkey",
                "description": "Press a keyboard shortcut.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["keys"],
                },
            },
        ]
        self.tools.extend(self._life_tools())

    # ---------------------------------------------------------
    # MODEL
    # ---------------------------------------------------------

    def _resolve_model(self) -> str:
        if settings.ai_model and settings.ai_model.lower() != "auto":
            return settings.ai_model

        try:
            models = self.client.models.list()
            if models.data:
                return models.data[0].id
        except Exception:
            pass

        return "local-model"

    # ---------------------------------------------------------
    # PERMISSIONS
    # ---------------------------------------------------------

    def _requires_permission(self, tool_name: str) -> bool:
        if not settings.require_action_approval:
            return False

        safe_tools = {
            "get_system_info",
            "get_system_health",
            "list_downloads",
            "get_mouse_position",
            "take_screenshot",
            "get_screen_text",
            "get_screen_summary",
            "get_monitor_info",
            "get_clipboard",
            "list_open_windows",
            "find_ui_elements",
            "search_installed_apps",
            "cancel_reminder",
            "create_alarm",
            "create_reminder",
            "list_reminders",
            "see_screen",
            "get_agenda",
            "list_gmail_drafts",
            "what_did_i_miss",
            "morning_brief",
            "poll_inbox",
            "read_user_file",
            "search_web",
            "news_brief",
            "list_workflows",
            "inventory_project",
            "read_project_file",
            "propose_patch",
            "repair_history",
            "add_calendar_event",
            "cancel_calendar_event",
            "create_gmail_draft",
            "import_ics",
            "sync_outlook_desktop",
            "build_context_pack",
            "read_outlook_inbox",
            "read_gmail_inbox",
            "ask_vision",
            "health_check",
            # open_executable and open_application still need approval
            # when require_action_approval is enabled.
        }
        return tool_name not in safe_tools

    def _tools_for(self, user_message: str):
        """Send only the tools this request needs so a small model can still call them."""
        text = (user_message or "").lower()
        core = {
            "open_application", "focus_application", "get_active_window",
            "type_text", "press_key", "hotkey", "take_screenshot",
            "get_screen_summary", "see_screen", "get_system_info",
            "get_system_health", "list_workflows", "run_workflow",
            "search_web", "news_brief", "morning_brief", "poll_inbox",
        }
        if any(word in text for word in ("project", "vscode", "vs code", "python", "code")):
            core.update({"create_project", "run_project", "open_in_vscode", "read_user_file", "read_project_file"})
        if any(word in text for word in ("mail", "email", "gmail", "outlook", "inbox")):
            core.update({"read_outlook_inbox", "read_gmail_inbox", "create_gmail_draft", "list_gmail_drafts"})
        if any(word in text for word in ("remind", "alarm", "calendar", "schedule")):
            core.update({"create_reminder", "create_alarm", "list_reminders", "get_agenda", "add_calendar_event"})
        if any(word in text for word in ("file", "inspect", "bug", "source")):
            core.update({"inventory_project", "read_project_file", "propose_patch", "repair_history"})
        if not any(word in text for word in ("project", "mail", "email", "remind", "file", "inspect")):
            core.update({"create_project", "open_in_vscode", "create_reminder", "read_outlook_inbox"})
        selected = [tool for tool in self.tools if tool.get("name") in core]
        return selected or self.tools[:12]

    def _risk_level(self, tool_name: str) -> str:
        high = {"send_gmail_draft", "open_executable", "reply_in_outlook_thread", "restore_backup"}
        medium = {"create_project", "run_project", "create_text_file", "queue_side_task", "watch_folder"}
        if tool_name in high:
            return "high"
        if tool_name in medium:
            return "medium"
        return "low"

    def _check_permission(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> None:
        if not self._requires_permission(tool_name):
            return
        risk = self._risk_level(tool_name)
        if risk == "low":
            return
        payload = dict(arguments or {})
        payload["_risk"] = risk
        if self.permission_callback:
            approved = self.permission_callback(tool_name, payload)
            if approved:
                return
        raise PermissionRequired(tool_name, arguments)

    # ---------------------------------------------------------
    # TOOL EXECUTION
    # ---------------------------------------------------------

    def _ask_failure_decision(self, tool_name: str, detail: str) -> str:
        """Ask the UI whether to retry, skip, or cancel a failed step."""
        if not self.failure_callback:
            return "cancel"
        try:
            choice = self.failure_callback(tool_name, detail)
            choice = str(choice or "cancel").strip().lower()
            if choice not in ("retry", "skip", "cancel"):
                return "cancel"
            return choice
        except Exception:
            return "cancel"

    def _history_path(self):
        import os
        folder = os.path.join(os.getcwd(), "data")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "chat_history.json")

    def _load_chat_history(self):
        try:
            import os
            path = self._history_path()
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, list):
                    return data[-24:]
        except Exception:
            pass
        return []

    def _save_chat_history(self):
        try:
            with open(self._history_path(), "w", encoding="utf-8") as handle:
                json.dump(self.chat_history[-24:], handle, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _remember_turn(self, user_message: str, answer: str) -> str:
        self.chat_history.append({"role": "user", "content": str(user_message)[:600]})
        self.chat_history.append({"role": "assistant", "content": str(answer)[:600]})
        self.chat_history = self.chat_history[-12:]
        self._save_chat_history()
        return answer

    def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        self._check_permission(tool_name, arguments)

        if tool_name == "see_screen":
            return see_screen(include_ocr=bool(arguments.get("include_ocr", True)))

        if tool_name == "add_calendar_event":
            return add_calendar_event(
                title=arguments["title"],
                when=arguments["when"],
                notes=arguments.get("notes", ""),
                duration_minutes=arguments.get("duration_minutes", 60),
            )

        if tool_name == "get_agenda":
            return get_agenda(arguments.get("day", "today"))

        if tool_name == "cancel_calendar_event":
            return cancel_calendar_event(arguments["id"])

        if tool_name == "create_gmail_draft":
            return create_gmail_draft(
                to=arguments.get("to", ""),
                subject=arguments.get("subject", ""),
                body=arguments.get("body", ""),
            )

        if tool_name == "list_gmail_drafts":
            return list_gmail_drafts()

        if tool_name == "open_gmail_draft":
            return open_gmail_draft(
                id=arguments["id"],
                approved=bool(arguments.get("approved", False)),
            )

        if tool_name == "what_did_i_miss":
            return what_did_i_miss()

        if tool_name == "import_ics":
            return import_ics(
                path=arguments["path"],
                limit=arguments.get("limit", 30),
            )

        if tool_name == "sync_outlook_desktop":
            return sync_outlook_desktop(
                days_ahead=arguments.get("days_ahead", 7),
                limit=arguments.get("limit", 20),
            )

        if tool_name == "build_context_pack":
            return build_context_pack(topic=arguments.get("topic", ""))

        if tool_name == "read_outlook_inbox":
            return read_outlook_inbox(limit=arguments.get("limit", 5))

        if tool_name == "read_gmail_inbox":
            return read_gmail_inbox(limit=arguments.get("limit", 5))

        if tool_name == "ask_vision":
            return ask_vision(question=arguments.get("question", ""))

        if tool_name == "create_project":
            return create_project(
                name=arguments["name"],
                language=arguments.get("language", "python"),
                folder=arguments.get("folder", "Documents"),
                files=arguments.get("files"),
            )

        if tool_name == "run_project":
            return run_project(
                project_path=arguments["project_path"],
                language=arguments.get("language", "python"),
            )

        if tool_name == "arrange_windows":
            return arrange_windows(
                left_title=arguments["left_title"],
                right_title=arguments["right_title"],
            )

        if tool_name == "open_in_vscode":
            return open_in_vscode(arguments["project_path"])

        if tool_name == "health_check":
            return health_check()

        if tool_name == "draft_reply_on_side":
            return draft_reply_on_side(
                to=arguments.get("to", ""),
                subject=arguments.get("subject", ""),
                body=arguments.get("body", ""),
                source=arguments.get("source", "gmail"),
            )

        if tool_name == "import_google_calendar_url":
            return import_google_calendar_url(
                url=arguments["url"],
                limit=arguments.get("limit", 30),
            )

        if tool_name == "connect_google":
            return connect_google()

        if tool_name == "list_google_threads":
            return list_google_threads(limit=arguments.get("limit", 5))

        if tool_name == "reply_in_gmail_thread":
            return reply_in_gmail_thread(
                thread_id=arguments["thread_id"],
                body=arguments.get("body", ""),
            )

        if tool_name == "list_google_events":
            return list_google_events(limit=arguments.get("limit", 5))

        if tool_name == "reply_in_outlook_thread":
            return reply_in_outlook_thread(
                subject=arguments.get("subject", ""),
                body=arguments.get("body", ""),
            )

        if tool_name == "queue_side_task":
            if not self.side_callback:
                return {"success": False, "verified": False, "error": "Side worker is not available."}
            self.side_callback(arguments)
            return {
                "success": True,
                "verified": True,
                "started": True,
                "message": "Side task started. Continue the desktop task. Nothing is sent.",
            }

        if tool_name == "morning_brief":
            return morning_brief()

        if tool_name == "prepare_inbox_replies":
            return prepare_inbox_replies(limit=arguments.get("limit", 3))

        if tool_name == "send_gmail_draft":
            return send_gmail_draft(
                draft_id=arguments["draft_id"],
                approved=bool(arguments.get("approved", False)),
            )

        if tool_name == "save_workflow":
            return save_workflow(arguments.get("name", ""), arguments.get("steps") or [])

        if tool_name == "list_workflows":
            return list_workflows()

        if tool_name == "watch_folder":
            return watch_folder(arguments.get("folder", ""), arguments.get("workflow", ""))

        if tool_name == "poll_inbox":
            return poll_inbox()

        if tool_name == "read_user_file":
            return read_user_file(arguments.get("path", ""), arguments.get("limit", 200))

        if tool_name == "search_web":
            return search_web(arguments.get("query", ""))

        if tool_name == "news_brief":
            return news_brief(arguments.get("topic", "world"))

        if tool_name == "run_workflow":
            found = get_workflow(arguments.get("name", ""))
            if not found.get("success"):
                return found
            completed = []
            for step in found.get("steps") or []:
                result = self._execute_tool(step.get("tool", ""), step.get("arguments") or {})
                completed.append({"tool": step.get("tool"), "result": result})
                if isinstance(result, dict) and result.get("success") is False:
                    return {"success": False, "verified": False, "completed": completed, "error": "Workflow stopped on a failed step."}
            return {"success": True, "verified": True, "completed": completed, "message": f"Ran workflow {arguments.get('name')}."}

        if tool_name == "inventory_project":
            return inventory_project()

        if tool_name == "read_project_file":
            return read_project_file(arguments.get("path", ""), arguments.get("limit", 200))

        if tool_name == "propose_patch":
            return propose_patch(
                arguments.get("path", ""),
                arguments.get("problem", ""),
                arguments.get("suggestion", ""),
            )

        if tool_name == "backup_project_file":
            return backup_project_file(arguments.get("path", ""))

        if tool_name == "restore_backup":
            return restore_backup(
                arguments.get("backup_path", ""),
                arguments.get("target_path", ""),
            )

        if tool_name == "repair_history":
            return repair_history()


        
        if tool_name == "create_reminder":
            return create_reminder(
                message=arguments["message"],
                when=arguments["when"],
            )

        if tool_name == "create_alarm":
            return create_alarm(
                message=arguments["message"],
                when=arguments["when"],
            )

        if tool_name == "list_reminders":
            return list_reminders(
                include_fired=bool(arguments.get("include_fired", False)),
                limit=arguments.get("limit", 20),
            )

        if tool_name == "cancel_reminder":
            return cancel_reminder(arguments["id"])

        if tool_name == "get_system_info":
            return get_system_info()

        if tool_name == "get_system_health":
            return get_system_health()

        if tool_name == "open_application":
            return open_application(arguments["application"])

        if tool_name == "search_installed_apps":
            return search_installed_apps(
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 15),
            )

        if tool_name == "open_executable":
            return open_executable(arguments["path"])

        if tool_name == "focus_application":
            return focus_application(arguments["application"])

        if tool_name == "get_active_window":
            return get_active_window()

        if tool_name == "list_downloads":
            return list_downloads()

        if tool_name == "create_text_file":
            return create_text_file(
                arguments["filename"],
                arguments["content"],
            )

        if tool_name == "take_screenshot":
            return take_screenshot()

        if tool_name == "get_screen_text":
            return get_screen_text(
                arguments.get("region", "full")
            )

        if tool_name == "get_screen_summary":
            return get_screen_summary()

        if tool_name == "get_monitor_info":
            return get_monitor_info()

        if tool_name == "get_clipboard":
            return get_clipboard()

        if tool_name == "set_clipboard":
            return set_clipboard(arguments["text"])

        if tool_name == "list_open_windows":
            return list_open_windows()

        if tool_name == "manage_window":
            return manage_window(
                action=arguments["action"],
                title=arguments.get("title"),
            )

        if tool_name == "find_ui_elements":
            return find_ui_elements(
                name=arguments.get("name", ""),
                control_type=arguments.get("control_type", ""),
            )

        if tool_name == "click_ui_element":
            return click_ui_element(
                name=arguments["name"],
                control_type=arguments.get("control_type", ""),
            )

        if tool_name == "type_into_ui_element":
            return type_into_ui_element(
                name=arguments["name"],
                text=arguments["text"],
                control_type=arguments.get("control_type", "Edit"),
            )

        if tool_name == "open_url":
            return open_url(
                url=arguments["url"],
                browser=arguments.get("browser", "chrome"),
            )

        if tool_name == "get_mouse_position":
            return get_mouse_position()

        if tool_name == "move_mouse":
            return move_mouse(arguments["x"], arguments["y"])

        if tool_name == "click_mouse":
            return click_mouse(arguments.get("button", "left"))

        if tool_name == "scroll_mouse":
            return scroll_mouse(arguments["amount"])

        if tool_name == "type_text":
            return type_text(
                arguments["text"],
                interval=arguments.get("interval", 0.05),
                target_application=arguments.get(
                    "target_application", ""
                ),
            )

        if tool_name == "press_key":
            return press_key(arguments["key"])

        if tool_name == "hotkey":
            return hotkey(arguments["keys"])

        return {
            "success": False,
            "verified": False,
            "error": f"Unknown tool: {tool_name}",
        }

    # ---------------------------------------------------------
    # TOOL RESULT VERIFICATION
    # ---------------------------------------------------------

    def _tool_result_successful(self, result: Any) -> bool:
        """
        Determine whether a tool actually succeeded.

        Tools can return structured results containing:
            success=True
            verified=True

        A task is considered failed when either success or
        verification explicitly reports False.

        Older/simple tools that do not return these fields
        are treated as successfully executed unless they
        raise an exception.
        """
        if not isinstance(result, dict):
            return True

        if result.get("success") is False:
            return False

        if result.get("verified") is False:
            return False

        return True

    def _verification_message(
        self,
        tool_name: str,
        result: Any,
    ) -> str:
        """
        Create a short internal message describing the
        verification state for the model.
        """
        if not isinstance(result, dict):
            return (
                f"{tool_name} executed successfully. "
                "No structured verification details were returned."
            )

        success = result.get("success")
        verified = result.get("verified")

        if success is False:
            return (
                f"{tool_name} failed. "
                f"The tool reported: {result}"
            )

        if verified is False:
            return (
                f"{tool_name} executed, but verification failed. "
                f"The tool reported: {result}"
            )

        if verified is True:
            return (
                f"{tool_name} executed successfully and "
                f"verification succeeded. Result: {result}"
            )

        if success is True:
            return (
                f"{tool_name} executed successfully. "
                f"Result: {result}"
            )

        return f"{tool_name} completed. Result: {result}"

    # ---------------------------------------------------------
    # TASK PROGRESS
    # ---------------------------------------------------------

    def _notify_task_progress(self) -> None:
        if self.task_progress_callback:
            try:
                self.task_progress_callback()
            except Exception:
                pass

    # ---------------------------------------------------------
    # COMPUTER AWARENESS
    # ---------------------------------------------------------

    def _get_computer_awareness(self) -> str:
        """
        Get a lightweight snapshot of the current computer state
        before Aethra begins a task.

        Prefers the richer get_screen_summary when available,
        otherwise falls back to active-window information only.
        """
        try:
            # Prefer the richer summary (window + mouse + OCR sample)
            summary = get_screen_summary()

            if isinstance(summary, dict) and summary.get("success"):
                lines = [
                    "\n\nCurrent computer awareness:",
                    f"- Active foreground window: {summary.get('active_window', 'Unknown')}",
                    f"- Active window process ID: {summary.get('active_pid', 'Unknown')}",
                ]

                mouse_x = summary.get("mouse_x")
                mouse_y = summary.get("mouse_y")
                if mouse_x is not None and mouse_y is not None:
                    lines.append(f"- Mouse position: ({mouse_x}, {mouse_y})")

                monitor_count = summary.get("monitor_count")
                v_w = summary.get("virtual_width")
                v_h = summary.get("virtual_height")
                if monitor_count is not None:
                    if v_w and v_h:
                        lines.append(
                            f"- Displays: {monitor_count} monitor(s), "
                            f"virtual desktop {v_w}x{v_h}"
                        )
                    else:
                        lines.append(f"- Displays: {monitor_count} monitor(s)")

                if summary.get("ocr_available") and summary.get("screen_text_sample"):
                    sample = summary["screen_text_sample"].strip()
                    if sample:
                        # Keep the injected sample short
                        if len(sample) > 400:
                            sample = sample[:400] + "..."
                        region = summary.get("ocr_region", "full")
                        lines.append(f"- Visible screen text sample ({region}):")
                        lines.append(sample)

                lines.append(
                    "- This is a starting-state snapshot. "
                    "The active window and screen content may change during the task."
                )
                return "\n".join(lines)

            # Fallback to basic active-window info
            result = get_active_window()

            if not isinstance(result, dict) or result.get("success") is not True:
                return (
                    "\n\nCurrent computer awareness:\n"
                    "- Active window information is unavailable."
                )

            title = result.get("window_title", "").strip() or "Untitled window"
            pid = result.get("pid")

            return (
                "\n\nCurrent computer awareness:\n"
                f"- Active foreground window: {title}\n"
                f"- Active window process ID: {pid}\n"
                "- This is a starting-state snapshot. "
                "The active window may change during the task."
            )
        except Exception:
            return (
                "\n\nCurrent computer awareness:\n"
                "- Active window information is unavailable."
            )

    def _refresh_computer_awareness(self) -> Optional[Dict[str, Any]]:
        """
        Refresh the current foreground-window state after
        a computer action.
        """
        try:
            result = get_active_window()

            if not isinstance(result, dict):
                return None

            if result.get("success") is not True:
                return None

            return {
                "window_title": (
                    result.get("window_title", "").strip()
                    or "Untitled window"
                ),
                "pid": result.get("pid"),
                "window_handle": result.get("window_handle"),
                "verified": result.get("verified", False),
            }
        except Exception:
            return None

    # ---------------------------------------------------------
    # COMPUTER ACTION RECOVERY
    # ---------------------------------------------------------

    def _attempt_computer_recovery(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_message: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt one safe recovery for common computer-action
        failures.

        This method does not bypass permissions.
        """
        recoverable_tools = {
            "type_text",
            "press_key",
            "hotkey",
            "click_mouse",
        }

        if tool_name not in recoverable_tools:
            return None

        message = user_message.lower()

        supported_applications = {
            "notepad": ["notepad", "note pad"],
            "calculator": ["calculator", "calc"],
            "paint": ["paint", "mspaint"],
            "vscode": ["vscode", "vs code", "visual studio code"],
            "chrome": ["chrome", "google chrome"],
            "edge": ["edge", "microsoft edge"],
            "explorer": ["explorer", "file explorer", "files"],
            "word": ["word", "microsoft word"],
            "excel": ["excel", "microsoft excel"],
            "powershell": ["powershell"],
            "cmd": ["cmd", "command prompt", "terminal"],
        }

        target_application = None
        for application, keywords in supported_applications.items():
            if any(keyword in message for keyword in keywords):
                target_application = application
                break

        if not target_application:
            return None

        active_window = get_active_window()

        if not isinstance(active_window, dict):
            return None

        if active_window.get("success") is not True:
            return None

        active_title = str(active_window.get("window_title", "")).lower()
        application_keywords = supported_applications[target_application]

        already_active = any(
            keyword in active_title for keyword in application_keywords
        )

        if already_active:
            return None

        try:
            focus_result = self._execute_tool(
                "focus_application",
                {"application": target_application},
            )

            if not self._tool_result_successful(focus_result):
                return {
                    "recovered": False,
                    "application": target_application,
                    "focus_result": focus_result,
                    "message": (
                        f"Recovery attempted, but "
                        f"{target_application} could not "
                        "be focused."
                    ),
                }

            refreshed = self._refresh_computer_awareness()

            return {
                "recovered": True,
                "application": target_application,
                "focus_result": focus_result,
                "awareness": refreshed,
                "message": (
                    f"Recovery focused {target_application} "
                    f"before retrying {tool_name}."
                ),
            }
        except Exception as exc:
            return {
                "recovered": False,
                "application": target_application,
                "error": str(exc),
                "message": (
                    f"Recovery failed while focusing "
                    f"{target_application}."
                ),
            }

    # ---------------------------------------------------------
    # TASK DETECTION
    # ---------------------------------------------------------

    def _is_task_request(self, message: str) -> bool:
        task_words = [
            "open",
            "create",
            "write",
            "type",
            "click",
            "move",
            "press",
            "check",
            "find",
            "show",
            "launch",
            "start",
            "save",
            "go to",
        ]

        message_lower = message.lower()
        matches = sum(1 for word in task_words if word in message_lower)
        return matches > 0

    # ---------------------------------------------------------
    # PERSISTENT MEMORY
    # ---------------------------------------------------------

    def handle_memory_command(self, message: str) -> Optional[str]:
        text = message.strip()
        lower_text = text.lower()

        # Save a memory
        remember_prefixes = [
            "remember that ",
            "remember ",
            "save this memory: ",
        ]

        for prefix in remember_prefixes:
            if lower_text.startswith(prefix):
                content = text[len(prefix):].strip()
                result = self.memory.remember(content)
                return result["message"]

        # Show all memories
        show_memory_commands = [
            "what do you remember about me?",
            "what do you remember?",
            "show my memories",
            "list my memories",
        ]

        if lower_text in show_memory_commands:
            memories = self.memory.get_all()
            if not memories:
                return "I don't have any saved memories yet."

            lines = [f"- {item['content']}" for item in memories]
            return "Here is what I remember:\n" + "\n".join(lines)

        # Forget a specific memory
        forget_prefixes = [
            "forget that ",
            "forget ",
            "remove memory: ",
        ]

        for prefix in forget_prefixes:
            if lower_text.startswith(prefix):
                phrase = text[len(prefix):].strip()
                result = self.memory.forget(phrase)

                if result.get("matches"):
                    matching_text = "\n".join(
                        f"- {item}" for item in result["matches"]
                    )
                    return result["message"] + "\n" + matching_text

                return result["message"]

        # Delete all memories only after clear confirmation
        if lower_text == "clear all my memories":
            return (
                "For safety, please type this exact "
                "confirmation if you want to permanently "
                "delete all saved memories:\n\n"
                "CONFIRM DELETE ALL MEMORIES"
            )

        if lower_text == "confirm delete all memories":
            result = self.memory.clear_all()
            return result["message"]

        return None

    def get_relevant_memories(self, message: str) -> str:
        memories = self.memory.search(message, limit=5)
        if not memories:
            return ""

        memory_lines = [f"- {item['content']}" for item in memories]
        return "\n\nRelevant saved memories:\n" + "\n".join(memory_lines)

    # ---------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------

    def respond(self, user_message: str) -> str:
        memory_response = self.handle_memory_command(user_message)
        if memory_response is not None:
            return memory_response

        self.task_engine.clear()

        if self._is_task_request(user_message):
            self.task_engine.create_task(user_message)
            self.task_engine.start_task()

        system_prompt = """
You are Aethra, an advanced local AI computer assistant.

You operate as the intelligence layer of AethraOS.

You can:
- answer questions
- inspect the computer
- open approved applications (Notepad, Calculator, Paint, VS Code, Chrome, Edge, File Explorer, Word, Excel, PowerShell, Command Prompt)
- search the PC for other installed apps (search_installed_apps)
- open a discovered .exe with user permission (open_executable)
- create local reminders and alarms (offline)
- list and cancel reminders
- see the live screen via UI Automation (see_screen), not only screenshots
- add and list local calendar events
- draft Gmail replies and open compose only after user approval (never auto-send)
- summarize what the user missed (reminders, agenda, drafts, open windows)
- import a Google/Outlook .ics file or sync the local Outlook calendar
- build a cross-app context pack from the active window, recent files, memory, and drafts
- read Outlook desktop inbox or Gmail IMAP inbox, then draft a reply for approval
- ask a local vision model what is on screen, including icons and dialogs
- create a project folder in Documents, Desktop, Downloads, or any folder in the user profile
- run that project with python, node, dotnet, or go and report the output
- place two windows side by side
- while the user codes, draft an email on the other side and wait for approval before compose opens
- open a project folder directly in VS Code
- after create_project, call open_in_vscode with project_path, then run_project with that same path and language. Do not ask the user for the file contents.
- Prefer a saved workflow with run_workflow when the user names one.
- For a repeated morning, use poll_inbox, search_web or news_brief, then say the next step. Do not open apps unless asked.
- Call the tool. Do not claim you typed, opened, or sent something unless the tool result says success.
- run a health check of local services
- import a secret Google or Outlook calendar URL
- inspect Downloads
- create text files
- take screenshots
- extract readable text from the screen using local OCR (get_screen_text)
- get a quick screen awareness summary (active window + mouse + text sample)
- read and set the system clipboard
- list open windows
- minimize, maximize, restore, close, or focus windows
- find and click named UI elements (buttons, menus) via UI Automation
- type into named input fields via UI Automation
- open http/https URLs in Chrome or Edge
- control the mouse
- check the active application window
- focus approved applications
- type text
- press keys
- use keyboard shortcuts

IMPORTANT SAFETY RULES:

1. Never perform destructive actions without explicit approval.
2. Never delete files.
3. Never access passwords, credentials, banking information, or private secrets.
4. Never execute arbitrary shell commands.
5. Use the available tools instead of pretending an action happened.
6. If a task requires multiple actions, first decide the logical sequence, then execute one step at a time.
7. For multi-step computer tasks, briefly outline the plan (in 2–5 short steps) before calling tools.
8. Keep the task sequence efficient and avoid unnecessary actions.
9. Verify the result when possible before considering the task complete.
10. Voice requests should be treated exactly like normal user messages.
11. If a task fails, explain what failed instead of pretending it succeeded.
12. Keep the user informed about important actions.
13. Prefer get_screen_text(region="active") when you only need text from the current window.
14. Use get_monitor_info or get_screen_summary when you need to understand the display layout.

VERIFICATION RULES:

- Pay attention to the success and verified fields returned by tools.
- success=false means the requested action failed.
- verified=false means the action could not be verified.
- Do not claim that an action succeeded when the tool reports failure.
- If a tool reports successful verification, you may tell the user that the action was verified.
- For mouse movement, the actual cursor position can be used as verification.
- For application launching, the launch process can be verified.
- For screenshots and files, successful file creation can be verified.
- For keyboard and mouse input, check active_window_before / active_window_after in the tool result.
- If verified=false after typing, focus was likely lost — call focus_application and retry type_text.
- If verification fails, explain the failure and attempt a sensible corrective action.
- CRITICAL TYPING SEQUENCE (always follow for "open X and type Y"):
  1. open_application (or focus_application if already open)
  2. Call type_text with BOTH text AND target_application set
     Example: type_text(text="Hello", target_application="notepad")
  3. target_application is REQUIRED when the user named an app — this forces
     focus away from Aethra onto that app before typing
  4. If type_text fails, call focus_application then retry type_text once
     with target_application set again
- Never claim text was typed into an app unless type_text reported success
  and verified=true.
- The user must be able to watch characters appear live in the target app.

You are an assistant operating a real computer.
- Never send email. create_gmail_draft, show the text, wait for approval, then open_gmail_draft(approved=true).
- Use see_screen when the user asks what is on screen, not only take_screenshot.
"""

        # Add instructions for the specialist selected by the coordinator
        agent_instructions = self.coordinator.get_agent_instructions(
            user_message
        )
        system_prompt += agent_instructions

        # Add current computer awareness for task requests
        if self._is_task_request(user_message):
            computer_awareness = self._get_computer_awareness()
            system_prompt += computer_awareness

        # Add relevant persistent memories
        relevant_memories = self.get_relevant_memories(user_message)
        system_prompt += relevant_memories

        conversation = [
            {"role": "system", "content": system_prompt},
        ]
        conversation.extend(self.chat_history[-4:])
        conversation.append({"role": "user", "content": user_message[:1500]})

        max_steps = 10

        # Allow at most one automatic recovery attempt
        # for each individual computer action.
        recovery_attempts: Dict[str, Any] = {}

        # Keep track of task steps that are temporarily waiting
        # for an automatic recovery/retry.
        recovery_steps: Dict[str, Any] = {}

        try:
            for _ in range(max_steps):
                try:
                    response = self.client.responses.create(
                        model=self.model,
                        input=conversation,
                        tools=self._tools_for(user_message),
                    )
                except Exception as exc:
                    if "context size" in str(exc).lower() or "8192" in str(exc):
                        short = conversation[:1] + conversation[-2:]
                        response = self.client.responses.create(
                            model=self.model,
                            input=short,
                            tools=self._tools_for(user_message),
                        )
                    else:
                        raise

                tool_calls = [
                    item
                    for item in response.output
                    if getattr(item, "type", None) == "function_call"
                ]

                # No more tools required
                if not tool_calls:
                    answer = response.output_text

                    # Only complete a task if it has not already failed
                    if self.task_engine.current_task:
                        if self.task_engine.get_status() != "failed":
                            self.task_engine.complete_task()
                            self._notify_task_progress()

                    return self._remember_turn(user_message, answer)

                # -------------------------------------------------
                # PRESERVE THE MODEL'S FUNCTION CALLS
                # -------------------------------------------------
                for call in tool_calls:
                    conversation.append({
                        "type": "function_call",
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": call.arguments,
                    })

                # -------------------------------------------------
                # EXECUTE TOOLS
                # -------------------------------------------------
                task_failed = False

                for call in tool_calls:
                    tool_name = call.name

                    try:
                        arguments = json.loads(call.arguments)
                    except Exception:
                        arguments = {}

                    step = None
                    recovery_key = (
                        f"{tool_name}:"
                        f"{json.dumps(arguments, sort_keys=True)}"
                    )

                    if self.task_engine.current_task:
                        # If this action previously failed but recovery succeeded,
                        # reuse the same task step for the retry.
                        if recovery_key in recovery_steps:
                            step = recovery_steps[recovery_key]
                        else:
                            step = self.task_engine.add_step(
                                f"Execute {tool_name}"
                            )
                            self.task_engine.start_step(step)

                        self._notify_task_progress()

                    # -------------------------------------------------
                    # EXECUTE THE TOOL
                    # -------------------------------------------------
                    try:
                        result = self._execute_tool(tool_name, arguments)
                    except Exception as exc:
                        result = {
                            "success": False,
                            "verified": False,
                            "error": str(exc),
                        }

                        if self.task_engine.current_task and step is not None:
                            self.task_engine.fail_step(step, str(exc))
                            self.task_engine.fail_task()
                            self._notify_task_progress()

                        task_failed = True

                        # Still feed the error back to the model
                        conversation.append({
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(
                                {
                                    "tool_result": result,
                                    "verification": (
                                        f"{tool_name} raised an exception: {exc}"
                                    ),
                                },
                                default=str,
                            ),
                        })
                        break  # stop the rest of the batch

                    # -------------------------------------------------
                    # VERIFY RESULT
                    # -------------------------------------------------
                    successful = self._tool_result_successful(result)

                    if self.task_engine.current_task and step is not None:
                        if successful:
                            # The action succeeded. Complete the existing step,
                            # including steps that were waiting for recovery.
                            self.task_engine.complete_step(step)

                            # The action has now recovered successfully,
                            # so remove its pending recovery state.
                            recovery_steps.pop(recovery_key, None)
                        else:
                            # Do NOT immediately fail the task.
                            # Give recovery a chance first.
                            recovery_result = self._attempt_computer_recovery(
                                tool_name,
                                arguments,
                                user_message,
                            )

                            if (
                                recovery_result
                                and recovery_result.get("recovered") is True
                            ):
                                # Keep this step alive while the model retries
                                # the original action.
                                recovery_steps[recovery_key] = step
                                task_failed = False
                            else:
                                detail = self._verification_message(tool_name, result)
                                choice = self._ask_failure_decision(tool_name, detail)
                                if choice == "retry":
                                    try:
                                        result = self._execute_tool(tool_name, arguments)
                                        if self._tool_result_successful(result):
                                            self.task_engine.complete_step(step)
                                            recovery_steps.pop(recovery_key, None)
                                            task_failed = False
                                        else:
                                            self.task_engine.fail_step(step, detail)
                                            self.task_engine.fail_task()
                                            task_failed = True
                                    except Exception as retry_exc:
                                        self.task_engine.fail_step(step, str(retry_exc))
                                        self.task_engine.fail_task()
                                        task_failed = True
                                elif choice == "skip":
                                    self.task_engine.fail_step(step, "Skipped by user")
                                    task_failed = False
                                else:
                                    self.task_engine.fail_step(step, detail)
                                    self.task_engine.fail_task()
                                    task_failed = True

                        self._notify_task_progress()

                    # -------------------------------------------------
                    # BUILD VERIFICATION CONTEXT FOR THE MODEL
                    # -------------------------------------------------
                    verification_context = self._verification_message(
                        tool_name, result
                    )

                    if not successful and recovery_key in recovery_steps:
                        verification_context += (
                            "\n\nRecovery analysis:\n"
                            "Automatic recovery was previously "
                            "successful. Retry the original action."
                        )

                    # Refresh computer awareness after a successful action
                    if successful:
                        refreshed_awareness = self._refresh_computer_awareness()
                        if refreshed_awareness:
                            verification_context += (
                                "\n\nUpdated computer awareness:\n"
                                f"- Active foreground window: "
                                f"{refreshed_awareness['window_title']}\n"
                                f"- Process ID: "
                                f"{refreshed_awareness['pid']}\n"
                                f"- Window verified: "
                                f"{refreshed_awareness['verified']}"
                            )

                    # -------------------------------------------------
                    # RETURN TOOL RESULT TO THE MODEL
                    # -------------------------------------------------
                    conversation.append({
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(
                            {
                                "tool_result": result,
                                "verification": verification_context,
                            },
                            default=str,
                        ),
                    })

                    # If one tool in a multi-tool response failed,
                    # do not continue executing the remaining actions
                    # from that batch.
                    if task_failed:
                        break

            # ---------------------------------------------------------
            # MAXIMUM STEPS REACHED
            # ---------------------------------------------------------
            if self.task_engine.current_task:
                self.task_engine.fail_task()
                self._notify_task_progress()

            return (
                "I could not complete the task within "
                "the allowed execution steps."
            )

        except PermissionRequired:
            raise

        except Exception as exc:
            if self.task_engine.current_task:
                self.task_engine.fail_task()
                self._notify_task_progress()

            return (
                f"I encountered an error while processing "
                f"your request: {exc}"
            )

    # ---------------------------------------------------------
    # TASK STATUS
    # ---------------------------------------------------------

    def get_task_status(self):
        return self.task_engine.get_status()

    def get_task_progress(self):
        return self.task_engine.get_progress()

    def get_task_summary(self):
        return self.task_engine.get_task_summary()
