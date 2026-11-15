import asyncio
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from core.config import config, get_logger
from web.dependencies import career_ops_service

logger = get_logger("CareerOpsRouter")

router = APIRouter(prefix="/api/career-ops", tags=["Career-Ops"])


class CareerOpsRequest(BaseModel):
    url: str
    template: str = "classic"
    send_to_discord: bool = True


@router.get("/status")
async def get_career_ops_status():
    """Returns the operational status of career-ops CLI and Discord notification channels."""
    workspace_ready = career_ops_service.workspace_dir.exists()
    has_webhook = bool(config.discord_webhook_url)
    has_bot_token = bool(config.discord_bot_token)

    return {
        "workspace_installed": workspace_ready,
        "workspace_path": str(career_ops_service.workspace_dir),
        "discord_webhook_configured": has_webhook,
        "discord_bot_configured": has_bot_token,
        "supported_features": [
            "Any Job URL Scraping (browser-extract.mjs & Playwright)",
            "ATS Scoring & Tailoring",
            "Automatic CV PDF Compilation",
            "Discord Webhook Notification with Attached PDF",
            "Discord Interactive Bot (!career <url>)",
        ],
    }


@router.post("/process")
async def process_job_url_endpoint(req: CareerOpsRequest):
    """
    Submits a Job URL to Career-Ops fast intake:
    - Extracts full Job Description from the URL.
    - Matches candidate profile and tailors CV.
    - Compiles ATS-ready PDF.
    - Saves Job in SQLite.
    - Dispatches rich embed + attached PDF directly to Discord!
    """
    url = req.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="URL không hợp lệ. Vui lòng nhập link bắt đầu bằng http:// hoặc https://")

    try:
        result = await career_ops_service.process_job_url(
            url=url,
            template=req.template,
            send_to_discord=req.send_to_discord,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to process career-ops URL '{url}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý Career-Ops: {str(e)}")


@router.get("/applications")
async def get_applications_tracker():
    """Returns the markdown text of data/applications.md."""
    from services.applications_tracker import generate_applications_markdown, get_applications_markdown_path

    content = generate_applications_markdown(career_ops_service.storage)
    path = get_applications_markdown_path()
    return {
        "file_path": str(path),
        "content": content,
    }


@router.post("/send-applications-tracker")
async def send_applications_tracker_endpoint():
    """Forces generation and dispatch of applications.md to Discord."""
    from services.notifier import DiscordNotifier

    notifier = DiscordNotifier()
    success = await notifier.send_applications_tracker()
    return {"success": success, "message": "Dispatched applications.md to Discord" if success else "Failed to send to Discord"}


@router.post("/trigger-daily-harvest")
async def trigger_daily_harvest_endpoint():
    """Triggers the full automated daily crawl and Career-Ops pipeline immediately."""
    from services.daily_scheduler import daily_scheduler

    asyncio.create_task(daily_scheduler.run_harvest_pipeline())
    return {
        "success": True,
        "message": "Đã kích hoạt tác vụ cào việc tự động & tạo CV Career-Ops ngầm trong hệ thống.",
    }
