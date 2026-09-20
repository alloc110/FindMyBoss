from typing import Dict, List, Optional
from playwright.async_api import Locator, Page

from config import config
from crawl.base_crawl import JobScraper
from models.Job import Job


class VietnamWorksJob(JobScraper):
    """Scraper implementation for VietnamWorks platform."""

    SELECTORS = {
        "state_indicators": "a[href*='-jv'], .noResultWrapper",
        "no_result_wrapper": ".noResultWrapper",
        "job_card_anchor": "a[href*='-jv']",
    }

    def __init__(self, page: Page, webhook_url: Optional[str] = None):
        super().__init__(page=page, webhook_url=webhook_url)
        self.url: str = "https://www.vietnamworks.com/viec-lam?q=IT"
        self.roles: Dict[str, str] = {
            "IT": "IT",
        }
        self.unfind: tuple[str, ...] = config.unwanted_titles

    async def parse_card_detail(self, card: Locator) -> Optional[Job]:
        """Transforms a VietnamWorks job card element into a Job dataclass."""
        try:
            card_text = await card.inner_text()
            lines = [l.strip() for l in card_text.splitlines() if l.strip() and l.strip() != "Urgent"]
            if not lines:
                return None

            title = lines[0].replace("Mới", "").strip()
            company = lines[1] if len(lines) > 1 else "Unknown Company"
            salary = "Thỏa thuận"
            address = "Hồ Chí Minh"
            posted_date = "Available"

            for line in lines[2:]:
                if any(curr in line for curr in ["$", "₫", "Triệu", "triệu", "Thương lượng", "Thoả thuận"]):
                    salary = line
                elif any(city in line for city in ["Hồ Chí Minh", "Hà Nội", "Đà Nẵng", "Bình Dương", "Toàn quốc", "Remote"]):
                    address = line
                elif any(kw in line.lower() for kw in ["ngày", "giờ", "hôm nay", "cập nhật", "vừa"]):
                    posted_date = line.replace("Cập nhật", "").replace(":", "").strip()

            a = card.locator("a[href*='-jv']").first
            href = await a.get_attribute("href") if await a.count() > 0 else ""
            link = f"https://www.vietnamworks.com{href}" if href and href.startswith("/") else (href or "N/A")

            return Job(
                title=title,
                company=company,
                link=link,
                address=address,
                exp=None,
                salary=salary,
                posted_date=posted_date,
                image="https://images.vietnamworks.com/img/company-default-logo.svg",
                time=self.now_iso(),
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to parse VietnamWorks card: {e}")
            return None

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job]:
        """Unified internal tracking processor executing extraction, deduplication, and time-frame filtering."""
        valid_jobs: List[Job] = []
        try:
            await self.page.wait_for_selector(self.SELECTORS["state_indicators"], timeout=12000)
        except Exception:
            self.logger.warning("⚠️ Target VietnamWorks page failed to respond in time.")
            return valid_jobs

        try:
            anchors = await self.page.locator(self.SELECTORS["job_card_anchor"]).all()
            self.logger.info(f"🔍 Found {len(anchors)} potential job anchors on VietnamWorks.")

            seen_links = set()
            for a in anchors:
                href = await a.get_attribute("href") or ""
                if not href or href in seen_links:
                    continue
                seen_links.add(href)
                link = f"https://www.vietnamworks.com{href}" if href.startswith("/") else href

                if link in self.scraped_links:
                    continue

                card = a.locator("xpath=ancestor::div[contains(@class, 'sc-')][3]")
                if await card.count() == 0:
                    continue

                job = await self.parse_card_detail(card)
                if not job or job.link == "N/A":
                    continue

                job.link = link

                if enforce_today:
                    date_lower = (job.posted_date or "").lower()
                    if not any(k in date_lower for k in ["hôm nay", "giờ", "phút", "vừa", "today"]):
                        continue

                self.scraped_links.add(link)
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

    async def crawl_all_pages(self, today: bool = False) -> List[Job]:
        """Executes full search engine permutation matrices over VietnamWorks IT jobs."""
        all_jobs: List[Job] = []

        try:
            self.logger.info(f"📂 Navigating VietnamWorks to target index: {self.url}")
            await self.page.goto(self.url, wait_until="load", timeout=config.navigation_timeout_ms)
            await self.page.wait_for_timeout(3000)

            all_jobs = await self.scrape_current_role_pages(today)
        except Exception as ex:
            self.logger.error(f"💥 Critical routing failure on VietnamWorks [{self.url}]: {str(ex)}")

        return all_jobs

    async def scrape_current_role_pages(self, today: bool = False) -> List[Job]:
        """Manages step-by-step UI pagination loops via safe client-side JavaScript execution."""
        current_page: int = 1
        role_jobs: List[Job] = []
        max_pages = 2

        while current_page <= max_pages:
            self.logger.info(f"Processing VietnamWorks batch at Page: {current_page}/{max_pages}")
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
                    await self.page.wait_for_timeout(2000)
                except Exception:
                    pass
            else:
                self.logger.info(f"🏁 VietnamWorks pagination terminal reached at ({current_page}) pages.")
                break

        return role_jobs