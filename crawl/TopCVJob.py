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
logger = logging.getLogger("TopCVJobScraper")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

VN_TIMEZONE = zoneinfo.ZoneInfo('Asia/Ho_Chi_Minh')

class TopCVJob(JobScraper):
    # --- CENTRALIZED SELECTORS DICTIONARY ---
    SELECTORS = {
        "empty_block": ".none-suitable-job",
        "job_list_container": ".job-list-search-result",
        "job_card": ".job-item-search-result",
        "job_title": "h3.title",
        "job_link": "h3.title a",
        "company_name": ".company-name",
        "label_update": ".label-update",
        "salary_label": "label.salary",
        "company_logo": ".avatar img.w-100",
        "next_page_btn": 'a[rel="next"]'
    }

    def __init__(self, page: Page, webhook_url: Optional[str]):
        super().__init__(page=page, webhook_url=webhook_url)
        self.url: str = "https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257?category_family=r257"
        self.roles: Dict[str, str] = {
            "Data Engineer": "https://www.topcv.vn/tim-viec-lam-data-engineer",
        }
        self.exp: Dict[str, str] = {"1": "Không yêu cầu", "2": "Dưới 1 năm", "3": "1 năm"}
        self.scraped_links: Set[str] = set()

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job.Job]:
        """Unified internal pipeline executing extraction, deduplication, and time-frame filtering."""
        valid_jobs: List[Job.Job] = []
        try:
            empty_block = self.page.locator(self.SELECTORS["empty_block"])
            if await empty_block.is_visible():
                logger.info("🔍 Empty state matched: No suitable target jobs available on this viewport.")
                return valid_jobs

            container = self.page.locator(self.SELECTORS["job_list_container"]).first
            cards = await container.locator(self.SELECTORS["job_card"]).all()
            logger.info(f"🔍 Found {len(cards)} raw job card tokens on current canvas area.")
            
            for card in cards: 
                job = await self.parse_card_detail(card)
                
                if job.link != "N/A" and job.link not in self.scraped_links:
                    # Enforce real-time temporal logging verification constraints if required
                    if enforce_today:
                        date_lower = job.posted_date.lower()
                        if not any(k in date_lower for k in ["hôm nay", "vừa đăng"]):
                            continue
                            
                    self.scraped_links.add(job.link)
                    valid_jobs.append(job)
        except Exception as e:
            logger.error(f"❌ Error executing page extraction block pipeline: {str(e)}")
        return valid_jobs

    async def crawl(self) -> List[Job.Job]:
        """Scrapes all accessible historical records present on the target listing workspace."""
        return await self._execute_extraction_pipeline(enforce_today=False)
    
    async def crawl_today(self) -> List[Job.Job]:
        """Scrapes records published exclusively within the current business date run context."""
        return await self._execute_extraction_pipeline(enforce_today=True)
    
    async def parse_card_detail(self, card: Locator) -> Job.Job:
        """Transforms unstable UI element boundaries into an explicit, standardized structural model."""
        ELEMENT_TIMEOUT: float = 1500.0  # Defensive 1.5s timeout barrier per individual data point
        
        try:
            title = await card.locator(self.SELECTORS["job_title"]).inner_text(timeout=ELEMENT_TIMEOUT)
            company = await card.locator(self.SELECTORS["company_name"]).inner_text(timeout=ELEMENT_TIMEOUT)
            link = await card.locator(self.SELECTORS["job_link"]).get_attribute("href", timeout=ELEMENT_TIMEOUT) or "N/A"
                
            label_locator = card.locator(self.SELECTORS["label_update"])
            posted_date = await label_locator.inner_text(timeout=ELEMENT_TIMEOUT) if await label_locator.count() > 0 else "Unknown"
            posted_date = posted_date.replace("Đăng", "").strip()  
                  
            salary_loc = card.locator(self.SELECTORS["salary_label"])
            salary = "Unknown"
            if await salary_loc.count() > 0:
                salary_raw = await salary_loc.inner_text(timeout=ELEMENT_TIMEOUT)
                salary = salary_raw.replace("\n", " ").strip() if salary_raw else "Unknown"
            
            logo_element = card.locator(self.SELECTORS["company_logo"])
            image = "N/A"
            if await logo_element.count() > 0:
                image = await logo_element.get_attribute("data-src", timeout=ELEMENT_TIMEOUT) or \
                        await logo_element.get_attribute("src", timeout=ELEMENT_TIMEOUT) or "N/A"

            return Job.Job(
                title=title.strip(),
                company=company.strip(),
                link=link,
                address="Hồ Chí Minh",
                exp=None,
                salary=salary,
                posted_date=posted_date,
                image=image,
                time=datetime.datetime.now(VN_TIMEZONE).isoformat()
            )
        except Exception as e:
            logger.warning(f"⚠️ Structural field extraction anomaly detected on target card block: {str(e)}")
            return Job.Job(title="N/A", company="N/A", link="N/A", address="Hồ Chí Minh", exp=None, salary="Unknown", posted_date="N/A", image=None, time=datetime.datetime.now(VN_TIMEZONE).isoformat())
        
    async def crawl_all_pages(self, today: bool = False) -> List[Job.Job]:
        """Executes full search engine permutation matrices over configured parameters."""
        all_jobs: List[Job.Job] = []
        
        for role, slug in self.roles.items():
            for exp, name_exp in self.exp.items():  
                logger.info(f"📂 Shifting focus context matrix to target: [{role}] | Class: [{name_exp}]")

                target_url = f"{slug}-tai-ho-chi-minh-kl2cr257?exp=1&type_keyword={exp}&sba=1&category_family=r257&locations=l2&saturday_status=0"
                
                try:
                    await self.page.goto(target_url, wait_until="load", timeout=25000)
                    await self.page.wait_for_timeout(5000)  # Safe buffer allowing TopCV AJAX schemas to finalize
                    
                    role_jobs = await self.scrape_current_role_pages(today)
                    
                    # Apply semantic experience structure values based on the matrix sequence path
                    exp_mapping = {
                        "1": "Không yêu cầu kinh nghiệm",
                        "2": "Dưới 1 năm kinh nghiệm",
                        "3": "1 năm kinh nghiệm"
                    }
                    for job in role_jobs:
                        job.exp = exp_mapping.get(exp, "Unknown")
                        
                    all_jobs.extend(role_jobs)
                    
                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=5000)
                    except:
                        pass
                except Exception as ex:
                    logger.error(f"💥 Critical routing failure requesting index endpoint target [{target_url}]: {str(ex)}")
                    continue
                    
        return all_jobs
    
    async def scrape_current_role_pages(self, today: bool = False) -> List[Job.Job]:
        """Manages step-by-step UI pagination loops via safe client-side JavaScript execution."""
        current_page: int = 1
        role_jobs: List[Job.Job] = []
        
        while True:
            logger.info(f"Processing evaluation batch index at Page: {current_page}")
            
            if today:
                role_jobs.extend(await self.crawl_today())
            else:
                role_jobs.extend(await self.crawl()) 
            
            next_button = self.page.locator(self.SELECTORS["next_page_btn"])

            if await next_button.count() > 0:
                logger.info("➡️ Pagination hyperlink layout matched. Transferring focus index via JS event.")
                current_page += 1
                
                # JavaScript element emission bypasses visibility obstruction edge cases perfectly
                await next_button.dispatch_event("click")
                
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                    await self.page.wait_for_timeout(1000)
                except:
                    pass
            else:
                logger.info(f"🏁 Pagination terminal edge reached. Processed array context closed at ({current_page}) total records.")
                break   
                    
        return role_jobs