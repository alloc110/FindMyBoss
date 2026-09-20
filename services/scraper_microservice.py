import asyncio
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Body
from pydantic import BaseModel

from config import get_logger
from services.storage import JobStorage

logger = get_logger("ScraperMicroservice")

app = FastAPI(
    title="FindMyBoss Job Harvester & Scraper Microservice",
    description="Dedicated microservice managing Playwright Chromium crawler worker for Vietnamese tech job portals.",
    version="1.0.0",
)

crawler_state: Dict[str, Any] = {
    "is_running": False,
    "current_stage": "idle",
    "current_portal": None,
    "last_run": None,
    "last_duration_seconds": None,
    "total_scraped_last_run": 0,
    "error": None,
}


class ScrapePayload(BaseModel):
    portals: Optional[List[str]] = None
    today_only: Optional[bool] = False


async def run_crawler_pipeline(portals: Optional[List[str]] = None, today_only: bool = False):
    global crawler_state
    crawler_state["is_running"] = True
    crawler_state["current_stage"] = "Khởi tạo trình duyệt Playwright..."
    crawler_state["current_portal"] = None
    crawler_state["error"] = None
    crawler_state["total_scraped_last_run"] = 0
    start_time = time.time()

    async def _progress_callback(portal_name: str, current_count: int, stage: str):
        crawler_state["current_portal"] = portal_name
        crawler_state["current_stage"] = f"Đang cào {portal_name.upper()}... (Đã thu thập {current_count} việc)"
        crawler_state["total_scraped_last_run"] = current_count

    try:
        from main import main_orchestrator
        crawler_state["current_stage"] = "Bắt đầu thu thập dữ liệu..."
        logger.info(f"🚀 Launching Playwright crawler pipeline in worker container (portals={portals}, today_only={today_only})...")
        jobs = await main_orchestrator(
            selected_portals=portals,
            today_only=today_only,
            progress_callback=_progress_callback,
        )
        duration = round(time.time() - start_time, 2)
        crawler_state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
        crawler_state["last_duration_seconds"] = duration
        crawler_state["total_scraped_last_run"] = len(jobs)
        crawler_state["current_stage"] = f"Hoàn tất: Đã cào {len(jobs)} jobs trong {duration}s"
        logger.info(f"✅ Crawler pipeline completed: {len(jobs)} jobs in {duration}s")
    except Exception as e:
        logger.error(f"❌ Crawler pipeline failed: {e}")
        crawler_state["error"] = str(e)
        crawler_state["current_stage"] = f"Lỗi: {str(e)}"
    finally:
        crawler_state["is_running"] = False


@app.get("/health")
async def health_check():
    """Health status of the scraper worker container."""
    storage = JobStorage()
    return {
        "status": "healthy",
        "service": "findmyboss-scraper",
        "is_running": crawler_state["is_running"],
        "total_jobs_in_db": storage.count_total_jobs(),
    }


@app.get("/api/scrape/status")
async def get_scrape_status():
    """Returns current crawling execution state."""
    storage = JobStorage()
    return {
        **crawler_state,
        "total_jobs_in_db": storage.count_total_jobs(),
    }


@app.post("/api/scrape")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    payload: Optional[ScrapePayload] = None,
):
    """
    Triggers the multi-portal job harvester pipeline in background.
    """
    if crawler_state["is_running"]:
        return {
            "success": False,
            "message": "Quá trình cào dữ liệu đang được thực thi. Vui lòng chờ phiên hiện tại hoàn thành.",
            "state": crawler_state,
        }

    portals = payload.portals if payload else None
    today_only = bool(payload.today_only) if (payload and payload.today_only is not None) else False

    async def _task():
        await run_crawler_pipeline(portals=portals, today_only=today_only)

    background_tasks.add_task(_task)
    return {
        "success": True,
        "message": "Đã kích hoạt tiến trình cào việc làm nền thành công trên worker container!",
        "state": crawler_state,
    }


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("SCRAPER_PORT", 8003))
    uvicorn.run("services.scraper_microservice:app", host="0.0.0.0", port=port, reload=True)

