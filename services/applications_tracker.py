import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_logger
from services.storage import JobStorage

logger = get_logger("ApplicationsTracker")

APPLICATIONS_MD_PATH = Path("data/applications.md")
CAREER_OPS_APPLICATIONS_MD = Path("career_ops_workspace/applications.md")


def generate_applications_markdown(storage: Optional[JobStorage] = None) -> str:
    """
    Generates a clean, comprehensive markdown table of all tracked job applications,
    ATS match scores, tailored CV files, and links from SQLite.
    """
    store = storage or JobStorage()
    jobs, total = store.get_jobs(limit=1000)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Metrics
    total_jobs = len(jobs)
    tailored_count = sum(1 for j in jobs if j.get("cv_id"))
    avg_score = (
        round(sum(j.get("match_score", 0) for j in jobs if j.get("cv_id")) / tailored_count, 1)
        if tailored_count > 0
        else 0
    )

    md_lines: List[str] = [
        "# 📋 Bảng Theo Dõi Đơn Tuyển Dụng & Đánh Giá ATS (Applications Tracker)",
        f"*Cập nhật tự động bởi **FindMyBoss** lúc: `{now_str}`*\n",
        "## 📊 Thống Kê Tổng Quan",
        f"- **Tổng số việc đã thu thập:** `{total_jobs}`",
        f"- **Số CV đã được tối ưu ATS & biên dịch PDF:** `{tailored_count}`",
        f"- **Điểm ATS Match trung bình:** `{avg_score}%`\n",
        "## 📑 Danh Sách Chi Tiết Các Vị Trí",
        "| ID | Vị Trí Tuyển Dụng | Công Ty | Điểm ATS Match | Trạng Thái | Link Tuyển Dụng | CV Đính Kèm | Ngày Lưu |",
        "|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|",
    ]

    for j in jobs:
        jid = j.get("id", 0)
        title = (j.get("title") or "N/A").replace("|", "-")
        company = (j.get("company") or "N/A").replace("|", "-")
        link = j.get("link") or "#"
        status = j.get("status") or "saved"
        status_badge = {
            "saved": "💾 Lưu trữ",
            "applied": "🚀 Đã nộp",
            "interviewing": "🤝 Phỏng vấn",
            "offered": "🎉 Offer",
            "rejected": "❌ Từ chối",
        }.get(status.lower(), status)

        score = j.get("match_score")
        if score is not None and score > 0:
            badge = "🔥" if score >= 80 else ("⚡" if score >= 60 else "⚠️")
            score_str = f"{badge} **{score}%**"
        else:
            score_str = "*Chưa chấm*"

        pdf_path = j.get("pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            cv_cell = f"[`{Path(pdf_path).name}`]({Path(pdf_path).name})"
        else:
            cv_cell = "*Chưa tạo*"

        created_at = (j.get("created_at") or "")[:10]

        md_lines.append(
            f"| #{jid} | **{title[:45]}** | {company[:30]} | {score_str} | {status_badge} | [Xem JD]({link}) | {cv_cell} | {created_at} |"
        )

    content = "\n".join(md_lines) + "\n"

    # Save to data/applications.md
    APPLICATIONS_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPLICATIONS_MD_PATH.write_text(content, encoding="utf-8")

    # Also copy to career_ops_workspace if it exists
    if CAREER_OPS_APPLICATIONS_MD.parent.exists():
        CAREER_OPS_APPLICATIONS_MD.write_text(content, encoding="utf-8")

    logger.info(f"Updated applications.md with {total_jobs} jobs ({tailored_count} tailored CVs).")
    return content


def get_applications_markdown_path() -> Path:
    """Returns the path to applications.md, creating/updating it if needed."""
    if not APPLICATIONS_MD_PATH.exists():
        generate_applications_markdown()
    return APPLICATIONS_MD_PATH
