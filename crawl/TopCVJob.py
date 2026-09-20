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
        """Navigates to TopCV job detail page to cleanly extract description, requirements, benefits, and skills without clutter."""
        if not job.link or job.link == "N/A":
            return job

        try:
            await self.page.goto(job.link, wait_until="load", timeout=config.navigation_timeout_ms)
            await self.page.wait_for_timeout(1500)

            # Auto dismiss cookie banners if present
            try:
                cookie_btn = self.page.locator('button:has-text("Chấp nhận"), button:has-text("Accept"), .btn-accept-cookie')
                if await cookie_btn.count() > 0:
                    await cookie_btn.first.click(timeout=1000)
            except Exception:
                pass

            # Target only job detail boxes, ignoring footer, cookie dialogs, similar jobs and platform links
            items = await self.page.locator(
                '.job-detail__body .box-job-information-detail-item, '
                '.job-detail__information-detail .job-description__item, '
                '.job-description__item'
            ).all()

            for it in items:
                header_elem = it.locator('.box-job-information-detail-item__title, h2, h3, h4, strong').first
                if await header_elem.count() == 0:
                    continue
                h_text = (await header_elem.inner_text()).strip().lower()

                # Strictly ignore non-job sections (SEO, similar jobs, company general info, reporting)
                if any(ign in h_text for ign in [
                    'việc làm liên quan', 'việc làm cùng', 'thông tin chung', 
                    'similar', 'details\ngửi', 'cách thức ứng tuyển', 'báo cáo tin'
                ]):
                    continue

                txt = (await it.inner_text()).strip()
                lines = txt.splitlines()
                # Strip heading from content body
                content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else txt

                # Filter out any lingering cookie or SEO promo phrases
                filtered_lines = [
                    l for l in content.splitlines() 
                    if not any(bad in l.lower() for bad in ['trải nghiệm của bạn', 'cookie', 'nhân viên bán hàng là một nghề', 'bản mô tả công việc nhân viên bán hàng'])
                ]
                clean_content = '\n'.join(filtered_lines).strip()

                if any(kw in h_text for kw in ['mô tả công việc', 'job description', 'nhiệm vụ']):
                    if clean_content:
                        job.description = clean_content
                elif any(kw in h_text for kw in ['yêu cầu', 'requirements', 'kỹ năng']):
                    if clean_content:
                        job.requirements = clean_content
                        # Extract skill tags if available
                        skill_match = re.search(r'Kỹ năng cần có[\s\n]+(.*?)(?=\n(?:Kỹ năng nên có|Kiến thức ngành|$))', clean_content, re.DOTALL | re.IGNORECASE)
                        if skill_match:
                            raw_s = skill_match.group(1).replace('\n', ',')
                            extracted_skills = [s.strip() for s in raw_s.split(',') if s.strip() and len(s.strip()) < 30]
                            if extracted_skills:
                                job.skills = list(dict.fromkeys(job.skills + extracted_skills))
                elif any(kw in h_text for kw in ['quyền lợi', 'benefits', 'đãi ngộ']):
                    if clean_content:
                        job.benefits = clean_content
                elif any(kw in h_text for kw in ['địa điểm', 'location', 'address']):
                    loc_match = re.search(r'(?:Hồ Chí Minh|Hà Nội|Đà Nẵng|Bình Dương)[^\n]*', clean_content)
                    if loc_match:
                        job.address = loc_match.group(0).strip()

            # If description or requirements are still empty, fall back to parsing strictly within .job-detail__body
            if not job.description or not job.requirements:
                body_elem = self.page.locator('.job-detail__body')
                if await body_elem.count() > 0:
                    body_text = await body_elem.inner_text()
                    if not job.description:
                        m = re.search(r'(?:Mô tả công việc|Job description)[\s\n]+(.*?)(?=\n(?:Yêu cầu ứng viên|Yêu cầu|Candidate Requirements|Quyền lợi)|$)', body_text, re.DOTALL | re.IGNORECASE)
                        if m:
                            job.description = m.group(1).strip()
                    if not job.requirements:
                        m = re.search(r'(?:Yêu cầu ứng viên|Candidate Requirements|Yêu cầu công việc)[\s\n]+(.*?)(?=\n(?:Quyền lợi ứng viên|Quyền lợi|Benefits|Địa điểm và thời gian|Địa điểm làm việc)|$)', body_text, re.DOTALL | re.IGNORECASE)
                        if m:
                            job.requirements = m.group(1).strip()
                    if not job.benefits:
                        m = re.search(r'(?:Quyền lợi ứng viên|Quyền lợi|Benefits)[\s\n]+(.*?)(?=\n(?:Địa điểm và thời gian|Địa điểm làm việc|Cách thức ứng tuyển|Việc làm liên quan)|$)', body_text, re.DOTALL | re.IGNORECASE)
                        if m:
                            job.benefits = m.group(1).strip()

            # Construct clean, pure JD without any platform fluff
            clean_sections = []
            if job.description:
                clean_sections.append(f"MÔ TẢ CÔNG VIỆC:\n{job.description}")
            if job.requirements:
                clean_sections.append(f"### YÊU CẦU ỨNG VIÊN:\n{job.requirements}")
            if job.benefits:
                clean_sections.append(f"### QUYỀN LỢI ĐƯỢC HƯỞNG:\n{job.benefits}")

            if clean_sections:
                job.description = "\n\n".join(clean_sections)
                job.full_jd_raw = f"""VỊ TRÍ: {job.title}
CÔNG TY: {job.company}
MỨC LƯƠNG: {job.salary}
ĐỊA ĐIỂM: {job.address}
KỸ NĂNG: {', '.join(job.skills) if job.skills else 'Xem chi tiết'}

""" + "\n\n".join(clean_sections)

        except Exception as e:
            self.logger.warning(f"⚠️ Failed to deep scrape TopCV job {job.link}: {str(e)}")

        return job

    async def crawl_all_pages(self, today: bool = False) -> List[Job]:
        """Executes full search matrix over TopCV IT listings."""
        all_jobs: List[Job] = []

        try:
            self.logger.info(f"📂 Navigating TopCV to target index: {self.url}")
            await self.page.goto(self.url, wait_until="load", timeout=config.navigation_timeout_ms)
            await self.page.wait_for_timeout(3000)

            all_jobs = await self.scrape_current_role_pages(today)
        except Exception as ex:
            self.logger.error(f"💥 Critical routing failure requesting TopCV [{self.url}]: {str(ex)}")

        return all_jobs

    async def scrape_current_role_pages(self, today: bool = False) -> List[Job]:
        """Manages step-by-step UI pagination loops via client-side JavaScript execution."""
        current_page: int = 1
        role_jobs: List[Job] = []
        max_pages = 2

        while current_page <= max_pages:
            self.logger.info(f"Processing TopCV batch at Page: {current_page}/{max_pages}")

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
                    await self.page.wait_for_timeout(2000)
                except Exception:
                    pass
            else:
                self.logger.info(f"🏁 TopCV pagination terminal reached at {current_page} pages.")
                break

        return role_jobs