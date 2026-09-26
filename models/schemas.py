from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------
# AI Tailoring Schemas
# -------------------------------------------------------------
class GeminiTailorResponse(BaseModel):
    match_score: int = Field(default=80, description="Percentage match between candidate and JD (0-100)")
    match_analysis: str = Field(default="", description="Brief assessment of strengths and gaps")
    missing_skills: List[str] = Field(default_factory=list, description="High-priority ATS skills present in JD but missing in candidate profile")
    tailored_summary: str = Field(default="", description="Tailored 3-4 sentence professional summary targeting this specific job")
    tailored_bullets: List[str] = Field(default_factory=list, description="3-4 tailored experience bullets in STAR/XYZ format emphasizing JD tech stack")


# -------------------------------------------------------------
# Job Status & Detail Schemas
# -------------------------------------------------------------
VALID_JOB_STATUSES = ["saved", "applied", "interviewing", "offered", "rejected"]


class JobStatusRequest(BaseModel):
    status: str = Field(..., description="Job application lifecycle status: saved, applied, interviewing, offered, rejected")


class RecompileRequest(BaseModel):
    latex_code: str = Field(..., description="Full LaTeX source code to recompile into PDF")


# -------------------------------------------------------------
# Scraper Schemas
# -------------------------------------------------------------
class ScraperPortalsConfig(BaseModel):
    itviec: bool = True
    topdev: bool = True
    topcv: bool = True
    vietnamworks: bool = True
    jobsgo: bool = True
    indeed: bool = True


class ScraperConfigModel(BaseModel):
    portals: Dict[str, bool] = Field(default_factory=lambda: {
        "itviec": True, "topdev": True, "topcv": True, "vietnamworks": True, "jobsgo": True, "indeed": True
    })
    keywords: List[str] = Field(default_factory=lambda: [
        "python", "backend", "data engineer", "intern", "fresher", "junior"
    ])
    levels: List[str] = Field(default_factory=lambda: ["intern", "fresher", "junior"])
    locations: List[str] = Field(default_factory=lambda: ["Hồ Chí Minh", "Hà Nội", "Toàn quốc", "Remote"])
    blacklisted_keywords: List[str] = Field(default_factory=lambda: [
        "senior", "lead", "middle", "mid", "sr", "manager", "director"
    ])
    max_pages_per_portal: int = 3
    delay_seconds: float = 2.0
    deep_scrape: bool = True

    # Aliases
    target_levels: Optional[List[str]] = None
    target_cities: Optional[List[str]] = None
    unwanted_titles: Optional[List[str]] = None


class ScrapePayload(BaseModel):
    portals: Optional[List[str]] = None
    today_only: Optional[bool] = False


# -------------------------------------------------------------
# Settings Schemas
# -------------------------------------------------------------
class TestConnectionPayload(BaseModel):
    provider: str = Field(default="gemini", description="AI provider: gemini, openai, claude, or custom")
    api_key: Optional[str] = Field(default=None, description="API Key for testing")
    model: Optional[str] = Field(default=None, description="Model ID")
    model_name: Optional[str] = Field(default=None, description="Alternative model field")
    base_url: Optional[str] = Field(default=None, description="Base URL for custom/OpenAI-compatible endpoints")


class SettingsUpdatePayload(BaseModel):
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    gemini_model: Optional[str] = None
    api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    custom_api_key: Optional[str] = None
    custom_base_url: Optional[str] = None
    theme: Optional[str] = None


# -------------------------------------------------------------
# Profile Schemas
# -------------------------------------------------------------
class CandidateProfile(BaseModel):
    name: str = "Candidate Name"
    title: str = "Software Engineer"
    email: str = "candidate@example.com"
    phone: str = "+84 901 234 567"
    location: str = "Hồ Chí Minh"
    summary: str = "Software engineer with solid technical experience."
    skills: Dict[str, List[str]] = Field(default_factory=dict)
    experiences: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    master_cv_text: Optional[str] = None
    master_cv_filename: Optional[str] = None
    master_cv_pages: Optional[int] = None
    master_cv_words: Optional[int] = None
    ats_rules: Optional[str] = None
    cv_rules: Optional[str] = None
