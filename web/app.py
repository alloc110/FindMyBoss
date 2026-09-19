import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel
import pypdf

from config import get_logger
from services.gemini_service import GeminiService
from services.latex_engine import LatexEngine
from services.storage import JobStorage

logger = get_logger("WebApp")

app = FastAPI(
    title="FindMyBoss - Job Dashboard & ATS CV Studio",
    description="Smart Job Board with Gemini AI CV Tailoring and Tectonic LaTeX PDF Generator",
    version="2.0.0",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure required directories exist
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "web" / "static"
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
DATA_DIR = BASE_DIR / "data"
PROFILE_FILE = DATA_DIR / "profile.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
CVS_DIR = DATA_DIR / "cvs"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
CVS_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def load_settings() -> Dict[str, Any]:
    """Loads system and AI model settings with environment variables as fallback."""
    defaults = {
        "ai_provider": "gemini",
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "custom_api_key": os.getenv("CUSTOM_AI_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", ""),
        "ai_model": "gemini-2.5-flash",
        "gemini_model": "gemini-2.5-flash",
        "custom_base_url": "https://api.deepseek.com/v1",
        "theme": "dark",
    }
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            defaults.update(saved)
        except Exception as e:
            logger.warning(f"Error reading settings.json: {e}")
    return defaults


def save_settings(settings_data: Dict[str, Any]) -> None:
    """Saves system settings to disk."""
    SETTINGS_FILE.write_text(json.dumps(settings_data, ensure_ascii=False, indent=2), encoding="utf-8")


# Initialize settings & services
initial_settings = load_settings()
init_provider = initial_settings.get("ai_provider", "gemini")
init_key = initial_settings.get(f"{init_provider}_api_key") or initial_settings.get("gemini_api_key")
if initial_settings.get("gemini_api_key"):
    os.environ["GEMINI_API_KEY"] = initial_settings["gemini_api_key"]

storage = JobStorage(db_path=str(DATA_DIR / "jobs.db"))
latex_engine = LatexEngine(output_dir=str(CVS_DIR))
gemini_service = GeminiService(
    api_key=init_key,
    model_name=initial_settings.get("ai_model", "gemini-2.5-flash"),
    provider=init_provider,
    base_url=initial_settings.get("custom_base_url"),
)


def load_profile() -> Dict[str, Any]:
    """Loads candidate profile from JSON file or provides default."""
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Error reading profile.json: {e}")
    return {
        "name": "Candidate Name",
        "title": "Software Engineer",
        "email": "candidate@example.com",
        "phone": "+84 901 234 567",
        "location": "Hồ Chí Minh",
        "summary": "Software engineer with solid technical experience.",
        "skills": {"Languages": ["Python", "JavaScript"], "Frameworks": ["FastAPI", "React"]},
        "experiences": [],
        "projects": [],
        "education": [],
    }


def save_profile(profile_data: Dict[str, Any]) -> None:
    """Saves candidate profile to disk."""
    PROFILE_FILE.write_text(json.dumps(profile_data, ensure_ascii=False, indent=2), encoding="utf-8")


# -------------------------------------------------------------
# Frontend Route
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the main single-page application dashboard."""
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>FindMyBoss UI is loading...</h1>")


# -------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------
@app.get("/api/stats")
async def get_dashboard_stats():
    """Provides overview statistics for the UI header."""
    stats = storage.get_stats()
    stats["has_gemini_key"] = bool(gemini_service.api_key)
    stats["ai_provider"] = gemini_service.provider
    stats["gemini_model"] = gemini_service.model_name
    return stats


@app.get("/api/settings/models")
async def get_available_models():
    """Returns the comprehensive curated model catalog across all supported AI providers."""
    return {
        "gemini": {
            "name": "Google Gemini",
            "key_label": "Google Gemini API Key",
            "placeholder": "Dán mã API Key của bạn (bắt đầu bằng AIzaSy...)",
            "hint": "Lấy API Key miễn phí tại Google AI Studio (aistudio.google.com). Nếu để trống, hệ thống sẽ chạy ở Chế độ Mô phỏng Thông minh.",
            "models": [
                {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "desc": "Khuyên dùng - Cực nhanh, thông minh & chuẩn xác nhất", "tag": "Khuyên dùng"},
                {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "desc": "Lập luận sâu, phân tích JD học thuật phức tạp", "tag": "Lý luận sâu"},
                {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "desc": "Tốc độ cao thế hệ mới", "tag": "Tốc độ"},
                {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "desc": "Cửa sổ ngữ cảnh siêu lớn", "tag": "Ngữ cảnh lớn"},
                {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "desc": "Tiết kiệm token & phản hồi nhanh", "tag": "Tiết kiệm"},
                {"id": "custom", "name": "Mô hình Gemini tùy chỉnh...", "desc": "Tự nhập ID mô hình", "tag": "Tùy biến"},
            ]
        },
        "openai": {
            "name": "OpenAI / ChatGPT",
            "key_label": "OpenAI API Key",
            "placeholder": "Dán mã OpenAI API Key của bạn (bắt đầu bằng sk-...)",
            "hint": "Lấy API Key tại platform.openai.com/api-keys. Hỗ trợ các dòng GPT-4o, GPT-3.5-Turbo và dòng suy luận o1/o3.",
            "models": [
                {"id": "gpt-4o", "name": "GPT-4o", "desc": "Mô hình đa năng hàng đầu của OpenAI", "tag": "Flagship"},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "desc": "Chi phí rẻ, tốc độ siêu tốc, tối ưu hóa CV chuẩn", "tag": "Tiết kiệm"},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "desc": "Mô hình ChatGPT kinh điển, độ ổn định cao", "tag": "Kinh điển"},
                {"id": "o1-mini", "name": "OpenAI o1 Mini", "desc": "Mô hình tư duy chuyên sâu Reasoning", "tag": "Suy luận"},
                {"id": "o3-mini", "name": "OpenAI o3 Mini", "desc": "Mô hình Reasoning thế hệ mới", "tag": "Lý luận cao"},
                {"id": "custom", "name": "Mô hình OpenAI tùy chỉnh...", "desc": "Tự nhập ID mô hình", "tag": "Tùy biến"},
            ]
        },
        "claude": {
            "name": "Anthropic Claude",
            "key_label": "Anthropic Claude API Key",
            "placeholder": "Dán mã Anthropic API Key của bạn (bắt đầu bằng sk-ant-...)",
            "hint": "Lấy API Key tại console.anthropic.com. Claude nổi tiếng về chất lượng viết văn tự nhiên, học thuật và chính xác.",
            "models": [
                {"id": "claude-3-7-sonnet-latest", "name": "Claude 3.7 Sonnet", "desc": "Mô hình mới nhất với khả năng viết lách & tư duy xuất sắc", "tag": "Mới nhất"},
                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "desc": "Chuẩn mực phân tích ATS và viết văn phong chuyên nghiệp", "tag": "Khuyên dùng"},
                {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "desc": "Tốc độ xử lý tức thì, chi phí tối ưu", "tag": "Tốc độ"},
                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "desc": "Mô hình năng lực tối đa cho tác vụ phức tạp", "tag": "Chuyên sâu"},
                {"id": "custom", "name": "Mô hình Claude tùy chỉnh...", "desc": "Tự nhập ID mô hình", "tag": "Tùy biến"},
            ]
        },
        "custom": {
            "name": "Tùy biến / DeepSeek / Local LLM",
            "key_label": "Custom API Key (Tùy chọn)",
            "placeholder": "Dán mã API Key (sk-...) hoặc để trống nếu chạy Ollama local",
            "hint": "Tương thích với mọi API chuẩn OpenAI: DeepSeek (api.deepseek.com), Ollama (localhost:11434), vLLM, OpenRouter.",
            "models": [
                {"id": "deepseek-chat", "name": "DeepSeek V3 (Chat)", "desc": "Mô hình mã nguồn mở chi phí siêu rẻ", "tag": "Hiệu năng cao"},
                {"id": "deepseek-reasoner", "name": "DeepSeek R1 (Reasoner)", "desc": "Mô hình tư duy lập luận sâu", "tag": "Suy luận"},
                {"id": "custom", "name": "Mô hình tùy chỉnh khác...", "desc": "Tự nhập model cho Ollama / OpenRouter", "tag": "Tùy biến"},
            ]
        },
    }


@app.post("/api/settings/test-connection")
async def test_ai_connection(payload: Dict[str, Any] = Body(...)):
    """Tests connection to the specified AI provider and measures latency."""
    provider = payload.get("provider", "gemini")
    api_key = payload.get("api_key")
    model = payload.get("model") or payload.get("model_name") or "gemini-2.5-flash"
    base_url = payload.get("base_url")

    # If api_key is empty or masked, fetch from saved settings
    if not api_key or api_key.startswith("AIzaSy...") or api_key.startswith("sk-...") or api_key == "***":
        settings = load_settings()
        key_name = f"{provider}_api_key" if f"{provider}_api_key" in settings else "gemini_api_key"
        api_key = settings.get(key_name, "")

    result = gemini_service.test_connection(
        provider=provider,
        api_key=api_key,
        model_name=model,
        base_url=base_url,
    )
    return result


@app.get("/api/settings")
async def get_app_settings():
    """Retrieves current application, theme, and AI model settings."""
    settings = load_settings()
    provider = settings.get("ai_provider", "gemini")
    key_name = f"{provider}_api_key" if f"{provider}_api_key" in settings else "gemini_api_key"
    current_key = settings.get(key_name, "")
    active_model = settings.get("ai_model") or settings.get("gemini_model", "gemini-2.5-flash")

    def mask_key(k: str) -> str:
        return (k[:6] + "..." + k[-4:]) if len(k) > 10 else ("***" if k else "")

    return {
        "ai_provider": provider,
        "ai_model": active_model,
        "gemini_model": active_model,
        "has_api_key": bool(current_key),
        "masked_api_key": mask_key(settings.get("gemini_api_key", "")),
        "masked_openai_key": mask_key(settings.get("openai_api_key", "")),
        "masked_anthropic_key": mask_key(settings.get("anthropic_api_key", "")),
        "masked_custom_key": mask_key(settings.get("custom_api_key", "")),
        "custom_base_url": settings.get("custom_base_url", "https://api.deepseek.com/v1"),
        "theme": settings.get("theme", "dark"),
    }


@app.put("/api/settings")
async def update_app_settings(payload: Dict[str, Any] = Body(...)):
    """Updates AI provider, model, API keys, and default theme."""
    settings = load_settings()

    if "ai_provider" in payload and payload["ai_provider"]:
        settings["ai_provider"] = str(payload["ai_provider"]).lower().strip()

    provider = settings.get("ai_provider", "gemini")
    key_field = f"{provider}_api_key" if f"{provider}_api_key" in settings else "gemini_api_key"

    # Accept specific provider keys or generic api_key
    new_key = (
        payload.get("api_key")
        or payload.get(key_field)
        or payload.get("openai_api_key")
        or payload.get("anthropic_api_key")
        or payload.get("custom_api_key")
        or payload.get("gemini_api_key")
    )
    if (
        new_key is not None
        and not new_key.startswith("AIzaSy...")
        and not new_key.startswith("sk-...")
        and not new_key.startswith("sk-ant-...")
        and new_key != "***"
    ):
        cleaned_key = new_key.strip()
        settings[key_field] = cleaned_key
        if provider == "gemini":
            settings["gemini_api_key"] = cleaned_key
            if cleaned_key:
                os.environ["GEMINI_API_KEY"] = cleaned_key
            else:
                os.environ.pop("GEMINI_API_KEY", None)
        elif provider == "openai":
            settings["openai_api_key"] = cleaned_key
            if cleaned_key:
                os.environ["OPENAI_API_KEY"] = cleaned_key
        elif provider == "claude":
            settings["anthropic_api_key"] = cleaned_key
            if cleaned_key:
                os.environ["ANTHROPIC_API_KEY"] = cleaned_key
        elif provider == "custom":
            settings["custom_api_key"] = cleaned_key
            if cleaned_key:
                os.environ["CUSTOM_API_KEY"] = cleaned_key

    model_val = payload.get("ai_model") or payload.get("gemini_model")
    if model_val:
        settings["ai_model"] = str(model_val).strip()
        settings["gemini_model"] = str(model_val).strip()

    if "custom_base_url" in payload:
        settings["custom_base_url"] = str(payload["custom_base_url"]).strip()

    if "theme" in payload and payload["theme"] in ["dark", "light"]:
        settings["theme"] = payload["theme"]

    save_settings(settings)

    # Dynamically reconfigure AI service
    active_key = settings.get(key_field, "")
    gemini_service.configure(
        api_key=active_key,
        model_name=settings.get("ai_model", "gemini-2.5-flash"),
        provider=settings.get("ai_provider", "gemini"),
        base_url=settings.get("custom_base_url"),
    )

    def mask_key(k: str) -> str:
        return (k[:6] + "..." + k[-4:]) if len(k) > 10 else ("***" if k else "")

    return {
        "success": True,
        "ai_provider": settings.get("ai_provider"),
        "ai_model": settings.get("ai_model"),
        "gemini_model": settings.get("ai_model"),
        "has_api_key": bool(active_key),
        "masked_api_key": mask_key(settings.get("gemini_api_key", "")),
        "masked_openai_key": mask_key(settings.get("openai_api_key", "")),
        "masked_anthropic_key": mask_key(settings.get("anthropic_api_key", "")),
        "masked_custom_key": mask_key(settings.get("custom_api_key", "")),
        "theme": settings.get("theme"),
    }


@app.get("/api/jobs")
async def list_jobs(
    q: Optional[str] = Query(None, description="Search keyword in title, company, or JD"),
    skill: Optional[str] = Query(None, description="Filter by tech skill"),
    has_cv: Optional[bool] = Query(None, description="Filter jobs with/without generated CV"),
    status: Optional[str] = Query(None, description="Filter by job status: saved, applied, interviewing, offered, rejected"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Retrieves paginated job listings with matching search criteria."""
    offset = (page - 1) * limit
    jobs, total = storage.get_jobs(query=q, skill=skill, has_cv=has_cv, status=status, limit=limit, offset=offset)
    total_pages = (total + limit - 1) // limit if total > 0 else 1

    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


@app.get("/api/jobs/{job_id}")
async def get_job_detail(job_id: int):
    """Retrieves full detail of a job by ID."""
    job = storage.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


class JobStatusRequest(BaseModel):
    status: str


@app.patch("/api/jobs/{job_id}/status")
async def update_job_status_endpoint(job_id: int, req: JobStatusRequest):
    """Updates job application status (saved, applied, interviewing, offered, rejected)."""
    valid_statuses = ["saved", "applied", "interviewing", "offered", "rejected"]
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Trạng thái không hợp lệ '{req.status}'. Chọn một trong: {', '.join(valid_statuses)}",
        )
    success = storage.update_job_status(job_id, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "job_id": job_id, "status": req.status}


@app.delete("/api/jobs/{job_id}")
async def delete_job_endpoint(job_id: int):
    """Deletes a job from the database, e.g. when rejected."""
    success = storage.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "message": f"Job #{job_id} đã được xóa thành công"}


class RecompileRequest(BaseModel):
    latex_code: str


SCRAPER_CONFIG_FILE = DATA_DIR / "scraper_config.json"


@app.get("/api/scraper/config")
async def get_scraper_config():
    """Returns dynamic scraper configuration."""
    cfg = {}
    if SCRAPER_CONFIG_FILE.exists():
        try:
            cfg = json.loads(SCRAPER_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    if not cfg:
        cfg = {
            "portals": {"itviec": True, "topdev": True, "topcv": True, "vietnamworks": True, "jobsgo": True, "indeed": True},
            "keywords": ["python", "backend", "data engineer", "intern", "fresher", "junior"],
            "levels": ["intern", "fresher", "junior"],
            "locations": ["Hồ Chí Minh", "Hà Nội", "Toàn quốc", "Remote"],
            "blacklisted_keywords": ["senior", "lead", "middle", "mid", "sr", "manager", "director"],
            "max_pages_per_portal": 3,
            "delay_seconds": 2.0,
            "deep_scrape": True,
        }
    # Ensure standard frontend keys and aliases are synchronized
    if "levels" not in cfg:
        cfg["levels"] = cfg.get("target_levels", ["intern", "fresher", "junior"])
    if "locations" not in cfg:
        cfg["locations"] = cfg.get("target_cities", ["Hồ Chí Minh", "Hà Nội", "Toàn quốc", "Remote"])
    if "blacklisted_keywords" not in cfg:
        cfg["blacklisted_keywords"] = cfg.get("unwanted_titles", ["senior", "lead", "manager"])
    if "max_pages_per_portal" not in cfg:
        cfg["max_pages_per_portal"] = 3
    if "delay_seconds" not in cfg:
        cfg["delay_seconds"] = 2.0
    return cfg


@app.put("/api/scraper/config")
async def update_scraper_config(cfg: Dict[str, Any] = Body(...)):
    """Saves dynamic scraper options."""
    if "levels" in cfg and "target_levels" not in cfg:
        cfg["target_levels"] = cfg["levels"]
    if "locations" in cfg and "target_cities" not in cfg:
        cfg["target_cities"] = cfg["locations"]
    if "blacklisted_keywords" in cfg and "unwanted_titles" not in cfg:
        cfg["unwanted_titles"] = cfg["blacklisted_keywords"]
    SCRAPER_CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "message": "Scraper configuration updated successfully"}


@app.post("/api/scraper/run")
async def run_scraper(background_tasks: BackgroundTasks):
    """Triggers job scraper either via Scraper Microservice or local subprocess."""
    scraper_url = os.getenv("SCRAPER_SERVICE_URL", "").rstrip("/")
    if scraper_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(f"{scraper_url}/api/scrape")
                return res.json()
        except Exception as e:
            logger.warning(f"Failed to trigger scraper microservice ({e}).")
            return {"success": False, "message": f"Không thể kết nối scraper microservice: {str(e)}"}
    else:
        async def _local_scrape():
            try:
                from main import main_orchestrator
                await main_orchestrator()
            except Exception as e:
                logger.error(f"Local scraper failed: {e}")
        background_tasks.add_task(_local_scrape)
        return {"success": True, "message": "Đã khởi chạy tiến trình cào việc làm cục bộ."}


@app.get("/api/scraper/status")
async def get_scraper_status():
    """Returns current crawler status from Scraper Microservice or local storage."""
    scraper_url = os.getenv("SCRAPER_SERVICE_URL", "").rstrip("/")
    if scraper_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{scraper_url}/api/scrape/status")
                return res.json()
        except Exception:
            pass
    return {"is_running": False, "status": "idle", "total_jobs_in_db": storage.count_total_jobs()}


@app.post("/api/jobs/{job_id}/tailor")
async def tailor_cv_for_job(
    job_id: int,
    template: str = Query("classic", description="LaTeX template: classic, modern, or compact"),
):
    """
    Executes the full automated ATS CV tailoring workflow:
    1. Fetches the job detail from SQLite.
    2. Loads candidate master PDF text + custom ATS & CV rules.
    3. Sends JD + rules to Gemini AI.
    4. Generates ATS-optimized LaTeX code using chosen template.
    5. Compiles LaTeX into PDF with Tectonic.
    6. Saves state in SQLite.
    """
    job = storage.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = load_profile()

    # Ensure master CV text from disk is loaded if present
    master_txt_file = DATA_DIR / "master_cv_text.txt"
    if master_txt_file.exists():
        disk_text = master_txt_file.read_text(encoding="utf-8").strip()
        if disk_text and not profile.get("master_cv_text"):
            profile["master_cv_text"] = disk_text

    logger.info(f"🤖 Triggering Gemini AI Tailoring for Job #{job_id}: {job.get('title')} at {job.get('company')} (Template: {template})")
    tailor_result = gemini_service.tailor_cv_for_job(job, profile)

    logger.info(f"📝 Generating LaTeX with tailored ATS content (Match Score: {tailor_result.match_score}%, Template: {template})...")
    latex_code = latex_engine.generate_latex_code(
        profile=profile,
        tailored_summary=tailor_result.tailored_summary,
        tailored_bullets=tailor_result.tailored_bullets,
        ats_keywords=tailor_result.missing_skills,
        template_name=template,
    )

    pdf_filename = f"cv_job_{job_id}.pdf"
    logger.info(f"🔨 Compiling PDF {pdf_filename} with Tectonic...")
    try:
        pdf_path = latex_engine.compile_pdf(latex_code, output_filename=pdf_filename)
    except Exception as e:
        logger.error(f"Failed to compile PDF for job #{job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"PDF Compilation error: {str(e)}")

    # Persist in SQLite
    storage.save_tailored_cv(
        job_id=job_id,
        match_score=tailor_result.match_score,
        missing_skills=tailor_result.missing_skills,
        tailored_summary=tailor_result.tailored_summary,
        tailored_bullets=tailor_result.tailored_bullets,
        latex_code=latex_code,
        pdf_path=str(pdf_path),
        status="completed",
    )

    has_master_cv = bool(profile.get("master_cv_text"))
    master_words = len(profile.get("master_cv_text", "").split()) if has_master_cv else 0

    return {
        "success": True,
        "job_id": job_id,
        "match_score": tailor_result.match_score,
        "match_analysis": tailor_result.match_analysis,
        "missing_skills": tailor_result.missing_skills,
        "tailored_summary": tailor_result.tailored_summary,
        "tailored_bullets": tailor_result.tailored_bullets,
        "latex_code": latex_code,
        "pdf_url": f"/api/jobs/{job_id}/pdf",
        "template_used": template,
        "used_master_cv": has_master_cv,
        "master_cv_words": master_words,
        "applied_rules": ["Quy tắc Đánh giá ATS", "Quy tắc Viết & Tối ưu CV"],
    }


@app.post("/api/jobs/{job_id}/recompile")
async def recompile_custom_latex(job_id: int, req: RecompileRequest):
    """Allows user to tweak the LaTeX code directly in the web UI and recompile the PDF."""
    job = storage.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    pdf_filename = f"cv_job_{job_id}.pdf"
    try:
        pdf_path = latex_engine.compile_pdf(req.latex_code, output_filename=pdf_filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"LaTeX compilation error: {str(e)}")

    storage.save_tailored_cv(
        job_id=job_id,
        match_score=job.get("match_score") or 80,
        missing_skills=job.get("missing_skills") or [],
        tailored_summary=job.get("tailored_summary") or "",
        tailored_bullets=job.get("tailored_bullets") or [],
        latex_code=req.latex_code,
        pdf_path=str(pdf_path),
        status="customized",
    )

    return {"success": True, "pdf_url": f"/api/jobs/{job_id}/pdf"}


@app.get("/api/jobs/{job_id}/pdf")
async def download_or_preview_pdf(job_id: int, download: bool = False):
    """Serves the generated PDF file for either preview (inline) or download."""
    pdf_filename = f"cv_job_{job_id}.pdf"
    pdf_path = CVS_DIR / pdf_filename

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="CV PDF has not been generated for this job yet.")

    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_filename,
        headers={"Content-Disposition": f"{disposition}; filename={pdf_filename}"},
    )


@app.get("/api/profile")
async def get_candidate_profile():
    """Returns the candidate's base profile."""
    return load_profile()


@app.put("/api/profile")
async def update_candidate_profile(profile: Dict[str, Any] = Body(...)):
    """Updates the candidate's base profile and ATS/CV rules."""
    save_profile(profile)
    return {"success": True, "message": "Profile and rules updated successfully"}


@app.post("/api/profile/upload-pdf")
async def upload_master_cv_pdf(file: UploadFile = File(...)):
    """
    Accepts an uploaded master CV PDF, saves it to data/master_cv.pdf,
    and extracts full raw text using pypdf for downstream Gemini AI tailoring.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Vui lòng tải lên đúng định dạng file .pdf!")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File PDF rỗng.")

    master_pdf_path = DATA_DIR / "master_cv.pdf"
    master_pdf_path.write_bytes(content)

    # Extract text with pypdf
    try:
        reader = pypdf.PdfReader(master_pdf_path)
        extracted_pages = []
        for idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_pages.append(page_text.strip())

        full_extracted_text = "\n\n--- Page Break ---\n\n".join(extracted_pages)
        page_count = len(reader.pages)
        word_count = len(full_extracted_text.split())

        # Save extracted text to plain text file
        (DATA_DIR / "master_cv_text.txt").write_text(full_extracted_text, encoding="utf-8")

        # Update profile
        profile = load_profile()
        profile["master_cv_filename"] = file.filename
        profile["master_cv_pages"] = page_count
        profile["master_cv_words"] = word_count
        profile["master_cv_text"] = full_extracted_text
        save_profile(profile)

        logger.info(f"📄 Successfully processed master CV PDF: {file.filename} ({page_count} pages, {word_count} words)")
        return {
            "success": True,
            "filename": file.filename,
            "pages": page_count,
            "word_count": word_count,
            "text_preview": full_extracted_text[:400] + ("..." if len(full_extracted_text) > 400 else ""),
        }
    except Exception as e:
        logger.error(f"Error reading uploaded PDF: {e}")
        raise HTTPException(status_code=400, detail=f"Không thể đọc nội dung PDF: {str(e)}")
