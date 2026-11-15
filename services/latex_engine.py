import html
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_logger

logger = get_logger("LatexEngine")


def escape_latex(text: Optional[str]) -> str:
    """
    Escapes special LaTeX characters to prevent compilation errors or injection.
    Handles &, %, $, #, _, {, }, ~, ^, \\
    """
    if text is None:
        return ""

    s = str(text)
    # Mapping of special characters
    special_chars = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }

    # Escape backslash first to avoid double-escaping
    s = s.replace("\\", special_chars["\\"])
    for char, replacement in special_chars.items():
        if char != "\\":
            s = s.replace(char, replacement)

    return s


class LatexEngine:
    """Compiles ATS-compliant LaTeX resumes into professional PDF documents using Tectonic."""

    def __init__(
        self,
        template_path: str = "templates/cv_template.tex",
        output_dir: str = "data/cvs",
        tectonic_path: Optional[str] = None,
    ):
        self.template_path = Path(template_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Locate tectonic binary (custom bin/tectonic, system path, or env)
        if tectonic_path and Path(tectonic_path).exists():
            self.tectonic_bin = str(Path(tectonic_path).resolve())
        elif Path("bin/tectonic").exists():
            self.tectonic_bin = str(Path("bin/tectonic").resolve())
        elif Path("bin/tectonic.exe").exists():
            self.tectonic_bin = str(Path("bin/tectonic.exe").resolve())
        else:
            self.tectonic_bin = shutil.which("tectonic") or shutil.which("tectonic.exe") or "tectonic"

    def format_skills_block(self, skills_dict: Dict[str, List[str]], ats_keywords: Optional[List[str]] = None) -> str:
        """Formats the skills section into LaTeX bullet items."""
        lines = []
        for category, skill_list in skills_dict.items():
            escaped_skills = [escape_latex(s) for s in skill_list if s]
            if escaped_skills:
                lines.append(f"\\textbf{{{escape_latex(category)}}}: {', '.join(escaped_skills)} \\\\")

        if ats_keywords:
            clean_ats = [escape_latex(k) for k in ats_keywords if k]
            if clean_ats:
                lines.append(f"\\textbf{{Target Role Keywords}}: {', '.join(clean_ats)} \\\\")

        return "\n".join(lines)

    def format_experience_block(self, experiences: List[Dict[str, Any]], tailored_bullets: Optional[List[str]] = None) -> str:
        """Formats work experiences into Jake's Resume subheadings and bullet lists."""
        blocks = []
        for idx, exp in enumerate(experiences):
            role = escape_latex(exp.get("role", "Software Engineer"))
            company = escape_latex(exp.get("company", "Company"))
            location = escape_latex(exp.get("location", "Việt Nam"))
            date = escape_latex(exp.get("date", "2023 - Present"))

            # If tailored bullets are provided, inject them into the first (most recent) experience
            bullets = exp.get("bullets", [])
            if idx == 0 and tailored_bullets:
                bullets = tailored_bullets

            bullet_items = "\n".join(
                [f"    \\resumeItem{{{escape_latex(b)}}}" for b in bullets if b]
            )

            block = f"""
  \\resumeSubheading
    {{{role}}}{{{location}}}
    {{{company}}}{{{date}}}
    \\resumeItemListStart
{bullet_items}
    \\resumeItemListEnd
"""
            blocks.append(block.strip())

        if not blocks:
            default_bullets = tailored_bullets or ["Executed core software engineering deliverables and system workflows."]
            bullet_items = "\n".join([f"    \\resumeItem{{{escape_latex(b)}}}" for b in default_bullets if b])
            return f"""  \\resumeSubheading
    {{Software Engineer}}{{Hồ Chí Minh, Việt Nam}}
    {{Professional Engineering Portfolio}}{{2023 -- Present}}
    \\resumeItemListStart
{bullet_items}
    \\resumeItemListEnd"""

        return "\n\n".join(blocks)

    def format_projects_block(self, projects: List[Dict[str, Any]]) -> str:
        """Formats key projects section."""
        blocks = []
        for proj in projects:
            name = escape_latex(proj.get("name", "Project"))
            techs = escape_latex(proj.get("technologies", ""))
            bullets = proj.get("bullets", [])

            bullet_items = "\n".join(
                [f"    \\resumeItem{{{escape_latex(b)}}}" for b in bullets if b]
            )

            block = f"""
  \\resumeSubheading
    {{{name}}}{{{techs}}}
    {{Key Contributor}}{{}}
    \\resumeItemListStart
{bullet_items}
    \\resumeItemListEnd
"""
            blocks.append(block.strip())

        if not blocks:
            return """  \\resumeSubheading
    {Engineering Projects}{Python, SQL, Cloud Architecture}
    {Lead Developer}{}
    \\resumeItemListStart
      \\resumeItem{Architected data processing workflows and scalable backend systems.}
    \\resumeItemListEnd"""

        return "\n\n".join(blocks)

    def format_education_block(self, education_list: List[Dict[str, Any]]) -> str:
        """Formats education section."""
        blocks = []
        for edu in education_list:
            school = escape_latex(edu.get("school", "University"))
            degree = escape_latex(edu.get("degree", "Degree"))
            location = escape_latex(edu.get("location", "Việt Nam"))
            date = escape_latex(edu.get("date", "2019 - 2023"))

            block = f"""
  \\resumeSubheading
    {{{school}}}{{{location}}}
    {{{degree}}}{{{date}}}
"""
            blocks.append(block.strip())

        if not blocks:
            return """  \\resumeSubheading
    {Đại học / University}{Việt Nam}
    {Bachelor of Science in Computer Science}{2020 -- 2024}"""

        return "\n\n".join(blocks)

    def generate_latex_code(
        self,
        profile: Dict[str, Any],
        tailored_summary: Optional[str] = None,
        tailored_bullets: Optional[List[str]] = None,
        ats_keywords: Optional[List[str]] = None,
        template_name: str = "classic",
    ) -> str:
        """Injects profile data and Gemini optimizations into the LaTeX template."""
        templates_map = {
            "classic": Path("templates/cv_template.tex"),
            "modern": Path("templates/cv_template_modern.tex"),
            "compact": Path("templates/cv_template_compact.tex"),
        }
        chosen_template = templates_map.get(template_name, self.template_path)
        if not chosen_template.exists():
            chosen_template = self.template_path

        template_text = chosen_template.read_text(encoding="utf-8")

        name = escape_latex(profile.get("name", "Candidate"))
        title = escape_latex(profile.get("title", "Software Engineer"))

        # Contact info line
        contacts = []
        if profile.get("phone"):
            contacts.append(escape_latex(profile["phone"]))
        if profile.get("email"):
            email = escape_latex(profile["email"])
            contacts.append(f"\\href{{mailto:{email}}}{{\\underline{{{email}}}}}")
        if profile.get("linkedin"):
            linkedin = profile["linkedin"]
            display_li = escape_latex(linkedin.replace("https://", "").replace("http://", ""))
            contacts.append(f"\\href{{{linkedin}}}{{\\underline{{{display_li}}}}}")
        if profile.get("github"):
            github = profile["github"]
            display_gh = escape_latex(github.replace("https://", "").replace("http://", ""))
            contacts.append(f"\\href{{{github}}}{{\\underline{{{display_gh}}}}}")
        if profile.get("location"):
            contacts.append(escape_latex(profile["location"]))

        contact_info_latex = " $|$ ".join(contacts)

        # Summary
        summary = tailored_summary or profile.get("summary", "")
        summary_latex = escape_latex(summary)

        # Skills, Experience, Projects, Education
        skills_latex = self.format_skills_block(profile.get("skills", {}), ats_keywords)
        exp_latex = self.format_experience_block(profile.get("experiences", []), tailored_bullets)
        proj_latex = self.format_projects_block(profile.get("projects", []))
        edu_latex = self.format_education_block(profile.get("education", []))

        replacements = {
            "{{ CANDIDATE_NAME }}": name,
            "{{ CANDIDATE_TITLE }}": title,
            "{{ CONTACT_INFO }}": contact_info_latex,
            "{{ TAILORED_SUMMARY }}": summary_latex,
            "{{ SKILLS_CONTENT }}": skills_latex,
            "{{ EXPERIENCE_CONTENT }}": exp_latex,
            "{{ PROJECTS_CONTENT }}": proj_latex,
            "{{ EDUCATION_CONTENT }}": edu_latex,
        }

        result = template_text
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        return result

    def compile_html_to_pdf(
        self,
        target_pdf: Path,
        profile: Optional[Dict[str, Any]] = None,
        tailored_summary: Optional[str] = None,
        tailored_bullets: Optional[List[str]] = None,
        ats_keywords: Optional[List[str]] = None,
    ) -> bool:
        """Renders an ATS-compliant, high-fidelity resume PDF via local headless Chromium."""
        try:
            from playwright.sync_api import sync_playwright

            if profile is None:
                try:
                    from services.profile_service import ProfileService
                    profile = ProfileService().load_profile()
                except Exception:
                    profile = {}

            name = html.escape(str(profile.get("name") or "Candidate Name"))
            title = html.escape(str(profile.get("title") or "Software Engineer"))
            summary = html.escape(str(tailored_summary or profile.get("summary") or ""))

            contacts = []
            if profile.get("phone"):
                contacts.append(html.escape(str(profile["phone"])))
            if profile.get("email"):
                contacts.append(html.escape(str(profile["email"])))
            if profile.get("location"):
                contacts.append(html.escape(str(profile["location"])))
            if profile.get("linkedin"):
                li = str(profile["linkedin"])
                disp_li = li.replace("https://", "").replace("http://", "")
                contacts.append(f"<a href='{html.escape(li)}'>{html.escape(disp_li)}</a>")
            if profile.get("github"):
                gh = str(profile["github"])
                disp_gh = gh.replace("https://", "").replace("http://", "")
                contacts.append(f"<a href='{html.escape(gh)}'>{html.escape(disp_gh)}</a>")
            contact_html = " | ".join(contacts)

            # Technical skills
            skills_html = []
            skills_dict = profile.get("skills", {})
            if isinstance(skills_dict, dict):
                for cat, items in skills_dict.items():
                    if items:
                        clean_items = [html.escape(str(i)) for i in items if i]
                        skills_html.append(
                            f"<div class='skill-line'><b>{html.escape(str(cat))}:</b> {', '.join(clean_items)}</div>"
                        )
            if ats_keywords:
                clean_ats = [html.escape(str(k)) for k in ats_keywords if k]
                skills_html.append(
                    f"<div class='skill-line'><b>Target Role Keywords:</b> {', '.join(clean_ats)}</div>"
                )

            # Experiences
            exp_html = []
            experiences = profile.get("experiences", [])
            for idx, exp in enumerate(experiences):
                r_role = html.escape(str(exp.get("role") or "Software Engineer"))
                r_company = html.escape(str(exp.get("company") or "Company"))
                r_loc = html.escape(str(exp.get("location") or "Việt Nam"))
                r_date = html.escape(str(exp.get("date") or "2023 - Present"))
                bullets = exp.get("bullets", [])
                if idx == 0 and tailored_bullets:
                    bullets = tailored_bullets
                bullet_items = "".join([f"<li>{html.escape(str(b))}</li>" for b in bullets if b])
                exp_html.append(f"""
                <div class='subheading'><div>{r_role}</div><div>{r_loc}</div></div>
                <div class='subheading-sub'><div>{r_company}</div><div>{r_date}</div></div>
                <ul>{bullet_items}</ul>
                """)

            # Projects
            proj_html = []
            for proj in profile.get("projects", []):
                p_name = html.escape(str(proj.get("name") or "Project"))
                p_tech = html.escape(str(proj.get("technologies") or ""))
                p_bullets = proj.get("bullets", [])
                bullet_items = "".join([f"<li>{html.escape(str(b))}</li>" for b in p_bullets if b])
                proj_html.append(f"""
                <div class='subheading'><div>{p_name} ({p_tech})</div><div>Key Contributor</div></div>
                <ul>{bullet_items}</ul>
                """)

            # Education
            edu_html = []
            for edu in profile.get("education", []):
                school = html.escape(str(edu.get("school") or "University"))
                degree = html.escape(str(edu.get("degree") or "Degree"))
                e_loc = html.escape(str(edu.get("location") or "Việt Nam"))
                e_date = html.escape(str(edu.get("date") or "2019 - 2023"))
                edu_html.append(f"""
                <div class='subheading'><div>{school}</div><div>{e_loc}</div></div>
                <div class='subheading-sub'><div>{degree}</div><div>{e_date}</div></div>
                """)

            full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<style>
  @page {{ size: letter; margin: 0.5in; }}
  body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.35; color: #111; margin: 0; padding: 0; }}
  .name {{ text-align: center; font-size: 18pt; font-weight: bold; text-transform: uppercase; margin-bottom: 2px; }}
  .title {{ text-align: center; font-size: 11pt; font-style: italic; color: #333; margin-bottom: 4px; }}
  .contact {{ text-align: center; font-size: 9pt; color: #555; margin-bottom: 12px; border-bottom: 1px solid #111; padding-bottom: 6px; }}
  .contact a {{ color: #111; text-decoration: none; }}
  .section-title {{ font-size: 11pt; font-weight: bold; text-transform: uppercase; border-bottom: 1px solid #333; margin-top: 10px; margin-bottom: 4px; padding-bottom: 1px; }}
  .subheading {{ display: flex; justify-content: space-between; font-weight: bold; font-size: 10pt; margin-top: 5px; }}
  .subheading-sub {{ display: flex; justify-content: space-between; font-style: italic; font-size: 9.5pt; color: #333; margin-bottom: 2px; }}
  ul {{ margin: 2px 0 6px 16px; padding: 0; }}
  li {{ margin-bottom: 2px; font-size: 9.5pt; }}
  .skill-line {{ margin-bottom: 3px; font-size: 9.5pt; }}
  .skill-line b {{ font-weight: bold; }}
  .summary-text {{ font-size: 9.5pt; text-align: justify; margin-bottom: 6px; }}
</style>
</head>
<body>
  <div class='name'>{name}</div>
  <div class='title'>{title}</div>
  <div class='contact'>{contact_html}</div>

  {"<div class='section-title'>Professional Summary</div><div class='summary-text'>" + summary + "</div>" if summary else ""}

  {"<div class='section-title'>Technical Skills</div>" + "".join(skills_html) if skills_html else ""}

  {"<div class='section-title'>Experience</div>" + "".join(exp_html) if exp_html else ""}

  {"<div class='section-title'>Key Projects</div>" + "".join(proj_html) if proj_html else ""}

  {"<div class='section-title'>Education</div>" + "".join(edu_html) if edu_html else ""}
</body>
</html>"""
            import concurrent.futures

            def _render_pdf_worker():
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    page = browser.new_page()
                    page.set_content(full_html)
                    page.pdf(path=str(target_pdf), format="Letter", print_background=True)
                    browser.close()
                return True

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                fut = executor.submit(_render_pdf_worker)
                fut.result(timeout=25.0)

            logger.info(f"✅ Playwright successfully compiled high-fidelity ATS PDF at: {target_pdf}")
            return True
        except Exception as e:
            logger.error(f"Playwright PDF fallback generation error: {e}")
            return False

    def compile_pdf(
        self,
        latex_code: str,
        output_filename: str,
        profile: Optional[Dict[str, Any]] = None,
        tailored_summary: Optional[str] = None,
        tailored_bullets: Optional[List[str]] = None,
        ats_keywords: Optional[List[str]] = None,
    ) -> Path:
        """
        Compiles the resume into an ATS PDF.
        Priority:
        1. Delegated Renderer Microservice (if configured)
        2. Local Tectonic compiler (fast check: <= 5s)
        3. Local Playwright Chromium renderer (robust offline HTML-to-PDF)
        """
        if not output_filename.endswith(".pdf"):
            output_filename += ".pdf"

        target_pdf = (self.output_dir / output_filename).resolve()

        # 1. Check if delegated Renderer Microservice is available
        renderer_url = os.getenv("RENDERER_SERVICE_URL", "").rstrip("/")
        if renderer_url:
            try:
                import httpx
                logger.info(f"🌐 Delegating LaTeX compilation to Renderer Microservice: {renderer_url}/api/render")
                resp = httpx.post(
                    f"{renderer_url}/api/render",
                    json={"latex_code": latex_code, "output_filename": output_filename},
                    timeout=60.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if target_pdf.exists():
                        logger.info(f"✅ Microservice compiled PDF confirmed at: {target_pdf}")
                        return target_pdf
                    return Path(data.get("pdf_path", str(target_pdf)))
                else:
                    logger.warning(f"⚠️ Renderer microservice returned {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to reach renderer microservice ({e}).")

        # 2. Check if local tectonic executable exists and compiles within short timeout
        tectonic_exists = bool(shutil.which(self.tectonic_bin) or Path(self.tectonic_bin).exists())
        if tectonic_exists:
            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_path = Path(tmp_dir)
                    tex_file = tmp_path / "resume.tex"
                    tex_file.write_text(latex_code, encoding="utf-8")

                    cmd = [
                        self.tectonic_bin,
                        str(tex_file),
                        "--outdir",
                        str(tmp_path),
                    ]

                    logger.info(f"🔨 Compiling LaTeX with Tectonic: {' '.join(cmd)}")
                    proc = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=5,
                    )

                    if proc.returncode == 0:
                        generated_pdf = tmp_path / "resume.pdf"
                        if generated_pdf.exists():
                            shutil.copy2(generated_pdf, target_pdf)
                            logger.info(f"✅ Tectonic generated PDF saved at: {target_pdf}")
                            return target_pdf
                    else:
                        logger.warning(f"Tectonic compilation failed or exited {proc.returncode}: {proc.stderr[:300]}")
            except Exception as tec_err:
                logger.warning(f"Tectonic compilation skipped/timed out: {tec_err}")

        # 3. Robust Playwright HTML-to-PDF Fallback
        logger.info(f"📄 Compiling ATS CV via Playwright Chromium renderer for {output_filename}...")
        success = self.compile_html_to_pdf(
            target_pdf=target_pdf,
            profile=profile,
            tailored_summary=tailored_summary,
            tailored_bullets=tailored_bullets,
            ats_keywords=ats_keywords,
        )
        if success and target_pdf.exists():
            return target_pdf

        # 4. Minimal safe PDF fallback if Playwright is also unavailable
        target_pdf.write_bytes(
            b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n"
            b"xref\n0 3\n0000000000 65535 f \ntrailer << /Size 3 /Root 1 0 R >>\nstartxref\n0\n%%EOF"
        )
        logger.info(f"ℹ️ Minimal PDF saved at: {target_pdf}")
        return target_pdf
