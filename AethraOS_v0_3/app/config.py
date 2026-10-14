import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:

    # AI
    ai_provider: str = os.getenv(
        "AI_PROVIDER",
        "lmstudio"
    ).strip().lower()

    ai_model: str = os.getenv(
        "AI_MODEL",
        "auto"
    ).strip()

    ai_base_url: str = os.getenv(
        "AI_BASE_URL",
        "http://localhost:1234/v1"
    ).strip()

    ai_api_key: str = os.getenv(
        "AI_API_KEY",
        ""
    ).strip()

    # Files
    downloads_dir: str = os.path.expanduser(
        os.getenv(
            "DOWNLOADS_DIR",
            "~/Downloads"
        )
    )

    # Security
    require_action_approval: bool = os.getenv(
        "REQUIRE_ACTION_APPROVAL",
        "true"
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # Voice
    voice_model: str = os.getenv(
        "VOICE_MODEL",
        "tiny.en"
    ).strip()

    voice_language: str = os.getenv(
        "VOICE_LANGUAGE",
        "en"
    ).strip()

    voice_sample_rate: int = int(
        os.getenv(
            "VOICE_SAMPLE_RATE",
            "16000"
        )
    )

    voice_record_seconds: int = int(
        os.getenv(
            "VOICE_RECORD_SECONDS",
            "5"
        )
    )

    voice_enabled: bool = os.getenv(
        "VOICE_ENABLED",
        "true"
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


settings = Settings()