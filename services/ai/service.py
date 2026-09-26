import os
from typing import Any, Dict, Optional

from config import get_logger
from models.schemas import GeminiTailorResponse
from services.ai.base import BaseAIProvider
from services.ai.claude_provider import ClaudeProvider
from services.ai.custom_provider import CustomProvider
from services.ai.gemini_provider import GeminiProvider
from services.ai.heuristic import HeuristicTailorEngine
from services.ai.openai_provider import OpenAIProvider

logger = get_logger("AIService")


class MultiProviderAIService:
    """
    Multi-Provider AI Service supporting Google Gemini, OpenAI (ChatGPT),
    Anthropic (Claude), and OpenAI-compatible endpoints (DeepSeek, Ollama, OpenRouter).
    Uses Strategy Pattern to dispatch requests to specialized providers.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        provider: str = "gemini",
        base_url: Optional[str] = None,
    ):
        self.provider = (provider or "gemini").lower().strip()
        self.model_name = model_name or "gemini-2.5-flash"
        self.api_key = api_key if api_key is not None else self._get_env_key_for_provider(self.provider)
        self.base_url = (base_url or "").strip() or None
        self._provider_instance: Optional[BaseAIProvider] = None
        self._init_provider()

    def _get_env_key_for_provider(self, provider: str) -> Optional[str]:
        if provider == "gemini":
            return os.getenv("GEMINI_API_KEY")
        elif provider == "openai":
            return os.getenv("OPENAI_API_KEY")
        elif provider == "claude":
            return os.getenv("ANTHROPIC_API_KEY")
        elif provider == "custom":
            return os.getenv("CUSTOM_AI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        return None

    def _init_provider(self):
        """Instantiates the specialized provider according to self.provider."""
        if not self.api_key:
            self._provider_instance = None
            logger.warning(
                f"API Key for {self.provider} not set. AIService will run in fallback simulation mode until key is provided."
            )
            return

        if self.provider == "gemini":
            self._provider_instance = GeminiProvider(
                api_key=self.api_key,
                model_name=self.model_name,
                base_url=self.base_url,
            )
        elif self.provider == "openai":
            self._provider_instance = OpenAIProvider(
                api_key=self.api_key,
                model_name=self.model_name,
                base_url=self.base_url,
            )
        elif self.provider == "claude":
            self._provider_instance = ClaudeProvider(
                api_key=self.api_key,
                model_name=self.model_name,
                base_url=self.base_url,
            )
        elif self.provider == "custom":
            self._provider_instance = CustomProvider(
                api_key=self.api_key,
                model_name=self.model_name,
                base_url=self.base_url,
            )
        else:
            self._provider_instance = None
            logger.warning(f"Unknown AI provider: '{self.provider}'. Running in fallback mode.")

    def configure(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Dynamically reconfigures provider, API key, model, and base URL."""
        if provider:
            self.provider = provider.lower().strip()
        if api_key is not None:
            self.api_key = api_key.strip() or None
        if model_name:
            self.model_name = model_name.strip()
        if base_url is not None:
            self.base_url = base_url.strip() or None
        self._init_provider()

    def test_connection(
        self,
        provider: str,
        api_key: str,
        model_name: str,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Actively tests whether the given provider, API key, and model can successfully connect.
        Returns latency in milliseconds and detailed status message.
        """
        provider_clean = (provider or "gemini").lower().strip()
        api_key_clean = (api_key or "").strip()
        model_clean = (model_name or "").strip()
        base_url_clean = (base_url or "").strip() or None

        if not api_key_clean:
            return {
                "ok": False,
                "success": False,
                "latency_ms": 0,
                "message": "Vui lòng nhập API Key trước khi kiểm tra.",
                "error": "Vui lòng nhập API Key trước khi kiểm tra.",
                "provider": provider_clean,
                "model": model_clean,
            }

        temp_provider: Optional[BaseAIProvider] = None
        if provider_clean == "gemini":
            temp_provider = GeminiProvider(api_key=api_key_clean, model_name=model_clean)
        elif provider_clean == "openai":
            temp_provider = OpenAIProvider(api_key=api_key_clean, model_name=model_clean)
        elif provider_clean == "claude":
            temp_provider = ClaudeProvider(api_key=api_key_clean, model_name=model_clean)
        elif provider_clean == "custom":
            temp_provider = CustomProvider(api_key=api_key_clean, model_name=model_clean, base_url=base_url_clean)

        if temp_provider:
            return temp_provider.test_connection(
                api_key=api_key_clean,
                model_name=model_clean,
                base_url=base_url_clean,
            )

        return {
            "ok": False,
            "success": False,
            "latency_ms": 0,
            "message": f"Nhà cung cấp không hỗ trợ: {provider_clean}",
            "error": f"Nhà cung cấp không hỗ trợ: {provider_clean}",
            "provider": provider_clean,
        }

    def tailor_cv_for_job(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        """
        Analyzes the Job Description and candidate profile, returning structured
        tailoring recommendations (Match score, missing keywords, tailored summary & bullets).
        Falls back gracefully to intelligent heuristic tailoring if API call fails or key is missing.
        """
        if self._provider_instance and self.api_key:
            try:
                return self._provider_instance.tailor_cv(job, profile)
            except Exception as e:
                logger.error(
                    f"{self.provider.upper()} API call failed: {e}. Falling back to intelligent heuristic tailoring."
                )

        return HeuristicTailorEngine.generate(job, profile)


# Backward-compatible alias
GeminiService = MultiProviderAIService
