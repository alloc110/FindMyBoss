from typing import List, Set, Optional, Dict
import datetime
import logging
import os
import random
import zoneinfo

from crawl.base_crawl import JobScraper
import models.Job as Job
from playwright.async_api import Page, Locator

# =================================================================
# COMPONENT-BASED NATIVE LOGGING (ENGLISH STANDARD)
# =================================================================
logger = logging.getLogger("JobsGoJobScraper")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

VN_TIMEZONE = zoneinfo.ZoneInfo('Asia/Ho_Chi_Minh')

class JobsGoJob(JobScraper):
    # --- CENTRALIZED SELECTORS DICTIONARY ---
    SELECTORS = {
        "job_list_container": ".job-list",
        "job_card": ".job-card",
        "job_title": ".job-title",
        "company_title": ".company-title",
        "detail_anchor": "a.text-decoration-none",
        "badge_custom": ".badge-custom",
        "card_image": ".image-wrapper img",
        "empty_state_text": "Hiện tại chưa có công việc phù hợp với yêu cầu của bạn",
        "empty_state_img": 'img[alt="Jobsgo Not Found"]',
        "next_page_btn": "li.next:not(.disabled) a"
    }

    def __init__(self, page: Page, webhook_url: Optional[str]):
        super().__init__(page=page, webhook_url=webhook_url)
        self.roles: Dict[str, str] = {
            "Software Engineer": "https://jobsgo.vn/viec-lam-software-engineer-tai-ho-chi-minh.html?sort=created",
            "Data Engineer": "https://jobsgo.vn/viec-lam-data-engineer-tai-ho-chi-minh.html?sort=created",
        }
        self.exp: List[str] = ["khong-can-kinh-nghiem", "duoi-1-nam-kinh-nghiem", "1-2-nam-kinh-nghiem"]
        self.scraped_links: Set[str] = set()

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job.Job]:
        """Unified internal processor handling extraction, deduplication, and time-frame filtering."""
        valid_jobs: List[Job.Job] = []
        try:
            container = self.page.locator(self.SELECTORS["job_list_container"])
            cards = await container.locator(self.SELECTORS["job_card"]).all()
            logger.info(f"🔍 Found {len(cards)} raw job card tokens on the current viewport.")
            
            for card in cards: 
                job = await self.parse_card_detail(card)
                
                if job.link != "N/A" and job.link not in self.scraped_links:
                    # Apply real-time temporal streaming validation if enforce_today is active
                    if enforce_today:
                        date_lower = job.posted_date.lower()
                        if not any(k in date_lower for k in ["phút", "giờ", "giây"]):
                            continue
                            
                    self.scraped_links.add(job.link)
                    jobs.append(job) if 'jobs' in locals() else valid_jobs.append(job)
        except Exception as e:
            logger.error(f"❌ Error during card extraction block pipeline: {str(e)}")
        return valid_jobs

    async def crawl(self) -> List[Job.Job]:
        """Scrapes all historical listings present on the matching page array index context."""
        return await self._execute_extraction_pipeline(enforce_today=False)
    
    async def crawl_today(self) -> List[Job.Job]:
        """Scrapes listings published exclusively within the current business date sequence."""
        return await self._execute_extraction_pipeline(enforce_today=True)

    async def parse_card_detail(self, card: Locator) -> Job.Job:
        """Transforms loose UI DOM nodes into an explicit, standardized structural Job schema model."""
        ELEMENT_TIMEOUT: float = 1500.0  # Defensive isolated 1.5s timeout barrier per attribute
        
        try:
            title = await card.locator(self.SELECTORS["job_title"]).inner_text(timeout=ELEMENT_TIMEOUT)
            company = await card.locator(self.SELECTORS["company_title"]).inner_text(timeout=ELEMENT_TIMEOUT)
            link = await card.locator(self.SELECTORS["detail_anchor"]).get_attribute("href", timeout=ELEMENT_TIMEOUT) or "N/A"
                
            badges = card.locator(self.SELECTORS["badge_custom"])
            posted_date = await badges.nth(2).inner_text(timeout=ELEMENT_TIMEOUT) if await badges.count() >= 3 else "N/A"
            image = await card.locator(self.SELECTORS["card_image"]).get_attribute("src", timeout=ELEMENT_TIMEOUT) or ""
            
            return Job.Job(
                title=title.strip(),
                company=company.strip(),
                link=link,
                address="Hồ Chí Minh",
                exp=None,
                salary="Deal",
                posted_date=posted_date.strip(),
                image=image,
                time=datetime.datetime.now(VN_TIMEZONE).isoformat()
            )
        except Exception as e:
            logger.warning(f"⚠️ Structural token decay or element mismatch detected on target card block: {str(e)}")
            return Job.Job(title="N/A", company="N/A", link="N/A", address="Hồ Chí Minh", exp=None, salary="Deal", posted_date="N/A", image=None, time=datetime.datetime.now(VN_TIMEZONE).isoformat())

    async def crawl_all_pages(self, today: bool = False) -> List[Job.Job]:
        """Coordinates execution matrix loops across designated Role paths and Experience thresholds."""
        all_jobs: List[Job.Job] = []
        
        for role, slug in self.roles.items():
            for exp in self.exp:  
                logger.info(f"📂 Navigating execution context matrix to: [{role}] | Filter: [{exp}]")
                target_url = f"{slug}&exp={exp}"
                
                try:
                    await self.page.goto(target_url, wait_until="load", timeout=20000)
                    await self.page.wait_for_timeout(2000) 
                    
                    # Intercept empty UI results early via Text Parsing
                    empty_state_text = self.page.get_by_text(self.SELECTORS["empty_state_text"])
                    if await empty_state_text.is_visible():
                        logger.warning(f"🚧 No target matches available for configuration: [{role}] | [{exp}]. Skipping loop.")
                        continue  
                        
                    role_jobs = await self.scrape_current_role_pages(today)
                    all_jobs.extend(role_jobs)
                    
                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=3000)
                    except:
                        pass
                        
                except Exception as ex:
                    logger.error(f"💥 Critical routing error requesting index target boundary [{target_url}]: {str(ex)}")
                    continue 
                    
        return all_jobs
    
    async def scrape_current_role_pages(self, today: bool = False) -> List[Job.Job]:
        """Orchestrates pagination state machines via programmatic JavaScript DOM execution handling."""
        current_page: int = 1
        role_jobs: List[Job.Job] = []
        
        # Intercept empty UI results early via Image Placeholder tracking
        empty_state_img = self.page.locator(self.SELECTORS["empty_state_img"])
        if await empty_state_img.count() > 0:
            logger.warning("📂 Jobsgo 'Not Found' image state detected. Terminating pagination sub-loop.")
            return role_jobs 

        while True:
            logger.info(f"Processing extraction batch at tracking index Page: {current_page}")
            
            if today:
                role_jobs.extend(await self.crawl_today())
            else:
                role_jobs.extend(await self.crawl()) 
        
            next_button = self.page.locator(self.SELECTORS["next_page_btn"])
            
            if await next_button.count() > 0:
                current_page += 1
                # Emitting clean JavaScript click events avoids UI visibility/overlay masking anomalies completely
                await next_button.dispatch_event("click")
                
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                    await self.page.wait_for_timeout(1000)
                except:
                    pass
            else:
                logger.info(f"🏁 Termination boundary reached. Paginated array finalized at total: ({current_page}) indexes.")
                break   
                
        return role_jobs