"""
CV Tailor & JD Matching Service.
Prepares full JD data and prompts for downstream AI / LLM CV tailoring.
"""

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


def load_scraped_jobs(data_path: str = "data/jobs.jsonl") -> Iterator[Dict[str, Any]]:
    """Yields parsed job records from SQLite database or fallback to JSONL dataset."""
    db_file = Path("data/jobs.db")
    if data_path == "data/jobs.jsonl" and db_file.exists():
        from services.storage import JobStorage

        storage = JobStorage(db_path=str(db_file), legacy_jsonl="")
        jobs, _ = storage.get_jobs(limit=1000)
        for j in reversed(jobs):
            yield j
        return

    path = Path(data_path)
    if not path.exists():
        return

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except Exception:
                    continue


def get_latest_jobs(limit: int = 10, data_path: str = "data/jobs.jsonl") -> List[Dict[str, Any]]:
    """Returns the most recent scraped jobs with full JD data."""
    all_jobs = list(load_scraped_jobs(data_path))
    return all_jobs[-limit:] if all_jobs else []


def build_cv_tailor_prompt(user_cv_text: str, job: Dict[str, Any]) -> str:
    """
    Constructs an optimized prompt for an LLM (Gemini, Claude, GPT, Ollama)
    to tailor the candidate's CV specifically for the scraped Job Description.
    """
    title = job.get("title", "Software Engineer")
    company = job.get("company", "Company")
    skills = ", ".join(job.get("skills", []))
    requirements = job.get("requirements") or "Xem chi tiết trong full JD bên dưới."
    full_jd = job.get("full_jd_raw") or job.get("description") or "N/A"

    prompt = f"""
Bạn là chuyên gia tư vấn tuyển dụng và tối ưu hoá CV (CV Tailoring & ATS Optimization Expert).
Nhiệm vụ của bạn là phân tích Job Description (JD) được cào từ hệ thống và điều chỉnh CV của ứng viên sao cho phù hợp nhất với vị trí này, tối ưu từ khóa ATS nhưng vẫn giữ tính trung thực.

---
### 1. THÔNG TIN VỊ TRÍ TUYỂN DỤNG (SCRAPED JD):
- **Vị trí:** {title}
- **Công ty:** {company}
- **Tech Stack / Kỹ năng:** {skills if skills else 'Tham khảo trong JD'}
- **Yêu cầu chính:**
{requirements}

**Full JD Raw Content:**
```
{full_jd[:3000]}
```

---
### 2. CV HIỆN TẠI CỦA ỨNG VIÊN:
```
{user_cv_text.strip()}
```

---
### 3. YÊU CẦU ĐẦU RA (OUTPUT):
1. **Đánh giá mức độ phù hợp (Match Score %):** Phân tích điểm mạnh và khoảng trống kỹ năng giữa CV và JD.
2. **Từ khóa quan trọng cần bổ sung (ATS Keywords):** Những kỹ năng/thuật ngữ kỹ thuật trong JD còn thiếu trong CV.
3. **Các Bullet Points được viết lại (Tailored Experience Bullets):** Viết lại 3-5 gạch đầu dòng kinh nghiệm trong CV theo công thức STAR / Google XYZ (Accomplished [X], measured by [Y], by doing [Z]), tập trung vào tech stack của JD này.
4. **Tóm tắt chuyên môn (Tailored Professional Summary):** Viết đoạn tóm tắt 3-4 câu phù hợp nhất với vị trí {title} tại {company}.
"""
    return prompt.strip()
