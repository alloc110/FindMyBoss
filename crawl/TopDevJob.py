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
logger = logging.getLogger("TopDevJobScraper")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

VN_TIMEZONE = zoneinfo.ZoneInfo('Asia/Ho_Chi_Minh')

class TopDevJobScraper(JobScraper):
    # --- CENTRALIZED SELECTORS DICTIONARY ---
    SELECTORS = {
        "job_list_container": "div.flex-col.gap-2",
        "job_card": ".text-card-foreground",
        "title_anchor": "a.text-brand-500",
        "company_name": "span.text-text-500",
        "grid_details": "div.grid span.line-clamp-1",
        "date_span": "div.border-t span.text-text-500",
        "card_image": "img[alt='job-image']",
        "it_category_span": "ul li span",
        "role_button_wrapper": 'div[style*="width:600px"] button'
    }

    def __init__(self, page: Page, webhook_url: Optional[str]):
        super().__init__(page=page, webhook_url=webhook_url)
        self.url: str = "https://topdev.vn/jobs/search"
        self.roles: List[str] = [
            "Software Developer", 
            "Data Engineer / Scientist / Analyst", 
            "Machine Learning / AI Engineer", 
            "DevOps Engineer"
        ]
        self.scraped_links: Set[str] = set()

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job.Job]:
        """Unified core pipeline handling card extraction, location validation, and deduplication."""
        valid_jobs: List[Job.Job] = []
        try:
            container = self.page.locator(self.SELECTORS["job_list_container"]).first
            cards = await container.locator(self.SELECTORS["job_card"]).all()        
            logger.info(f"Found {len(cards)} raw job card tokens on the current page viewport.")
            
            for card in cards:
                job_data = await self.parse_card_detail(card) 
                
                if "Hồ Chí Minh" in job_data.address:
                    if enforce_today:
                        date_lower = job_data.posted_date.lower()
                        if not any(k in date_lower for k in ["hours", "giờ", "phút"]):
                            continue
                            
                    if job_data.link not in self.scraped_links:
                        valid_jobs.append(job_data)
                        self.scraped_links.add(job_data.link)
        except Exception as e:
            logger.error(f"❌ Error during card extraction block pipeline: {str(e)}")
        return valid_jobs

    async def crawl(self) -> List[Job.Job]:
        """Scrapes all historical listings present on the current search viewport index."""
        return await self._execute_extraction_pipeline(enforce_today=False)

    async def crawl_today(self) -> List[Job.Job]:
        """Scrapes listings published exclusively within the current business date sequence."""
        return await self._execute_extraction_pipeline(enforce_today=True)
    
    async def parse_card_detail(self, card: Locator) -> Job.Job:
        """Transforms loose UI DOM elements into an explicit structural Job schema model."""
        ELEMENT_TIMEOUT: float = 1500.0  # Defensive isolated 1.5s timeout barrier per individual data point
        
        try:
            anchor = card.locator(self.SELECTORS["title_anchor"]).first
            title = await anchor.inner_text(timeout=ELEMENT_TIMEOUT)
            cleaned_title = title.rsplit(' (', 1)[0] if ' (' in title else title
            
            company = await card.locator(self.SELECTORS["company_name"]).first.inner_text(timeout=ELEMENT_TIMEOUT)
            link = "https://topdev.vn" + (await anchor.get_attribute("href", timeout=ELEMENT_TIMEOUT) or "")
            
            details = await card.locator(self.SELECTORS["grid_details"]).all_inner_texts()
            address = details[0].strip() if len(details) > 0 else "N/A"
            
            exp_data = details[1].split(",") if len(details) > 1 else ["N/A"]      
            level = exp_data[0].strip() if len(exp_data) > 0 else "N/A"
           
            date_locator = card.locator(self.SELECTORS["date_span"]).first
            posted_date = await date_locator.inner_text(timeout=ELEMENT_TIMEOUT) if await date_locator.count() > 0 else "N/A"
            
            image = await card.locator(self.SELECTORS["card_image"]).get_attribute("src", timeout=ELEMENT_TIMEOUT) or ""
            
            return Job.Job(
                title=cleaned_title.strip(),
                company=company.strip(),
                link=link,
                address=address,
                exp=level,
                salary="Deal",
                posted_date=posted_date.strip(),
                image=image,
                time=datetime.datetime.now(VN_TIMEZONE).isoformat()
            )
        except Exception as e:
            logger.warning(f"⚠️ Structural field extraction anomaly detected on target card block: {str(e)}")
            return Job.Job(title="N/A", company="N/A", link="N/A", address="Unknown", exp="N/A", salary="Deal", posted_date="N/A", image=None, time=datetime.datetime.now(VN_TIMEZONE).isoformat())
    
    async def crawl_all_pages(self, today: bool = False) -> List[Job.Job]:
        """Initializes complex functional search filters and supervises the global pagination machine loop."""
        current_page: int = 1
        all_jobs: List[Job.Job] = []
        
        try:
            logger.info(f"🚀 Navigating orchestration framework to target endpoint index: {self.url}")
            await self.page.goto(self.url, wait_until="load", timeout=25000)
            
            # Trigger drop-down functional filter block
            await self.page.get_by_role("button", name="All Categories").click()
            await self.page.wait_for_timeout(1000)
            
            # JavaScript element emission bypasses layout element overlay blocking bugs entirely
            it_span = self.page.locator(self.SELECTORS["it_category_span"]).filter(has_text="IT").first
            logger.info("🎯 Selecting target domain specialization classification [IT] via client JS Engine...")
            await it_span.dispatch_event("click")
            
            # Select target roles sequentially inside the initialized viewport boundary wrapper
            for role in self.roles:
                role_button = self.page.locator(self.SELECTORS["role_button_wrapper"]).filter(has_text=role)
                if await role_button.count() > 0:
                    await role_button.dispatch_event("click")
            
            # Commit selected structures
            await self.page.get_by_role("button", name="Apply", exact=True).click() 
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(2000)
            
        except Exception as e:
            logger.error(f"💥 Critical layout configuration failure during initial form assembly routing: {str(e)}")
            return all_jobs

        # Programmatic pagination machine execution block
        while True:
            logger.info(f"Processing execution matrix extraction on context tracking page index: {current_page}")
            
            if today:
                all_jobs.extend(await self.crawl_today())
            else:
                all_jobs.extend(await self.crawl()) 
            
            next_button = self.page.get_by_label("Go to next page")
 
            if await next_button.count() > 0 and await next_button.is_visible():
                class_attr = await next_button.get_attribute("class") or ""
                
                # Intercept tail tracking endpoints if custom CSS tags mark elements disabled
                if "pointer-events-none opacity-0" in class_attr or "disabled" in class_attr:
                    logger.info("🚫 Next page button status flag marked disabled. Terminal array index matched.")
                    break
                
                logger.info("➡️ Transitioning focus layout frame to the next paginated page index.")
                await next_button.dispatch_event("click")  
                current_page += 1
                
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                    await self.page.wait_for_timeout(3000)  # Safe delay allowing incoming AJAX payloads to settle
                except:
                    pass
            else:
                logger.info("🏁 No matching transition elements remaining on active DOM hierarchy. Loop closed.")
                break
               
        return all_jobs
    
    def send_to_discord(self, job_data: Job.Job) -> None:
        super().send_to_discord(job_data)