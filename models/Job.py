import urllib.parse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional


def _detect_portal(url: Optional[str]) -> str:
    """Infers job portal source from URL."""
    if not url or url == "N/A":
        return "Tuyển dụng"
    url_lower = url.lower()
    if "topdev.vn" in url_lower:
        return "TopDev"
    if "itviec.com" in url_lower:
        return "ITviec"
    if "vietnamworks.com" in url_lower:
        return "VietnamWorks"
    if "indeed.com" in url_lower:
        return "Indeed"
    if "linkedin.com" in url_lower:
        return "LinkedIn"
    return "Tuyển dụng"


def _detect_role_tag(title: Optional[str], skills: List[str]) -> str:
    """Extracts a concise role or technology badge for footer display."""
    if not title:
        return skills[0] if skills else "Tech"
    title_lower = title.lower()
    common_roles = [
        ("ai engineer", "AI Engineer"),
        ("machine learning", "AI/ML Engineer"),
        ("data engineer", "Data Engineer"),
        ("data analyst", "Data Analyst"),
        ("data scientist", "Data Scientist"),
        ("backend", "Backend Engineer"),
        ("frontend", "Frontend Engineer"),
        ("fullstack", "Fullstack Developer"),
        ("devops", "DevOps Engineer"),
        ("cloud", "Cloud Engineer"),
        ("security", "Security Engineer"),
        ("qa", "QA / Tester"),
        ("tester", "QA / Tester"),
        ("mobile", "Mobile Developer"),
        ("software engineer", "Software Engineer"),
    ]
    for key, label in common_roles:
        if key in title_lower:
            return label
    if skills:
        return skills[0]
    return "Tech"


@dataclass
class Job:
    """Represents a job opportunity scraped from Vietnamese tech job portals."""

    title: str
    company: str
    link: str
    address: str = "Hồ Chí Minh"
    exp: Optional[str] = None
    salary: Optional[str] = "Deal"
    posted_date: Optional[str] = "N/A"
    image: Optional[str] = None
    time: Optional[str] = None

    # Full data fields for AI ATS analysis & CV tailoring
    skills: List[str] = field(default_factory=list)
    description: Optional[str] = None       # Full job role & responsibilities
    requirements: Optional[str] = None      # Full candidate requirements
    benefits: Optional[str] = None          # Full company benefits
    full_jd_raw: Optional[str] = None       # 100% full raw text of job post for LLM prompts

    # Career-Ops & Tailoring metadata
    match_score: Optional[int] = None
    tailored_summary: Optional[str] = None
    cv_generated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Converts Job dataclass to dict for JSON/database serialization."""
        return asdict(self)

    def to_discord_embed(self) -> Dict[str, Any]:
        """
        Formats a clean, modern Discord Embed matching the Bot Viên layout:
        - Title: clickable link
        - Description: 🏛️ {company} · 📍 {address} (\n\n🔗 [Xem chi tiết]({link}))
        - Fields (3 inline columns): 💰 Mức lương | 🎯 ATS Score / Level | 📅 Ngày đăng
        - Thumbnail: Company / Portal logo
        - Footer: FindMyBoss · {role} · Nguồn: {portal} · React ✅ nhận thông báo · ❌ tắt
        """
        # Description Line 1: 🏛️ {company} · 📍 {address} (· ⏳ {exp} if ATS score evaluated)
        company_name = self.company if self.company and self.company != "N/A" else "Tuyển dụng"
        desc_parts = [f"🏛️ {company_name}"]
        if self.address and self.address != "N/A":
            desc_parts.append(f"📍 {self.address}")

        if self.match_score is not None and self.exp and self.exp not in ["N/A", "Chưa rõ", ""]:
            desc_parts.append(f"⏳ {self.exp}")

        desc_line1 = " · ".join(desc_parts)

        # Description Line 2: 🔗 Xem chi tiết (Markdown link)
        desc_line2 = (
            f"🔗 [Xem chi tiết]({self.link})"
            if self.link and self.link != "N/A"
            else ""
        )

        embed_desc = f"{desc_line1}\n\n{desc_line2}" if desc_line2 else desc_line1

        # Base Embed Color:
        # Default: Bot Viên Blue (0x1E88E5 / 2001125)
        # ATS evaluated: 🟢 Tốt (>=80), 🟡 Có thể (60-79), 🔴 Không hợp (<60)
        embed_color = 2001125  # Modern Blue

        fields: List[Dict[str, Any]] = [
            {
                "name": "💰 Mức lương",
                "value": self.salary if self.salary and self.salary != "N/A" else "Thoả thuận",
                "inline": True,
            },
            {
                "name": "🎯 Level",
                "value": self.exp if self.exp and self.exp != "N/A" else "Không giới hạn",
                "inline": True,
            },
        ]

        if self.match_score is not None:
            if self.match_score >= 80:
                score_badge = "🟢 Tốt"
                embed_color = 3066993  # Green (0x2ECC71)
            elif self.match_score >= 60:
                score_badge = "🟡 Có thể"
                embed_color = 15844367  # Yellow (0xF1C40F)
            else:
                score_badge = "🔴 Không hợp"
                embed_color = 15158332  # Red (0xE74C3C)

            fields.append({
                "name": "🎯 ATS Score",
                "value": f"**{self.match_score}%** ({score_badge})",
                "inline": True,
            })

        portal = _detect_portal(self.link)
        role_tag = _detect_role_tag(self.title, self.skills)
        footer_text = f"FindMyBoss · {role_tag} · Nguồn: {portal} · React ✅ nhận thông báo · ❌ tắt"

        embed: Dict[str, Any] = {
            "title": self.title[:256] if self.title else "Job Alert",
            "url": self.link if self.link and self.link != "N/A" else None,
            "color": embed_color,
            "description": embed_desc,
            "fields": fields,
            "footer": {
                "text": footer_text,
            },
        }

        # Square top-right thumbnail (employer logo or high-res portal fallback)
        logo_url = None
        if self.image and self.image.startswith("http") and not self.image.lower().endswith(".svg"):
            logo_url = self.image
        else:
            # Fallback 1: Dynamic company branding avatar (renders company initials crisply)
            if self.company and self.company.lower() not in ["n/a", "unknown", "tuyển dụng", "công ty tuyển dụng", "doanh nghiệp tuyển dụng"]:
                safe_comp = urllib.parse.quote(self.company.strip())
                logo_url = f"https://ui-avatars.com/api/?name={safe_comp}&background=1E88E5&color=fff&size=256&bold=true&font-size=0.4"
            elif self.link and self.link != "N/A":
                portal_logos = {
                    "TopDev": "https://topdev.vn/v4/assets/images/topdev-logo.png",
                    "ITviec": "https://itviec.com/favicon-96x96.png",
                    "VietnamWorks": "https://images.vietnamworks.com/logo/vnw_logo.png",
                    "Indeed": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fa/Indeed_logo.png/600px-Indeed_logo.png",
                    "LinkedIn": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/LinkedIn_logo_initials.png/600px-LinkedIn_logo_initials.png",
                }
                logo_url = portal_logos.get(portal)

        if logo_url:
            embed["thumbnail"] = {"url": logo_url}

        if self.time:
            embed["timestamp"] = self.time
        else:
            embed["timestamp"] = datetime.now(timezone.utc).isoformat()

        return embed
