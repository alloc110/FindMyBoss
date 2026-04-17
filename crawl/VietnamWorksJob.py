from crawl.base_crawl import JobScraper
from playwright.async_api import async_playwright
import asyncio
import models.Job as Job
import re
from datetime import datetime
class VietnamWorksJob(JobScraper):
    def __init__(self, page, webhook_url):
        super().__init__(page = page, webhook_url = webhook_url)
        # https://www.vietnamworks.com/viec-lam?q=data-engineer&l=29&level=
        self.url = "https://www.vietnamworks.com/viec-lam?q="
        self.roles = {
                        "Software Engineer": "software-engineer",
                        "Backend Developer": "backend-developer",
                        "Frontend Developer": "frontend-developer",
                        "Data Engineer": "data-engineer",
                        "Data Analysist": "data-analyst"
                    }
        
        self.exp = {"8": "Thực tập sinh/Sinh viên", "1": "Mới tốt nghiệp", "5": "Nhân viên"} # 8: Thuc tap/ sinh vien  1: Moi ra truong, 3: Nhan vien
        self.scraped_links = set() # Dùng để lưu các link đã cào được, tránh trùng lặp khi crawl nhiều trang
        self.unfind=["senior", "middle", "sr", "mid", "lead"]
        
    async def crawl(self):
        jobs = []
        try:
            await self.page.wait_for_selector(".view_job_item, .noResultWrapper", timeout=10000)
        except:
            print("⚠️ Hết thời gian chờ: Trang không phản hồi.")
            return []
     
        if await self.page.locator(".noResultWrapper").is_visible():
            print("🚫 Không tìm thấy công việc nào. Đang thoát...")
            return []
        
        await self.page.wait_for_selector(".block-job-list")
        cards = await self.page.locator(".view_job_item").all()
        
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links:
                self.scraped_links.add(job.link)
                jobs.append(job)
                                
        return jobs
    
    async def parse_card_detail(self, card):
        
        
        title = await card.locator("h2 a").inner_text()
        title = title.replace("Mới", "").strip()
        company = await card.locator(".sc-cpgxJx").inner_text()
        raw_href = await card.locator("h2 a").get_attribute("href")
        link = f"https://www.vietnamworks.com{raw_href}"            


        salary = await card.locator(".sc-dauhQT").inner_text()

        posted_date = await card.locator(".sc-lccgLh").inner_text()
        posted_date = posted_date.replace("Cập nhật:", "").strip()
        image = await card.locator(".img_job_card img").get_attribute("src")
        if(image == "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"): image = "https://images.vietnamworks.com/img/company-default-logo.svg"
        # Lấy giá trị từ thuộc tính data-srcset hoặc srcset
        job = Job.Job(
            title=title,
            company=company,
            link=link,
            address="Hồ Chí Minh",
            exp=None,
            salary= salary,
            posted_date=posted_date,
            image=image
        )
        return job
       
    
    async def crawl_all_pages(self, today = False):
        all_jobs = []
        for role, slug in self.roles.items():
            for exp, name_exp in self.exp.items():  
                print(f"📂 Đang chuyển sang chuyên mục: {role} | {name_exp}")

                target_url = self.url + slug + f"&l=29&level={exp}"
                
                await self.page.goto(target_url)
            
                await self.page.wait_for_timeout(2000) # Đợi thêm 2s để chắc chắn trang đã load xong
                # Thực hiện cào dữ liệu ở đây...
                role_jobs = await self.scrape_current_role_pages(today)
                for job in role_jobs:
                    if exp == "8":
                        job.exp = "Thực tập sinh/Sinh viên"
                    elif exp == "1":
                        job.exp = "Mới tốt nghiệp"
                    elif exp == "5":
                        job.exp = "Nhân viên"
                all_jobs.extend(role_jobs)
                
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass
            try:
                await self.page.wait_for_load_state("networkidle", timeout=2000)
            except:
                pass
            
        all_jobs = self.filter(all_jobs)
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
            
            next_button = self.page.locator(f".pagination button:text-is('{current_page+1}')")    
            if await next_button.count() > 0:
                print("➡️ Đang chuyển sang trang tiếp theo...")
                
                await next_button.dispatch_event("click")
                current_page += 1
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
        try:
            await self.page.wait_for_selector(".view_job_item, .noResultWrapper", timeout=10000)
        except:
            print("⚠️ Hết thời gian chờ: Trang không phản hồi.")
            return []
     
        if await self.page.locator(".noResultWrapper").is_visible():
            print("🚫 Không tìm thấy công việc nào. Đang thoát...")
            return []
        
        await self.page.wait_for_selector(".block-job-list")
        cards = await self.page.locator(".view_job_item").all()
        
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links and "Hôm nay" == job.posted_date:
                self.scraped_links.add(job.link)
                jobs.append(job)
                                
        return jobs
    
    def filter(self, all_jobs):
        cleaned_job = [
        job for job in all_jobs 
        if not any(filter_name in job.title.lower() for filter_name in self.unfind)
        ]
        return cleaned_job