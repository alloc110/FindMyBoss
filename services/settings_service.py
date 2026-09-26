import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from config import get_logger

logger = get_logger("SettingsService")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "ai_provider": "gemini",
    "gemini_api_key": "",
    "openai_api_key": "",
    "anthropic_api_key": "",
    "custom_api_key": "",
    "ai_model": "gemini-2.5-flash",
    "gemini_model": "gemini-2.5-flash",
    "custom_base_url": "https://api.deepseek.com/v1",
    "theme": "dark",
}


class SettingsService:
    """Manages application settings, AI model choices, and API keys with atomic persistence."""

    def __init__(self, settings_file: Optional[Path] = None):
        self.settings_file = settings_file or Path("data/settings.json")
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> Dict[str, Any]:
        """Loads system and AI model settings with environment variables as fallback."""
        settings = dict(DEFAULT_SETTINGS)
        # Seed from current environment
        settings["gemini_api_key"] = os.getenv("GEMINI_API_KEY", "")
        settings["openai_api_key"] = os.getenv("OPENAI_API_KEY", "")
        settings["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY", "")
        settings["custom_api_key"] = os.getenv("CUSTOM_AI_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")

        if self.settings_file.exists():
            try:
                saved = json.loads(self.settings_file.read_text(encoding="utf-8"))
                settings.update(saved)
            except Exception as e:
                logger.warning(f"Error reading settings.json: {e}")

        return settings

    def save_settings(self, settings_data: Dict[str, Any]) -> None:
        """Saves system settings to disk atomically."""
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(self.settings_file.parent), prefix="settings_", suffix=".tmp")
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, ensure_ascii=False, indent=2)
            # Atomic rename
            os.replace(tmp_path, str(self.settings_file))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    @staticmethod
    def mask_key(k: Optional[str]) -> str:
        """Masks sensitive API key for UI display."""
        if not k:
            return ""
        if len(k) > 10:
            return f"{k[:6]}...{k[-4:]}"
        return "***"

    def get_masked_settings(self) -> Dict[str, Any]:
        """Returns current settings with sensitive API keys safely masked."""
        settings = self.load_settings()
        provider = settings.get("ai_provider", "gemini")
        key_name = f"{provider}_api_key" if f"{provider}_api_key" in settings else "gemini_api_key"
        current_key = settings.get(key_name, "")
        active_model = settings.get("ai_model") or settings.get("gemini_model", "gemini-2.5-flash")

        return {
            "ai_provider": provider,
            "ai_model": active_model,
            "gemini_model": active_model,
            "has_api_key": bool(current_key),
            "masked_api_key": self.mask_key(settings.get("gemini_api_key", "")),
            "masked_openai_key": self.mask_key(settings.get("openai_api_key", "")),
            "masked_anthropic_key": self.mask_key(settings.get("anthropic_api_key", "")),
            "masked_custom_key": self.mask_key(settings.get("custom_api_key", "")),
            "custom_base_url": settings.get("custom_base_url", "https://api.deepseek.com/v1"),
            "theme": settings.get("theme", "dark"),
        }

    def update_settings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Updates settings based on incoming payload and synchronizes environment variables."""
        settings = self.load_settings()

        if "ai_provider" in payload and payload["ai_provider"]:
            settings["ai_provider"] = str(payload["ai_provider"]).lower().strip()

        provider = settings.get("ai_provider", "gemini")
        key_field = f"{provider}_api_key" if f"{provider}_api_key" in settings else "gemini_api_key"

        new_key = (
            payload.get("api_key")
            or payload.get(key_field)
            or payload.get("openai_api_key")
            or payload.get("anthropic_api_key")
            or payload.get("custom_api_key")
            or payload.get("gemini_api_key")
        )

        if (
            new_key is not None
            and not new_key.startswith("AIzaSy...")
            and not new_key.startswith("sk-...")
            and not new_key.startswith("sk-ant-...")
            and new_key != "***"
        ):
            cleaned_key = new_key.strip()
            settings[key_field] = cleaned_key

            # Sync environment variables
            if provider == "gemini":
                settings["gemini_api_key"] = cleaned_key
                if cleaned_key:
                    os.environ["GEMINI_API_KEY"] = cleaned_key
                else:
                    os.environ.pop("GEMINI_API_KEY", None)
            elif provider == "openai":
                settings["openai_api_key"] = cleaned_key
                if cleaned_key:
                    os.environ["OPENAI_API_KEY"] = cleaned_key
            elif provider == "claude":
                settings["anthropic_api_key"] = cleaned_key
                if cleaned_key:
                    os.environ["ANTHROPIC_API_KEY"] = cleaned_key
            elif provider == "custom":
                settings["custom_api_key"] = cleaned_key
                if cleaned_key:
                    os.environ["CUSTOM_API_KEY"] = cleaned_key

        model_val = payload.get("ai_model") or payload.get("gemini_model")
        if model_val:
            settings["ai_model"] = str(model_val).strip()
            settings["gemini_model"] = str(model_val).strip()

        if "custom_base_url" in payload:
            settings["custom_base_url"] = str(payload["custom_base_url"]).strip()

        if "theme" in payload and payload["theme"] in ["dark", "light"]:
            settings["theme"] = payload["theme"]

        self.save_settings(settings)
        return settings
