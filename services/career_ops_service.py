import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from core.config import config, get_logger
from models.Job import Job
from services.latex_engine import LatexEngine
from services.notifier import DiscordNotifier
from services.profile_service import ProfileService
from services.storage import JobStorage

logger = get_logger("CareerOpsService")


class CareerOpsService:
    """
    Integrates career-ops (@santifer/career-ops) CLI capabilities with FindMyBoss:
    1. Extracts full JD content from any job URL via browser-extract.mjs / HTTP fallback.
    2. Syncs candidate profile and master CV into career-ops workspace.
    3. Runs AI ATS matching and tailoring.
    4. Compiles high-converting ATS PDF resumes.
    5. Dispatches Job details + tailored PDF directly to Discord webhook.
    """

    def __init__(
        self,
        workspace_dir: Optional[Path] = None,
        storage: Optional[JobStorage] = None,
        profile_service: Optional[ProfileService] = None,
        latex_engine: Optional[LatexEngine] = None,
        notifier: Optional[DiscordNotifier] = None,
        ai_service: Optional[Any] = None,
    ):
        self.workspace_dir = workspace_dir or Path("career_ops_workspace")
        self.storage = storage or JobStorage()
        self.profile_service = profile_service or ProfileService()
        self.latex_engine = latex_engine or LatexEngine()
        self.notifier = notifier or DiscordNotifier()

        if ai_service is not None:
            self.ai_service = ai_service
        else:
            from services.ai.service import MultiProviderAIService
            self.ai_service = MultiProviderAIService()

        self._ensure_workspace_synced()

    def _ensure_workspace_synced(self) -> None:
        """Syncs FindMyBoss profile into career_ops_workspace cv.md and config."""
        try:
            if not self.workspace_dir.exists():
                logger.warning(f"Career-Ops workspace not found at {self.workspace_dir}. Running in internal mode.")
                return

            profile = self.profile_service.load_profile()
            cv_md_path = self.workspace_dir / "cv.md"
            master_text = profile.get("master_cv_text") or ""

            # Build rich, structured Markdown CV for career-ops
            md_lines = [
                f"# {profile.get('name', 'Candidate')}",
                f"## {profile.get('title', 'Software Engineer')}",
                f"- Email: {profile.get('email', '')}",
                f"- Phone: {profile.get('phone', '')}",
                f"- Location: {profile.get('location', '')}",
            ]
            if profile.get("github"):
                md_lines.append(f"- GitHub: {profile.get('github')}")
            if profile.get("linkedin"):
                md_lines.append(f"- LinkedIn: {profile.get('linkedin')}")

            md_lines.extend(["", "### Professional Summary", profile.get("summary", ""), ""])

            skills = profile.get("skills", {})
            if skills:
                md_lines.append("### Technical Skills")
                if isinstance(skills, dict):
                    for cat, s_list in skills.items():
                        if isinstance(s_list, list):
                            md_lines.append(f"- **{cat}**: {', '.join(s_list)}")
                elif isinstance(skills, list):
                    md_lines.append(f"- {', '.join(skills)}")
                md_lines.append("")

            experiences = profile.get("experiences", [])
            if experiences:
                md_lines.append("### Experience")
                for exp in experiences:
                    md_lines.append(f"#### {exp.get('role', 'Role')} | {exp.get('company', 'Company')} ({exp.get('date', '')})")
                    if exp.get("location"):
                        md_lines.append(f"*{exp.get('location')}*")
                    for b in exp.get("bullets", []):
                        md_lines.append(f"- {b}")
                    md_lines.append("")

            projects = profile.get("projects", [])
            if projects:
                md_lines.append("### Projects")
                for proj in projects:
                    md_lines.append(f"#### {proj.get('name', 'Project')} ({proj.get('technologies', '')})")
                    for b in proj.get("bullets", []):
                        md_lines.append(f"- {b}")
                    md_lines.append("")

            education = profile.get("education", [])
            if education:
                md_lines.append("### Education")
                for edu in education:
                    md_lines.append(f"- **{edu.get('school', '')}**: {edu.get('degree', '')} ({edu.get('date', '')})")
                md_lines.append("")

            if master_text:
                md_lines.extend([
                    "### Master CV Portfolio (Raw Extracted Text)",
                    "```text",
                    master_text,
                    "```",
                    ""
                ])

            cv_content = "\n".join(md_lines)
            cv_md_path.write_text(cv_content, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not sync profile to career-ops workspace: {e}")

    async def extract_jd_from_url(self, url: str) -> Dict[str, Any]:
        """
        Extracts JD title, company, and raw text from any job listing URL.
        First tries career-ops headless browser-extract.mjs, falling back to HTTP scrape.
        """
        url = url.strip()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        logger.info(f"🌐 Extracting JD from URL: {url} (domain: {domain})")

        # 0. Check if job already exists in storage with rich data
        existing = self.storage.get_job_by_link(url) if self.storage else None
        known_title = existing.get("title") if existing and not (existing.get("title") or "").startswith("Vị trí tuyển dụng") else None
        known_company = existing.get("company") if existing and existing.get("company") != domain else None
        known_desc = (existing.get("description") or existing.get("full_jd_raw")) if existing else None

        if known_desc and len(known_desc) > 150 and known_title:
            logger.info(f"✨ Found existing rich JD in storage for {url}: {known_title} ({known_company})")
            return self._build_job_dict(
                title=known_title,
                company=known_company or self._infer_company(known_title, known_desc, domain),
                link=url,
                raw_text=known_desc,
            )

        # 1. Attempt extraction via career-ops browser-extract.mjs
        extract_script = self.workspace_dir / "browser-extract.mjs"
        if extract_script.exists():
            try:
                cmd = ["node", str(extract_script.name), url, "--mode", "jd", "--timeout", "15000"]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.workspace_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode == 0 and stdout:
                    raw_out = stdout.decode("utf-8", errors="replace").strip()
                    data = json.loads(raw_out)
                    title = data.get("title") or "Tuyển Dụng Kỹ Sư / Chuyên Viên"
                    text = data.get("text") or ""
                    company = ""

                    # TopDev specific title and company extraction
                    if "topdev.vn" in domain or "topdev.vn" in url:
                        m_topdev = re.match(
                            r"^(?:Recruiting|Tuyển dụng)\s+(.*?)\s+(?:at|tại)\s+(.*?)(?:\s*\|\s*(?:Saramin|TopDev|Việc làm).*|$)",
                            title,
                            re.IGNORECASE,
                        )
                        if m_topdev:
                            clean_t = m_topdev.group(1).strip()
                            clean_c = m_topdev.group(2).strip()
                            if clean_t:
                                title = clean_t
                            if clean_c and clean_c.lower() not in ["topdev", "saramin", "hot jobs", "việc làm", "tuyển dụng"]:
                                company = clean_c
                        else:
                            title = re.sub(r"\s*\|\s*(?:Saramin|TopDev).*$", "", title).strip()
                            title = re.sub(r"^(?:Recruiting|Tuyển dụng)\s+", "", title, flags=re.I).strip()

                    if len(text) > 100:
                        if not company:
                            company = self._infer_company(title, text, domain, url=url)
                        return self._build_job_dict(title=title, company=company, link=url, raw_text=text)
            except Exception as e:
                logger.warning(f"browser-extract.mjs run exception for {url}: {e}")

        # 2. Resilient fallback via httpx + BeautifulSoup
        logger.info(f"Falling back to direct HTTP fetch for {url}...")
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")

                    # Extract page title
                    title = ""
                    title_elem = soup.find("h1") or soup.find("title")
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                    if not title:
                        title = "Cơ Hội Nghề Nghiệp Tuyển Dụng"

                    # TopDev specific title and company extraction from HTML <title> and DOM
                    company = ""
                    if "topdev.vn" in domain or "topdev.vn" in url:
                        raw_page_title = soup.title.string.strip() if soup.title else title
                        m_topdev = re.match(
                            r"^(?:Recruiting|Tuyển dụng)\s+(.*?)\s+(?:at|tại)\s+(.*?)(?:\s*\|\s*(?:Saramin|TopDev|Việc làm).*|$)",
                            raw_page_title,
                            re.IGNORECASE,
                        )
                        if m_topdev:
                            title = m_topdev.group(1).strip()
                            company = m_topdev.group(2).strip()
                        else:
                            clean_t = re.sub(r"\s*\|\s*(?:Saramin|TopDev).*$", "", raw_page_title).strip()
                            clean_t = re.sub(r"^(?:Recruiting|Tuyển dụng)\s+", "", clean_t, flags=re.I).strip()
                            if clean_t:
                                title = clean_t

                        # Try DOM company link
                        for a_comp in soup.select('a[href*="/companies/"]'):
                            if "/companies/group/" in a_comp.get("href", ""):
                                continue
                            c_text = a_comp.get_text(separator=" ", strip=True)
                            if "Industry" in c_text:
                                c_text = c_text.split("Industry")[0].strip()
                            if "View company" not in c_text and 2 < len(c_text) < 100:
                                company = c_text
                                break

                    # Remove script, style, nav, footer tags
                    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                        tag.decompose()

                    # Find job container or main text
                    main_content = (
                        soup.find("article")
                        or soup.find("main")
                        or soup.find("div", class_=re.compile(r"job|description|detail|content", re.I))
                        or soup.body
                    )
                    raw_text = main_content.get_text(separator="\n", strip=True) if main_content else soup.get_text(separator="\n", strip=True)

                    # Deduplicate whitespace lines
                    clean_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
                    clean_text = "\n".join(clean_lines)

                    # Extract og:image or company logo from HTML
                    image_url = None
                    try:
                        og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
                        if og_img and og_img.get("content"):
                            cand_img = og_img["content"].strip()
                            if cand_img.startswith("http") and not cand_img.lower().endswith(".svg"):
                                image_url = cand_img
                        if not image_url:
                            logo_elem = soup.select_one("img[src*='company'], img[src*='logo'], img[alt*='logo'], .company-logo img, .employer-logo img")
                            if logo_elem and logo_elem.get("src"):
                                src = logo_elem["src"].strip()
                                if src.startswith("http") and not src.lower().endswith(".svg"):
                                    image_url = src
                                elif src.startswith("/"):
                                    from urllib.parse import urljoin
                                    image_url = urljoin(url, src)
                    except Exception:
                        pass

                    if not company:
                        company = self._infer_company(title, clean_text, domain, url=url)
                    return self._build_job_dict(title=title, company=company, link=url, raw_text=clean_text, image=image_url)
        except Exception as e:
            logger.error(f"Failed fallback HTTP scrape for {url}: {e}")

        # 3. Minimal fallback if completely unreachable
        fallback_title = known_title or f"Vị trí tuyển dụng ({domain})"
        fallback_company = known_company or self._infer_company(fallback_title, known_desc or "", domain, url=url)
        fallback_desc = known_desc or f"Chi tiết công việc xem tại: {url}"
        return self._build_job_dict(
            title=fallback_title,
            company=fallback_company,
            link=url,
            raw_text=fallback_desc,
        )

    def _infer_company(self, title: str, text: str, domain: str, url: str = "") -> str:
        """
        Infers company name from title, text keywords, or URL host without fabricating portal names.
        Prioritizes structural layout hints from ITviec, TopCV, Indeed, TopDev, etc.
        """
        portal_keywords = {
            "itviec", "indeed", "topcv", "topdev", "vietnamworks", "jobsgo",
            "careerbuilder", "linkedin", "công ty tuyển dụng", "hot jobs", "saramin",
            "việc làm", "tuyển dụng"
        }

        # 0. TopDev specific pattern: Recruiting <Job> at <Company> | Saramin
        m_topdev = re.match(
            r"^(?:Recruiting|Tuyển dụng)\s+(.*?)\s+(?:at|tại)\s+(.*?)(?:\s*\|\s*(?:Saramin|TopDev|Việc làm).*|$)",
            title,
            re.IGNORECASE,
        )
        if m_topdev:
            cand = m_topdev.group(2).strip()
            if cand.lower() not in portal_keywords and len(cand) > 2:
                return cand

        # 1. ITviec specific pattern: Company name is right before 'Company type' / 'Loại công ty'
        match_itviec = re.search(
            r"\n([^\n]+)\n+(?:Company type|Loại công ty|Company size|Quy mô công ty)",
            text,
            re.IGNORECASE,
        )
        if match_itviec:
            cand = match_itviec.group(1).strip()
            if 2 < len(cand) < 80 and cand.lower() not in portal_keywords and not cand.lower().startswith("about"):
                return cand

        # 2. Check line immediately following job title (standard on ITviec, LinkedIn, etc.)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if title:
            for idx, line in enumerate(lines[:10]):
                if title.lower() in line.lower() or line.lower() in title.lower():
                    if idx + 1 < len(lines):
                        next_line = lines[idx + 1]
                        ignore_phrases = [
                            "sign in", "apply", "đăng nhập", "ứng tuyển", "posted", "vừa xong",
                            "salary", "lương", "view salary", "job expertise", "job domain", "skills:"
                        ]
                        if not any(k in next_line.lower() for k in ignore_phrases):
                            if 2 < len(next_line) < 80 and next_line.lower() not in portal_keywords:
                                return next_line
                    break

        # 3. Check patterns like "Job Title at Company" or "Job Title - Company"
        match_at = re.search(r"\bat\s+([A-Za-z0-9\s.,&_-]+?)(?:\||-|$)", title, re.IGNORECASE)
        if match_at and len(match_at.group(1).strip()) > 2:
            cand = match_at.group(1).strip()
            if cand.lower() not in portal_keywords:
                return cand

        match_dash = re.search(r"-\s*([A-Za-z0-9\s.,&_-]+)$", title)
        if match_dash and len(match_dash.group(1).strip()) > 2:
            cand = match_dash.group(1).strip()
            if cand.lower() not in portal_keywords:
                return cand

        # 4. Check early lines for explicit company keywords
        for line in lines[:15]:
            line_clean = line.strip()
            if any(k in line_clean.lower() for k in ["about company", "về công ty", "company overview", "company profile"]):
                continue
            if re.search(r"\b(công ty|tập đoàn|company)\b", line_clean, re.I):
                clean = re.sub(
                    r"^(công ty|tập đoàn|company)\s*(tnhh|cp|cổ phần)?\s*[:\-]?\s*",
                    "",
                    line_clean,
                    flags=re.I,
                ).strip()
                if 2 < len(clean) < 60 and clean.lower() not in portal_keywords:
                    if not any(k in clean.lower() for k in ["our company", "the company", "no explicit", "a company", "this company"]):
                        return clean

        # 5. Extract company slug from ITviec or TopDev URL if available
        if url and ("itviec.com" in url or "topdev.vn" in url):
            slug_match = re.search(r"/(?:detail-jobs|it-jobs)/(?:.*?/)?([a-z0-9-]+)-(\d+)(?:\?|$)", url)
            if not slug_match:
                slug_match = re.search(r"-([a-z0-9-]+)-(\d+)(?:\?|$)", url)
            if slug_match:
                full_slug = slug_match.group(1)
                # If title is available, strip title words from slug to isolate company name
                if title:
                    clean_title_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
                    if clean_title_slug and full_slug.startswith(clean_title_slug):
                        full_slug = full_slug[len(clean_title_slug):].strip("-")
                    else:
                        # Strip common job role prefixes
                        full_slug = re.sub(
                            r"^(?:remote-|junior-|senior-|lead-|intern-|fresher-)?(?:software-engineer|data-engineer|backend-engineer|frontend-engineer|data-services-specialist|data-analyst|devops-engineer|ai-engineer)-?",
                            "",
                            full_slug,
                            flags=re.I,
                        )
                slug_name = full_slug.replace("-", " ").strip().title()
                if slug_name.lower() not in portal_keywords and len(slug_name) > 2:
                    return slug_name

        # 6. Fallback (Strictly DO NOT return job portal name as employer!)
        parts = domain.replace("www.", "").split(".")
        root_domain = parts[0].lower() if parts else ""
        if root_domain in portal_keywords or not parts:
            return "Công ty Tuyển Dụng"

        return parts[0].capitalize()

    def _build_job_dict(self, title: str, company: str, link: str, raw_text: str, image: Optional[str] = None) -> Dict[str, Any]:
        """Constructs a standard job dict matching FindMyBoss schema."""
        # Simple extraction of common tech skills
        tech_keywords = [
            "Python", "JavaScript", "TypeScript", "React", "Node.js", "FastAPI",
            "Django", "Docker", "Kubernetes", "AWS", "GCP", "SQL", "PostgreSQL",
            "MongoDB", "Redis", "Git", "Go", "Golang", "Java", "C++", "C#",
            "Linux", "CI/CD", "HTML", "CSS", "Tailwind", "Next.js", "Vue", "PHP"
        ]
        found_skills = [s for s in tech_keywords if re.search(r"\b" + re.escape(s) + r"\b", raw_text, re.IGNORECASE)]

        return {
            "title": title[:200],
            "company": company[:150],
            "link": link,
            "address": "Hồ Chí Minh / Toàn Quốc",
            "salary": "Thoả thuận",
            "exp": "Không giới hạn",
            "posted_date": "Vừa đăng",
            "image": image,
            "skills": found_skills[:8],
            "description": raw_text[:3000],
            "requirements": "Xem chi tiết trong full JD.",
            "benefits": "Xem chi tiết trong full JD.",
            "full_jd_raw": raw_text[:20000],
        }

    async def process_job_url(
        self,
        url: str,
        template: str = "classic",
        send_to_discord: bool = True,
        job_override: Optional[Job] = None,
    ) -> Dict[str, Any]:
        """
        End-to-End Career-Ops Fast Intake Pipeline:
        1. Extract JD from URL or use job_override.
        2. Store Job in SQLite jobs.db.
        3. Match & tailor CV via AI Service.
        4. Compile tailored ATS CV PDF.
        5. Save tailored CV record in SQLite.
        6. Dispatch rich Job Alert + attached PDF directly to Discord webhook.
        """
        logger.info(f"🚀 Processing Career-Ops Intake for URL: {url}")

        existing = self.storage.get_job_by_link(url) if self.storage else None
        domain = urlparse(url).netloc.lower()

        if job_override is not None:
            job_obj = job_override
        else:
            # Step 1: Extract JD
            job_data = await self.extract_jd_from_url(url)
            title = job_data["title"]
            company = job_data["company"]

            # Prefer existing database values if extractor gave generic fallback
            portal_names = {"itviec", "indeed", "topcv", "topdev", "vietnamworks", "jobsgo", "công ty tuyển dụng", domain, domain.split(".")[0]}
            if existing:
                if (not title or title.startswith("Vị trí tuyển dụng")) and existing.get("title"):
                    title = existing["title"]
                if (not company or company.lower() in portal_names) and existing.get("company"):
                    company = existing["company"]

            job_obj = Job(
                title=title,
                company=company,
                link=job_data["link"],
                address=job_data.get("address", "Hồ Chí Minh"),
                salary=job_data.get("salary", "Thoả thuận"),
                exp=job_data.get("exp"),
                posted_date=job_data.get("posted_date", "Vừa xong"),
                image=job_data.get("image") or (existing.get("image") if existing else None),
                skills=job_data.get("skills", []),
                description=job_data.get("description"),
                requirements=job_data.get("requirements"),
                benefits=job_data.get("benefits"),
                full_jd_raw=job_data.get("full_jd_raw"),
            )

        # Step 2: Persist or get existing job record
        portal_names = {"itviec", "indeed", "topcv", "topdev", "vietnamworks", "jobsgo", "công ty tuyển dụng", domain, domain.split(".")[0]}
        if existing:
            job_id = existing["id"]
            if existing.get("title") and (not job_obj.title or job_obj.title.startswith("Vị trí tuyển dụng")):
                job_obj.title = existing["title"]
            if existing.get("company") and (not job_obj.company or job_obj.company.lower() in portal_names):
                job_obj.company = existing["company"]
            logger.info(f"Found existing Job #{job_id} for URL: {url} ({job_obj.title} at {job_obj.company})")
        else:
            self.storage.save_jobs([job_obj])
            refetched = self.storage.get_job_by_link(url)
            job_id = refetched["id"] if refetched else 1
            logger.info(f"Saved new Job #{job_id} into database.")

        # Step 3: Run AI ATS Evaluation & CV Tailoring
        self._ensure_workspace_synced()
        profile = self.profile_service.load_profile()

        logger.info(f"🤖 Tailoring CV for Job #{job_id} ({job_obj.title} at {job_obj.company})...")
        tailor_result = self.ai_service.tailor_cv_for_job(job_obj.to_dict(), profile)

        # Step 4: Compile tailored ATS PDF
        logger.info(f"📝 Generating LaTeX (Match Score: {tailor_result.match_score}%, Template: {template})...")
        latex_code = self.latex_engine.generate_latex_code(
            profile=profile,
            tailored_summary=tailor_result.tailored_summary,
            tailored_bullets=tailor_result.tailored_bullets,
            ats_keywords=tailor_result.missing_skills,
            template_name=template,
        )

        pdf_filename = f"cv_job_{job_id}.pdf"
        pdf_path = self.latex_engine.compile_pdf(
            latex_code,
            output_filename=pdf_filename,
            profile=profile,
            tailored_summary=tailor_result.tailored_summary,
            tailored_bullets=tailor_result.tailored_bullets,
            ats_keywords=tailor_result.missing_skills,
        )
        logger.info(f"✅ Generated tailored CV PDF: {pdf_path}")

        # Step 5: Save tailored CV in SQLite
        self.storage.save_tailored_cv(
            job_id=job_id,
            match_score=tailor_result.match_score,
            missing_skills=tailor_result.missing_skills,
            tailored_summary=tailor_result.tailored_summary,
            tailored_bullets=tailor_result.tailored_bullets,
            latex_code=latex_code,
            pdf_path=str(pdf_path),
            status="completed",
        )

        # Update applications.md tracker
        try:
            from services.applications_tracker import generate_applications_markdown
            generate_applications_markdown(self.storage)
        except Exception as e:
            logger.warning(f"Could not update applications.md: {e}")

        # Update job object metadata for embed formatting
        job_obj.match_score = tailor_result.match_score
        job_obj.tailored_summary = tailor_result.tailored_summary
        job_obj.cv_generated = True

        # Step 6: Dispatch to Discord
        discord_sent = False
        if send_to_discord:
            logger.info(f"📬 Dispatching Job #{job_id} + CV PDF to Discord...")
            discord_sent = await self.notifier.send_job(job_obj, cv_pdf_path=str(pdf_path))
            if discord_sent:
                logger.info("🎉 Successfully dispatched Job and tailored CV PDF to Discord!")
            else:
                logger.warning("Discord delivery skipped or webhook not responding.")

        return {
            "success": True,
            "job_id": job_id,
            "job": {
                "id": job_id,
                "title": job_obj.title,
                "company": job_obj.company,
                "link": job_obj.link,
                "skills": job_obj.skills,
                "salary": job_obj.salary,
                "address": job_obj.address,
            },
            "match_score": tailor_result.match_score,
            "match_analysis": tailor_result.match_analysis,
            "missing_skills": tailor_result.missing_skills,
            "tailored_summary": tailor_result.tailored_summary,
            "tailored_bullets": tailor_result.tailored_bullets,
            "pdf_path": str(pdf_path),
            "pdf_url": f"/api/jobs/{job_id}/pdf",
            "discord_sent": discord_sent,
        }
