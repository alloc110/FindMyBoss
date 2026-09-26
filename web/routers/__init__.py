from web.routers.jobs import router as jobs_router
from web.routers.profile import router as profile_router
from web.routers.scraper import router as scraper_router
from web.routers.settings import router as settings_router

__all__ = ["jobs_router", "profile_router", "scraper_router", "settings_router"]
