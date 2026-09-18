from typing import Dict, List, Optional
from playwright.async_api import Locator, Page

from config import config
from crawl.base_crawl import JobScraper
from models.Job import Job


class JobsGoJob(JobScraper):
    """Scraper implementation for JobsGO platform."""

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
        "next_page_btn": "li.next:not(.disabled) a",
    }

    def __init__(self, page: Page, webhook_url: Optional[str] = None):
        super().__init__(page=page, webhook_url=webhook_url)
        self.roles: Dict[str, str] = {
            "Software Engineer": "https://jobsgo.vn/viec-lam-software-engineer-tai-ho-chi-minh.html?sort=created",
            "Data Engineer": "https://jobsgo.vn/viec-lam-data-engineer-tai-ho-chi-minh.html?sort=created",
        }
        self.exp: List[str] = [
            "khong-can-kinh-nghiem",
            "duoi-1-nam-kinh-nghiem",
            "1-2-nam-kinh-nghiem",
        ]

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job]:
        """Unified internal processor handling extraction, deduplication, and time-frame filtering."""
        valid_jobs: List[Job] = []
        try:
            container = self.page.locator(self.SELECTORS["job_list_container"])
            cards = await container.locator(self.SELECTORS["job_card"]).all()
            self.logger.info(f"🔍 Found {len(cards)} raw job card tokens on the current viewport.")

            for card in cards:
                job = await self.parse_card_detail(card)
                if not job or job.link == "N/A" or job.link in self.scraped_links:
                    continue

                # Apply real-time temporal validation if enforce_today is active
                if enforce_today:
                    date_lower = (job.posted_date or "").lower()
                    if not any(k in date_lower for k in ["phút", "giờ", "giây"]):
                        continue

                self.scraped_links.add(job.link)
                valid_jobs.append(job)

        except Exception as e:
            self.logger.error(f"❌ Error during JobsGO card extraction: {str(e)}")

        return valid_jobs

    async def crawl(self) -> List[Job]:
        """Scrapes all historical listings present on the matching page array index context."""
        return await self._execute_extraction_pipeline(enforce_today=False)

    async def crawl_today(self) -> List[Job]:
        """Scrapes listings published exclusively within the current business date sequence."""
        return await self._execute_extraction_pipeline(enforce_today=True)

    async def parse_card_detail(self, card: Locator) -> Optional[Job]:
        """Transforms UI DOM nodes into standardized Job schema model."""
        timeout = config.element_timeout_ms

        try:
            title = await card.locator(self.SELECTORS["job_title"]).inner_text(timeout=timeout)
            company = await card.locator(self.SELECTORS["company_title"]).inner_text(timeout=timeout)
            link = await card.locator(self.SELECTORS["detail_anchor"]).get_attribute("href", timeout=timeout) or "N/A"

            badges = card.locator(self.SELECTORS["badge_custom"])
            posted_date = await badges.nth(2).inner_text(timeout=timeout) if await badges.count() >= 3 else "N/A"
            image = await card.locator(self.SELECTORS["card_image"]).get_attribute("src", timeout=timeout) or ""

            return Job(
                title=title.strip(),
                company=company.strip(),
                link=link,
                address="Hồ Chí Minh",
                exp=None,
                salary="Deal",
                posted_date=posted_date.strip(),
                image=image,
                time=self.now_iso(),
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Structural mismatch on JobsGO card: {str(e)}")
            return None

    async def crawl_all_pages(self, today: bool = False) -> List[Job]:
        """Coordinates execution matrix loops across designated Role paths and Experience thresholds."""
        all_jobs: List[Job] = []

        for role, slug in self.roles.items():
            for exp in self.exp:
                self.logger.info(f"📂 Navigating execution context: [{role}] | Filter: [{exp}]")
                target_url = f"{slug}&exp={exp}"

                try:
                    await self.page.goto(target_url, wait_until="load", timeout=config.navigation_timeout_ms)
                    await self.page.wait_for_timeout(2000)

                    # Intercept empty UI results early
                    empty_state_text = self.page.get_by_text(self.SELECTORS["empty_state_text"])
                    if await empty_state_text.is_visible():
                        self.logger.warning(f"🚧 No target matches for [{role}] | [{exp}]. Skipping.")
                        continue

                    role_jobs = await self.scrape_current_role_pages(today)
                    all_jobs.extend(role_jobs)

                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=3000)
                    except Exception:
                        pass

                except Exception as ex:
                    self.logger.error(f"💥 Error requesting JobsGO index [{target_url}]: {str(ex)}")
                    continue

        return all_jobs

    async def scrape_current_role_pages(self, today: bool = False) -> List[Job]:
        """Orchestrates pagination state machines via JavaScript DOM execution handling."""
        current_page: int = 1
        role_jobs: List[Job] = []

        empty_state_img = self.page.locator(self.SELECTORS["empty_state_img"])
        if await empty_state_img.count() > 0:
            self.logger.warning("📂 JobsGO 'Not Found' image state detected. Terminating pagination.")
            return role_jobs

        while True:
            self.logger.info(f"Processing JobsGO extraction page: {current_page}")

            if today:
                role_jobs.extend(await self.crawl_today())
            else:
                role_jobs.extend(await self.crawl())

            next_button = self.page.locator(self.SELECTORS["next_page_btn"])

            if await next_button.count() > 0:
                current_page += 1
                await next_button.dispatch_event("click")

                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                    await self.page.wait_for_timeout(1000)
                except Exception:
                    pass
            else:
                self.logger.info(f"🏁 Termination boundary reached. Finalized at {current_page} pages.")
                break

        return role_jobs