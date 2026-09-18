import os
import random
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from playwright.async_api import Locator, Page

from config import config
from crawl.base_crawl import JobScraper
from models.Job import Job


class IndeedJob(JobScraper):
    """Scraper implementation for Indeed Vietnam platform."""

    SELECTORS = {
        "job_card": "li .job_seen_beacon",
        "title_span": "a.jcs-JobTitle span",
        "title_anchor": "a.jcs-JobTitle",
        "company": "[data-testid='company-name']",
        "location": "[data-testid='text-location']",
        "close_popup": "button.icl-CloseButton, .mosaic-desktop-mosaic-provider-popup-close",
    }

    def __init__(self, page: Page, webhook_url: Optional[str] = None):
        super().__init__(page=page, webhook_url=webhook_url)
        self.base_search_url: str = "https://vn.indeed.com/jobs"
        self.roles: Dict[str, str] = {
            "Data Engineer": "data engineer",
            "Data Engineer Intern": "data engineer intern",
        }
        self.unfind: tuple[str, ...] = config.unwanted_titles

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
                self.logger.info("🛡️ Indeed modal detected and successfully closed.")
        except Exception:
            pass

    async def crawl_today(self) -> List[Job]:
        """Scrape job postings updated within the last 24 hours."""
        jobs: List[Job] = []
        try:
            await self._handle_indeed_popups()
            cards = await self.page.locator(self.SELECTORS["job_card"]).all()
            self.logger.info(f"🔍 [Today] Found {len(cards)} job cards on this page viewport")

            for card in cards:
                job = await self.parse_card_detail(card)
                if job and job.link != "N/A" and job.link not in self.scraped_links:
                    self.scraped_links.add(job.link)
                    job.posted_date = "Today"
                    jobs.append(job)
        except Exception as e:
            self.logger.error(f"❌ Error executing crawl_today data extraction: {str(e)}")
        return jobs

    async def parse_card_detail(self, card: Locator) -> Optional[Job]:
        """Extract job details from HTML element into Job dataclass."""
        timeout = config.element_timeout_ms

        try:
            title_element = card.locator(self.SELECTORS["title_span"])
            title = await title_element.get_attribute("title", timeout=timeout)
            if not title:
                title = await title_element.inner_text(timeout=timeout)

            company = await card.locator(self.SELECTORS["company"]).inner_text(timeout=timeout)
            location = await card.locator(self.SELECTORS["location"]).inner_text(timeout=timeout)

            raw_href = await card.locator(self.SELECTORS["title_anchor"]).get_attribute("href", timeout=timeout)
            job_link = f"https://vn.indeed.com{raw_href}" if raw_href else "N/A"

            return Job(
                title=title.strip() if title else "N/A",
                company=company.strip() if company else "N/A",
                link=job_link,
                address=location.strip() if location else "N/A",
                exp=None,
                salary="Deal",
                posted_date="Available",
                image=None,
                time=self.now_iso(),
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to parse Indeed job card: {str(e)}")
            return None

    async def crawl_all_pages(self, today: bool = False) -> List[Job]:
        """Runs search queries directly via target URL parameters."""
        all_jobs: List[Job] = []

        try:
            for role, slug_name in self.roles.items():
                await self.page.wait_for_timeout(random.randint(1000, 3000))

                query_parameters = {
                    "q": slug_name,
                    "l": "Thành phố Hồ Chí Minh",
                    "fromage": "1",  # 24-hour filter parameter
                }
                target_url = self._inject_query_param(self.base_search_url, query_parameters)

                self.logger.info(f"🚀 Routing to Indeed target endpoint: {target_url}")
                await self.page.goto(target_url, wait_until="load", timeout=config.navigation_timeout_ms)
                await self.page.wait_for_timeout(3000)

                role_jobs = await self.scrape_current_role_pages(today)
                all_jobs.extend(role_jobs)

            all_jobs = self.filter_unwanted_titles(all_jobs, self.unfind)

        except Exception as e:
            screenshot_name = "indeed_cloudflare_capture.png"
            try:
                await self.page.screenshot(path=screenshot_name)
                self.logger.error(
                    f"💥 Pipeline exception on Indeed: {str(e)}. Screenshot captured at: {screenshot_name}",
                    exc_info=True,
                )
            except Exception:
                self.logger.error(f"💥 Pipeline exception on Indeed: {str(e)}")

        return all_jobs

    async def scrape_current_role_pages(self, today: bool = False) -> List[Job]:
        """Manages pagination and extraction flow."""
        current_page: int = 1
        role_jobs: List[Job] = []

        self.logger.info(f"Processing Indeed batch page: {current_page}")
        role_jobs.extend(await self.crawl_today())

        return role_jobs