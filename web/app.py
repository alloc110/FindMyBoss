"""
FindMyBoss — Main Web Application & API Gateway.
Smart Job Board with Multi-Provider AI CV Tailoring and Tectonic LaTeX PDF Generator.
"""
from typing import Any, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import get_logger
from web.dependencies import (
    STATIC_DIR,
    TEMPLATES_DIR,
    gemini_service,
    latex_engine,
    profile_service,
    settings_service,
    storage,
)
from web.routers import jobs_router, profile_router, scraper_router, settings_router

logger = get_logger("WebApp")

app = FastAPI(
    title="FindMyBoss - Job Dashboard & ATS CV Studio",
    description="Smart Job Board with Multi-Provider AI CV Tailoring and Tectonic LaTeX PDF Generator",
    version="2.0.0",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include Modular API Routers
app.include_router(jobs_router)
app.include_router(settings_router)
app.include_router(profile_router)
app.include_router(scraper_router)


# -------------------------------------------------------------
# Core Frontend & Stats Routes
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the main single-page application dashboard."""
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>FindMyBoss UI is loading...</h1>")


@app.get("/api/stats")
async def get_dashboard_stats():
    """Provides overview statistics for the UI header."""
    stats = storage.get_stats()
    stats["has_gemini_key"] = bool(gemini_service.api_key)
    stats["ai_provider"] = gemini_service.provider
    stats["gemini_model"] = gemini_service.model_name
    return stats


# -------------------------------------------------------------
# Backward-Compatible Helper Functions & Re-exports
# -------------------------------------------------------------
def load_settings() -> Dict[str, Any]:
    return settings_service.load_settings()


def save_settings(settings_data: Dict[str, Any]) -> None:
    settings_service.save_settings(settings_data)


def load_profile() -> Dict[str, Any]:
    return profile_service.load_profile()


def save_profile(profile_data: Dict[str, Any]) -> None:
    profile_service.save_profile(profile_data)


__all__ = [
    "app",
    "storage",
    "latex_engine",
    "gemini_service",
    "settings_service",
    "profile_service",
    "load_settings",
    "save_settings",
    "load_profile",
    "save_profile",
]
