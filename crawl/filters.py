import re
from typing import Any, Dict, List, Optional, Tuple

from config import config
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


def filter_jobs_by_web_config(
    jobs: List[Job],
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Job], List[Tuple[Job, str]]]:
    """
    Applies real-time web filtering rules loaded directly from data/scraper_config.json:
    1. Blacklist (Unwanted titles/keywords: e.g. Senior, Lead, Manager, Trưởng phòng)
    2. Location filter (e.g. Hồ Chí Minh, Hà Nội, Remote)
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

        passed_jobs.append(job)

    return passed_jobs, rejected_jobs
