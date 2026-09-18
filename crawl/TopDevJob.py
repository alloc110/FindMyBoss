import re
from typing import List, Optional
from playwright.async_api import Locator, Page

from config import config
from crawl.base_crawl import JobScraper
from models.Job import Job


class TopDevJob(JobScraper):
    """Scraper implementation for TopDev platform with Two-Phase Deep Scraping support."""

    SELECTORS = {
        "job_list_container": "div.flex-col.gap-2",
        "job_card": ".text-card-foreground",
        "title_anchor": 'a[href*="/detail-jobs/"], a.text-brand-600, a.text-brand-500',
        "company_name": "span.text-text-500",
        "grid_details": "div.grid span.line-clamp-1",
        "date_span": "div.border-t span.text-text-500, div.border-t span",
        "card_image": "img[alt='job-image']",
        "it_category_span": "ul li span",
        "role_button_wrapper": 'div[style*="width:600px"] button',
    }

    def __init__(self, page: Page, webhook_url: Optional[str] = None):
        super().__init__(page=page, webhook_url=webhook_url)
        self.url: str = "https://topdev.vn/jobs/search"
        self.roles: List[str] = [
            "Software Developer",
            "Data Engineer / Scientist / Analyst",
            "Machine Learning / AI Engineer",
            "DevOps Engineer",
        ]

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job]:
        """Unified core pipeline handling card extraction, location validation, and deduplication."""
        valid_jobs: List[Job] = []
        try:
            container = self.page.locator(self.SELECTORS["job_list_container"]).first
            cards = await container.locator(self.SELECTORS["job_card"]).all()
            self.logger.info(f"Found {len(cards)} raw job cards on TopDev.")

            for card in cards:
                job_data = await self.parse_card_detail(card)
                if not job_data:
                    continue

                if "Hồ Chí Minh" in job_data.address:
                    if enforce_today:
                        date_lower = (job_data.posted_date or "").lower()
                        if not any(k in date_lower for k in ["hours", "hour", "minute", "giờ", "phút"]):
                            continue

                    if job_data.link not in self.scraped_links:
                        valid_jobs.append(job_data)
                        self.scraped_links.add(job_data.link)
        except Exception as e:
            self.logger.error(f"❌ Error during TopDev card extraction: {str(e)}")

        return valid_jobs

    async def crawl(self) -> List[Job]:
        """Scrapes all historical listings present on the current search viewport index."""
        return await self._execute_extraction_pipeline(enforce_today=False)

    async def crawl_today(self) -> List[Job]:
        """Scrapes listings published exclusively within the current business date sequence."""
        return await self._execute_extraction_pipeline(enforce_today=True)

    async def parse_card_detail(self, card: Locator) -> Optional[Job]:
        """Transforms UI DOM elements into explicit Job schema model."""
        timeout = config.element_timeout_ms

        try:
            anchor = card.locator(self.SELECTORS["title_anchor"]).first
            title = await anchor.inner_text(timeout=timeout)
            cleaned_title = title.rsplit(" (", 1)[0] if " (" in title else title

            company = await card.locator(self.SELECTORS["company_name"]).first.inner_text(timeout=timeout)
            raw_href = await anchor.get_attribute("href", timeout=timeout) or ""
            link = f"https://topdev.vn{raw_href}" if raw_href.startswith("/") else raw_href

            details = await card.locator(self.SELECTORS["grid_details"]).all_inner_texts()
            address = details[0].strip() if len(details) > 0 else "N/A"

            exp_data = details[1].split(",") if len(details) > 1 else ["N/A"]
            level = exp_data[0].strip() if len(exp_data) > 0 else "N/A"

            date_locator = card.locator(self.SELECTORS["date_span"]).first
            posted_date = (
                await date_locator.inner_text(timeout=timeout)
                if await date_locator.count() > 0
                else "N/A"
            )

            image = await card.locator(self.SELECTORS["card_image"]).get_attribute("src", timeout=timeout) or ""

            # Extract card skill tags if present on the listing view
            card_skill_anchors = await card.locator('a[href*="/jobs/search?keyword="]').all_inner_texts()
            skills = [s.strip() for s in card_skill_anchors if s.strip()]

            return Job(
                title=cleaned_title.strip(),
                company=company.strip(),
                link=link,
                address=address,
                exp=level,
                salary="Deal",
                posted_date=posted_date.strip(),
                image=image if image else None,
                time=self.now_iso(),
                skills=skills,
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Structural anomaly detected on TopDev card: {str(e)}")
            return None

    async def crawl_job_detail(self, job: Job) -> Job:
        """Navigates to TopDev job detail page to extract 100% full raw JD, salary, skills, requirements, and benefits."""
        if not job.link or job.link == "N/A":
            return job

        try:
            await self.page.goto(job.link, wait_until="load", timeout=config.navigation_timeout_ms)
            await self.page.wait_for_timeout(1500)

            body_text = await self.page.locator("body").inner_text()
            # Save 100% of raw page text for downstream AI/LLM CV matching
            job.full_jd_raw = body_text.strip()

            # 1. Real Salary
            salary_match = re.search(r"•\s*Salary:\s*(.*?)(?:\n|•|$)", body_text, re.IGNORECASE)
            if salary_match:
                extracted_sal = salary_match.group(1).strip()
                if "login" not in extracted_sal.lower():
                    job.salary = extracted_sal

            # 2. Detailed address
            loc_match = re.search(r"•\s*Location:\s*(.*?)(?:\n|•|$)", body_text, re.IGNORECASE)
            if loc_match:
                job.address = loc_match.group(1).strip()

            # 3. Skills / Tech Stack
            skill_anchors = await self.page.locator('a[href*="/jobs/search?keyword="]').all_inner_texts()
            detail_skills = [s.strip() for s in skill_anchors if s.strip() and len(s.strip()) < 30]
            if detail_skills:
                job.skills = list(dict.fromkeys(job.skills + detail_skills))

            # 4. Full Job Description (Roles & Responsibilities)
            desc_pattern = r"(?:Your role & responsibilities|Role & responsibilities|Job description|Mô tả công việc)[\s\n]+(.*?)(?=\n(?:Your skills & qualifications|Job requirements|Requirements|Yêu cầu)|$)"
            desc_match = re.search(desc_pattern, body_text, re.DOTALL | re.IGNORECASE)
            if desc_match:
                job.description = desc_match.group(1).strip()

            # 5. Full Requirements
            req_pattern = r"(?:Your skills & qualifications|Job requirements|Requirements|Yêu cầu ứng viên|Yêu cầu)[\s\n]+(.*?)(?=\n(?:Benefits|Quyền lợi|Why you|Company|Về công ty)|$)"
            req_match = re.search(req_pattern, body_text, re.DOTALL | re.IGNORECASE)
            if req_match:
                job.requirements = req_match.group(1).strip()

            # 6. Full Benefits
            ben_pattern = r"(?:Benefits|Quyền lợi ứng viên|Quyền lợi|Why you\'ll love working here)[\s\n]+(.*?)(?=\n(?:Company|About us|Về công ty|Việc làm liên quan)|$)"
            ben_match = re.search(ben_pattern, body_text, re.DOTALL | re.IGNORECASE)
            if ben_match:
                job.benefits = ben_match.group(1).strip()

        except Exception as e:
            self.logger.warning(f"⚠️ Failed to deep scrape TopDev job {job.link}: {str(e)}")

        return job

    async def crawl_all_pages(self, today: bool = False) -> List[Job]:
        """Initializes complex functional search filters and supervises pagination."""
        current_page: int = 1
        all_jobs: List[Job] = []

        try:
            self.logger.info(f"🚀 Navigating TopDev to target index: {self.url}")
            await self.page.goto(self.url, wait_until="load", timeout=config.navigation_timeout_ms)

            # Trigger dropdown
            await self.page.get_by_role("button", name="All Categories").click()
            await self.page.wait_for_timeout(1000)

            it_span = self.page.locator(self.SELECTORS["it_category_span"]).filter(has_text="IT").first
            self.logger.info("🎯 Selecting IT domain on TopDev...")
            await it_span.dispatch_event("click")

            for role in self.roles:
                role_button = self.page.locator(self.SELECTORS["role_button_wrapper"]).filter(has_text=role)
                if await role_button.count() > 0:
                    await role_button.dispatch_event("click")

            await self.page.get_by_role("button", name="Apply", exact=True).click()
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(2000)

        except Exception as e:
            self.logger.error(f"💥 Critical layout configuration failure on TopDev: {str(e)}")
            return all_jobs

        while True:
            self.logger.info(f"Processing TopDev extraction on page: {current_page}")

            if today:
                all_jobs.extend(await self.crawl_today())
            else:
                all_jobs.extend(await self.crawl())

            next_button = self.page.get_by_label("Go to next page")

            if await next_button.count() > 0 and await next_button.is_visible():
                class_attr = await next_button.get_attribute("class") or ""

                if "pointer-events-none opacity-0" in class_attr or "disabled" in class_attr:
                    self.logger.info("🚫 TopDev next page button marked disabled.")
                    break

                await next_button.dispatch_event("click")
                current_page += 1

                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                    await self.page.wait_for_timeout(3000)
                except Exception:
                    pass
            else:
                self.logger.info("🏁 No matching pagination elements remaining on TopDev. Loop closed.")
                break

        return all_jobs


# Backward compatibility alias
TopDevJobScraper = TopDevJob