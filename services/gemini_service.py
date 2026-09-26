"""
Facade for MultiProviderAIService.
Maintains 100% backward-compatibility with existing imports from services.gemini_service.
"""
from models.schemas import GeminiTailorResponse
from services.ai.service import GeminiService, MultiProviderAIService

__all__ = [
    "GeminiTailorResponse",
    "GeminiService",
    "MultiProviderAIService",
]
