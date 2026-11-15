import re
from typing import Dict, List, Optional
from playwright.async_api import Locator, Page

from core.config import config
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

                if enforce_today:
                    date_lower = (job_data.posted_date or "").lower()
                    if not any(k in date_lower for k in ["hours", "hour", "minute", "giờ", "phút", "today", "hôm nay", "vừa"]):
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
            # 1. Strictly require detail-jobs anchor to filter out non-job company banners/carousels
            anchor_loc = card.locator('a[href*="/detail-jobs/"]')
            if await anchor_loc.count() == 0:
                return None

            anchor = anchor_loc.first
            title = await anchor.inner_text(timeout=timeout)
            cleaned_title = title.rsplit(" (", 1)[0] if " (" in title else title
            cleaned_title = cleaned_title.strip()

            raw_href = await anchor.get_attribute("href", timeout=timeout) or ""
            link = f"https://topdev.vn{raw_href}" if raw_href.startswith("/") else raw_href

            # 2. Extract company name from card (adjacent to title or in company span)
            company = ""
            company_loc = card.locator('a[href*="/detail-jobs/"] + span, a[href*="/detail-jobs/"] ~ span, span.line-clamp-1')
            if await company_loc.count() > 0:
                cand = (await company_loc.first.inner_text(timeout=timeout)).strip()
                if cand and cand != cleaned_title and cand.lower() not in ["topdev", "saramin", "hot jobs"]:
                    company = cand

            # Fallback 1: Extract from company link in card if available
            if not company or company == cleaned_title:
                comp_anchor = card.locator('a[href*="/companies/"]:not([href*="/group/"])')
                if await comp_anchor.count() > 0:
                    cand = (await comp_anchor.first.inner_text(timeout=timeout)).strip()
                    if cand and cand != cleaned_title:
                        company = cand

            # Fallback 2: Extract from TopDev URL slug: /detail-jobs/...-{company-slug}-{id}
            if not company or company == cleaned_title or company.lower() in ["topdev", "saramin", "hot jobs"]:
                slug_match = re.search(r"-([a-z0-9-]+)-(\d+)(?:\?|$)", link)
                if slug_match:
                    slug_name = slug_match.group(1).replace("-", " ").strip().title()
                    if slug_name.lower() not in ["topdev", "saramin", "hot jobs"] and len(slug_name) > 2:
                        company = slug_name

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

            image = ""
            try:
                img_loc = card.locator(self.SELECTORS["card_image"]).first
                if await img_loc.count() > 0:
                    image = await img_loc.get_attribute("src", timeout=timeout) or ""
                if not image or image.lower().endswith(".svg"):
                    first_img = card.locator("img").first
                    if await first_img.count() > 0:
                        image = await first_img.get_attribute("src", timeout=timeout) or ""
            except Exception:
                pass

            # Extract card skill tags if present on the listing view
            card_skill_anchors = await card.locator('a[href*="/jobs/search?keyword="]').all_inner_texts()
            skills = [s.strip() for s in card_skill_anchors if s.strip()]

            return Job(
                title=cleaned_title,
                company=company or "Doanh nghiệp tuyển dụng",
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

            # 0. Refine Job Title and Company from Detail Page Title & DOM
            try:
                page_title = await self.page.title()
                if page_title:
                    m = re.match(
                        r"^(?:Recruiting|Tuyển dụng)\s+(.*?)\s+(?:at|tại)\s+(.*?)(?:\s*\|\s*(?:Saramin|TopDev|Việc làm).*|$)",
                        page_title.strip(),
                        re.IGNORECASE,
                    )
                    if m:
                        cand_title = m.group(1).strip()
                        cand_comp = m.group(2).strip()
                        if cand_title:
                            job.title = cand_title
                        if cand_comp and (not job.company or job.company == job.title or job.company.lower() in ["topdev", "saramin", "hot jobs", "doanh nghiệp tuyển dụng"]):
                            job.company = cand_comp

                # Also verify employer anchor on detail page
                comp_anchor = self.page.locator('a[href*="/companies/"]:not([href*="/group/"])')
                if await comp_anchor.count() > 0:
                    c_text = (await comp_anchor.first.inner_text()).strip()
                    if "Industry" in c_text:
                        c_text = c_text.split("Industry")[0].strip()
                    if "View company" not in c_text and 2 < len(c_text) < 100:
                        job.company = c_text
            except Exception as ref_err:
                self.logger.debug(f"Could not refine TopDev title/company: {ref_err}")

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
            extracted_desc = desc_match.group(1).strip() if desc_match else ""

            # 5. Full Requirements
            req_pattern = r"(?:Your skills & qualifications|Job requirements|Requirements|Yêu cầu ứng viên|Yêu cầu)[\s\n]+(.*?)(?=\n(?:Benefits|Quyền lợi|Why you|Company|Về công ty)|$)"
            req_match = re.search(req_pattern, body_text, re.DOTALL | re.IGNORECASE)
            extracted_req = req_match.group(1).strip() if req_match else ""

            # 6. Full Benefits
            ben_pattern = r"(?:Benefits|Quyền lợi ứng viên|Quyền lợi|Why you\'ll love working here)[\s\n]+(.*?)(?=\n(?:Company|About us|Về công ty|Việc làm liên quan)|$)"
            ben_match = re.search(ben_pattern, body_text, re.DOTALL | re.IGNORECASE)
            extracted_ben = ben_match.group(1).strip() if ben_match else ""

            job.requirements = extracted_req or None
            job.benefits = extracted_ben or None

            # Gom toàn bộ nội dung cào được vào Mô tả công việc (job.description)
            full_parts = []
            if extracted_desc:
                full_parts.append(extracted_desc)
            if extracted_req:
                full_parts.append(f"### YÊU CẦU ỨNG VIÊN:\n{extracted_req}")
            if extracted_ben:
                full_parts.append(f"### QUYỀN LỢI ĐƯỢC HƯỞNG:\n{extracted_ben}")

            if full_parts:
                job.description = "\n\n".join(full_parts)
            elif not job.description:
                job.description = body_text.strip()

            # 7. Extract company logo from detail page if missing
            try:
                if not job.image or job.image.lower().endswith(".svg"):
                    logo_loc = self.page.locator("img[src*='company'], img[src*='logo'], img[alt*='logo'], .company-logo img").first
                    if await logo_loc.count() > 0:
                        detail_img_src = await logo_loc.get_attribute("src")
                        if detail_img_src and detail_img_src.startswith("http") and not detail_img_src.lower().endswith(".svg"):
                            job.image = detail_img_src
            except Exception:
                pass

        except Exception as e:
            self.logger.warning(f"⚠️ Failed to deep scrape TopDev job {job.link}: {str(e)}")

        return job

    ROLE_MAP: Dict[str, str] = {
        "backend": "Backend Developer",
        "frontend": "Frontend Developer",
        "fullstack": "Fullstack Developer",
        "da": "Data Analyst",
        "de": "Data Engineer",
        "ai_ml": "AI Machine Learning",
        "mobile": "Mobile Developer",
        "tester": "Tester QA QC",
        "devops": "DevOps",
    }

    async def crawl_all_pages(self, today: bool = False, roles: Optional[List[str]] = None, **kwargs) -> List[Job]:
        """Initializes complex functional search filters and supervises pagination for specified roles."""
        import urllib.parse
        all_jobs: List[Job] = []

        target_queries: List[tuple[str, str]] = []
        if roles and "all" not in [r.lower() for r in roles]:
            for r in roles:
                r_key = r.strip().lower()
                if r_key in self.ROLE_MAP:
                    q = self.ROLE_MAP[r_key]
                    target_queries.append((q, f"https://topdev.vn/jobs/search?keyword={urllib.parse.quote_plus(q)}"))

        if not target_queries:
            target_queries = [("Tech", self.url)]

        for role_name, target_url in target_queries:
            try:
                self.logger.info(f"🚀 Navigating TopDev to target [{role_name}]: {target_url}")
                await self.page.goto(target_url, wait_until="load", timeout=config.navigation_timeout_ms)
                await self.page.wait_for_timeout(2000)

                current_page = 1
                max_pages = 2
                while current_page <= max_pages:
                    self.logger.info(f"Processing TopDev extraction [{role_name}] on page: {current_page}/{max_pages}")

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
                            await self.page.wait_for_timeout(2000)
                        except Exception:
                            pass
                    else:
                        self.logger.info(f"🏁 Finalized TopDev [{role_name}] at page {current_page}.")
                        break

            except Exception as e:
                self.logger.error(f"💥 TopDev query failure [{target_url}]: {str(e)}")
                continue

        return all_jobs


# Backward compatibility alias
TopDevJobScraper = TopDevJob