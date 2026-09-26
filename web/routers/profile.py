from typing import Any, Dict
from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from web.dependencies import profile_service

router = APIRouter(prefix="/api/profile", tags=["Profile"])


@router.get("")
async def get_candidate_profile():
    """Returns the candidate's base profile."""
    return profile_service.load_profile()


@router.put("")
async def update_candidate_profile(profile: Dict[str, Any] = Body(...)):
    """Updates the candidate's base profile and ATS/CV rules."""
    profile_service.save_profile(profile)
    return {"success": True, "message": "Profile and rules updated successfully"}


@router.post("/upload-pdf")
async def upload_master_cv_pdf(file: UploadFile = File(...)):
    """
    Accepts an uploaded master CV PDF, saves it to data/master_cv.pdf,
    and extracts full raw text using pypdf for downstream AI tailoring.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Vui lòng tải lên đúng định dạng file .pdf!")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File PDF rỗng.")

    try:
        result = profile_service.process_master_cv_pdf(content, file.filename)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể đọc nội dung PDF: {str(e)}")
