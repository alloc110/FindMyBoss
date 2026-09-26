import json
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Body
import httpx

from config import get_logger
from web.dependencies import SCRAPER_CONFIG_FILE, storage

logger = get_logger("ScraperRouter")

router = APIRouter(prefix="/api/scraper", tags=["Scraper"])


@router.get("/config")
async def get_scraper_config():
    """Returns dynamic scraper configuration."""
    cfg = {}
    if SCRAPER_CONFIG_FILE.exists():
        try:
            cfg = json.loads(SCRAPER_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    if not cfg:
        cfg = {
            "portals": {"itviec": True, "topdev": True, "topcv": True, "vietnamworks": True, "jobsgo": True, "indeed": True},
            "keywords": ["python", "backend", "data engineer", "intern", "fresher", "junior"],
            "levels": ["intern", "fresher", "junior"],
            "locations": ["Hồ Chí Minh", "Hà Nội", "Toàn quốc", "Remote"],
            "blacklisted_keywords": ["senior", "lead", "middle", "mid", "sr", "manager", "director"],
            "max_pages_per_portal": 3,
            "delay_seconds": 2.0,
            "deep_scrape": True,
        }

    # Ensure standard frontend keys and aliases are synchronized
    if "levels" not in cfg:
        cfg["levels"] = cfg.get("target_levels", ["intern", "fresher", "junior"])
    if "locations" not in cfg:
        cfg["locations"] = cfg.get("target_cities", ["Hồ Chí Minh", "Hà Nội", "Toàn quốc", "Remote"])
    if "blacklisted_keywords" not in cfg:
        cfg["blacklisted_keywords"] = cfg.get("unwanted_titles", ["senior", "lead", "manager"])
    if "max_pages_per_portal" not in cfg:
        cfg["max_pages_per_portal"] = 3
    if "delay_seconds" not in cfg:
        cfg["delay_seconds"] = 2.0

    return cfg


@router.put("/config")
async def update_scraper_config(cfg: Dict[str, Any] = Body(...)):
    """Saves dynamic scraper options."""
    if "levels" in cfg and "target_levels" not in cfg:
        cfg["target_levels"] = cfg["levels"]
    if "locations" in cfg and "target_cities" not in cfg:
        cfg["target_cities"] = cfg["locations"]
    if "blacklisted_keywords" in cfg and "unwanted_titles" not in cfg:
        cfg["unwanted_titles"] = cfg["blacklisted_keywords"]

    SCRAPER_CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "message": "Scraper configuration updated successfully"}


@router.post("/run")
async def run_scraper(
    background_tasks: BackgroundTasks,
    payload: Optional[Dict[str, Any]] = Body(None),
):
    """Triggers job scraper either via Scraper Microservice or local background worker."""
    scraper_url = os.getenv("SCRAPER_SERVICE_URL", "").rstrip("/")
    if scraper_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(f"{scraper_url}/api/scrape", json=payload or {})
                return res.json()
        except Exception as e:
            logger.warning(f"Failed to trigger scraper microservice ({e}).")
            return {"success": False, "message": f"Không thể kết nối scraper microservice: {str(e)}"}
    else:
        async def _local_scrape():
            try:
                from main import main_orchestrator
                portals = (payload or {}).get("portals")
                today_only = (payload or {}).get("today_only", False)
                await main_orchestrator(selected_portals=portals, today_only=today_only)
            except Exception as e:
                logger.error(f"Local scraper failed: {e}")

        background_tasks.add_task(_local_scrape)
        return {"success": True, "message": "Đã khởi chạy tiến trình cào việc làm cục bộ."}


@router.get("/status")
async def get_scraper_status():
    """Returns current crawler status from Scraper Microservice or local storage."""
    scraper_url = os.getenv("SCRAPER_SERVICE_URL", "").rstrip("/")
    if scraper_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{scraper_url}/api/scrape/status")
                return res.json()
        except Exception:
            pass

    return {"is_running": False, "status": "idle", "total_jobs_in_db": storage.count_total_jobs()}
