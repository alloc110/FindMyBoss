import asyncio
import time
from typing import Any, Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException
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
    "last_run": None,
    "last_duration_seconds": None,
    "total_scraped_last_run": 0,
    "error": None,
}


async def run_crawler_pipeline():
    global crawler_state
    crawler_state["is_running"] = True
    crawler_state["current_stage"] = "starting"
    crawler_state["error"] = None
    start_time = time.time()

    try:
        from main import main_orchestrator
        crawler_state["current_stage"] = "harvesting"
        logger.info("🚀 Launching Playwright crawler pipeline in worker container...")
        await main_orchestrator()
        duration = round(time.time() - start_time, 2)
        crawler_state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
        crawler_state["last_duration_seconds"] = duration
        crawler_state["current_stage"] = "completed"
        logger.info(f"✅ Crawler pipeline completed in {duration}s")
    except Exception as e:
        logger.error(f"❌ Crawler pipeline failed: {e}")
        crawler_state["error"] = str(e)
        crawler_state["current_stage"] = "failed"
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
async def trigger_scrape(background_tasks: BackgroundTasks):
    """
    Triggers the multi-portal job harvester pipeline in background.
    """
    if crawler_state["is_running"]:
        return {
            "success": False,
            "message": "Quá trình cào dữ liệu đang được thực thi. Vui lòng chờ phiên hiện tại hoàn thành.",
            "state": crawler_state,
        }

    background_tasks.add_task(run_crawler_pipeline)
    return {
        "success": True,
        "message": "Đã kích hoạt tiến trình cào việc làm nền thành công trên worker container!",
        "state": crawler_state,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.scraper_microservice:app", host="0.0.0.0", port=8002, reload=True)
