"""
Local vision model path.

Sends a screenshot to the same OpenAI-compatible server Aethra already uses
(LM Studio or similar) if that model accepts images. Falls back to the
UI Automation + OCR see_screen tool.
"""

from __future__ import annotations

import base64
import os
from typing import Any, Dict


def ask_vision(question: str = "Describe what is on the screen, including icons and dialogs.") -> Dict[str, Any]:
    question = str(question or "Describe the screen.").strip()
    try:
        from app.tools.computer import take_screenshot
        shot = take_screenshot()
    except Exception as exc:
        shot = {"success": False, "error": str(exc)}

    path = ""
    if isinstance(shot, dict):
        path = shot.get("path") or shot.get("file") or shot.get("screenshot_path") or ""
        if not path:
            # common key used by this project
            for key in ("filepath", "image_path", "saved_path"):
                if shot.get(key):
                    path = shot[key]
                    break

    if not path or not os.path.isfile(path):
        # last resort: newest screenshot
        folder = os.path.join(os.getcwd(), "data", "screenshots")
        if os.path.isdir(folder):
            files = [
                os.path.join(folder, name)
                for name in os.listdir(folder)
                if name.lower().endswith(".png")
            ]
            if files:
                path = max(files, key=os.path.getmtime)

    fallback = {}
    try:
        from app.tools.vision import see_screen
        fallback = see_screen(include_ocr=True)
    except Exception:
        fallback = {}

    if not path or not os.path.isfile(path):
        return {
            "success": bool(fallback),
            "verified": False,
            "source": "ui_automation_fallback",
            "vision_model": False,
            "screen": fallback,
            "message": "No screenshot file found. Returned the UI Automation view instead.",
        }

    try:
        from app.config import settings
        from openai import OpenAI

        provider = (settings.ai_provider or "").lower()
        if provider == "lmstudio":
            client = OpenAI(
                base_url=settings.ai_base_url or "http://localhost:1234/v1",
                api_key=settings.ai_api_key or "lm-studio",
            )
        else:
            client = OpenAI(api_key=settings.ai_api_key)
        model = os.environ.get("AETHRA_VISION_MODEL") or (
            settings.ai_model if settings.ai_model and settings.ai_model.lower() != "auto" else "local-model"
        )
        fallback_model = os.environ.get("AETHRA_VISION_MODEL_2") or ""
        with open(path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                ],
            }],
            max_tokens=400,
        )
        answer = response.choices[0].message.content or ""
        return {
            "success": True,
            "verified": True,
            "source": "local_vision_model",
            "vision_model": True,
            "answer": answer,
            "screenshot": path,
            "message": "Local vision model described the screen.",
        }
    except Exception as exc:
        if fallback_model:
            try:
                response = client.chat.completions.create(
                    model=fallback_model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                        ],
                    }],
                    max_tokens=400,
                )
                answer = response.choices[0].message.content or ""
                return {
                    "success": True,
                    "verified": True,
                    "source": "second_vision_model",
                    "vision_model": True,
                    "answer": answer,
                    "message": "Second vision model described the screen.",
                }
            except Exception:
                pass
        return {
            "success": bool(fallback),
            "verified": False,
            "source": "ui_automation_fallback",
            "vision_model": False,
            "error": str(exc),
            "screen": fallback,
            "message": "Vision model was unavailable. Returned the UI Automation and OCR view instead.",
        }
