import re
from typing import Dict, List, Optional
from playwright.async_api import Locator, Page

from config import config
from crawl.base_crawl import JobScraper
from models.Job import Job


class TopCVJob(JobScraper):
    """Scraper implementation for TopCV platform with Two-Phase Deep Scraping support."""

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
        "next_page_btn": 'a[rel="next"]',
    }

    EXP_MAPPING = {
        "1": "Không yêu cầu",
        "2": "Dưới 1 năm",
        "3": "1 năm",
    }

    def __init__(self, page: Page, webhook_url: Optional[str] = None):
        super().__init__(page=page, webhook_url=webhook_url)
        self.url: str = "https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257?category_family=r257"
        self.roles: Dict[str, str] = {
            "Data Engineer": "https://www.topcv.vn/tim-viec-lam-data-engineer",
        }

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job]:
        """Unified internal pipeline executing extraction, deduplication, and time-frame filtering."""
        valid_jobs: List[Job] = []
        try:
            empty_block = self.page.locator(self.SELECTORS["empty_block"])
            if await empty_block.is_visible():
                self.logger.info("🔍 TopCV empty state matched: No suitable jobs on this viewport.")
                return valid_jobs

            container = self.page.locator(self.SELECTORS["job_list_container"]).first
            cards = await container.locator(self.SELECTORS["job_card"]).all()
            self.logger.info(f"🔍 Found {len(cards)} raw job cards on TopCV.")

            for card in cards:
                job = await self.parse_card_detail(card)
                if not job or job.link == "N/A" or job.link in self.scraped_links:
                    continue

                if enforce_today:
                    date_lower = (job.posted_date or "").lower()
                    if not any(k in date_lower for k in ["hôm nay", "vừa đăng", "giờ", "phút"]):
                        continue

                self.scraped_links.add(job.link)
                valid_jobs.append(job)

        except Exception as e:
            self.logger.error(f"❌ Error executing TopCV page extraction: {str(e)}")

        return valid_jobs

    async def crawl(self) -> List[Job]:
        """Scrapes all accessible historical records present on the target listing workspace."""
        return await self._execute_extraction_pipeline(enforce_today=False)

    async def crawl_today(self) -> List[Job]:
        """Scrapes records published exclusively within the current business date run context."""
        return await self._execute_extraction_pipeline(enforce_today=True)

    async def parse_card_detail(self, card: Locator) -> Optional[Job]:
        """Transforms UI element boundaries into standardized Job model."""
        timeout = config.element_timeout_ms

        try:
            title = await card.locator(self.SELECTORS["job_title"]).inner_text(timeout=timeout)
            company = await card.locator(self.SELECTORS["company_name"]).inner_text(timeout=timeout)
            link = await card.locator(self.SELECTORS["job_link"]).get_attribute("href", timeout=timeout) or "N/A"

            label_locator = card.locator(self.SELECTORS["label_update"])
            posted_date = (
                await label_locator.inner_text(timeout=timeout)
                if await label_locator.count() > 0
                else "Unknown"
            )
            posted_date = posted_date.replace("Đăng", "").strip()

            salary_loc = card.locator(self.SELECTORS["salary_label"])
            salary = "Unknown"
            if await salary_loc.count() > 0:
                salary_raw = await salary_loc.inner_text(timeout=timeout)
                salary = salary_raw.replace("\n", " ").strip() if salary_raw else "Unknown"

            logo_element = card.locator(self.SELECTORS["company_logo"])
            image = "N/A"
            if await logo_element.count() > 0:
                image = (
                    await logo_element.get_attribute("data-src", timeout=timeout)
                    or await logo_element.get_attribute("src", timeout=timeout)
                    or "N/A"
                )

            return Job(
                title=title.strip(),
                company=company.strip(),
                link=link,
                address="Hồ Chí Minh",
                exp=None,
                salary=salary,
                posted_date=posted_date,
                image=image if image != "N/A" else None,
                time=self.now_iso(),
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Structural anomaly on TopCV card: {str(e)}")
            return None

    async def crawl_job_detail(self, job: Job) -> Job:
        """Navigates to TopCV job detail page to extract 100% full raw JD, requirements, and benefits."""
        if not job.link or job.link == "N/A":
            return job

        try:
            await self.page.goto(job.link, wait_until="load", timeout=config.navigation_timeout_ms)
            await self.page.wait_for_timeout(1500)

            body_text = await self.page.locator("body").inner_text()
            job.full_jd_raw = body_text.strip()

            # 1. Full Description (Mô tả công việc)
            desc_pattern = r"(?:Mô tả công việc)[\s\n]+(.*?)(?=\n(?:Yêu cầu ứng viên|Yêu cầu|Quyền lợi)|$)"
            desc_match = re.search(desc_pattern, body_text, re.DOTALL | re.IGNORECASE)
            if desc_match:
                job.description = desc_match.group(1).strip()

            # 2. Full Requirements (Yêu cầu ứng viên)
            req_pattern = r"(?:Yêu cầu ứng viên|Yêu cầu công việc)[\s\n]+(.*?)(?=\n(?:Quyền lợi ứng viên|Quyền lợi|Địa điểm và thời gian|Địa điểm làm việc)|$)"
            req_match = re.search(req_pattern, body_text, re.DOTALL | re.IGNORECASE)
            if req_match:
                job.requirements = req_match.group(1).strip()

            # 3. Full Benefits (Quyền lợi)
            ben_pattern = r"(?:Quyền lợi ứng viên|Quyền lợi)[\s\n]+(.*?)(?=\n(?:Địa điểm và thời gian|Địa điểm làm việc|Cách thức ứng tuyển|Việc làm liên quan)|$)"
            ben_match = re.search(ben_pattern, body_text, re.DOTALL | re.IGNORECASE)
            if ben_match:
                job.benefits = ben_match.group(1).strip()

        except Exception as e:
            self.logger.warning(f"⚠️ Failed to deep scrape TopCV job {job.link}: {str(e)}")

        return job

    async def crawl_all_pages(self, today: bool = False) -> List[Job]:
        """Executes full search matrix over configured parameters."""
        all_jobs: List[Job] = []

        for role, slug in self.roles.items():
            for exp_key, name_exp in self.EXP_MAPPING.items():
                self.logger.info(f"📂 TopCV shifting context: [{role}] | Level: [{name_exp}]")

                target_url = (
                    f"{slug}-tai-ho-chi-minh-kl2cr257?exp=1&type_keyword={exp_key}"
                    f"&sba=1&category_family=r257&locations=l2&saturday_status=0"
                )

                try:
                    await self.page.goto(target_url, wait_until="load", timeout=config.navigation_timeout_ms)
                    await self.page.wait_for_timeout(4000)

                    role_jobs = await self.scrape_current_role_pages(today)

                    # Annotate experience cleanly
                    for job in role_jobs:
                        job.exp = name_exp

                    all_jobs.extend(role_jobs)

                    try:
                        await self.page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                except Exception as ex:
                    self.logger.error(f"💥 Critical routing failure requesting TopCV [{target_url}]: {str(ex)}")
                    continue

        return all_jobs

    async def scrape_current_role_pages(self, today: bool = False) -> List[Job]:
        """Manages step-by-step UI pagination loops via client-side JavaScript execution."""
        current_page: int = 1
        role_jobs: List[Job] = []

        while True:
            self.logger.info(f"Processing TopCV batch at Page: {current_page}")

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
                self.logger.info(f"🏁 TopCV pagination terminal reached at {current_page} pages.")
                break

        return role_jobs