import re
from typing import Any, Dict, List, Optional, Tuple

from core.config import config
from models.Job import Job


def is_title_blacklisted(title: str, exp: str, blacklist: List[str]) -> Tuple[bool, Optional[str]]:
    """Checks if job title or experience contains blacklisted keywords."""
    title_lower = (title or "").lower()
    exp_lower = (exp or "").lower()

    for b_kw in blacklist:
        if len(b_kw) <= 3 and b_kw.isalpha():
            if re.search(rf"\b{re.escape(b_kw)}\b", title_lower) or re.search(rf"\b{re.escape(b_kw)}\b", exp_lower):
                return True, b_kw
        else:
            if b_kw in title_lower or b_kw in exp_lower:
                return True, b_kw

    return False, None


def is_location_matched(address: str, locations: List[str]) -> bool:
    """Checks if job address matches any target locations."""
    if not locations:
        return True

    addr_lower = (address or "").lower()
    if not addr_lower or addr_lower in ["chưa rõ", "n/a", "deal"] or any(k in addr_lower for k in ["toàn quốc", "remote"]):
        return True

    for loc in locations:
        loc_clean = (loc or "").lower().strip()
        if not loc_clean:
            continue
        if loc_clean in addr_lower:
            return True
        if loc_clean in ["hồ chí minh", "hcm", "tp.hcm", "tphcm"] and any(k in addr_lower for k in ["hồ chí minh", "hcm", "sài gòn"]):
            return True
        if loc_clean in ["hà nội", "hn"] and any(k in addr_lower for k in ["hà nội", "hn"]):
            return True

    return False


def is_level_matched(title: str, exp: str, levels: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Checks if job matches targeted experience levels (intern, fresher, junior, middle, senior).
    """
    if not levels:
        return True, None

    title_lower = (title or "").lower()
    exp_lower = (exp or "").lower()
    combined = f"{title_lower} {exp_lower}"

    level_set = {lvl.strip().lower() for lvl in levels}

    # If all standard levels are selected, allow all
    if {"intern", "fresher", "junior", "middle", "senior"}.issubset(level_set):
        return True, None

    # 1. Block Senior / Lead / Manager if Senior was NOT selected
    if "senior" not in level_set:
        for s_word in ["senior", "sr.", "sr ", "lead", "trưởng", "quản lý", "manager", "director", "architect", "chuyên gia"]:
            if re.search(rf"\b{re.escape(s_word)}\b", combined) or s_word in title_lower:
                return False, f"Cấp bậc '{s_word}' không nằm trong tùy chọn cấp bậc bạn chọn"

    # 2. Block Middle (3-5 years) if Middle was NOT selected
    if "middle" not in level_set:
        mid_indicators = ["middle", "mid-level", "mid level", "3-5 năm", "4 năm", "5 năm", "3+ năm", "4+ năm"]
        if any(m in combined for m in mid_indicators):
            return False, "Cấp bậc Middle (3-5 năm) không nằm trong tùy chọn bạn chọn"

    # 3. If user selected ONLY intern
    if level_set == {"intern"}:
        intern_keywords = ["intern", "thực tập", "trainee", "học việc", "apprentice"]
        if not any(k in combined for k in intern_keywords):
            return False, "Tin tuyển dụng không dành riêng cho Thực tập sinh (Intern)"

    # 4. If user selected ONLY fresher
    if level_set == {"fresher"}:
        fresher_keywords = ["fresher", "mới tốt nghiệp", "chưa có kinh nghiệm", "không yêu cầu kinh nghiệm", "0-1 năm", "dưới 1 năm"]
        if not any(k in combined for k in fresher_keywords):
            return False, "Tin tuyển dụng không dành riêng cho Fresher / Mới tốt nghiệp"

    # 5. If user selected ONLY intern & fresher (no junior)
    if level_set.issubset({"intern", "fresher"}):
        entry_keywords = [
            "intern", "thực tập", "trainee", "fresher", "mới tốt nghiệp",
            "0-1", "dưới 1", "không yêu cầu", "chưa có kinh nghiệm", "học việc"
        ]
        has_entry = any(k in combined for k in entry_keywords)
        has_junior = any(j in combined for j in ["junior", "1-2 năm", "1-3 năm", "2 năm", "3 năm"])
        if not has_entry and has_junior:
            return False, "Yêu cầu kinh nghiệm Junior/Middle cao hơn mức Intern/Fresher đã chọn"

    return True, None


ROLE_KEYWORDS: Dict[str, List[str]] = {
    "backend": [
        "backend", "back-end", "back end", "python", "node", "nodejs", "java", "golang",
        "c#", ".net", "dotnet", "php", "ruby", "django", "fastapi", "spring", "laravel",
        "kỹ sư backend", "lập trình viên backend"
    ],
    "frontend": [
        "frontend", "front-end", "front end", "react", "reactjs", "vue", "vuejs",
        "angular", "nextjs", "javascript", "typescript", "html/css", "web developer",
        "lập trình viên frontend"
    ],
    "fullstack": [
        "fullstack", "full-stack", "full stack", "lập trình viên fullstack"
    ],
    "da": [
        "data analyst", "data analytics", "phân tích dữ liệu", "bi analyst",
        "business intelligence", "sql analyst", "power bi", "powerbi", "tableau", "da intern", "da fresher"
    ],
    "de": [
        "data engineer", "data engineering", "kỹ sư dữ liệu", "etl", "big data",
        "data pipeline", "spark", "airflow", "de intern", "de fresher"
    ],
    "ai_ml": [
        "machine learning", "ai engineer", "ai researcher", "data scientist",
        "deep learning", "nlp", "computer vision", "llm", "trí tuệ nhân tạo", "khoa học dữ liệu"
    ],
    "mobile": [
        "mobile", "android", "ios", "flutter", "react native", "swift", "kotlin",
        "lập trình di động", "lập trình mobile"
    ],
    "tester": [
        "tester", "qa", "qc", "kiểm thử", "quality assurance", "test engineer",
        "automation test", "manual test", "kiểm thử phần mềm"
    ],
    "devops": [
        "devops", "cloud", "sre", "infrastructure", "system engineer",
        "kỹ sư hệ thống", "aws", "kubernetes", "k8s"
    ],
}


def is_role_matched(title: str, full_jd: str, roles: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Checks if job matches any of the targeted role specializations (e.g. backend, da, de, tester, etc.).
    """
    if not roles:
        return True, None

    normalized_roles = [r.strip().lower() for r in roles if r and r.strip()]
    if not normalized_roles or "all" in normalized_roles:
        return True, None

    title_lower = (title or "").lower()
    full_sample = ((full_jd or "")[:500]).lower()
    combined = f"{title_lower} {full_sample}"

    for role_key in normalized_roles:
        keywords = ROLE_KEYWORDS.get(role_key, [role_key])
        for kw in keywords:
            if kw in title_lower or kw in combined:
                return True, None

    role_labels = [r.upper() for r in normalized_roles]
    return False, f"Vị trí không thuộc Role mục tiêu bạn chọn ({', '.join(role_labels)})"


def filter_jobs_by_web_config(
    jobs: List[Job],
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Job], List[Tuple[Job, str]]]:
    """
    Applies real-time web filtering rules loaded directly from data/scraper_config.json:
    1. Blacklist (Unwanted titles/keywords: e.g. Senior, Lead, Manager, Trưởng phòng)
    2. Location filter (e.g. Hồ Chí Minh, Hà Nội, Remote)
    3. Experience Level filter (e.g. Intern, Fresher, Junior)
    4. Target Role filter (e.g. Backend, DA, DE, Tester, Mobile)
    Returns:
        passed_jobs: list of qualified jobs
        rejected_jobs: list of (job, reason) tuples
    """
    if not cfg:
        return jobs, []

    # 1. Compile Blacklist (combine blacklisted_keywords & unwanted_titles with fallback)
    raw_blacklist = cfg.get("blacklisted_keywords") or cfg.get("unwanted_titles") or list(config.unwanted_titles)
    blacklist = [kw.strip().lower() for kw in raw_blacklist if kw and kw.strip()]

    # 2. Locations
    raw_locations = cfg.get("locations") or cfg.get("target_cities") or []
    locations = [loc.strip().lower() for loc in raw_locations if loc and loc.strip()]

    # 3. Target Levels
    raw_levels = cfg.get("levels") or cfg.get("target_levels") or []
    levels = [lvl.strip().lower() for lvl in raw_levels if lvl and lvl.strip()]

    # 4. Target Roles
    raw_roles = cfg.get("roles") or []
    roles = [r.strip().lower() for r in raw_roles if r and r.strip()]

    passed_jobs: List[Job] = []
    rejected_jobs: List[Tuple[Job, str]] = []

    for job in jobs:
        # Rule 1: Check Blacklist
        is_blocked, matched_kw = is_title_blacklisted(job.title, job.exp or "", blacklist)
        if is_blocked and matched_kw:
            rejected_jobs.append((job, f"Chứa từ khóa loại trừ: '{matched_kw}'"))
            continue

        # Rule 2: Check Location
        if locations and not is_location_matched(job.address, locations):
            rejected_jobs.append((job, f"Địa điểm '{job.address}' không thuộc bộ lọc ({', '.join(locations)})"))
            continue

        # Rule 3: Check Level
        if levels:
            is_matched, level_reason = is_level_matched(job.title, job.exp or "", levels)
            if not is_matched and level_reason:
                rejected_jobs.append((job, level_reason))
                continue

        # Rule 4: Check Role
        if roles and "all" not in roles:
            is_role_ok, role_reason = is_role_matched(job.title, job.full_jd_raw or job.description or "", roles)
            if not is_role_ok and role_reason:
                rejected_jobs.append((job, role_reason))
                continue

        passed_jobs.append(job)

    return passed_jobs, rejected_jobs

