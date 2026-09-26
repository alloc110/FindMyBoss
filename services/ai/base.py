import abc
import json
import re
import time
from typing import Any, Dict, Optional

import httpx

from config import get_logger
from models.schemas import GeminiTailorResponse

logger = get_logger("BaseAIProvider")


def build_tailor_prompt(job: Dict[str, Any], profile: Dict[str, Any]) -> str:
    """Builds a standardized prompt for ATS CV tailoring."""
    title = job.get("title", "Software Engineer")
    company = job.get("company", "Company")
    skills = ", ".join(job.get("skills", []))
    full_jd = job.get("full_jd_raw") or job.get("description") or "N/A"
    requirements = job.get("requirements") or "Xem full JD."

    master_cv_text = profile.get("master_cv_text", "").strip()
    ats_rules = profile.get("ats_rules", "").strip() or "Standard ATS scoring: prioritize core skills and quantify experience."
    cv_rules = profile.get("cv_rules", "").strip() or "Follow Google XYZ / STAR format, truthful experience selection, action verbs."

    candidate_context = ""
    if master_cv_text:
        candidate_context = f"""
### 2. CANDIDATE MASTER PORTFOLIO / RAW CV TEXT (EXTRACTED FROM UPLOADED PDF):
```text
{master_cv_text[:8000]}
```
"""
    else:
        profile_json = json.dumps(profile, ensure_ascii=False, indent=2)
        candidate_context = f"""
### 2. CANDIDATE BASE PROFILE:
```json
{profile_json}
```
"""

    return f"""
You are an elite Executive Tech Recruiter and ATS Resume Optimization Specialist.
Your goal is to analyze the target Job Description (JD) and tailor the candidate's CV to maximize ATS keyword scoring, pass initial screening filters, and highlight relevant technical competencies truthfully.

---
### 1. TARGET JOB DESCRIPTION:
- Title: {title}
- Company: {company}
- Required Tech Stack: {skills}
- Key Requirements:
{requirements}

- Full JD Raw Content:
{full_jd[:4000]}

---
{candidate_context}

---
### 3. USER CUSTOM ATS EVALUATION RULES:
Strictly adhere to the following rules when evaluating fit and identifying skill gaps:
{ats_rules}

---
### 4. USER CUSTOM CV WRITING & TAILORING RULES:
Strictly adhere to the following rules when generating summary and experience bullets:
{cv_rules}

---
### 5. OUTPUT INSTRUCTIONS:
Produce a JSON object strictly matching this schema:
- match_score: integer from 0 to 100 based on realistic technical alignment against the JD.
- match_analysis: 2-3 sentences explaining candidate's top strengths and primary technical gaps.
- missing_skills: list of up to 5 critical technologies/methodologies mentioned in the JD that the candidate should be aware of.
- tailored_summary: A 3-4 sentence powerful professional summary tailored specifically for {title} at {company}, emphasizing the candidate's existing strengths while seamlessly integrating relevant JD keywords.
- tailored_bullets: 3-4 high-impact bullet points for the candidate's most recent position. Follow Google XYZ formula: "Accomplished [X] as measured by [Y] by doing [Z]", naturally featuring technical keywords from this JD.
"""


def clean_and_parse_json(text: str) -> Dict[str, Any]:
    """Strips markdown code blocks and extracts JSON payload cleanly."""
    clean = (text or "").strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()
    try:
        return json.loads(clean)
    except Exception:
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def extract_json_block(text: str) -> str:
    """Extracts JSON block from text if wrapped in markdown code blocks."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match_brace = re.search(r"(\{.*\})", text, re.DOTALL)
    if match_brace:
        return match_brace.group(1)
    return text


class BaseAIProvider(abc.ABC):
    """Abstract Base Class for AI Providers."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "", base_url: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url

    @abc.abstractmethod
    def test_connection(self, api_key: str, model_name: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        """Tests API key and model connectivity, returning latency and status."""
        pass

    @abc.abstractmethod
    def tailor_cv(self, job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        """Sends prompt to AI model and returns structured tailoring response."""
        pass
