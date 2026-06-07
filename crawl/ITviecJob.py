from typing import List, Set, Optional, Dict
import datetime
import logging
import os
import zoneinfo

from crawl.base_crawl import JobScraper
import models.Job as Job
from playwright.async_api import Page, Locator

# =================================================================
# COMPONENT-BASED NATIVE LOGGING (ENGLISH STANDARD)
# =================================================================
logger = logging.getLogger("ITviecJobScraper")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

VN_TIMEZONE = zoneinfo.ZoneInfo('Asia/Ho_Chi_Minh')

class ITviecJob(JobScraper):
    # --- CENTRALIZED SELECTORS (Easy to maintain when UI changes) ---
    SELECTORS = {
        "job_list_container": '[data-search--pagination-target="jobList"]',
        "job_card": ".job-card",
        "job_title": 'h3[data-search--job-selection-target="jobTitle"]',
        "company_name": ".ims-2 a",
        "location_div": "div[title]",
        "posted_date": ".small-text.text-dark-grey",
        "logo_source": "picture source",
        "next_page_btn": 'div.page.next a[rel="next"]'
    }

    def __init__(self, page: Page, webhook_url: Optional[str]):
        super().__init__(page=page, webhook_url=webhook_url)
        self.url: str = "https://itviec.com/jobs-expertise-index"
        
        # Target screening filters
        self.find_level: List[str] = ["INTERN", "FRESHER", "JUNIOR"]
        self.un_find_level: List[str] = [
            "SENIOR", "LEAD", "MANAGER", "DIRECTOR", "HEAD", "CHIEF",
            "TRƯỞNG", "PHÓ", "GIÁM ĐỐC", "QUẢN LÝ", "TRƯỞNG PHÒNG",
            "PHÓ PHÒNG", "TRƯỞNG BAN", "PHÓ BAN", "TRƯỞNG NHÓM",
            "PHÓ NHÓM", "TRƯỞNG DỰ ÁN"
        ]
        self.roles: Dict[str, str] = {
            "Data Analyst": "data-analyst",
            "Big Data Engineer": "big-data-engineer",
            "Data Engineer": "data-engineer",
            "DataOps / MLOps Engineer": "dataops-mlops-engineer",
            "Database Engineer": "database-engineer"
        }
        self.scraped_links: Set[str] = set()

    def _filter_and_classify(self, job: Job.Job, enforce_today: bool = False) -> Optional[Job.Job]:
        """
        Internal Helper: Encapsulates location validation, time filtering, 
        and experience level classification (Solves DRY violation).
        """
        # 1. Location Validation
        if "Hồ Chí Minh" not in job.address:
            return None

        # 2. Real-time Daily Filter (Only if enforce_today is enabled)
        if enforce_today and "hours" not in job.posted_date.lower():
            return None

        job_title_upper = job.title.upper()

        # 3. Target Level Matching (Intern, Fresher, Junior)
        for level in self.find_level:
            if level in job_title_upper:
                job.exp = level
                return job

        # 4. Blacklisted Management/Senior Titles Exclusion
        for level in self.un_find_level:
            if level in job_title_upper:
                return None

        # 5. Default Fallback
        job.exp = "Unknown"
        return job

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job.Job]:
        """Unified extraction processor across both dynamic historical & batch pipelines."""
        valid_jobs: List[Job.Job] = []
        try:
            container = self.page.locator(self.SELECTORS["job_list_container"]).first
            cards = await container.locator(self.SELECTORS["job_card"]).all()
            logger.info(f"🔍 Found {len(cards)} job tokens raw blocks on current canvas.")
            
            for card in cards: 
                job = await self.parse_card_detail(card)
                
                if job.link != "N/A" and job.link not in self.scraped_links:
                    self.scraped_links.add(job.link)
                    
                    # Process classification pipelines sequentially
                    processed_job = self._filter_and_classify(job, enforce_today=enforce_today)
                    if processed_job:
                        valid_jobs.append(processed_job)
                        
        except Exception as e:
            logger.error(f"❌ Error executing page extraction block pipeline: {str(e)}")
        return valid_jobs

    async def crawl(self) -> List[Job.Job]:
        """Scrapes all matching historical roles available on the current index page."""
        return await self._execute_extraction_pipeline(enforce_today=False)
    
    async def crawl_today(self) -> List[Job.Job]:
        """Scrapes only freshly posted rows updated within the last 24 hours."""
        return await self._execute_extraction_pipeline(enforce_today=True)
    
    async def parse_card_detail(self, card: Locator) -> Job.Job:
        """Extracts structured DOM boundaries safely into a unified Job schema mapping."""
        ELEMENT_TIMEOUT: float = 1500.0  # Defensive 1.5s timeout constraint per card attribute
        
        try:
            title_element = card.locator(self.SELECTORS["job_title"])
            title = await title_element.inner_text(timeout=ELEMENT_TIMEOUT)
            
            company = await card.locator(self.SELECTORS["company_name"]).inner_text(timeout=ELEMENT_TIMEOUT)
            data_url = await title_element.get_attribute("data-url", timeout=ELEMENT_TIMEOUT) or "N/A"
            
            location_attr = await card.locator(self.SELECTORS["location_div"]).last.get_attribute("title", timeout=ELEMENT_TIMEOUT) or ""
            location = "Hồ Chí Minh" if "Ho Chi Minh" in location_attr else location_attr
                
            posted_date_elem = card.locator(self.SELECTORS["posted_date"]).first
            posted_date = await posted_date_elem.inner_text(timeout=ELEMENT_TIMEOUT) if await posted_date_elem.count() > 0 else "N/A"
            posted_date = posted_date.replace("Posted", "").strip()
            
            logo_url = await card.locator(self.SELECTORS["logo_source"]).get_attribute("data-srcset", timeout=ELEMENT_TIMEOUT) or ""
            
            return Job.Job(
                title=title.strip(),
                company=company.strip(),
                link=data_url,
                address=location,
                exp=None,
                salary="Deal",
                posted_date=posted_date,
                image=logo_url,
                time=datetime.datetime.now(VN_TIMEZONE).isoformat()
            )
        except Exception as e:
            logger.warning(f"⚠️ Structural token decay or element mismatch detected on target card block: {str(e)}")
            return Job.Job(title="N/A", company="N/A", link="N/A", address="Unknown", exp=None, salary="Deal", posted_date="N/A", image=None, time=datetime.datetime.now(VN_TIMEZONE).isoformat())
        
    async def crawl_all_pages(self, today: bool = False) -> List[Job.Job]:
        """Iterates cleanly through defined technical target domains."""
        all_jobs: List[Job.Job] = []
        
        for role, slug in self.roles.items():
            logger.info(f"📂 Navigating execution matrix context to specialization: [{role}]")
            target_url = f"https://itviec.com/it-jobs/{slug}"
            
            try:
                await self.page.goto(target_url, wait_until="load", timeout=25000)
                await self.page.wait_for_timeout(2000)  # Stabilize UI state layout
                
                role_jobs = await self.scrape_current_role_pages(today)
                all_jobs.extend(role_jobs)
            except Exception as e:
                logger.error(f"💥 Failed to fetch target index context domain for route [{target_url}]: {str(e)}")
                continue
        
        return all_jobs
    
    async def scrape_current_role_pages(self, today: bool = False) -> List[Job.Job]:
        """Automated state machine engine to execute extraction across index pagination blocks."""
        current_page: int = 1
        role_jobs: List[Job.Job] = []
        
        while True:
            logger.info(f"Batch processing extraction matrix index at Page: {current_page}")
            
            if today:
                role_jobs.extend(await self.crawl_today())
            else:
                role_jobs.extend(await self.crawl()) 
            
            next_button = self.page.locator(self.SELECTORS["next_page_btn"])

            if await next_button.count() > 0:
                logger.info("➡️ Pagination hyperlink boundary verified. Dispatched JS event click.")
                current_page += 1
                
                # JavaScript emission bypasses layout element obstruction bugs entirely
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