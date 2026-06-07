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
logger = logging.getLogger("VietnamWorksJobScraper")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

VN_TIMEZONE = zoneinfo.ZoneInfo('Asia/Ho_Chi_Minh')

class VietnamWorksJob(JobScraper):
    # --- CENTRALIZED SELECTORS DICTIONARY ---
    SELECTORS = {
        "state_indicators": ".view_job_item, .noResultWrapper",
        "no_result_wrapper": ".noResultWrapper",
        "job_list_block": ".block-job-list",
        "job_card": ".view_job_item",
        "title_anchor": "h2 a",
        "company_name": ".sc-cpgxJx",
        "salary_text": ".sc-dauhQT",
        "posted_date": ".sc-lccgLh",
        "company_logo": ".img_job_card img"
    }

    def __init__(self, page: Page, webhook_url: Optional[str]):
        super().__init__(page=page, webhook_url=webhook_url)
        self.url: str = "https://www.vietnamworks.com/viec-lam?q="
        self.roles: Dict[str, str] = {
            "Data Engineer": "data-engineer",
        }
        self.exp: Dict[str, str] = {"8": "Thực tập sinh/Sinh viên", "1": "Mới tốt nghiệp", "5": "Nhân viên"}
        self.scraped_links: Set[str] = set()
        self.unfind: List[str] = ["senior", "middle", "sr", "mid", "lead"]
        
    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job.Job]:
        """Unified internal tracking processor executing extraction, deduplication, and time-frame filtering."""
        valid_jobs: List[Job.Job] = []
        try:
            # Synchronize initial indicators early
            await self.page.wait_for_selector(self.SELECTORS["state_indicators"], timeout=10000)
        except Exception:
            logger.warning("⚠️ Execution timeout exceeded: Target platform failed to respond.")
            return valid_jobs
     
        if await self.page.locator(self.SELECTORS["no_result_wrapper"]).is_visible():
            logger.info("🚫 Empty state matched: No target jobs matching search criteria on this layout.")
            return valid_jobs
        
        try:
            await self.page.wait_for_selector(self.SELECTORS["job_list_block"], timeout=5000)
            cards = await self.page.locator(self.SELECTORS["job_card"]).all()
            logger.info(f"🔍 Found {len(cards)} raw job card tokens on the current page viewport.")
            
            for card in cards: 
                job = await self.parse_card_detail(card)
                
                if job.link != "N/A" and job.link not in self.scraped_links:
                    # Enforce real-time temporal logging verification validation if required
                    if enforce_today and "hôm nay" not in job.posted_date.lower():
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
        """Scrapes records published exclusively within the current business date sequence."""
        return await self._execute_extraction_pipeline(enforce_today=True)
    
    async def parse_card_detail(self, card: Locator) -> Job.Job:
        """Transforms unstable UI styled-component element boundaries into an explicit structural model."""
        ELEMENT_TIMEOUT: float = 1500.0  # Defensive isolated 1.5s timeout barrier per dynamic field
        
        try:
            title_anchor = card.locator(self.SELECTORS["title_anchor"]).first
            title_raw = await title_anchor.inner_text(timeout=ELEMENT_TIMEOUT)
            title = title_raw.replace("Mới", "").strip()
            
            raw_href = await title_anchor.get_attribute("href", timeout=ELEMENT_TIMEOUT)
            link = f"https://www.vietnamworks.com{raw_href}" if raw_href else "N/A"
        except Exception as e:
            logger.warning(f"⚠️ Failed to extract fundamental tracking bounds (Title/Link) from layout element: {str(e)}")
            return Job.Job(title="N/A", company="N/A", link="N/A", address="Unknown", exp=None, salary="Deal", posted_date="N/A", image=None, time=datetime.datetime.now(VN_TIMEZONE).isoformat())

        # Defensive handling for unpredictable styled-component hashes
        try:
            company = await card.locator(self.SELECTORS["company_name"]).inner_text(timeout=ELEMENT_TIMEOUT)
            company = company.strip()
        except Exception:
            company = "Unknown Company"

        try:
            salary = await card.locator(self.SELECTORS["salary_text"]).inner_text(timeout=ELEMENT_TIMEOUT)
            salary = salary.strip()
        except Exception:
            salary = "Competitive / Deal"

        try:
            posted_date_raw = await card.locator(self.SELECTORS["posted_date"]).inner_text(timeout=ELEMENT_TIMEOUT)
            posted_date = posted_date_raw.replace("Cập nhật:", "").strip()
        except Exception:
            posted_date = "Available"

        try:
            image = await card.locator(self.SELECTORS["company_logo"]).get_attribute("src", timeout=ELEMENT_TIMEOUT)
            if not image or image.startswith("data:image/gif"):
                image = "https://images.vietnamworks.com/img/company-default-logo.svg"
        except Exception:
            image = "https://images.vietnamworks.com/img/company-default-logo.svg"
        
        return Job.Job(
            title=title,
            company=company,
            link=link,
            address="Hồ Chí Minh",
            exp=None,
            salary=salary,
            posted_date=posted_date,
            image=image,
            time=datetime.datetime.now(VN_TIMEZONE).isoformat()
        )
       
    async def crawl_all_pages(self, today: bool = False) -> List[Job.Job]:
        """Executes full search engine permutation matrices over configured parameters."""
        all_jobs: List[Job.Job] = []
        
        exp_mapping = {
            "8": "Thực tập sinh/Sinh viên",
            "1": "Mới tốt nghiệp",
            "5": "Nhân viên"
        }
        
        for role, slug in self.roles.items():
            for exp, name_exp in self.exp.items():  
                logger.info(f"📂 Shifting focus context matrix to target: [{role}] | Level Filter: [{name_exp}]")
                target_url = f"{self.url}{slug}&l=29&level={exp}"
                
                try:
                    await self.page.goto(target_url, wait_until="load", timeout=25000)
                    await self.page.wait_for_timeout(2000) 
                    
                    role_jobs = await self.scrape_current_role_pages(today)
                    
                    # Apply semantic mapping logic cleanly post-extraction
                    for job in role_jobs:
                        job.exp = exp_mapping.get(exp, "Unknown")
                        
                    all_jobs.extend(role_jobs)
                    
                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                except Exception as ex:
                    logger.error(f"💥 Critical routing failure requesting index endpoint target [{target_url}]: {str(ex)}")
                    continue
            
        all_jobs = self.filter(all_jobs)
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
            
            # Formulate dynamic next-page target selector tracking indices sequentially
            next_button = self.page.locator(f".pagination button:text-is('{current_page + 1}')")    
            if await next_button.count() > 0:
                logger.info(f"➡️ Pagination layout matched target step index {current_page + 1}. Dispatched JS event.")
                
                await next_button.dispatch_event("click")
                current_page += 1
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                    await self.page.wait_for_timeout(1000)
                except Exception:
                    pass
            else:
                logger.info(f"🏁 Pagination terminal edge reached. Processed array context closed at ({current_page}) total records.")
                break   
                    
        return role_jobs
    
    def filter(self, all_jobs: List[Job.Job]) -> List[Job.Job]:
        """Filter out jobs containing management/senior level keywords via list comprehension."""
        cleaned_job = [
            job for job in all_jobs 
            if not any(filter_name in job.title.lower() for filter_name in self.unfind)
        ]
        logger.info(f"📋 Global execution summary filter: Retained {len(cleaned_job)}/{len(all_jobs)} valid jobs.")
        return cleaned_job