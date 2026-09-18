from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Job:
    title: str
    company: str
    link: str
    address: str = "Hồ Chí Minh"
    exp: Optional[str] = None
    salary: Optional[str] = "Deal"
    posted_date: Optional[str] = "N/A"
    image: Optional[str] = None
    time: Optional[str] = None

    # Full data fields for future AI / CV tailoring
    skills: List[str] = field(default_factory=list)
    description: Optional[str] = None       # Full job role & responsibilities
    requirements: Optional[str] = None      # Full candidate requirements
    benefits: Optional[str] = None          # Full company benefits
    full_jd_raw: Optional[str] = None       # 100% full raw text of job post for LLM prompts

    def to_dict(self) -> Dict[str, Any]:
        """Converts Job dataclass to dict for JSON/database serialization."""
        return asdict(self)

    def to_discord_embed(self) -> Dict[str, Any]:
        """
        Formats a clean, lightweight Discord Embed notification.
        Does NOT include bulky JD text (as requested), keeping only quick-glance info.
        """
        desc_lines = [
            f"🏢 **Công ty:** {self.company}",
            f"💰 **Lương:** {self.salary or 'Thoả thuận'}",
            f"⏳ **Kinh nghiệm:** {self.exp or 'Chưa rõ'}",
            f"📍 **Địa điểm:** {self.address}",
            f"📅 **Ngày đăng:** {self.posted_date or 'N/A'}",
        ]

        embed: Dict[str, Any] = {
            "title": self.title[:256] if self.title else "Job Alert",
            "url": self.link if self.link and self.link != "N/A" else None,
            "color": 3066993,  # Emerald Green
            "description": "\n".join(desc_lines),
            "fields": [],
            "footer": {
                "text": "FindMyBoss 🎯 • 💾 Đã lưu full JD vào hệ thống!"
            },
        }

        # Include Tech Stack badges for quick review
        if self.skills:
            skills_formatted = " ".join([f"`{s.strip()}`" for s in self.skills[:10] if s.strip()])
            if skills_formatted:
                embed["fields"].append({
                    "name": "🛠️ Tech Stack",
                    "value": skills_formatted[:1024],
                    "inline": False,
                })

        if self.image and self.image.startswith("http"):
            embed["thumbnail"] = {"url": self.image}

        if self.time:
            embed["timestamp"] = self.time

        return embed