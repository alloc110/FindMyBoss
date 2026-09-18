from typing import Dict, List, Optional
from playwright.async_api import Locator, Page

from config import config
from crawl.base_crawl import JobScraper
from models.Job import Job


class VietnamWorksJob(JobScraper):
    """Scraper implementation for VietnamWorks platform."""

    SELECTORS = {
        "state_indicators": ".view_job_item, .noResultWrapper",
        "no_result_wrapper": ".noResultWrapper",
        "job_list_block": ".block-job-list",
        "job_card": ".view_job_item",
        "title_anchor": "h2 a",
        "company_name": ".sc-cpgxJx",
        "salary_text": ".sc-dauhQT",
        "posted_date": ".sc-lccgLh",
        "company_logo": ".img_job_card img",
    }

    EXP_MAPPING = {
        "8": "Thực tập sinh/Sinh viên",
        "1": "Mới tốt nghiệp",
        "5": "Nhân viên",
    }

    def __init__(self, page: Page, webhook_url: Optional[str] = None):
        super().__init__(page=page, webhook_url=webhook_url)
        self.url: str = "https://www.vietnamworks.com/viec-lam?q="
        self.roles: Dict[str, str] = {
            "Data Engineer": "data-engineer",
        }
        self.unfind: tuple[str, ...] = config.unwanted_titles

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job]:
        """Unified internal tracking processor executing extraction, deduplication, and time-frame filtering."""
        valid_jobs: List[Job] = []
        try:
            await self.page.wait_for_selector(self.SELECTORS["state_indicators"], timeout=10000)
        except Exception:
            self.logger.warning("⚠️ Target VietnamWorks page failed to respond in time.")
            return valid_jobs

        if await self.page.locator(self.SELECTORS["no_result_wrapper"]).is_visible():
            self.logger.info("🚫 No jobs matching search criteria on VietnamWorks layout.")
            return valid_jobs

        try:
            await self.page.wait_for_selector(self.SELECTORS["job_list_block"], timeout=5000)
            cards = await self.page.locator(self.SELECTORS["job_card"]).all()
            self.logger.info(f"🔍 Found {len(cards)} raw job cards on VietnamWorks.")

            for card in cards:
                job = await self.parse_card_detail(card)
                if not job or job.link == "N/A" or job.link in self.scraped_links:
                    continue

                if enforce_today and "hôm nay" not in (job.posted_date or "").lower():
                    continue

                self.scraped_links.add(job.link)
                valid_jobs.append(job)
        except Exception as e:
            self.logger.error(f"❌ Error during VietnamWorks extraction: {str(e)}")

        return valid_jobs

    async def crawl(self) -> List[Job]:
        """Scrapes all accessible historical records present on VietnamWorks."""
        return await self._execute_extraction_pipeline(enforce_today=False)

    async def crawl_today(self) -> List[Job]:
        """Scrapes records published within current business date sequence."""
        return await self._execute_extraction_pipeline(enforce_today=True)

    async def parse_card_detail(self, card: Locator) -> Optional[Job]:
        """Extracts card elements defensively into standardized Job model."""
        timeout = config.element_timeout_ms

        try:
            title_anchor = card.locator(self.SELECTORS["title_anchor"]).first
            title_raw = await title_anchor.inner_text(timeout=timeout)
            title = title_raw.replace("Mới", "").strip()

            raw_href = await title_anchor.get_attribute("href", timeout=timeout)
            link = f"https://www.vietnamworks.com{raw_href}" if raw_href else "N/A"
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to extract Title/Link from VietnamWorks card: {str(e)}")
            return None

        try:
            company = await card.locator(self.SELECTORS["company_name"]).inner_text(timeout=timeout)
            company = company.strip()
        except Exception:
            company = "Unknown Company"

        try:
            salary = await card.locator(self.SELECTORS["salary_text"]).inner_text(timeout=timeout)
            salary = salary.strip()
        except Exception:
            salary = "Competitive / Deal"

        try:
            posted_date_raw = await card.locator(self.SELECTORS["posted_date"]).inner_text(timeout=timeout)
            posted_date = posted_date_raw.replace("Cập nhật:", "").strip()
        except Exception:
            posted_date = "Available"

        try:
            image = await card.locator(self.SELECTORS["company_logo"]).get_attribute("src", timeout=timeout)
            if not image or image.startswith("data:image/gif"):
                image = "https://images.vietnamworks.com/img/company-default-logo.svg"
        except Exception:
            image = "https://images.vietnamworks.com/img/company-default-logo.svg"

        return Job(
            title=title,
            company=company,
            link=link,
            address="Hồ Chí Minh",
            exp=None,
            salary=salary,
            posted_date=posted_date,
            image=image,
            time=self.now_iso(),
        )

    async def crawl_all_pages(self, today: bool = False) -> List[Job]:
        """Executes full search engine permutation matrices over configured parameters."""
        all_jobs: List[Job] = []

        for role, slug in self.roles.items():
            for exp_key, name_exp in self.EXP_MAPPING.items():
                self.logger.info(f"📂 Shifting VietnamWorks context: [{role}] | Level: [{name_exp}]")
                target_url = f"{self.url}{slug}&l=29&level={exp_key}"

                try:
                    await self.page.goto(target_url, wait_until="load", timeout=config.navigation_timeout_ms)
                    await self.page.wait_for_timeout(2000)

                    role_jobs = await self.scrape_current_role_pages(today)

                    for job in role_jobs:
                        job.exp = name_exp

                    all_jobs.extend(role_jobs)

                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                except Exception as ex:
                    self.logger.error(f"💥 Critical routing failure on VietnamWorks [{target_url}]: {str(ex)}")
                    continue

        all_jobs = self.filter_unwanted_titles(all_jobs, self.unfind)
        return all_jobs

    async def scrape_current_role_pages(self, today: bool = False) -> List[Job]:
        """Manages step-by-step UI pagination loops via safe client-side JavaScript execution."""
        current_page: int = 1
        role_jobs: List[Job] = []

        while True:
            self.logger.info(f"Processing VietnamWorks batch at Page: {current_page}")
            if today:
                role_jobs.extend(await self.crawl_today())
            else:
                role_jobs.extend(await self.crawl())

            next_button = self.page.locator(f".pagination button:text-is('{current_page + 1}')")
            if await next_button.count() > 0:
                self.logger.info(f"➡️ VietnamWorks next page {current_page + 1}. Dispatched JS event.")
                await next_button.dispatch_event("click")
                current_page += 1

                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                    await self.page.wait_for_timeout(1000)
                except Exception:
                    pass
            else:
                self.logger.info(f"🏁 VietnamWorks pagination terminal reached at ({current_page}) pages.")
                break

        return role_jobs