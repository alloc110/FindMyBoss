from dataclasses import dataclass
from datetime import datetime

@dataclass
class Job:
    title: str
    company: str
    link: str
    address: str
    exp: str
    salary: str 
    posted_date: str
    image: str 

    def to_discord_embed(self):
        return {
            "title": f"🚀 {self.title}",
            "description": f"**Công ty:** {self.company}\n**Lương:** {self.salary}",
            "LOGO": self.link, # Sử dụng link làm logo tạm thời
            "url": self.link,
            "color": 5814783, # Màu xanh dương
            "footer": {"text": f"Nguồn: {self.posted_date}"},
            "image": {"url": self.image}
        }
   