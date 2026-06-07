import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Tuple, Type
import random

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import Stealth

# Import your custom scrapers cleanly
from crawl.base_crawl import JobScraper
from crawl.IndeedJob import IndeedJob
from crawl.ITviecJob import ITviecJob
from crawl.JobsGoJob import JobsGoJob
from crawl.TopCVJob import TopCVJob
from crawl.TopDevJob import TopDevJobScraper
from crawl.VietnamWorksJob import VietnamWorksJob

# =================================================================
# ORCHESTRATOR NATIVE LOGGING CONFIGURATION
# =================================================================
logger = logging.getLogger("ScraperOrchestrator")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

load_dotenv()

# Centralized Configuration via Environment Variables
DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL")
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def execute_crawler(browser: Browser, crawler_class: Type[JobScraper], stealth_driver: Stealth) -> list:
    """
    Executes a single crawler within an isolated Browser Context.
    Ensures zero state-bleeding (cookies/session contamination) between different sites.
    """
    context: BrowserContext = await browser.new_context(
        user_agent=BROWSER_USER_AGENT,
        viewport={'width': 1280, 'height': 800},
        locale="vi-VN",
        timezone_id="Asia/Ho_Chi_Minh"
    )
    
    # CRITICAL ANTI-BOT STEP: Apply stealth scripts *BEFORE* allocating any pages
    await stealth_driver.apply_stealth_async(context)
    page: Page = await context.new_page()
    
    # Mimic initial organic human interaction on blank canvas
    await page.wait_for_timeout(1000)
    await page.mouse.move(random.randint(100, 300), random.randint(200, 400))
    
    scraped_jobs = []
    logger.info(f"================ Launching Engine: {crawler_class.__name__} ================")
    
    try:
        scraper = crawler_class(page=page, webhook_url=DISCORD_WEBHOOK_URL)
        # Execute targeted real-time daily batch scraping
        scraped_jobs = await scraper.crawl_all_pages(today=True)
        
        logger.info(f"Successfully harvested {len(scraped_jobs)} jobs from {crawler_class.__name__}")
        
        # Dispatch alerts out asynchronously
        for job in scraped_jobs:
            scraper.send_to_discord(job)
            
    except Exception as e:
        logger.error(f"Execution failed inside target subsystem {crawler_class.__name__}: {str(e)}", exc_info=True)
        
    finally:
        # Guarantee resource teardown to prevent dangling memory leaks
        await context.close()
        
    return scraped_jobs

async def main_orchestrator() -> None:
    """Main Orchestrator handling the global browser lifecycle and metrics tracking."""
    crawlers: Tuple[Type[JobScraper], ...] = (IndeedJob,VietnamWorksJob, ITviecJob, JobsGoJob, TopCVJob, TopDevJobScraper) 
    all_collected_jobs = []
    
    start_perf_time = time.perf_counter()
    logger.info("Initializing global enterprise chromium infrastructure...")
    
    async with async_playwright() as p:
        # Headless mode can be switched to True in real production deployments
        browser: Browser = await p.chromium.launch(headless=True)
        stealth_driver = Stealth(init_scripts_only=True)
        
        for crawler_class in crawlers:
            jobs = await execute_crawler(browser, crawler_class, stealth_driver)
            all_collected_jobs.extend(jobs)
            
            # Throttling delay between sites to lower IP blocking probabilities
            await asyncio.sleep(5)
            logger.info(f"Cumulative tracking metric: {len(all_collected_jobs)} total jobs aggregated so far.")
            
        await browser.close()
        
    # Execution metrics performance calculations
    end_perf_time = time.perf_counter()
    duration_seconds = end_perf_time - start_perf_time
    
    logger.info("=" * 80)
    logger.info(f"Pipeline executed successfully. Aggregated jobs count: {len(all_collected_jobs)}")
    logger.info(f"Total orchestration execution duration: {round(duration_seconds, 2)} seconds")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main_orchestrator())