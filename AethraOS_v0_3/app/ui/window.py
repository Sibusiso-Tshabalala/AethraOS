import sys
import html

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
    QMessageBox,
    QCheckBox,
    QSizePolicy,
    QStackedWidget,
)

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap

from app.agent.brain import AethraBrain, PermissionRequired
from app.voice.voice import VoiceEngine, VoiceWorker
from app.ui.avatar import AethraAvatar
from app.ui.bot_mascot import BotMascot


class AethraWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("AethraOS")
        self.resize(900, 750)

        self.voice_worker = None
        self.speech_worker = None

        self.speech_enabled = True
        self.is_processing = False
        self.compact_mode = False

        # Conversation Mode
        self.conversation_mode = False
        self.conversation_stop_requested = False
        self.conversation_speech_response = False

# Used to drag the compact assistant around the desktop.
        self._drag_position = None

        self.setup_ui()

        self.brain = AethraBrain(
            permission_callback=self.request_permission,
            task_progress_callback=self.on_task_progress,
            failure_callback=self.ask_step_decision,
            side_callback=self.start_side_task,
        )

        self.voice_engine = VoiceEngine()

        # Local reminder/alarm checker (every 15 seconds)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(15_000)
        self.reminder_timer.timeout.connect(self._check_due_reminders)
        self.reminder_timer.start()
        self.health_timer = QTimer(self)
        self.health_timer.setInterval(20000)
        self.health_timer.timeout.connect(self._paint_health_chip)
        self.health_timer.start()
        self.watch_timer = QTimer(self)
        self.watch_timer.setInterval(20000)
        self.watch_timer.timeout.connect(self._poll_watch)
        self.watch_timer.start()
        QTimer.singleShot(1500, self._paint_health_chip)

        self.add_message(
            "Aethra",
            "Hello! I'm Aethra. How can I help you today?"
        )

        self.set_aethra_state("idle")

    def setup_ui(self):

        self.setStyleSheet("""
            QWidget {
                background-color: #0B1018;
                color: #E6EDF7;
                font-family: Segoe UI;
                font-size: 14px;
            }

            AethraWindow {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #121A2B, stop:0.45 #0C1422, stop:1 #101C30);
                border: 1px solid #2EE6FF;
                border-radius: 18px;
            }

            QTextEdit {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #172033, stop:1 #0E1622);
                border: 1px solid #2E4A68;
                border-radius: 16px;
                padding: 12px;
                color: #E6EDF7;
            }

            QLineEdit {
                background-color: #101A28;
                border: 1px solid #2E4A68;
                border-radius: 12px;
                padding: 10px;
                color: #E6EDF7;
            }

            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #22344C, stop:1 #152233);
                border: 1px solid #3A5A78;
                border-radius: 10px;
                padding: 10px 16px;
                color: #E6EDF7;
            }

            QPushButton:hover {
                background-color: #203650;
            }

            QPushButton:disabled {
                color: #64748B;
                background-color: #111927;
                border-color: #1E293B;
            }

            QCheckBox {
                spacing: 8px;
            }
        """)

        main_layout = QVBoxLayout()

        self.title_label = QLabel("AETHRA")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            font-size: 30px;
            font-weight: bold;
            color: #00D9FF;
            letter-spacing: 5px;
        """)

        self.avatar = AethraAvatar()
        self._apply_window_icon()
        self._build_compact_face()

        self.status_label = QLabel("Idle")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            color: #00FFAA;
            font-size: 14px;
            font-weight: bold;
        """)

        self.specialist_label = QLabel("Specialist: General Assistant")
        self.specialist_label.setAlignment(Qt.AlignCenter)
        self.specialist_label.setStyleSheet("""
            color: #7DD3FC;
            font-size: 12px;
        """)

        self.task_label = QLabel("")
        self.task_label.hide()
        self.task_label.setAlignment(Qt.AlignCenter)
        self.task_label.setStyleSheet("color: #94A3B8;")

        self.task_detail_label = QLabel("")
        self.task_detail_label.setAlignment(Qt.AlignCenter)
        self.task_detail_label.setStyleSheet("""
            color: #64748B;
            font-size: 11px;
        """)
        self.task_detail_label.setWordWrap(True)
        self.task_detail_label.hide()

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Talk to Aethra...")

        self.send_button = QPushButton("Send")
        self.voice_button = QPushButton("🎤 Speak")
        self.stop_listening_button = QPushButton("⏹ Stop Listening")
        self.stop_listening_button.setEnabled(False)

        self.conversation_button = QPushButton("🤝 Conversation Mode")

        self.mode_button = QPushButton("🤖 Compact Mode")
        self.mode_button.setToolTip(
            "Switch between the full chat window and compact assistant mode."
        )

        self.stop_button = QPushButton("⏹ Stop Speaking")
        self.stop_button.setEnabled(False)

        self.clear_button = QPushButton("🗑 Clear Chat")

        self.voice_checkbox = QCheckBox("Enable voice responses")
        self.voice_checkbox.setChecked(True)
        self.voice_checkbox.stateChanged.connect(self.toggle_voice_responses)
        self.wake_checkbox = QCheckBox("Wake word: say Aethra")
        self.wake_checkbox.setChecked(False)
        self.wake_checkbox.stateChanged.connect(self.toggle_wake_word)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.voice_button)
        input_layout.addWidget(self.stop_listening_button)

        # --------------------------------------------------
        # QUICK ACTION CHIPS
        # --------------------------------------------------
        self.quick_actions_layout = QHBoxLayout()
        self.quick_actions_layout.setSpacing(6)

        quick_actions = [
            ("🌐 Chrome", "Open Chrome"),
            ("📁 Explorer", "Open File Explorer"),
            ("👁 What's on screen?", "What's on my screen right now?"),
            ("📋 Clipboard", "What's on my clipboard?"),
            ("📸 Screenshot", "Take a screenshot"),
            ("🩺 Health", "__health__"),
        ]

        self.quick_action_buttons = []
        for label, prompt in quick_actions:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #132033;
                    border: 1px solid #2A3F5F;
                    border-radius: 12px;
                    padding: 6px 12px;
                    color: #CBD5E1;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #1A2D45;
                    border-color: #00D9FF;
                    color: #E6EDF7;
                }
                QPushButton:disabled {
                    color: #475569;
                    border-color: #1E293B;
                }
            """)
            btn.clicked.connect(
                lambda checked=False, p=prompt: self._run_quick_action(p)
            )
            self.quick_actions_layout.addWidget(btn)
            self.quick_action_buttons.append(btn)

        self.quick_actions_layout.addStretch()

        control_layout = QHBoxLayout()

        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.clear_button)
        control_layout.addWidget(self.conversation_button)
        control_layout.addWidget(self.mode_button)

        full_page = QWidget()
        full_layout = QVBoxLayout(full_page)
        full_layout.addWidget(self.title_label)
        full_layout.addWidget(self.avatar, 0, Qt.AlignHCenter)
        full_layout.addWidget(self.voice_checkbox)
        full_layout.addWidget(self.wake_checkbox)
        full_layout.addWidget(self.status_label)
        full_layout.addWidget(self.specialist_label)
        full_layout.addWidget(self.task_label)
        full_layout.addWidget(self.task_detail_label)
        full_layout.addWidget(self.chat, 1)
        full_layout.addLayout(input_layout)
        self.voice_hint = QLabel("Say it: take a screenshot, open Chrome, what's on my screen.")
        self.voice_hint.setAlignment(Qt.AlignCenter)
        self.voice_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        full_layout.addWidget(self.voice_hint)
        full_layout.addLayout(control_layout)

        compact_controls = QHBoxLayout()
        self.compact_speak_button = QPushButton("Speak")
        self.compact_speak_button.clicked.connect(self.start_voice)
        self.compact_talk_button = QPushButton("Talk")
        self.compact_talk_button.clicked.connect(self.toggle_conversation_mode)
        self.compact_full_button = QPushButton("Full chat")
        self.compact_full_button.clicked.connect(lambda: self.set_compact_mode(False))
        compact_controls.addWidget(self.compact_speak_button)
        compact_controls.addWidget(self.compact_talk_button)
        compact_controls.addWidget(self.compact_full_button)

        compact_page = QWidget()
        compact_page.setStyleSheet(
            "background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #162033, stop:1 #0B1018);"
            "border: 1px solid #22D3EE; border-radius: 22px;"
        )
        compact_layout = QVBoxLayout(compact_page)
        compact_layout.setContentsMargins(16, 16, 16, 16)
        self.compact_title = QLabel("AETHRA")
        self.compact_title.setAlignment(Qt.AlignCenter)
        self.compact_title.setStyleSheet("color: #67E8F9; font-size: 13px; letter-spacing: 4px; font-weight: bold;")
        compact_layout.addWidget(self.compact_title)
        compact_layout.addWidget(self.mascot_label, 0, Qt.AlignHCenter)
        compact_layout.addWidget(self.bubble)
        compact_layout.addWidget(self.wave_label)
        compact_layout.addLayout(compact_controls)
        self.mascot_label.clicked.connect(self.start_voice)

        self.pages = QStackedWidget()
        self.pages.addWidget(full_page)
        self.pages.addWidget(compact_page)

        for label in (
            self.title_label,
            self.status_label,
            self.specialist_label,
            self.task_label,
            self.task_detail_label,
            self.wave_label,
        ):
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.avatar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.avatar.setFixedSize(260, 200)
        self.mascot_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.chat.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.pages)
        self.setLayout(main_layout)
        self._refresh_greeting()

        self.send_button.clicked.connect(self.send_message)
        self.voice_button.clicked.connect(self.start_voice)
        self.stop_listening_button.clicked.connect(self.stop_listening)
        self.conversation_button.clicked.connect(
            self.toggle_conversation_mode
        )
        self.input_field.returnPressed.connect(self.send_message)

        self.stop_button.clicked.connect(self.stop_speaking)
        self.clear_button.clicked.connect(self.clear_chat)
        self.mode_button.clicked.connect(self.toggle_compact_mode)

    def _asset(self, name):
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(here, "assets", name)

    def _apply_window_icon(self):
        import os
        path = self._asset("aethra_mark.jpg")
        if os.path.isfile(path):
            self.setWindowIcon(QIcon(path))

    def _build_compact_face(self):
        self.mascot_label = BotMascot(self)
        self.mascot_label.hide()

        self.bubble = QLabel("Good evening.\nHow can I help you today?", self)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.bubble.setStyleSheet(
            "background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #182536, stop:1 #101826);"
            "color: #E6EDF7; border: 1px solid #67E8F9; border-radius: 18px; padding: 14px; font-size: 14px;"
        )
        self.bubble.setMinimumHeight(72)
        self.bubble.hide()

        self.wave_label = QLabel("▁ ▂ ▃ ▅ ▆ ▅ ▃ ▂ ▁", self)
        self.wave_label.setAlignment(Qt.AlignCenter)
        self.wave_label.setStyleSheet("color: #22D3EE; font-size: 18px; letter-spacing: 2px;")
        self.wave_label.hide()

    def toggle_wake_word(self):
        enabled = self.wake_checkbox.isChecked()
        if enabled:
            if getattr(self, "wake_worker", None) is None:
                self.wake_worker = WakeWorker(self.voice_engine)
                self.wake_worker.heard.connect(self._on_wake)
                self.wake_worker.start()
            self.add_message("Aethra", "Wake word on. Say Aethra. The app must already be running.")
        else:
            worker = getattr(self, "wake_worker", None)
            if worker is not None:
                worker.stop()
                self.wake_worker = None

    def _on_wake(self):
        if self.is_processing or self.voice_worker is not None:
            return
        self.add_message("Aethra", "Wake word heard.")
        self.start_voice()

    def start_side_task(self, payload):
        """Run mail or calendar work without blocking the desktop task."""
        if getattr(self, "side_worker", None) is not None:
            return
        kind = (payload or {}).get("kind", "draft")
        self.side_worker = SideWorker(kind, payload)
        self.side_worker.finished_text.connect(self._side_done)
        self.side_worker.start()
        self.add_message("Aethra", f"Side task started: {kind}. Desktop work can continue.")

    def _side_done(self, text):
        self.side_worker = None
        self.add_message("Aethra", f"Side task finished: {text}")
        if self.compact_mode and hasattr(self, "bubble"):
            self.bubble.setText(str(text)[:160])

    def set_aethra_state(self, state):

        self.avatar.set_state(state)

        states = {
            "idle": ("Idle", "#00FFAA"),
            "listening": ("Listening...", "#00D9FF"),
            "thinking": ("Thinking...", "#FFD166"),
            "speaking": ("Speaking...", "#00D9FF"),
            "error": ("Error", "#FF5555"),
        }

        text, color = states.get(
            state,
            ("Idle", "#00FFAA")
        )

        self.status_label.setText(text)

        self.status_label.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: bold;"
        )
        waves = {
            "idle": "▁ ▁ ▂ ▁ ▁ ▂ ▁ ▁",
            "listening": "▁ ▃ ▅ ▇ ▅ ▃ ▅ ▇ ▅ ▃",
            "thinking": "▃ ▃ ▃ ▃ ▃ ▃ ▃",
            "speaking": "▂ ▅ ▇ ▅ ▂ ▅ ▇ ▅ ▂",
            "error": "▇ ▁ ▇ ▁ ▇",
        }
        if hasattr(self, "wave_label"):
            self.wave_label.setText(waves.get(state, waves["idle"]))
        if hasattr(self, "mascot_label"):
            self.mascot_label.set_state(state)
        if hasattr(self, "bubble") and self.compact_mode:
            greet = {
                "idle": "Good evening.\nHow can I help you today?",
                "listening": "Listening...",
                "thinking": "One moment.",
                "speaking": "Speaking...",
                "error": "Something went wrong.",
            }
            self.bubble.setText(greet.get(state, greet["idle"]))

    # --------------------------------------------------
    # CHAT DISPLAY
    # --------------------------------------------------

    def add_message(self, sender, message):

        safe_sender = html.escape(str(sender))
        safe_message = html.escape(str(message))

        safe_message = safe_message.replace("\n", "<br>")

        self.chat.append(
            f'<div style="margin:8px 0; text-align:{"right" if sender == "You" else "left"};">'
            f'<span style="display:inline-block; max-width:80%; text-align:left; '
            f'background:{"#16324A" if sender == "You" else "#121A27"}; '
            f'border:1px solid {"#38BDF8" if sender == "You" else "#2EE6FF"}; '
            f'border-radius:14px; padding:8px 12px;">'
            f'<b>{safe_sender}</b><br>{safe_message}'
            f'</span></div>'
        )
        if sender == "Aethra":
            self.last_reply = str(message).strip().replace("\n", " ")
            if len(self.last_reply) > 160:
                self.last_reply = self.last_reply[:157] + "..."
            if self.compact_mode and hasattr(self, "bubble"):
                self.bubble.setText(self.last_reply or self._greeting())

    def _greeting(self):
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            hello = "Good morning."
        elif hour < 18:
            hello = "Good afternoon."
        else:
            hello = "Good evening."
        return f"{hello}\nHow can I help you today?"

    def _refresh_greeting(self):
        self.last_reply = ""
        if hasattr(self, "bubble"):
            self.bubble.setText(self._greeting())

    def _refresh_alert(self):
        waiting = False
        try:
            from app.tools.scheduler import list_reminders
            from app.tools.gmail_draft import list_gmail_drafts
            reminders = list_reminders().get("items") or []
            drafts = list_gmail_drafts().get("drafts") or []
            waiting = bool(reminders or drafts)
        except Exception:
            waiting = False
        if hasattr(self, "mascot_label"):
            self.mascot_label.has_alert = waiting
            self.mascot_label.update()

    def clear_chat(self):

        reply = QMessageBox.question(
            self,
            "Clear Chat",
            "Clear the visible conversation?\n\n"
            "This will not delete Aethra's saved memory.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:

            self.chat.clear()

            self.add_message(
                "Aethra",
                "Chat cleared. Your saved memory has not been changed."
            )

    # --------------------------------------------------
    # QUICK ACTIONS
    # --------------------------------------------------

    def _run_quick_action(self, prompt: str):
        """Send a predefined prompt as if the user typed it."""
        if prompt == "__health__":
            self.show_health_check()
            return
        if self.is_processing:
            return
        self.input_field.setText(prompt)
        self.send_message()

    def show_health_check(self):
        try:
            from app.tools.workspace import health_check
            result = health_check()
            lines = [f"{key}: {value}" for key, value in result.get("checks", {}).items()]
            QMessageBox.information(self, "Aethra health", "\n".join(lines) or "No checks.")
        except Exception as exc:
            QMessageBox.warning(self, "Aethra health", str(exc))

    # --------------------------------------------------
    # SCREENSHOT THUMBNAILS
    # --------------------------------------------------

    def _latest_screenshot_path(self):
        """Return the newest screenshot file path, or None."""
        try:
            import os
            from pathlib import Path

            folder = Path(os.getcwd()) / "data" / "screenshots"
            if not folder.is_dir():
                return None

            files = sorted(
                folder.glob("screenshot_*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not files:
                return None
            return str(files[0])
        except Exception:
            return None

    def _maybe_show_screenshot_thumbnail(self):
        """
        If a new screenshot was just created, show a small
        thumbnail in the chat.
        """
        try:
            path = self._latest_screenshot_path()
            if not path:
                return

            # Only show if it is very recent (last 15 seconds)
            import os
            import time
            age = time.time() - os.path.getmtime(path)
            if age > 15:
                return

            # Avoid showing the same screenshot twice
            if getattr(self, "_last_shown_screenshot", None) == path:
                return
            self._last_shown_screenshot = path

            # Embed a modest-size image in the chat
            # QTextEdit supports local file images via HTML
            safe_path = path.replace("\\", "/")
            html = (
                f'<div style="margin:6px 0;">'
                f'<b>Screenshot:</b><br>'
                f'<img src="file:///{safe_path}" '
                f'width="320" style="border-radius:8px; '
                f'border:1px solid #263449;" />'
                f'</div>'
            )
            self.chat.append(html)
            self.chat.verticalScrollBar().setValue(
                self.chat.verticalScrollBar().maximum()
            )
        except Exception:
            pass

    # --------------------------------------------------
    # MESSAGE PROCESSING
    # --------------------------------------------------

    def send_message(self):

        if self.is_processing:
            return

        message = self.input_field.text().strip()

        if not message:
            return

        self.input_field.clear()

        self.process_message(message)

    def process_message(self, message):

        if self.is_processing:
            return

        self.is_processing = True

        self.add_message("You", message)

        self.set_aethra_state("thinking")
        self.update_specialist(message)
        self.update_controls()

        try:
            self._brain_worker = BrainWorker(self.brain, message, conversation=False)
            self._brain_worker.done.connect(self._on_brain_done)
            self._brain_worker.failed.connect(self._on_brain_failed)
            self._brain_worker.start()
        except Exception as exc:
            self.add_message("Aethra", f"Error: {exc}")
            self.finish_processing(error=True)

    # --------------------------------------------------
    # TEXT TO SPEECH
    # --------------------------------------------------

    def speak_response(
        self,
        response,
        conversation_response=False
    ):

        if not self.speech_enabled or not response:

            self.finish_processing()
            return

        if self.speech_worker is not None:

            self.finish_processing()
            return

        self.set_aethra_state("speaking")

        self.speech_worker = SpeechWorker(
            self.voice_engine,
            response
        )

        self.conversation_speech_response = (
            conversation_response
        )

        self.speech_worker.speech_done.connect(
            self.on_speech_finished
        )

        self.speech_worker.error.connect(
            self.on_speech_error
        )

        self.speech_worker.start()

        self.update_controls()

    def stop_speaking(self):

        if self.speech_worker is None:
            return

        self.stop_button.setEnabled(False)

        self.add_message(
            "Aethra",
            "Stopping speech..."
        )

        self.voice_engine.stop_speaking()

    def on_speech_finished(self):

        self.speech_worker = None

        conversation_response = getattr(
            self,
            "conversation_speech_response",
            False
        )

        self.conversation_speech_response = False

        if (
            conversation_response
            and self.conversation_mode
            and not self.conversation_stop_requested
        ):
            self.continue_conversation()
            return

        self.finish_processing()
        
    def on_speech_error(self, error_message):

        self.speech_worker = None

        self.add_message(
            "Aethra",
            f"Speech error: {error_message}"
        )

        conversation_response = getattr(
            self,
            "conversation_speech_response",
            False
        )

        self.conversation_speech_response = False

        if (
            conversation_response
            and self.conversation_mode
            and not self.conversation_stop_requested
        ):
            self.set_aethra_state("error")

            self.is_processing = False

            self.update_controls()

            return

        self.finish_processing(error=True)

    # --------------------------------------------------
    # VOICE RESPONSE SETTINGS
    # --------------------------------------------------

    def toggle_voice_responses(self, state):

        self.speech_enabled = state == Qt.Checked

        if not self.speech_enabled and self.speech_worker is not None:

            self.voice_engine.stop_speaking()

        message = (
            "Voice responses enabled."
            if self.speech_enabled
            else "Voice responses disabled."
        )

        self.add_message("Aethra", message)

    # --------------------------------------------------
    # TASK STATUS
    # --------------------------------------------------

    def update_task_status(self):

        task_engine = getattr(
            self.brain,
            "task_engine",
            None
        )

        if not task_engine:
            self.task_label.hide()
            self.task_detail_label.hide()
            return

        task = getattr(task_engine, "current_task", None)
        if not task:
            self.task_label.hide()
            self.task_detail_label.hide()
            self.task_label.setText("")
            self.task_detail_label.setText("")
            return
        self.task_label.show()
        self.task_detail_label.show()

        status = getattr(task, "status", "pending")
        steps = getattr(task, "steps", [])
        total = len(steps)

        completed = sum(
            1 for step in steps
            if getattr(step, "status", "") == "completed"
        )
        failed = sum(
            1 for step in steps
            if getattr(step, "status", "") == "failed"
        )
        in_progress = sum(
            1 for step in steps
            if getattr(step, "status", "") == "in_progress"
        )

        current_step_obj = None
        if hasattr(task_engine, "get_current_step"):
            current_step_obj = task_engine.get_current_step()

        current_desc = ""
        if current_step_obj is not None:
            current_desc = getattr(
                current_step_obj, "description", ""
            ) or ""
        elif isinstance(current_step_obj, str):
            current_desc = current_step_obj

        # Build a short visible plan from step descriptions
        plan_bits = []
        for i, step in enumerate(steps[:6], start=1):
            desc = getattr(step, "description", "") or f"Step {i}"
            st = getattr(step, "status", "pending")
            marker = {
                "completed": "✓",
                "failed": "✗",
                "in_progress": "→",
                "waiting_for_approval": "…",
            }.get(st, "·")
            # Keep each step short
            short = desc if len(desc) <= 40 else desc[:37] + "..."
            plan_bits.append(f"{marker} {short}")

        plan_text = "  |  ".join(plan_bits) if plan_bits else ""

        # Main status line
        if status == "completed":
            self.task_label.setText(
                f"Task completed • {completed}/{total} steps"
            )
            self.task_detail_label.setText(plan_text)
        elif status == "failed":
            self.task_label.setText(
                f"Task failed • {completed}/{total} steps"
            )
            err = getattr(task, "error", "") or ""
            self.task_detail_label.setText(
                err if err else plan_text
            )
        elif current_desc:
            self.task_label.setText(
                f"Task: {completed}/{total} steps"
            )
            detail = f"Now: {current_desc}"
            if plan_text:
                detail = f"{detail}\n{plan_text}"
            self.task_detail_label.setText(detail)
        elif status == "running":
            self.task_label.setText("Task: Planning...")
            self.task_detail_label.setText(plan_text)
        else:
            self.task_label.setText("Task: Preparing...")
            self.task_detail_label.setText(plan_text)

        # Optional richer detail when multiple steps exist
        if total > 0 and status not in ("completed", "failed"):
            parts = []
            if completed:
                parts.append(f"{completed} done")
            if in_progress:
                parts.append(f"{in_progress} running")
            if failed:
                parts.append(f"{failed} failed")
            pending = total - completed - in_progress - failed
            if pending > 0:
                parts.append(f"{pending} pending")
            if parts and not current_desc:
                self.task_detail_label.setText(" • ".join(parts))

    def on_task_progress(self):
        self.update_task_status()
        QApplication.processEvents()

    def _check_due_reminders(self):
        """Poll local scheduler and notify when reminders/alarms fire."""
        try:
            from app.tools.scheduler import check_due_reminders

            result = check_due_reminders()
            items = result.get("items") or []
            if not items:
                return

            for item in items:
                kind = (item.get("kind") or "reminder").title()
                message = item.get("message") or ""
                due = item.get("due_at") or ""
                text = f"{kind}: {message}"
                if due:
                    text += f" (due {due})"

                self.add_message("Aethra", f"⏰ {text}")

                # Speak alarms/reminders if voice is enabled
                if self.speech_enabled and not self.is_processing:
                    try:
                        self.speak_response(f"{kind}. {message}")
                    except Exception:
                        pass

                # Also raise a small system dialog for alarms
                if (item.get("kind") or "").lower() == "alarm":
                    try:
                        QMessageBox.information(
                            self,
                            "Aethra Alarm",
                            message or "Alarm",
                        )
                    except Exception:
                        pass
        except Exception:
            pass

    def update_specialist(self, message: str = ""):
        """
        Update the specialist indicator from the coordinator.
        """
        try:
            coordinator = getattr(self.brain, "coordinator", None)
            if coordinator and hasattr(coordinator, "get_agent_name"):
                name = coordinator.get_agent_name(message or "")
                self.specialist_label.setText(f"Specialist: {name}")
            else:
                self.specialist_label.setText("Specialist: General Assistant")
        except Exception:
            self.specialist_label.setText("Specialist: General Assistant")

    # --------------------------------------------------
    # PERMISSIONS
    # --------------------------------------------------

    def _humanize_tool_action(self, tool_name: str, arguments=None) -> str:
        """
        Turn a tool name + arguments into a short human description.
        """
        args = arguments or {}
        name = str(tool_name).lower()

        descriptions = {
            "open_application": lambda: (
                f"Open the application “{args.get('application', 'unknown')}”"
            ),
            "focus_application": lambda: (
                f"Bring “{args.get('application', 'unknown')}” to the front"
            ),
            "type_text": lambda: (
                f"Type text into the active window "
                f"({len(str(args.get('text', '')))} characters)"
            ),
            "press_key": lambda: (
                f"Press the “{args.get('key', 'unknown')}” key"
            ),
            "hotkey": lambda: (
                "Press the shortcut: "
                + " + ".join(str(k) for k in args.get("keys", []))
            ),
            "click_mouse": lambda: (
                f"Click the mouse ({args.get('button', 'left')} button)"
            ),
            "move_mouse": lambda: (
                f"Move the mouse to ({args.get('x')}, {args.get('y')})"
            ),
            "scroll_mouse": lambda: (
                f"Scroll the mouse wheel by {args.get('amount', 0)}"
            ),
            "create_text_file": lambda: (
                f"Create a text file named “{args.get('filename', 'file')}”"
            ),
            "set_clipboard": lambda: (
                f"Put text on the clipboard "
                f"({len(str(args.get('text', '')))} characters)"
            ),
            "manage_window": lambda: (
                f"{str(args.get('action', 'manage')).title()} the window"
                + (
                    f" “{args.get('title')}”"
                    if args.get("title")
                    else " (current window)"
                )
            ),
            "click_ui_element": lambda: (
                f"Click the UI element “{args.get('name', 'unknown')}”"
            ),
            "type_into_ui_element": lambda: (
                f"Type into the UI field “{args.get('name', 'unknown')}”"
            ),
            "open_url": lambda: (
                f"Open URL {args.get('url', '')} in "
                f"{args.get('browser', 'chrome')}"
            ),
            "find_ui_elements": lambda: (
                f"Search for UI elements matching “{args.get('name', '')}”"
            ),
            "search_installed_apps": lambda: (
                f"Search installed apps for “{args.get('query', '')}”"
            ),
            "open_executable": lambda: (
                f"Launch executable:\n{args.get('path', 'unknown')}"
            ),
        }

        if name in descriptions:
            try:
                return descriptions[name]()
            except Exception:
                pass

        return f"Perform the action: {tool_name}"

    def request_permission(self, tool_name, arguments=None):
        human = self._humanize_tool_action(tool_name, arguments)
        risk = str((arguments or {}).get("_risk") or "medium").upper()
        box = QMessageBox(self)
        box.setWindowTitle(f"{risk} risk")
        box.setText(human)
        box.setInformativeText("High risk stops until you allow it. Nothing is sent unless this is a send action and you already confirmed the text.")
        box.setStyleSheet(
            "QMessageBox { background-color: #121A27; }"
            "QLabel { color: #E6EDF7; }"
        )
        allow = box.addButton("Allow", QMessageBox.YesRole)
        box.addButton("Deny", QMessageBox.NoRole)
        box.exec()
        return box.clickedButton() == allow

    def ask_step_decision(self, tool_name, detail=""):
        """Ask the user to retry, skip, or cancel a failed step."""
        box = QMessageBox(self)
        box.setWindowTitle("Aethra step failed")
        box.setText(f"{tool_name} did not succeed.")
        box.setInformativeText(str(detail or "")[:500])
        retry = box.addButton("Retry", QMessageBox.AcceptRole)
        skip = box.addButton("Skip", QMessageBox.ActionRole)
        cancel = box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == retry:
            return "retry"
        if clicked == skip:
            return "skip"
        return "cancel"
    
    
    # --------------------------------------------------
    # CONVERSATION MODE
    # --------------------------------------------------

    def toggle_conversation_mode(self):
        """
        Start or stop Aethra's hands-free conversation mode.
        """

        if self.conversation_mode:
            self.stop_conversation_mode()
        else:
            self.start_conversation_mode()

    def start_conversation_mode(self):
        """
        Start hands-free conversation mode.

        Flow:

        Listen
            ↓
        Transcribe
            ↓
        Process message
            ↓
        Aethra responds
            ↓
        Aethra speaks
            ↓
        Listen again
        """

        if self.conversation_mode:
            return

        if self.is_processing:
            return

        if self.voice_worker is not None:
            return

        if self.speech_worker is not None:
            return

        self.conversation_mode = True
        self.conversation_stop_requested = False

        self.conversation_button.setText("⏹ Stop Conversation")
        if hasattr(self, "compact_talk_button"):
            self.compact_talk_button.setText("Stop")
        if self.compact_mode and hasattr(self, "bubble"):
            self.bubble.setText("Listening. Say a task.")

        self.add_message(
            "Aethra",
            "Conversation Mode started. I'm listening."
        )

        self.update_controls()

        self.start_conversation_listening()

    def stop_conversation_mode(self):
        """
        Stop hands-free conversation mode.
        """

        if not self.conversation_mode:
            return

        self.conversation_mode = False
        self.conversation_stop_requested = True

        # Stop active microphone recording.
        if self.voice_worker is not None:
            self.voice_engine.stop_listening()

        # Stop active speech.
        if self.speech_worker is not None:
            self.voice_engine.stop_speaking()

        self.conversation_button.setText(
            "🤝 Conversation Mode"
        )
        if hasattr(self, "compact_talk_button"):
            self.compact_talk_button.setText("Talk")

        self.add_message(
            "Aethra",
            "Conversation Mode stopped."
        )

        self.set_aethra_state("idle")

        self.update_controls()

    def start_conversation_listening(self):
        """
        Start another listening cycle in Conversation Mode.
        """

        if not self.conversation_mode:
            return

        if self.conversation_stop_requested:
            return

        if self.voice_worker is not None:
            return

        if self.is_processing:
            return

        self.set_aethra_state("listening")

        self.voice_worker = VoiceWorker(
            self.voice_engine
        )

        self.voice_worker.status.connect(
            self.on_voice_status
        )

        self.voice_worker.finished.connect(
            self.on_conversation_voice_finished
        )

        self.voice_worker.error.connect(
            self.on_conversation_voice_error
        )

        self.update_controls()

        self.voice_worker.start()

    def on_conversation_voice_finished(self, text):
        """
        Handle transcription while Conversation Mode is active.
        """

        self.voice_worker = None

        if not self.conversation_mode:
            self.update_controls()
            return

        if self.conversation_stop_requested:
            self.update_controls()
            return

        text = str(text).strip()

        if not text:
            self.add_message(
                "Aethra",
                "I didn't hear anything. I'll listen again."
            )

            self.set_aethra_state("idle")

            self.update_controls()

            # Listen again.
            self.start_conversation_listening()

            return

        # Show what Aethra heard.
        self.input_field.setText(text)

        self.input_field.setCursorPosition(
            len(self.input_field.text())
        )

        # Automatically process the message.
        self.process_conversation_message(text)

    def process_conversation_message(self, message):
        """
        Send a transcribed message directly to Aethra
        without requiring the user to press Send.
        """

        if not self.conversation_mode:
            return

        if self.conversation_stop_requested:
            return

        if self.is_processing:
            return

        self.input_field.clear()

        self.is_processing = True

        self.add_message(
            "You",
            message
        )

        self.set_aethra_state("thinking")
        self.update_specialist(message)

        self.update_controls()

        try:
            self._brain_worker = BrainWorker(self.brain, message, conversation=True)
            self._brain_worker.done.connect(self._on_brain_done)
            self._brain_worker.failed.connect(self._on_brain_failed)
            self._brain_worker.start()
        except Exception as exc:
            self.add_message("Aethra", f"Error: {exc}")
            self.finish_processing(error=True)

    def _on_brain_done(self, response, conversation):
        self.add_message("Aethra", response)
        self._maybe_show_screenshot_thumbnail()
        self.update_task_status()
        self.speak_response(response, conversation_response=conversation)

    def _on_brain_failed(self, message):
        self.add_message("Aethra", message)
        self.finish_processing(error=True)

    def continue_conversation(self):
        """
        Start another listening cycle after Aethra
        has finished speaking.
        """

        if not self.conversation_mode:
            return

        if self.conversation_stop_requested:
            return

        # Make sure the UI has returned to an idle state
        # before listening again.
        self.is_processing = False

        self.set_aethra_state("idle")

        self.update_controls()

        # Start the next conversation turn.
        self.start_conversation_listening()

    def on_conversation_voice_error(self, error_message):
        """
        Handle microphone/transcription errors during
        Conversation Mode.
        """

        self.voice_worker = None

        if not self.conversation_mode:
            self.finish_processing(
                error=True
            )
            return

        if self.conversation_stop_requested:
            self.update_controls()
            return

        self.add_message(
            "Aethra",
            f"Voice input error: {error_message}"
        )

        self.set_aethra_state("error")

        self.update_controls()
    # --------------------------------------------------
    # VOICE INPUT
    # --------------------------------------------------
    def stop_listening(self):
        """
        Stop the active microphone recording.
        """

        if self.voice_worker is None:
            return

        self.stop_listening_button.setEnabled(False)

        self.status_label.setText(
            "Stopping recording..."
        )

        self.voice_engine.stop_listening()


    def start_voice(self):

        if self.is_processing or self.voice_worker is not None:
            return

        self.set_aethra_state("listening")

        self.voice_worker = VoiceWorker(self.voice_engine)

        self.voice_worker.status.connect(
            self.on_voice_status
        )

        self.voice_worker.finished.connect(
            self.on_voice_finished
        )

        self.voice_worker.error.connect(
            self.on_voice_error
        )

        self.update_controls()

        self.voice_worker.start()

    def on_voice_status(self, status):

        if status == "Listening...":

            self.set_aethra_state("listening")

        elif status == "Transcribing...":

            self.set_aethra_state("thinking")

    def on_voice_finished(self, text):
        """
        Handle completed voice transcription.

        Show the recognized text in the input field so the
        user can review or edit it before sending it to Aethra.
        """

        self.voice_worker = None

        if text and text.strip():

            # Put the transcription in the input field.
            self.input_field.setText(text.strip())

            # Move the cursor to the end of the transcription.
            self.input_field.setCursorPosition(
                len(self.input_field.text())
            )

            self.finish_processing()

            # Let the user know the transcription is ready.
            self.status_label.setText(
                "Review transcription and press Send"
            )

            # Focus the input field so it can be edited immediately.
            self.input_field.setFocus()

        else:

            self.add_message(
                "Aethra",
                "I didn't hear anything. Please try again."
            )

            self.finish_processing()

    def on_voice_error(self, error_message):

        self.voice_worker = None

        self.add_message(
            "Aethra",
            f"Voice input error: {error_message}"
        )

        self.finish_processing(error=True)

        
    # --------------------------------------------------
    # COMPACT ASSISTANT MODE
    # --------------------------------------------------
    # --------------------------------------------------
    # COMPACT ASSISTANT MODE
    # --------------------------------------------------

    def toggle_compact_mode(self):
        """Toggle between the normal chat interface and compact mode."""

        if self.compact_mode:
            self.set_compact_mode(False)
        else:
            self.set_compact_mode(True)

    def set_compact_mode(self, enabled):
        """Switch between the full Aethra interface and floating compact mode."""

        self.compact_mode = enabled
        self._refresh_alert()

        if enabled:
            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            )
            self.pages.setCurrentIndex(1)
            self.mascot_label.show()
            self.bubble.show()
            self.wave_label.show()
            self._restore_compact_position()
            if getattr(self, "last_reply", ""):
                self.bubble.setText(self.last_reply)
            else:
                self.bubble.setText(self._greeting())
            self.mode_button.setText("Full chat")
            self.resize(300, 460)
            self.show()
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self.width() - 24, screen.bottom() - self.height() - 24)
            self._restore_compact_position()
        else:
            self._save_compact_position()
            self.setWindowFlags(Qt.Window)
            self.pages.setCurrentIndex(0)
            self.mode_button.setText("🤖 Compact Mode")
            self.avatar.setFixedSize(260, 200)
            self.avatar.show()
            self.resize(900, 750)
            self.show()
            if self.layout() is not None:
                self.layout().activate()
            self.updateGeometry()

        self.update_controls()
        return

    def _position_path(self):
        import os
        folder = os.path.join(os.getcwd(), "data")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "window_state.json")

    def _save_compact_position(self):
        try:
            import json
            pos = self.pos()
            with open(self._position_path(), "w", encoding="utf-8") as handle:
                json.dump({"x": pos.x(), "y": pos.y()}, handle)
        except Exception:
            pass

    def _restore_compact_position(self):
        try:
            import json
            import os
            path = self._position_path()
            if not os.path.isfile(path):
                return
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.move(int(data.get("x", 80)), int(data.get("y", 80)))
        except Exception:
            pass

    def _companion_check(self):
        """Speak first with a short next step. Does not click or send."""
        if getattr(self, "is_processing", False):
            return
        notes = []
        try:
            from app.tools.morning_brief import morning_brief
            brief = morning_brief()
            if brief.get("message"):
                notes.append(brief["message"])
        except Exception:
            pass
        try:
            from app.tools.inbox_watch import poll_inbox
            mail = poll_inbox()
            notes.extend(mail.get("plans") or [])
        except Exception:
            pass
        if not notes:
            notes.append("Say Run Morning for mail, news, and PC health. Say Run Project to open a scratch project.")
        text = notes[0][:240]
        self.add_message("Aethra", text)
        if self.compact_mode and hasattr(self, "bubble"):
            self.bubble.setText(text[:160])

    def _poll_watch(self):
        try:
            from app.tools.watcher import poll_watch
            from app.tools.inbox_watch import poll_inbox
            found = poll_watch()
            for name in found.get("new_files") or []:
                self.add_message("Aethra", f"New file in watched folder: {name}")
            mail = poll_inbox()
            for plan in mail.get("plans") or []:
                self.add_message("Aethra", plan)
        except Exception:
            pass

    def _paint_health_chip(self):
        try:
            from app.tools.workspace import health_check
            checks = health_check().get("checks", {})
            bad = any(
                "not" in str(checks.get(key, "")).lower()
                for key in ("lm_studio", "tesseract")
            )
        except Exception:
            bad = True
        for btn in getattr(self, "quick_action_buttons", []):
            if "Health" in btn.text():
                color = "#7F1D1D" if bad else "#132033"
                border = "#F87171" if bad else "#2A3F5F"
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {color}; border: 1px solid {border}; "
                    "border-radius: 12px; padding: 6px 12px; color: #E6EDF7; font-size: 12px; }"
                )

    def _unused_old_compact(self):
        if False:
            # --------------------------------------------------
            # FLOATING COMPACT WINDOW
            # --------------------------------------------------

            self.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            )
            self.setAttribute(Qt.WA_TranslucentBackground, False)

            # Hide full-chat widgets
            for w in (
                self.title_label,
                self.avatar,
                self.chat,
                self.input_field,
                self.send_button,
                self.voice_checkbox,
                self.clear_button,
                self.specialist_label,
                self.task_label,
                self.task_detail_label,
            ):
                w.hide()

            for btn in getattr(self, "quick_action_buttons", []):
                btn.hide()

            for w in (
                self.mascot_label,
                self.bubble,
                self.wave_label,
                self.status_label,
                self.voice_button,
                self.stop_listening_button,
                self.stop_button,
                self.mode_button,
            ):
                w.show()

            self.conversation_button.hide()
            self.mode_button.setText("Full chat")
            self.resize(340, 520)

            self.status_label.setStyleSheet(
                "color: #00D9FF; font-size: 16px; font-weight: bold; padding: 4px;"
            )
            self.specialist_label.setStyleSheet(
                "color: #38BDF8; font-size: 11px; padding: 2px;"
            )
            self.task_label.setStyleSheet(
                "color: #94A3B8; font-size: 12px; padding: 2px;"
            )
            self.task_detail_label.setStyleSheet(
                "color: #64748B; font-size: 10px; padding: 1px;"
            )

            compact_btn = """
                QPushButton {
                    background-color: #111927;
                    color: #E6EDF7;
                    border: 1px solid #263449;
                    border-radius: 10px;
                    padding: 8px 12px;
                    font-size: 12px;
                    min-height: 36px;
                }
                QPushButton:hover {
                    background-color: #17263A;
                    border: 1px solid #00D9FF;
                }
                QPushButton:disabled {
                    color: #64748B;
                    border: 1px solid #1E293B;
                }
            """
            for btn in (
                self.voice_button,
                self.stop_listening_button,
                self.stop_button,
                self.conversation_button,
                self.mode_button,
            ):
                btn.setStyleSheet(compact_btn)
                btn.setMinimumWidth(100)

            self.show()

        else:
            # --------------------------------------------------
            # RESTORE FULL CHAT WINDOW
            # --------------------------------------------------

            self.setWindowFlags(Qt.Window)
            self.setAttribute(Qt.WA_TranslucentBackground, False)

            # Show everything that belongs in full mode
            for w in (
                self.title_label,
                self.avatar,
                self.voice_checkbox,
                self.status_label,
                self.specialist_label,
                self.task_label,
                self.task_detail_label,
                self.chat,
                self.input_field,
                self.send_button,
                self.voice_button,
                self.stop_listening_button,
                self.stop_button,
                self.clear_button,
                self.conversation_button,
                self.mode_button,
            ):
                w.show()

            for extra in (self.mascot_label, self.bubble, self.wave_label):
                extra.hide()

            for btn in getattr(self, "quick_action_buttons", []):
                btn.show()

            self.mode_button.setText("🤖 Compact Mode")
            self.avatar.setFixedSize(260, 200)

            # Fully reset control button size constraints + styles
            for btn in (
                self.voice_button,
                self.stop_listening_button,
                self.stop_button,
                self.conversation_button,
                self.mode_button,
                self.send_button,
                self.clear_button,
            ):
                btn.setMinimumSize(0, 0)
                btn.setMaximumSize(16777215, 16777215)
                btn.setStyleSheet("")  # fall back to global stylesheet

            # Restore label styles
            self.status_label.setStyleSheet(
                "color: #00FFAA; font-size: 14px; font-weight: bold;"
            )
            self.specialist_label.setStyleSheet(
                "color: #7DD3FC; font-size: 12px;"
            )
            self.task_label.setStyleSheet("color: #94A3B8;")
            self.task_detail_label.setStyleSheet(
                "color: #64748B; font-size: 11px;"
            )

            # Restore specialist text
            self.update_specialist("")

            self.resize(900, 750)
            self.avatar.setFixedSize(260, 200)
            self.avatar.show()
            self.avatar.update()
            self.show()

            # Force layout recalculation (fixes overlap after flag changes)
            if self.layout() is not None:
                self.layout().activate()
            self.updateGeometry()
            self.repaint()

        self.update_controls()

        # --------------------------------------------------
    # CONTROL STATES
    # --------------------------------------------------

    def update_controls(self):

        busy = self.is_processing
        recording = self.voice_worker is not None

        self.send_button.setEnabled(not busy and not recording)
        self.input_field.setEnabled(not busy and not recording)

        self.voice_button.setEnabled(
            not busy
            and not recording
            and not self.conversation_mode
        )

        self.stop_listening_button.setEnabled(
            recording and not busy
        )

        self.stop_button.setEnabled(
            self.speech_worker is not None
        )

        # Quick action chips
        for btn in getattr(self, "quick_action_buttons", []):
            btn.setEnabled(not busy and not recording)

        # Conversation Mode has its own start/stop control.
        if self.conversation_mode:
            self.conversation_button.setText(
                "⏹ Stop Conversation"
            )
        else:
            self.conversation_button.setText(
                "🤝 Conversation Mode"
            )
        self.clear_button.setEnabled(True)

    def finish_processing(self, error=False):

        self.is_processing = False

        if error:
            self.set_aethra_state("error")
        else:
            self.set_aethra_state("idle")

        self.update_controls()

    # --------------------------------------------------
    # COMPACT WINDOW DRAGGING
    # --------------------------------------------------

    def mousePressEvent(self, event):

        if (
            self.compact_mode
            and event.button() == Qt.LeftButton
        ):
            self._drag_position = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

            event.accept()

        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):

        if (
            self.compact_mode
            and self._drag_position is not None
            and event.buttons() & Qt.LeftButton
        ):
            self.move(
                event.globalPosition().toPoint()
                - self._drag_position
            )

            event.accept()

        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.LeftButton:

            self._drag_position = None

            event.accept()

        else:
            super().mouseReleaseEvent(event)
            
class BrainWorker(QThread):
    done = Signal(str, bool)
    failed = Signal(str)

    def __init__(self, brain, message, conversation=False):
        super().__init__()
        self.brain = brain
        self.message = message
        self.conversation = conversation

    def run(self):
        try:
            response = self.brain.respond(self.message)
            self.done.emit(str(response or ""), self.conversation)
        except Exception as exc:
            name = type(exc).__name__
            if name == "PermissionRequired":
                self.failed.emit(f"Permission was denied. I did not perform {getattr(exc, 'tool_name', 'that action')}.")
            else:
                self.failed.emit(f"Error: {exc}")


class WakeWorker(QThread):
    heard = Signal()

    def __init__(self, voice_engine):
        super().__init__()
        self.voice_engine = voice_engine
        self._stop = False

    def stop(self):
        self._stop = True
        try:
            self.voice_engine.stop_listening()
        except Exception:
            pass

    def run(self):
        while not self._stop:
            try:
                if self.voice_engine.listen_for_wake("aethra"):
                    self.heard.emit()
            except Exception:
                self.msleep(800)
            self.msleep(300)


class SideWorker(QThread):
    finished_text = Signal(str)

    def __init__(self, kind, payload):
        super().__init__()
        self.kind = kind
        self.payload = payload or {}

    def run(self):
        kind = (self.kind or "").lower()
        try:
            if kind == "draft":
                from app.tools.mail_side import draft_reply_on_side
                result = draft_reply_on_side(
                    self.payload.get("to", ""),
                    self.payload.get("subject", ""),
                    self.payload.get("body", ""),
                )
            elif kind == "outlook_inbox":
                from app.tools.inbox import read_outlook_inbox
                result = read_outlook_inbox()
            elif kind == "agenda":
                from app.tools.calendar_local import get_agenda
                result = get_agenda("today")
            elif kind == "gmail_threads":
                from app.tools.google_account import list_google_threads
                result = list_google_threads()
            else:
                result = {"success": False, "error": f"Unknown side task: {kind}"}
            text = result.get("message") or result.get("error") or str(result)[:400]
        except Exception as exc:
            text = str(exc)
        self.finished_text.emit(text)


class SpeechWorker(QThread):

    speech_done = Signal()
    error = Signal(str)

    def __init__(self, voice_engine, text):

        super().__init__()

        self.voice_engine = voice_engine
        self.text = text

    def run(self):

        try:

            self.voice_engine.speak(self.text)

            self.speech_done.emit()

        except Exception as exc:

            self.error.emit(str(exc))


def run():

    app = QApplication(sys.argv)

    window = AethraWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()