import re
from typing import Dict, List, Optional
from playwright.async_api import Locator, Page

from config import config
from crawl.base_crawl import JobScraper
from models.Job import Job


class ITviecJob(JobScraper):
    """Scraper implementation for ITviec platform with Two-Phase Deep Scraping support."""

    SELECTORS = {
        "job_list_container": '[data-search--pagination-target="jobList"]',
        "job_card": ".job-card",
        "job_title": 'h3[data-search--job-selection-target="jobTitle"]',
        "company_name": ".ims-2 a",
        "location_div": "div[title]",
        "posted_date": ".small-text.text-dark-grey",
        "logo_source": "picture source",
        "next_page_btn": 'div.page.next a[rel="next"]',
    }

    def __init__(self, page: Page, webhook_url: Optional[str] = None):
        super().__init__(page=page, webhook_url=webhook_url)
        self.url: str = "https://itviec.com/jobs-expertise-index"

        self.find_level: List[str] = ["INTERN", "FRESHER", "JUNIOR"]
        self.un_find_level: List[str] = list(config.unwanted_titles)

        self.roles: Dict[str, str] = {
            "Data Analyst": "data-analyst",
            "Big Data Engineer": "big-data-engineer",
            "Data Engineer": "data-engineer",
            "DataOps / MLOps Engineer": "dataops-mlops-engineer",
            "Database Engineer": "database-engineer",
        }

    def _filter_and_classify(self, job: Job, enforce_today: bool = False) -> Optional[Job]:
        """Encapsulates location validation, temporal filtering, and experience classification."""
        # 1. Location Validation
        if "Hồ Chí Minh" not in job.address:
            return None

        # 2. Daily Filter
        if enforce_today:
            date_lower = (job.posted_date or "").lower()
            if not any(k in date_lower for k in ["hour", "minute", "giờ", "phút"]):
                return None

        job_title_upper = job.title.upper()

        # 3. Target Level Matching
        for level in self.find_level:
            if level in job_title_upper:
                job.exp = level
                return job

        # 4. Blacklisted Management/Senior Titles Exclusion
        for level in self.un_find_level:
            if level.upper() in job_title_upper:
                return None

        # 5. Default Fallback
        job.exp = "Entry / Junior"
        return job

    async def _execute_extraction_pipeline(self, enforce_today: bool = False) -> List[Job]:
        """Processes extraction across current canvas."""
        valid_jobs: List[Job] = []
        try:
            container = self.page.locator(self.SELECTORS["job_list_container"]).first
            cards = await container.locator(self.SELECTORS["job_card"]).all()
            self.logger.info(f"🔍 Found {len(cards)} raw job cards on current canvas.")

            for card in cards:
                job = await self.parse_card_detail(card)
                if not job or job.link == "N/A" or job.link in self.scraped_links:
                    continue

                self.scraped_links.add(job.link)
                processed_job = self._filter_and_classify(job, enforce_today=enforce_today)
                if processed_job:
                    valid_jobs.append(processed_job)

        except Exception as e:
            self.logger.error(f"❌ Error executing page extraction pipeline: {str(e)}")

        return valid_jobs

    async def crawl(self) -> List[Job]:
        """Scrapes matching listings available on the current index page."""
        return await self._execute_extraction_pipeline(enforce_today=False)

    async def crawl_today(self) -> List[Job]:
        """Scrapes only freshly posted listings updated within 24 hours."""
        return await self._execute_extraction_pipeline(enforce_today=True)

    async def parse_card_detail(self, card: Locator) -> Optional[Job]:
        """Extracts structured DOM boundaries safely into a unified Job schema mapping."""
        timeout = config.element_timeout_ms

        try:
            title_element = card.locator(self.SELECTORS["job_title"])
            title = await title_element.inner_text(timeout=timeout)

            company = await card.locator(self.SELECTORS["company_name"]).inner_text(timeout=timeout)
            data_url = await title_element.get_attribute("data-url", timeout=timeout) or "N/A"

            location_attr = await card.locator(self.SELECTORS["location_div"]).last.get_attribute("title", timeout=timeout) or ""
            location = "Hồ Chí Minh" if "Ho Chi Minh" in location_attr else location_attr

            posted_date_elem = card.locator(self.SELECTORS["posted_date"]).first
            posted_date = await posted_date_elem.inner_text(timeout=timeout) if await posted_date_elem.count() > 0 else "N/A"
            posted_date = posted_date.replace("Posted", "").strip()

            logo_url = await card.locator(self.SELECTORS["logo_source"]).get_attribute("data-srcset", timeout=timeout) or ""

            # Extract skill tags on card if available
            card_tags = await card.locator(".itag, .tag-list a").all_inner_texts()
            skills = [t.strip() for t in card_tags if t.strip()]

            return Job(
                title=title.strip(),
                company=company.strip(),
                link=data_url,
                address=location,
                exp=None,
                salary="Deal",
                posted_date=posted_date,
                image=logo_url,
                time=self.now_iso(),
                skills=skills,
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Structural token decay or element mismatch on card: {str(e)}")
            return None

    async def crawl_job_detail(self, job: Job) -> Job:
        """Navigates to ITviec job detail page to extract 100% full raw JD, skills, address, requirements, and benefits."""
        if not job.link or job.link == "N/A":
            return job

        try:
            await self.page.goto(job.link, wait_until="load", timeout=config.navigation_timeout_ms)
            await self.page.wait_for_timeout(1500)

            body_text = await self.page.locator("body").inner_text()
            # Save 100% full raw text for AI prompt & dataset
            job.full_jd_raw = body_text.strip()

            # 1. Extract skills from text section
            skills_match = re.search(r"Skills:[\s\n]+(.*?)(?=\nJob Expertise:|\nJob Domain:|$)", body_text, re.DOTALL)
            if skills_match:
                skill_lines = [s.strip() for s in skills_match.group(1).splitlines() if s.strip()]
                job.skills = list(dict.fromkeys(job.skills + skill_lines))

            # 2. Extract address
            addr_match = re.search(r"\n(\d+[^,\n]+,\s*[^,\n]+,\s*TP Hồ Chí Minh[^\n]*)", body_text)
            if addr_match:
                job.address = addr_match.group(1).strip()

            # 3. Full Job Description (About the team / Responsibilities)
            desc_pattern = r"(?:Job description|Mô tả công việc)[\s\n]+(.*?)(?=\n(?:Your skills and experience|Qualifications|Yêu cầu)|$)"
            desc_match = re.search(desc_pattern, body_text, re.DOTALL | re.IGNORECASE)
            if desc_match:
                job.description = desc_match.group(1).strip()

            # 4. Full Requirements
            req_pattern = r"(?:Your skills and experience|Qualifications|Yêu cầu công việc)[\s\n]+(.*?)(?=\n(?:Why you\'ll love working here|Top 3 reasons|Benefits|More jobs)|$)"
            req_match = re.search(req_pattern, body_text, re.DOTALL | re.IGNORECASE)
            if req_match:
                job.requirements = req_match.group(1).strip()

            # 5. Full Benefits
            ben_pattern = r"(?:Top 3 reasons to join us|Why you\'ll love working here|Benefits)[\s\n]+(.*?)(?=\n(?:Job description|Company overview|More jobs)|$)"
            ben_match = re.search(ben_pattern, body_text, re.DOTALL | re.IGNORECASE)
            if ben_match:
                job.benefits = ben_match.group(1).strip()

        except Exception as e:
            self.logger.warning(f"⚠️ Failed to deep scrape ITviec job {job.link}: {str(e)}")

        return job

    async def crawl_all_pages(self, today: bool = False) -> List[Job]:
        """Iterates through defined technical target domains and pages."""
        all_jobs: List[Job] = []

        for role, slug in self.roles.items():
            self.logger.info(f"📂 Navigating execution context to specialization: [{role}]")
            target_url = f"https://itviec.com/it-jobs/{slug}"

            try:
                await self.page.goto(target_url, wait_until="load", timeout=config.navigation_timeout_ms)
                await self.page.wait_for_timeout(2000)

                role_jobs = await self.scrape_current_role_pages(today)
                all_jobs.extend(role_jobs)
            except Exception as e:
                self.logger.error(f"💥 Failed to fetch target index context for [{target_url}]: {str(e)}")
                continue

        return all_jobs

    async def scrape_current_role_pages(self, today: bool = False) -> List[Job]:
        """Executes extraction across pagination blocks."""
        current_page: int = 1
        role_jobs: List[Job] = []

        while True:
            self.logger.info(f"Batch processing extraction matrix index at Page: {current_page}")

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
                self.logger.info(f"🏁 Termination boundary reached at ({current_page}) pages.")
                break

        return role_jobs