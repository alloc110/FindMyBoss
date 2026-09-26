import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
import pypdf

from config import get_logger

logger = get_logger("ProfileService")

DEFAULT_PROFILE: Dict[str, Any] = {
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


class ProfileService:
    """Manages candidate profile, master CV PDF uploads, and text extraction."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data")
        self.profile_file = self.data_dir / "profile.json"
        self.master_pdf_path = self.data_dir / "master_cv.pdf"
        self.master_text_path = self.data_dir / "master_cv_text.txt"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_profile(self) -> Dict[str, Any]:
        """Loads candidate profile from JSON file with disk master CV text fallback."""
        profile = dict(DEFAULT_PROFILE)
        if self.profile_file.exists():
            try:
                saved = json.loads(self.profile_file.read_text(encoding="utf-8"))
                profile.update(saved)
            except Exception as e:
                logger.warning(f"Error reading profile.json: {e}")

        # Ensure master CV text from disk is loaded if present and not in profile
        if self.master_text_path.exists():
            disk_text = self.master_text_path.read_text(encoding="utf-8").strip()
            if disk_text and not profile.get("master_cv_text"):
                profile["master_cv_text"] = disk_text

        return profile

    def save_profile(self, profile_data: Dict[str, Any]) -> None:
        """Saves candidate profile to disk atomically."""
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(self.data_dir), prefix="profile_", suffix=".tmp")
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self.profile_file))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def process_master_cv_pdf(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Saves uploaded master CV PDF, extracts full raw text using pypdf,
        and updates the candidate profile.
        """
        if not content:
            raise ValueError("File PDF rỗng.")

        self.master_pdf_path.write_bytes(content)

        reader = pypdf.PdfReader(self.master_pdf_path)
        extracted_pages = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_pages.append(page_text.strip())

        full_extracted_text = "\n\n--- Page Break ---\n\n".join(extracted_pages)
        page_count = len(reader.pages)
        word_count = len(full_extracted_text.split())

        # Save extracted text to plain text file
        self.master_text_path.write_text(full_extracted_text, encoding="utf-8")

        # Update profile
        profile = self.load_profile()
        profile["master_cv_filename"] = filename
        profile["master_cv_pages"] = page_count
        profile["master_cv_words"] = word_count
        profile["master_cv_text"] = full_extracted_text
        self.save_profile(profile)

        logger.info(f"📄 Successfully processed master CV PDF: {filename} ({page_count} pages, {word_count} words)")
        return {
            "success": True,
            "filename": filename,
            "pages": page_count,
            "word_count": word_count,
            "text_preview": full_extracted_text[:400] + ("..." if len(full_extracted_text) > 400 else ""),
        }
