from crawl.base_crawl import JobScraper
from playwright.async_api import async_playwright
import asyncio
import models.Job as Job
import re
from datetime import datetime
import random
class IndeedJob(JobScraper):
    def __init__(self, page, webhook_url):
        super().__init__(page = page, webhook_url = webhook_url)
        self.url = "https://vn.indeed.com/"
        self.roles = {
                        "Software Engineer": "software engineer",
                        "Backend Developer": "backend developer",
                        "Frontend Developer": "frontend developer",
                        "Data Engineer": "data engineer",
                    }
        self.unfind = ["senior", "lead", "middle", "mid", "sr", "supervisor"]        
        self.scraped_links = set() # Dùng để lưu các link đã cào được, tránh trùng lặp khi crawl nhiều trang
        
        
    async def crawl(self):
        jobs = []
        await self.page.goto(self.page.url + "&fromage=1")
        
        cards = await self.page.locator("li .job_seen_beacon").all() 
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links:
                self.scraped_links.add(job.link)
                jobs.append(job)
              
        return jobs
    
    async def parse_card_detail(self, card):
        
        title = await card.locator("h2.jobTitle span").get_attribute("title")
    
        company = await card.locator("[data-testid='company-name']").inner_text()
        
        location = await card.locator("[data-testid='text-location']").inner_text()
        
        raw_href = await card.locator("a.jcs-JobTitle").get_attribute("href")

        if raw_href:
            job_link = f"https://vn.indeed.com{raw_href}"
        else:
            job_link = "N/A"
        
        job = Job.Job(
            title=title,
            company=company,
            link=job_link,
            address=location,
            exp=None,
            salary= "Deal",
            posted_date="Available",
            image=None
        )
        return job
       
    
    async def crawl_all_pages(self, today = False):
        all_jobs = []
        await self.page.goto(self.url)

        for role, slug_name in self.roles.items():    
            await self.page.wait_for_timeout(2000) 

            await self.page.locator("#text-input-what").click()
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await self.page.locator("#text-input-what").fill(slug_name)
            
            await self.page.wait_for_timeout(random.randint(1000, 3000))
            
            await self.page.locator("#text-input-where").click()
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await self.page.locator("#text-input-where").fill("Thành phố Hồ Chí Minh")
            
            await self.page.keyboard.press("Enter")
            
            await self.page.wait_for_timeout(2000) 

            role_jobs = await self.scrape_current_role_pages(today)
            
            all_jobs.extend(role_jobs)
            await self.page.goto(self.url)
            
        all_jobs = self.filter(all_jobs)
                    
        return all_jobs
    
    async def scrape_current_role_pages(self, today=False):
        current_page = 1
        role_jobs = []
        

        print(f"🚅 Crawling page {current_page} for current role...")
        
        if(today):
            role_jobs.extend(await self.crawl_today())
        else:
            role_jobs.extend(await self.crawl()) 
        
                    
        return role_jobs
                
    async def crawl_today(self):
        jobs = []
        await self.page.goto(self.page.url + "&fromage=1")
        
        cards = await self.page.locator("li .job_seen_beacon").all() 
        print(f"🔍 Tìm thấy {len(cards)} công việc trên trang này")
        
        for card in cards: 
            job = await self.parse_card_detail(card)
            if job.link not in self.scraped_links:
                self.scraped_links.add(job.link)
                job.posted_date = "Today"
                jobs.append(job)
              
        return jobs
    
    def filter(self, all_jobs):
        cleaned_job = []
        
        for job in all_jobs:
            flag = True
            for filter_name in self.unfind:
                if job.title.lower().find(filter_name) != -1 :
                    flag = False
                    break
            if flag:
                cleaned_job.append(job)
        
        return cleaned_job
    
