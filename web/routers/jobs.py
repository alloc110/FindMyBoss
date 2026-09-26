from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from config import get_logger
from models.schemas import JobStatusRequest, RecompileRequest, VALID_JOB_STATUSES
from web.dependencies import CVS_DIR, gemini_service, latex_engine, profile_service, storage

logger = get_logger("JobsRouter")

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get("")
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


@router.get("/{job_id}")
async def get_job_detail(job_id: int):
    """Retrieves full detail of a job by ID."""
    job = storage.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}/status")
async def update_job_status_endpoint(job_id: int, req: JobStatusRequest):
    """Updates job application status (saved, applied, interviewing, offered, rejected)."""
    if req.status not in VALID_JOB_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Trạng thái không hợp lệ '{req.status}'. Chọn một trong: {', '.join(VALID_JOB_STATUSES)}",
        )
    success = storage.update_job_status(job_id, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "job_id": job_id, "status": req.status}


@router.delete("/{job_id}")
async def delete_job_endpoint(job_id: int):
    """Deletes a job from the database, e.g. when rejected."""
    success = storage.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "message": f"Job #{job_id} đã được xóa thành công"}


@router.post("/{job_id}/tailor")
async def tailor_cv_for_job(
    job_id: int,
    template: str = Query("classic", description="LaTeX template: classic, modern, or compact"),
):
    """
    Executes the full automated ATS CV tailoring workflow:
    1. Fetches the job detail from SQLite.
    2. Loads candidate master PDF text + custom ATS & CV rules.
    3. Sends JD + rules to AI service.
    4. Generates ATS-optimized LaTeX code using chosen template.
    5. Compiles LaTeX into PDF with Tectonic.
    6. Saves state in SQLite.
    """
    job = storage.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    profile = profile_service.load_profile()

    logger.info(f"🤖 Triggering AI Tailoring for Job #{job_id}: {job.get('title')} at {job.get('company')} (Template: {template})")
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


@router.post("/{job_id}/recompile")
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


@router.get("/{job_id}/pdf")
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
