"""
Services package for FindMyBoss.
Gracefully handles modular microservice environments where only a subset
of optional dependencies (e.g. AI SDKs or PDF parsers) are installed.
"""
from services.notifier import DiscordNotifier
from services.storage import JobStorage

try:
    from services.ai.service import GeminiService, MultiProviderAIService
except ImportError:
    GeminiService = None  # type: ignore
    MultiProviderAIService = None  # type: ignore

try:
    from services.latex_engine import LatexEngine, escape_latex
except ImportError:
    LatexEngine = None  # type: ignore
    escape_latex = None  # type: ignore

try:
    from services.settings_service import SettingsService
except ImportError:
    SettingsService = None  # type: ignore

try:
    from services.profile_service import ProfileService
except ImportError:
    ProfileService = None  # type: ignore

__all__ = [
    "JobStorage",
    "GeminiService",
    "MultiProviderAIService",
    "LatexEngine",
    "escape_latex",
    "DiscordNotifier",
    "SettingsService",
    "ProfileService",
]
