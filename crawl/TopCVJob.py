from crawl.base_crawl import JobScraper
from playwright.async_api import async_playwright
import asyncio
import models.Job as Job
import requests
import random
class TopCVJob(JobScraper):
    def __init__(self, page, webhook_url):
        super().__init__(page = page, webhook_url = webhook_url)
        self.url = "https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257?category_family=r257"
        self.roles = {
                        "Software Engineer": "https://www.topcv.vn/tim-viec-lam-software-engineer",
                        "Backend Developer": "https://www.topcv.vn/tim-viec-lam-backend-developer",
                        "Frontend Developer": "https://www.topcv.vn/tim-viec-lam-frontend-developer",
                        "Data Engineer": "https://www.topcv.vn/tim-viec-lam-data-engineer",
                    }
        
        self.exp = ["1", "2", "3"] # 1: Không yêu cầu, 2: Dưới 1 năm, 3: 1 năm
        self.scraped_links = set() # Dùng để lưu các link đã cào được, tránh trùng lặp khi crawl nhiều trang
        
        
    async def crawl(self):
        jobs = []
        empty_block = self.page.locator('.none-suitable-job')
        if  await empty_block.is_visible():
            print(f"🔍 Không tìm thấy công việc phù hợp")

            return jobs
        container = self.page.locator(".job-list-search-result").first
        cards = await container.locator(".job-item-search-result").all()
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links:
                self.scraped_links.add(job.link)
                jobs.append(job)
                                
        return jobs
    
    async def parse_card_detail(self, card):
        
        title = await card.locator('h3.title').inner_text()    
        company = await card.locator('.company-name').inner_text()  
        link = await card.locator('h3.title a').get_attribute('href')
            
        label_locator = card.locator(".label-update")

        # Kiểm tra số lượng phần tử tìm thấy
        if await label_locator.count() > 0:
            posted_date = await label_locator.inner_text()
        else:
            posted_date = "Không rõ ngày đăng"    
        posted_date = posted_date.replace("Đăng", "").strip()  
              
        salary = await card.locator('label.salary').inner_text()
        salary = salary.replace("\n", " ").strip() if salary else "Không rõ mức lương"
        
        logo_element = card.locator(".avatar img.w-100")
        image = await logo_element.get_attribute("data-src") or await logo_element.get_attribute("src")
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
            for exp in self.exp:  
                print(f"📂 Đang chuyển sang chuyên mục: {role} | {exp}")

                target_url = slug + f"-tai-ho-chi-minh-kl2cr257?exp=1&type_keyword={exp}&sba=1&category_family=r257&locations=l2&saturday_status=0"
                
                await self.page.goto(target_url)
                # 1. Gọi function chuyên xử lý việc chuyển trang/chọn role
            
                await self.page.wait_for_timeout(2000) # Đợi thêm 2s để chắc chắn trang đã load xong
                # Thực hiện cào dữ liệu ở đây...
                role_jobs = await self.scrape_current_role_pages(today)
                for job in role_jobs:
                    if exp == "1":
                        job.exp = "Không yêu cầu kinh nghiệm"
                    elif exp == "2":
                        job.exp = "Dưới 1 năm kinh nghiệm"
                    elif exp == "3":
                        job.exp = "1 năm kinh nghiệm"
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
            current_page += 1
            if(today):
                role_jobs.extend(await self.crawl_today())
            else:
                role_jobs.extend(await self.crawl()) 
            
            next_button = self.page.locator('a[rel="next"]')

            if await next_button.count() > 0:
                print("➡️ Đang chuyển sang trang tiếp theo...")
                
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
        
        empty_block = self.page.locator('.none-suitable-job')
        if  await empty_block.is_visible():
            print(f"🔍 Không tìm thấy - 0 công việc phù hợp")
            return jobs
        container = self.page.locator(".job-list-search-result").first
        cards = await container.locator(".job-item-search-result").all()
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links and ("hôm nay" in job.posted_date.lower() or "vừa đăng" in job.posted_date.lower()):
                self.scraped_links.add(job.link)
                jobs.append(job)
                                
        return jobs
    