from typing import Any, Dict
from models.schemas import GeminiTailorResponse


class HeuristicTailorEngine:
    """
    Intelligent offline fallback mode when no API Key is yet configured or network is unreachable.
    Analyzes overlaps between candidate profile and JD skills.
    """

    @staticmethod
    def generate(job: Dict[str, Any], profile: Dict[str, Any]) -> GeminiTailorResponse:
        jd_skills = set(s.lower() for s in job.get("skills", []))
        user_skills = set()

        skills_dict = profile.get("skills", {})
        if isinstance(skills_dict, dict):
            for sublist in skills_dict.values():
                if isinstance(sublist, list):
                    for s in sublist:
                        user_skills.add(s.lower())

        master_cv_text = profile.get("master_cv_text", "").lower()
        matched = []
        missing = []

        for skill in jd_skills:
            if skill in user_skills or (master_cv_text and skill in master_cv_text):
                matched.append(skill.title())
            else:
                missing.append(skill.title())

        total = len(jd_skills)
        score = int((len(matched) / total * 35) + 60) if total > 0 else 75
        score = min(score, 95)

        title = job.get("title", "Kỹ sư phần mềm")
        company = job.get("company", "Công ty")

        summary = (
            f"Kỹ sư giàu nhiệt huyết với nền tảng vững chắc và thế mạnh kỹ thuật phù hợp cho vị trí {title} tại {company}. "
            f"Thành thạo trong các công nghệ cốt lõi {', '.join(matched[:3]) if matched else 'phát triển hệ thống'}, "
            f"luôn chủ động cập nhật các kỹ năng hiện đại và tối ưu hóa giải pháp theo chuẩn mực chất lượng cao."
        )

        bullets = [
            f"Thiết kế và tối ưu kiến trúc phần mềm sử dụng {matched[0] if matched else 'Python/FastAPI'}, cải thiện 30% hiệu năng và thông lượng xử lý hệ thống.",
            f"Hợp tác liên chức năng để chuẩn hóa quy trình triển khai và tích hợp liên tục (CI/CD), rút ngắn 40% chu kỳ phát hành sản phẩm.",
            f"Nghiên cứu áp dụng các công nghệ mục tiêu ({', '.join(missing[:2]) if missing else 'Containerization & Cloud'}), nâng cao tính mở rộng và khả năng giám sát vận hành.",
        ]

        analysis = (
            f"Hồ sơ đáp ứng tốt {len(matched)}/{total} kỹ năng trọng tâm của JD ({', '.join(matched[:3]) if matched else 'các kỹ năng cơ bản'}). "
            f"Cần lưu ý bổ sung hoặc nhấn mạnh kinh nghiệm với: {', '.join(missing[:3]) if missing else 'các công cụ quản lý dự án'} để đạt điểm tuyệt đối."
        )

        return GeminiTailorResponse(
            match_score=score,
            match_analysis=analysis,
            missing_skills=missing[:5],
            tailored_summary=summary,
            tailored_bullets=bullets,
        )
