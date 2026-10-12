import argparse
import asyncio
import json
import random
import re
import sys
import time

# Reconfigure stdout/stderr for Windows UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from core.config import config, get_logger
from crawl.base_crawl import JobScraper
from crawl.IndeedJob import IndeedJob
from crawl.ITviecJob import ITviecJob
from crawl.JobsGoJob import JobsGoJob
from crawl.TopCVJob import TopCVJob
from crawl.TopDevJob import TopDevJob
from crawl.VietnamWorksJob import VietnamWorksJob
from crawl.filters import filter_jobs_by_web_config
from models.Job import Job
from services.notifier import DiscordNotifier
from services.storage import JobStorage

logger = get_logger("ScraperOrchestrator")

CRAWLER_REGISTRY: Dict[str, Type[JobScraper]] = {
    "topdev": TopDevJob,
    "vietnamworks": VietnamWorksJob,
    "itviec": ITviecJob,
    "topcv": TopCVJob,
    "jobsgo": JobsGoJob,
    "indeed": IndeedJob,
}


async def execute_crawler(
    browser: Browser,
    crawler_class: Type[JobScraper],
    stealth_driver: Stealth,
    notifier: DiscordNotifier,
    storage: JobStorage,
    today: bool = False,
    scraper_cfg: Optional[Dict[str, Any]] = None,
) -> List[Job]:
    """
    Executes a single crawler within an isolated Browser Context using a Two-Phase approach:
    - Phase 1: Fast listing discovery & initial filtering
    - Phase 2: Targeted deep scraping to extract 100% FULL raw JD, skills, requirements, and real salary
    - Phase 3: Persistent storage to SQLite database + lightweight Discord alert
    """
    context: BrowserContext = await browser.new_context(
        user_agent=config.user_agent,
        viewport={"width": 1280, "height": 800},
        locale="vi-VN",
        timezone_id="Asia/Ho_Chi_Minh",
    )

    # Apply stealth scripts BEFORE allocating pages
    await stealth_driver.apply_stealth_async(context)
    page: Page = await context.new_page()

    # Mimic initial organic human interaction on blank canvas
    await page.wait_for_timeout(1000)
    await page.mouse.move(random.randint(100, 300), random.randint(200, 400))

    enriched_jobs: List[Job] = []
    logger.info(f"================ Launching Engine: {crawler_class.__name__} ================")

    try:
        scraper = crawler_class(page=page, webhook_url=config.discord_webhook_url)

        # Phase 1: Fast listing discovery across pagination
        target_roles = (scraper_cfg or {}).get("roles") or []
        try:
            scraped_jobs = await scraper.crawl_all_pages(today=today, roles=target_roles)
        except TypeError:
            scraped_jobs = await scraper.crawl_all_pages(today=today)
        logger.info(
            f"Phase 1 complete: Harvested {len(scraped_jobs)} candidate jobs from {crawler_class.__name__}"
        )

        # Phase 2: Targeted deep scraping on candidate jobs (Extract full 100% JD)
        for idx, job in enumerate(scraped_jobs, 1):
            if job.link and job.link != "N/A":
                logger.info(f"🔍 [Phase 2] Deep scraping full JD ({idx}/{len(scraped_jobs)}): {job.title} ({job.company})")
                try:
                    detailed_job = await scraper.crawl_job_detail(job)
                    enriched_jobs.append(detailed_job)
                    # Polite throttle between detail requests
                    await page.wait_for_timeout(1500)
                except Exception as err:
                    logger.warning(f"⚠️ Failed to deep scrape job details ({job.link}): {err}")
                    enriched_jobs.append(job)
            else:
                enriched_jobs.append(job)

        # Phase 3: Filter jobs according to Web Configuration before saving & Discord notification
        if enriched_jobs:
            passed_jobs, rejected_jobs = filter_jobs_by_web_config(enriched_jobs, scraper_cfg)

            logger.info(
                f"🛡️ Web Filter [{crawler_class.__name__}]: "
                f"{len(passed_jobs)} passed, {len(rejected_jobs)} rejected."
            )
            for r_job, reason in rejected_jobs:
                logger.info(f"   🚫 Đã lọc bỏ: [{r_job.title}] ({r_job.company}) — Lý do: {reason}")

            if passed_jobs:
                saved_count = storage.save_jobs(passed_jobs)
                logger.info(f"💾 Saved {saved_count} qualified jobs to SQLite (Total in DB: {storage.count_total_jobs()})")

                # Print rich summary to console
                print("\n" + "=" * 70)
                print(f"📦 KẾT QUẢ ĐẠT TIÊU CHUẨN BỘ LỌC ({len(passed_jobs)} Jobs từ {crawler_class.__name__}):")
                print("=" * 70)
                for i, j in enumerate(passed_jobs, 1):
                    scraper.print_job_detail(j, i)
                print("=" * 70 + "\n")

                # Dispatch clean alert (WITHOUT long bulky JD) to Discord for qualified jobs ONLY
                logger.info(f"📬 Dispatching {len(passed_jobs)} qualified alert(s) to Discord...")
                await notifier.send_jobs(passed_jobs)
                return passed_jobs
            else:
                logger.info(f"ℹ️ Không có job nào từ {crawler_class.__name__} thỏa mãn bộ lọc Web.")
                return []

    except Exception as e:
        logger.error(
            f"Execution failed inside subsystem {crawler_class.__name__}: {str(e)}",
            exc_info=True,
        )

    finally:
        try:
            await context.close()
        except Exception:
            pass

    return []


async def main_orchestrator(
    selected_portals: Optional[List[str]] = None,
    today_only: Optional[bool] = None,
    progress_callback: Optional[Callable] = None,
    scraper_cfg_override: Optional[Dict[str, Any]] = None,
) -> List[Job]:
    """Main Orchestrator handling dynamic portal execution, browser lifecycle, and progress callbacks."""
    # Load full web scraper configuration
    cfg_file = Path("data/scraper_config.json")
    scraper_cfg: Dict[str, Any] = {}
    if cfg_file.exists():
        try:
            scraper_cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not load data/scraper_config.json: {e}")

    # Merge dynamic overrides (e.g. from Quick Scrape modal or CLI)
    if scraper_cfg_override:
        scraper_cfg.update({k: v for k, v in scraper_cfg_override.items() if v is not None})

    # Resolve today_only priority:
    # 1. Parameter passed explicitly (True / False)
    # 2. scraper_cfg_override ("today_only")
    # 3. scraper_cfg ("today_only")
    # 4. Default to False
    if today_only is None:
        if scraper_cfg_override and "today_only" in scraper_cfg_override and scraper_cfg_override["today_only"] is not None:
            today_only = bool(scraper_cfg_override["today_only"])
        else:
            today_only = bool(scraper_cfg.get("today_only", False))

    logger.info(
        f"⏳ Chế độ cào: {'[CHỈ CÀO HÔM NAY (today_only=True)]' if today_only else '[CÀO TẤT CẢ MỚI NHẤT (today_only=False)]'}"
    )

    # Determine which portals to crawl
    target_crawlers: Dict[str, Type[JobScraper]] = {}
    if selected_portals:
        normalized_requested = [p.lower().strip() for p in selected_portals]
        target_crawlers = {
            k: v for k, v in CRAWLER_REGISTRY.items() if k in normalized_requested
        }

    if not target_crawlers and scraper_cfg:
        portal_flags = scraper_cfg.get("portals", {})
        target_crawlers = {
            k: v for k, v in CRAWLER_REGISTRY.items() if portal_flags.get(k, True)
        }

    # Default to all if still empty
    if not target_crawlers:
        target_crawlers = dict(CRAWLER_REGISTRY)

    all_collected_jobs: List[Job] = []
    notifier = DiscordNotifier()
    storage = JobStorage()

    start_perf_time = time.perf_counter()
    logger.info(f"Initializing Chromium infrastructure for portals: {list(target_crawlers.keys())}...")

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--log-level=3",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
            ],
        )
        stealth_driver = Stealth(init_scripts_only=True)

        for portal_name, crawler_class in target_crawlers.items():
            if progress_callback:
                try:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(portal_name, len(all_collected_jobs), "crawling")
                    else:
                        progress_callback(portal_name, len(all_collected_jobs), "crawling")
                except Exception as cb_err:
                    logger.warning(f"Progress callback error: {cb_err}")

            try:
                jobs = await execute_crawler(
                    browser, crawler_class, stealth_driver, notifier, storage, today=today_only, scraper_cfg=scraper_cfg
                )
                all_collected_jobs.extend(jobs)
            except Exception as portal_err:
                logger.error(f"❌ Error during crawling {portal_name}: {portal_err}")

            # Throttling delay between sites
            await asyncio.sleep(config.throttle_delay_seconds)
            logger.info(
                f"Cumulative tracking metric: {len(all_collected_jobs)} total jobs aggregated so far."
            )

        try:
            await browser.close()
        except Exception:
            pass

    duration_seconds = time.perf_counter() - start_perf_time

    logger.info("=" * 80)
    logger.info(f"Pipeline executed successfully. Aggregated jobs count: {len(all_collected_jobs)}")
    logger.info(f"Total dataset records in SQLite DB: {storage.count_total_jobs()}")
    logger.info(f"Total orchestration execution duration: {round(duration_seconds, 2)} seconds")
    logger.info("=" * 80)

    return all_collected_jobs


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FindMyBoss Scraper Orchestrator - Automated tech job harvester for Vietnam portals."
    )
    parser.add_argument(
        "-t",
        "--today",
        action="store_true",
        default=None,
        help="Chỉ cào các tin tuyển dụng đăng trong ngày hôm nay (24 giờ gần nhất).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Cào mọi tin tuyển dụng mới nhất (bỏ qua thiết lập today_only trong scraper_config.json).",
    )
    parser.add_argument(
        "-p",
        "--portals",
        type=str,
        default=None,
        help="Danh sách các cổng tuyển dụng cách nhau bởi dấu phẩy (vd: itviec,topcv,topdev,vietnamworks,jobsgo,indeed).",
    )
    parser.add_argument(
        "-r",
        "--roles",
        type=str,
        default=None,
        help="Danh sách chuyên môn (roles) cách nhau bởi dấu phẩy (vd: backend,frontend,da,de,ai_ml,mobile,tester,devops).",
    )
    parser.add_argument(
        "-m",
        "--max-pages",
        type=int,
        default=None,
        help="Số trang tối đa mỗi cổng tuyển dụng (mặc định theo cấu hình).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_cli_args()

    # Determine today_only priority from CLI
    target_today: Optional[bool] = None
    if cli_args.today:
        target_today = True
    elif cli_args.all:
        target_today = False

    target_portals = (
        [p.strip().lower() for p in cli_args.portals.split(",") if p.strip()]
        if cli_args.portals
        else None
    )

    cli_overrides: Dict[str, Any] = {}
    if cli_args.roles:
        cli_overrides["roles"] = [r.strip().lower() for r in cli_args.roles.split(",") if r.strip()]
    if cli_args.max_pages:
        cli_overrides["max_pages_per_portal"] = cli_args.max_pages

    asyncio.run(
        main_orchestrator(
            selected_portals=target_portals,
            today_only=target_today,
            scraper_cfg_override=cli_overrides if cli_overrides else None,
        )
    )
