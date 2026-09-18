import asyncio
import random
import time
from typing import List, Tuple, Type

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from config import config, get_logger
from crawl.base_crawl import JobScraper
from crawl.IndeedJob import IndeedJob
from crawl.ITviecJob import ITviecJob
from crawl.JobsGoJob import JobsGoJob
from crawl.TopCVJob import TopCVJob
from crawl.TopDevJob import TopDevJob
from crawl.VietnamWorksJob import VietnamWorksJob
from models.Job import Job
from services.notifier import DiscordNotifier
from services.storage import JobStorage

logger = get_logger("ScraperOrchestrator")


async def execute_crawler(
    browser: Browser,
    crawler_class: Type[JobScraper],
    stealth_driver: Stealth,
    notifier: DiscordNotifier,
    storage: JobStorage,
) -> List[Job]:
    """
    Executes a single crawler within an isolated Browser Context using a Two-Phase approach:
    - Phase 1: Fast listing discovery & initial filtering
    - Phase 2: Targeted deep scraping to extract 100% FULL raw JD, skills, requirements, and real salary
    - Phase 3: Persistent storage to data/jobs.jsonl for future CV tailoring apps + lightweight Discord alert
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
        scraped_jobs = await scraper.crawl_all_pages(today=True)
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

        # Phase 3: Persist full raw JDs to JSONL dataset for future AI CV-matching app
        if enriched_jobs:
            saved_count = storage.save_jobs(enriched_jobs)
            logger.info(f"💾 Saved {saved_count} jobs to data/jobs.jsonl (Total in DB: {storage.count_total_jobs()})")

            # Print rich summary to console
            print("\n" + "=" * 70)
            print(f"📦 KẾT QUẢ CHI TIẾT ({len(enriched_jobs)} Jobs từ {crawler_class.__name__}):")
            print("=" * 70)
            for i, j in enumerate(enriched_jobs, 1):
                scraper.print_job_detail(j, i)
            print("=" * 70 + "\n")

            # Dispatch clean alert (WITHOUT long bulky JD) to Discord
            logger.info(f"Dispatching {len(enriched_jobs)} clean alert(s) to Discord...")
            await notifier.send_jobs(enriched_jobs)

    except Exception as e:
        logger.error(
            f"Execution failed inside subsystem {crawler_class.__name__}: {str(e)}",
            exc_info=True,
        )

    finally:
        # Guarantee resource teardown to prevent dangling memory leaks
        await context.close()

    return enriched_jobs


async def main_orchestrator() -> None:
    """Main Orchestrator handling the global browser lifecycle and metrics tracking."""
    crawlers: Tuple[Type[JobScraper], ...] = (
        IndeedJob,
        VietnamWorksJob,
        ITviecJob,
        JobsGoJob,
        TopCVJob,
        TopDevJob,
    )
    all_collected_jobs: List[Job] = []
    notifier = DiscordNotifier()
    storage = JobStorage()

    start_perf_time = time.perf_counter()
    logger.info("Initializing global enterprise chromium infrastructure...")

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--log-level=3",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        stealth_driver = Stealth(init_scripts_only=True)

        for crawler_class in crawlers:
            jobs = await execute_crawler(browser, crawler_class, stealth_driver, notifier, storage)
            all_collected_jobs.extend(jobs)

            # Throttling delay between sites to lower IP blocking probabilities
            await asyncio.sleep(config.throttle_delay_seconds)
            logger.info(
                f"Cumulative tracking metric: {len(all_collected_jobs)} total jobs aggregated so far."
            )

        await browser.close()

    duration_seconds = time.perf_counter() - start_perf_time

    logger.info("=" * 80)
    logger.info(f"Pipeline executed successfully. Aggregated jobs count: {len(all_collected_jobs)}")
    logger.info(f"Total dataset records in data/jobs.jsonl: {storage.count_total_jobs()}")
    logger.info(f"Total orchestration execution duration: {round(duration_seconds, 2)} seconds")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main_orchestrator())