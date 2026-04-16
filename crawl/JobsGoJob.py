from crawl.base_crawl import JobScraper
from playwright.async_api import async_playwright
import asyncio
import models.Job as Job
import requests
import random
class JobsGoJob(JobScraper):
    def __init__(self, page, webhook_url):
        super().__init__(page = page, webhook_url = webhook_url)
        self.roles = {
                        "Software Engineer": "https://jobsgo.vn/viec-lam-lap-trinh-phat-trien-phan-mem-tai-ho-chi-minh.html?sort=created",
                        "Data Engineer": "https://jobsgo.vn/viec-lam-du-lieu-ai-hoc-may-tai-ho-chi-minh.html?sort=created",
                    }
        
        self.exp = ["khong-can-kinh-nghiem","duoi-1-nam-kinh-nghiem","1-2-nam-kinh-nghiem"]# 1: Không yêu cầu, 2: Dưới 1 năm, 3: 1 năm
        self.scraped_links = set() # Dùng để lưu các link đã cào được, tránh trùng lặp khi crawl nhiều trang
        
        
    async def crawl(self):
        jobs = []
       
        container = self.page.locator(".job-list")
        cards = await container.locator(".job-card").all()
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links:
                self.scraped_links.add(job.link)
                jobs.append(job)
                                
        return jobs
    
    async def parse_card_detail(self, card):
        
        title = await card.locator(".job-title").inner_text()
        company = await card.locator(".company-title").inner_text()
        link = await card.locator("a.text-decoration-none").get_attribute("href")
            

        badges = card.locator(".badge-custom")
        if await badges.count() >= 3:
            posted_date = await badges.nth(2).inner_text()
        else:
            posted_date = "N/A" 
              
        image = await card.locator(".image-wrapper img").get_attribute("src")
        # Lấy giá trị từ thuộc tính data-srcset hoặc srcset
        job = Job.Job(
            title=title,
            company=company,
            link=link,
            address="Hồ Chí Minh",
            exp=None,
            salary= "Deal",
            posted_date=posted_date,
            image=image
        )
        
        return job
    
    async def crawl_all_pages(self, today = False):
        all_jobs = []
        for role, slug in self.roles.items():
            for exp in self.exp:  
                print(f"📂 Đang chuyển sang chuyên mục: {role} | {exp}")

                target_url = slug + f"&exp={exp}"
                
                await self.page.goto(target_url)
                # 1. Gọi function chuyên xử lý việc chuyển trang/chọn role
            
                await self.page.wait_for_timeout(2000) # Đợi thêm 2s để chắc chắn trang đã load xong
                # Thực hiện cào dữ liệu ở đây...
                role_jobs = await self.scrape_current_role_pages(today)
    
                all_jobs.extend(role_jobs)
                
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass
            try:
                await self.page.wait_for_load_state("networkidle", timeout=2000)
            except:
                pass
        return all_jobs
    
    async def scrape_current_role_pages(self, today=False):
        current_page = 1
        role_jobs = []
        
        while True:
            print(f"🚅 Crawling page {current_page} for current role...")
            if(today):
                role_jobs.extend(await self.crawl_today())
            else:
                role_jobs.extend(await self.crawl()) 
            
            next_button = self.page.locator("li.next:not(.disabled) a")
            
            if await next_button.count() > 0:
                print("➡️  Đang chuyển sang trang tiếp theo...")
                current_page += 1
                await next_button.dispatch_event("click")
                
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass
                
            else:
                print("🏁 Last page .")
                break   
                    
        return role_jobs
    

                
    async def crawl_today(self):
        jobs = []
       
        container = self.page.locator(".job-list")
        cards = await container.locator(".job-card").all()
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links and ("phút" in job.posted_date.lower() or "giờ" in job.posted_date.lower() or "giây" in job.posted_date.lower()):
                self.scraped_links.add(job.link)
                jobs.append(job)
                                
        return jobs
    