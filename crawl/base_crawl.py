import requests
from playwright.async_api import async_playwright
from models.Job import Job
import time
class JobScraper:
    def __init__(self, page = None, url = None, webhook_url  = None):
        self.page = page
        self.url = url
        self.webhook_url = webhook_url
        
    def send_to_discord(self, job_data):
        color = 3066993 
        payload = {
            "username": "Find My Boss Bot",
            "avatar_url": "https://www.shutterstock.com/image-vector/beautiful-mole-illustration-vector-art-600nw-2721821771.jpg",
            "embeds": [
                {
                    "title": job_data.title,
                    "url": job_data.link,
                    "color": 3066993,
                    # Dùng f-string để gộp mọi thứ vào description
                    "description": (
                        f"🏢 **Công ty:** {job_data.company}\n"
                        f"💰 **Lương:** {job_data.salary}\n"
                        f"⏳ **Kinh nghiệm:** {job_data.exp}\n"
                        f"📍 **Địa điểm:** {job_data.address}\n"
                        f"📅 **Ngày đăng:** {job_data.posted_date}"
                    ),
                    "thumbnail": {
                        "url": job_data.image if job_data.image else ""
                    },
                    "footer": {
                        "text": "Data Zoo 🦫 • ⚡ Phản hồi nhanh để chiếm ưu thế! •"
                    }
                }
            ]
        }
        response = requests.post(self.webhook_url, json=payload)
        time.sleep(1) # Nghỉ nhẹ 1 giâ

    
    def print_jobs(self, jobs):
        for i, job in enumerate(jobs, 1):
            print(f"🔹 [{i}] {job.title.upper()}")
            print(f"   🏢 Công ty:   {job.company}")
            print(f"   📍 Địa điểm:  {job.address}")
            print(f"   ⏳ Kinh nghiệm: {job.exp}")
            print(f"   💰 Lương:     {job.salary}")
            print(f"   🕒 Đăng cách đây: {job.posted_date}")
            print(f"   🔗 Link:      {job.link}")
            print(f"   🖼️ Logo:      {job.image}")
            print(f"{'-'*60}")