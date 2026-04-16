from crawl.base_crawl import JobScraper
from playwright.async_api import async_playwright
import asyncio
import models.Job as Job
import requests
import random
class ITviecJob(JobScraper):
    def __init__(self, page, webhook_url):
        super().__init__(page = page, webhook_url = webhook_url)
        self.url = "https://itviec.com/jobs-expertise-index"
        self.find_level = [
                            "INTERN", 
                            "FRESHER", 
                            "JUNIOR"
                            ]
        self.un_find_level = [
                            "SENIOR",
                            "LEAD",
                            "MANAGER",
                            "DIRECTOR",
                            "HEAD",
                            "CHIEF",
                            "TRƯỞNG",
                            "PHÓ",
                            "GIÁM ĐỐC",
                            "QUẢN LÝ",
                            "TRƯỞNG PHÒNG",
                            "PHÓ PHÒNG",
                            "TRƯỞNG BAN",
                            "PHÓ BAN",
                            "TRƯỞNG NHÓM",
                            "PHÓ NHÓM",
                            "TRƯỞNG DỰ ÁN",    
                            ]
        self.roles = {
                      "Backend Developer": "backend-developer" ,
                      "Frontend Developer": "frontend-developer",
                      "Fullstack Developer": "fullstack-developer"                      
        }
        # "Frontend Developer": "frontend-developer",
        #               "Fullstack Developer": "fullstack-developer",
        #               "Mobile Application Developer": "mobile-application-developer",
        #               "Data Analyst": "data-analyst",
        #               "Big Data Engineer": "big-data-engineer"  ,
        #               "Data Engineer": "data-engineer",
        #               "DataOps / MLOps Engineer": "dataops-mlops-engineer",
        #               "Database Engineer": "database-engineer",
        #               "AI / Machine Learning Engineer": "ai-machine-learning-engineer",
        #               "AI Researcher": "ai-researcher",
        #               "Computer Vision Engineer": "computer-vision-engineer",
        #               "Data Scientist": "data-scientist",
        #               "UX/UI Designer": "ux-ui-designer"    
        self.scraped_links = set() # Dùng để lưu các link đã cào được, tránh trùng lặp khi crawl nhiều trang
        
        
    async def crawl(self):
        jobs = []
        
        container = self.page.locator('[data-search--pagination-target="jobList"]').first
        cards = await container.locator(".job-card").all()
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links:
                self.scraped_links.add(job.link)
                if job.address.find("Hồ Chí Minh") != -1:
                    flag = False
                    for level in self.find_level:
                        if job.title.upper().find(level) != -1:
                            job.exp = level
                            jobs.append(job)
                            Flag = True
                            break
                    flag2 = False       
                    if not flag:
                        for level in self.un_find_level:
                            if job.title.upper().find(level) != -1:
                                flag2 = True
                                break
                        if not flag2:
                            job.exp = "Unknown"
                            jobs.append(job)
        return jobs
    
    async def parse_card_detail(self, card):
        title_element = card.locator('h3[data-search--job-selection-target="jobTitle"]')
        
        title = await title_element.inner_text()
        company = await card.locator(".ims-2 a").inner_text()
        
        data_url = await title_element.get_attribute("data-url")

        
        location = await card.locator('div[title]').last.get_attribute("title")
        if location.find("Ho Chi Minh") != -1:
            location = "Hồ Chí Minh"
            
        posted_date = await card.locator(".small-text.text-dark-grey").first.inner_text()
        posted_date = posted_date.replace("Posted", "").strip()
        
        logo_element = card.locator('picture source')

# Lấy giá trị từ thuộc tính data-srcset hoặc srcset
        logo_url = await logo_element.get_attribute("data-srcset")
        job = Job.Job(
            title=title,
            company=company,
            link=data_url,
            address=location,
            exp=None,
            salary="Deal",
            posted_date=posted_date,
            image=logo_url
        )
        return job
    
    async def crawl_all_pages(self, today = False):
        all_jobs = []
        for role, slug in self.roles.items():
            print(f"📂 Đang chuyển sang chuyên mục: {role}")
            target_url = f"https://itviec.com/it-jobs/{slug}"
            
            await self.page.goto(target_url)
            
            await self.page.wait_for_timeout(2000) # Đợi thêm 2s để chắc chắn trang đã load xong
            # Thực hiện cào dữ liệu ở đây...
            role_jobs = await self.scrape_current_role_pages(today)
            all_jobs.extend(role_jobs)
        
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
            
            next_button = self.page.locator('div.page.next a[rel="next"]')

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
        
        container = self.page.locator('[data-search--pagination-target="jobList"]').first
        cards = await container.locator(".job-card").all()
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links:
                self.scraped_links.add(job.link)
                if job.address.find("Hồ Chí Minh") != -1 and job.posted_date.find("hours") != -1:
                    flag = False
                    for level in self.find_level:
                        if job.title.upper().find(level) != -1:
                            job.exp = level
                            jobs.append(job)
                            Flag = True
                            break
                    flag2 = False       
                    if not flag:
                        for level in self.un_find_level:
                            if job.title.upper().find(level) != -1:
                                flag2 = True
                                break
                        if not flag2:
                            job.exp = "Unknown"
                            jobs.append(job) 
        
        return jobs
    