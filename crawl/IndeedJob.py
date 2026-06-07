from typing import List, Set, Optional, Dict
import datetime
import logging
import os
import random
import zoneinfo
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from crawl.base_crawl import JobScraper
import models.Job as Job
from playwright.async_api import Page, Locator

# =================================================================
# COMPONENT-BASED NATIVE LOGGING (ENGLISH STANDARD)
# =================================================================
logger = logging.getLogger("IndeedJobScraper")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

VN_TIMEZONE = zoneinfo.ZoneInfo('Asia/Ho_Chi_Minh')

class IndeedJob(JobScraper):
    # --- CENTRALIZED SELECTORS DICTIONARY ---
    SELECTORS = {
        "job_card": "li .job_seen_beacon",
        "title_span": "a.jcs-JobTitle span",
        "title_anchor": "a.jcs-JobTitle",
        "company": "[data-testid='company-name']",
        "location": "[data-testid='text-location']",
        "close_popup": "button.icl-CloseButton, .mosaic-desktop-mosaic-provider-popup-close"
    }

    def __init__(self, page: Page, webhook_url: Optional[str]):
        super().__init__(page=page, webhook_url=webhook_url)
        # Direct search API entry-point replacing unstable home index view
        self.base_search_url: str = "https://vn.indeed.com/jobs"
        self.roles: Dict[str, str] = {
            "Data Engineer": "data engineer",
            "Data Engineer Intern": "data engineer intern",
        }
        self.unfind: List[str] = ["senior", "lead", "middle", "mid", "sr", "supervisor"]        
        self.scraped_links: Set[str] = set()

    def _inject_query_param(self, url: str, params: Dict[str, str]) -> str:
        """Safely inject query parameters into a URL without breaking its structure."""
        url_parts = list(urlparse(url))
        query = dict(parse_qsl(url_parts[4]))
        query.update(params)
        url_parts[4] = urlencode(query)
        return urlunparse(url_parts)

    async def _handle_indeed_popups(self) -> None:
        """Automatically detect and dismiss intrusive Indeed pop-ups or modals."""
        try:
            popup_close_btn = self.page.locator(self.SELECTORS["close_popup"]).first
            if await popup_close_btn.is_visible(timeout=500):
                await popup_close_btn.click()
                logger.info("🛡️ Indeed intrusive modal detected and successfully closed.")
        except Exception:
            pass

    async def crawl_today(self) -> List[Job.Job]:
        """Scrape job postings updated within the last 24 hours."""
        jobs: List[Job.Job] = []
        try:
            await self._handle_indeed_popups()
            cards = await self.page.locator(self.SELECTORS["job_card"]).all() 
            logger.info(f"🔍 [Today] Found {len(cards)} job cards on this page viewport")
            
            for card in cards: 
                job = await self.parse_card_detail(card)
                if job.link != "N/A" and job.link not in self.scraped_links:
                    self.scraped_links.add(job.link)
                    job.posted_date = "Today"
                    jobs.append(job)
        except Exception as e:
            logger.error(f"❌ Error executing crawl_today data extraction logic: {str(e)}")
        return jobs
    
    async def parse_card_detail(self, card: Locator) -> Job.Job:
        """Extract job details from HTML token into an Object Model with defensive timeout."""
        ELEMENT_TIMEOUT: float = 1500.0
        
        try:
            title_element = card.locator(self.SELECTORS["title_span"])
            title = await title_element.get_attribute("title", timeout=ELEMENT_TIMEOUT)
            if not title:
                title = await title_element.inner_text(timeout=ELEMENT_TIMEOUT)
            
            company = await card.locator(self.SELECTORS["company"]).inner_text(timeout=ELEMENT_TIMEOUT)
            location = await card.locator(self.SELECTORS["location"]).inner_text(timeout=ELEMENT_TIMEOUT)
            
            raw_href = await card.locator(self.SELECTORS["title_anchor"]).get_attribute("href", timeout=ELEMENT_TIMEOUT)
            job_link = f"https://vn.indeed.com{raw_href}" if raw_href else "N/A"
            
            return Job.Job(
                title=title.strip() if title else "N/A",
                company=company.strip() if company else "N/A",
                link=job_link,
                address=location.strip() if location else "N/A",
                exp=None,
                salary="Deal",
                posted_date="Available",
                image=None,
                time=datetime.datetime.now(VN_TIMEZONE).isoformat()
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse job card details or fields missing: {str(e)}")
            return Job.Job(title="N/A", company="N/A", link="N/A", address="Unknown", exp=None, salary="Deal", posted_date="N/A", image=None, time=datetime.datetime.now(VN_TIMEZONE).isoformat())
       
    async def crawl_all_pages(self, today: bool = False) -> List[Job.Job]:
        """Initialize routing paths directly via target URL params matrix."""
        all_jobs: List[Job.Job] = []
        
        try:
            for role, slug_name in self.roles.items():    
                await self.page.wait_for_timeout(random.randint(1000, 3000)) 

                # SENIOR BYPASS HACK: Build target query paths parameters directly 
                # Avoids form fields element interaction, minimizing Cloudflare behavior tracking
                query_parameters = {
                    "q": slug_name,
                    "l": "Thành phố Hồ Chí Minh",
                    "fromage": "1"  # Force 24-hour filter parameter inside the URL mapping natively
                }
                target_url = self._inject_query_param(self.base_search_url, query_parameters)
                
                logger.info(f"🚀 Routing directly to search results target endpoint: {target_url}")
                await self.page.goto(target_url, wait_until="load", timeout=30000)
                await self.page.wait_for_timeout(3000) 

                role_jobs = await self.scrape_current_role_pages(today)
                all_jobs.extend(role_jobs)
                
            all_jobs = self.filter(all_jobs)
            
        except Exception as e:
            # PRODUCTION DIAGNOSTIC CAPTURE: Saves exactly what the browser viewport renders on failure
            error_screenshot_path = "/home/loc/job-scraper/indeed_cloudflare_capture.png"
            await self.page.screenshot(path=error_screenshot_path)
            logger.error(f"💥 Critical pipeline exception: {str(e)}. Diagnostic state screenshot captured at: {error_screenshot_path}", exc_info=True)
                        
        return all_jobs
    
    async def scrape_current_role_pages(self, today: bool = False) -> List[Job.Job]:
        """Manage pagination and extraction flow."""
        current_page: int = 1
        role_jobs: List[Job.Job] = []
        
        logger.info(f"Processing extraction on batch page: {current_page}")
        role_jobs.extend(await self.crawl_today()) 
                    
        return role_jobs
    
    def filter(self, all_jobs: List[Job.Job]) -> List[Job.Job]:
        """Filter out jobs containing blacklisted titles (Senior, Lead, etc.)."""
        cleaned_job = [
            job for job in all_jobs
            if not any(filter_name in job.title.lower() for filter_name in self.unfind)
        ]
        logger.info(f"📋 Filter summary: Retained {len(cleaned_job)}/{len(all_jobs)} matching jobs.")
        return cleaned_job