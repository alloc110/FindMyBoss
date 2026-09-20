import abc
import re
from datetime import datetime
from typing import List, Optional, Set
from playwright.async_api import Page

from config import VN_TIMEZONE, config, get_logger
from models.Job import Job


class JobScraper(abc.ABC):
    """Abstract Base Class for all specialized job portal scrapers."""

    def __init__(self, page: Optional[Page] = None, url: Optional[str] = None, webhook_url: Optional[str] = None):
        self.page: Optional[Page] = page
        self.url: Optional[str] = url
        self.webhook_url: Optional[str] = webhook_url or config.discord_webhook_url
        self.scraped_links: Set[str] = set()
        self.logger = get_logger(self.__class__.__name__)

    @abc.abstractmethod
    async def crawl_all_pages(self, today: bool = False) -> List[Job]:
        """Main entry point to execute scraping across all designated roles and pagination."""
        pass

    @abc.abstractmethod
    async def parse_card_detail(self, card) -> Optional[Job]:
        """Extracts job details from a single card/element on the DOM."""
        pass

    async def crawl_job_detail(self, job: Job) -> Job:
        """
        Two-phase hook: navigates into the job detail page to enrich
        Job Description, Requirements, Tech Stack and Salary.
        Subclasses can override or utilize this base extractor.
        """
        if not self.page or not job.link or job.link == "N/A" or not job.link.startswith("http"):
            return job

        try:
            await self.page.goto(job.link, wait_until="load", timeout=config.navigation_timeout_ms)
            await self.page.wait_for_timeout(1500)

            body_text = await self.page.locator("body").inner_text()
            if body_text:
                # Safeguard against saving Cloudflare challenge / Turnstile error pages
                if any(cf_kw in body_text.lower() for cf_kw in [
                    "just a moment...", "attention required", "xác minh bạn là con người",
                    "verify you are human", "khắc phục sự cố lỗi cloudflare"
                ]):
                    self.logger.warning(f"🛡️ Phát hiện Cloudflare Challenge tại {job.link}. Bỏ qua cào chi tiết để tránh lưu dữ liệu rác.")
                    return job

                job.full_jd_raw = body_text.strip()

                # Extract description, requirements, benefits
                desc_match = re.search(
                    r"(?:Mô tả công việc|Job description|Job Description|Chi tiết công việc)[\s\n]+(.*?)(?=\n(?:Yêu cầu|Requirements|Qualifications|Quyền lợi|Benefits)|$)",
                    body_text,
                    re.DOTALL | re.IGNORECASE,
                )
                req_match = re.search(
                    r"(?:Yêu cầu ứng viên|Yêu cầu công việc|Yêu cầu|Requirements|Job requirements|Qualifications)[\s\n]+(.*?)(?=\n(?:Quyền lợi|Benefits|Why you|Về công ty|About company)|$)",
                    body_text,
                    re.DOTALL | re.IGNORECASE,
                )
                ben_match = re.search(
                    r"(?:Quyền lợi ứng viên|Quyền lợi|Benefits|Chế độ đãi ngộ)[\s\n]+(.*?)(?=\n(?:Địa điểm|Địa chỉ|Về công ty|Thông tin khác)|$)",
                    body_text,
                    re.DOTALL | re.IGNORECASE,
                )

                extracted_desc = desc_match.group(1).strip() if desc_match else (job.description or "")
                extracted_req = req_match.group(1).strip() if req_match else (job.requirements or "")
                extracted_ben = ben_match.group(1).strip() if ben_match else (job.benefits or "")

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

        except Exception as e:
            self.logger.warning(f"⚠️ Generic detail scraper failed for {job.link}: {str(e)}")

        return job

    def filter_unwanted_titles(
        self,
        jobs: List[Job],
        unwanted_keywords: Optional[tuple[str, ...] | List[str]] = None,
    ) -> List[Job]:
        """Filters out jobs containing blacklisted senior/lead titles."""
        blacklist = tuple(unwanted_keywords) if unwanted_keywords else config.unwanted_titles

        cleaned_jobs = [
            job
            for job in jobs
            if not any(keyword in job.title.lower() for keyword in blacklist)
        ]
        self.logger.info(
            f"📋 Filter summary: Retained {len(cleaned_jobs)}/{len(jobs)} valid jobs."
        )
        return cleaned_jobs

    @staticmethod
    def clean_bullet_points(raw_text: str, max_points: int = 4, max_chars: int = 450) -> str:
        """Cleans raw HTML/text into neat, readable bullet points."""
        if not raw_text:
            return ""

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        cleaned_bullets = []

        for line in lines:
            # Skip very short lines or navigation noise
            if len(line) < 10:
                continue
            # Remove leading bullet symbols, numbering (e.g. 1., 2), -, *, •)
            clean_line = re.sub(r"^[\-\•\*\+\–\—\d\.\)]+\s*", "", line).strip()
            if clean_line:
                cleaned_bullets.append(f"• {clean_line}")
            if len(cleaned_bullets) >= max_points:
                break

        result = "\n".join(cleaned_bullets)
        if len(result) > max_chars:
            result = result[: max_chars - 3] + "..."
        return result

    @staticmethod
    def now_iso() -> str:
        """Returns the current ISO-formatted timestamp in Vietnam timezone."""
        return datetime.now(VN_TIMEZONE).isoformat()

    def print_job_detail(self, job: Job, index: int = 1) -> None:
        """Prints a rich, formatted view of an enriched job to stdout."""
        print(f"\n🔹 [{index}] {job.title.upper()} - {job.company}")
        print(f"   🔗 Link:        {job.link}")
        print(f"   💰 Lương:       {job.salary or 'Thoả thuận'}")
        print(f"   ⏳ Kinh nghiệm: {job.exp or 'Chưa rõ'}")
        print(f"   📍 Địa điểm:    {job.address}")
        if job.skills:
            print(f"   🛠️ Tech Stack:  {', '.join(job.skills)}")
        if job.requirements:
            print(f"   📋 Yêu cầu ứng viên:")
            for req_line in job.requirements.splitlines():
                print(f"      {req_line}")
        if job.benefits:
            print(f"   🎁 Quyền lợi:")
            for ben_line in job.benefits.splitlines():
                print(f"      {ben_line}")
        print(f"   📅 Đăng:        {job.posted_date or 'N/A'}")
        print("-" * 70)

    def print_jobs(self, jobs: List[Job]) -> None:
        """Prints a human-readable summary of scraped jobs to stdout."""
        for i, job in enumerate(jobs, 1):
            self.print_job_detail(job, i)