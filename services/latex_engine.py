import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import get_logger

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
        else:
            self.tectonic_bin = shutil.which("tectonic") or "tectonic"

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

    def compile_pdf(self, latex_code: str, output_filename: str) -> Path:
        """
        Compiles the raw LaTeX code into a PDF using Tectonic.
        Returns the absolute Path to the generated PDF.
        """
        if not output_filename.endswith(".pdf"):
            output_filename += ".pdf"

        target_pdf = (self.output_dir / output_filename).resolve()

        # Check if delegated Renderer Microservice is available
        renderer_url = os.getenv("RENDERER_SERVICE_URL", "").rstrip("/")
        if renderer_url:
            try:
                import httpx
                logger.info(f"🌐 Delegating LaTeX compilation to Renderer Microservice: {renderer_url}/api/render")
                resp = httpx.post(
                    f"{renderer_url}/api/render",
                    json={"latex_code": latex_code, "output_filename": output_filename},
                    timeout=180.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if target_pdf.exists():
                        logger.info(f"✅ Microservice compiled PDF confirmed at: {target_pdf}")
                        return target_pdf
                    return Path(data.get("pdf_path", str(target_pdf)))
                else:
                    logger.warning(f"⚠️ Renderer microservice returned {resp.status_code}: {resp.text}. Falling back to local execution.")
            except Exception as e:
                logger.warning(f"⚠️ Failed to reach renderer microservice ({e}). Falling back to local Tectonic.")

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
                timeout=180,
            )

            if proc.returncode != 0:
                logger.error(f"❌ Tectonic compilation failed:\n{proc.stderr}")
                raise RuntimeError(f"LaTeX Compilation Error:\n{proc.stderr}\nStdout:\n{proc.stdout}")

            generated_pdf = tmp_path / "resume.pdf"
            if not generated_pdf.exists():
                raise FileNotFoundError("Compiled resume.pdf not found in output directory")

            shutil.copy2(generated_pdf, target_pdf)
            logger.info(f"✅ Generated PDF saved at: {target_pdf}")
            return target_pdf
