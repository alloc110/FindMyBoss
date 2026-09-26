import os
from pathlib import Path

from services.ai.service import GeminiService
from services.latex_engine import LatexEngine
from services.profile_service import ProfileService
from services.settings_service import SettingsService
from services.storage import JobStorage

# Directory structure
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "web" / "static"
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
DATA_DIR = BASE_DIR / "data"
CVS_DIR = DATA_DIR / "cvs"
SCRAPER_CONFIG_FILE = DATA_DIR / "scraper_config.json"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
CVS_DIR.mkdir(parents=True, exist_ok=True)

# Shared Service Singletons
storage = JobStorage(db_path=str(DATA_DIR / "jobs.db"))
settings_service = SettingsService(settings_file=DATA_DIR / "settings.json")
profile_service = ProfileService(data_dir=DATA_DIR)
latex_engine = LatexEngine(output_dir=str(CVS_DIR))

# Initialize AI Service from persisted settings
initial_settings = settings_service.load_settings()
init_provider = initial_settings.get("ai_provider", "gemini")
init_key = initial_settings.get(f"{init_provider}_api_key") or initial_settings.get("gemini_api_key")
if initial_settings.get("gemini_api_key"):
    os.environ["GEMINI_API_KEY"] = initial_settings["gemini_api_key"]

gemini_service = GeminiService(
    api_key=init_key,
    model_name=initial_settings.get("ai_model", "gemini-2.5-flash"),
    provider=init_provider,
    base_url=initial_settings.get("custom_base_url"),
)
