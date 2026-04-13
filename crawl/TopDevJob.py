from crawl.base_crawl import JobScraper
from playwright.async_api import async_playwright
import asyncio
import models.Job as Job
import requests

class TopDevJobScraper(JobScraper):
    def __init__(self, page, webhook_url):
        super().__init__(page = page, webhook_url = webhook_url)
        self.url = "https://topdev.vn/jobs/search"
        self.find_level = ["Intern", "Fresher", "Junior"]
    async def crawl(self):
        jobs = []
        container = self.page.locator("div.flex-col.gap-2").first
        cards = await container.locator(".text-card-foreground").all()        
        print(f"🔍 Found {len(cards)} job cards")
        for i in range(len(cards)):
            # print(f"📄 Processing card {i+1}/{len(cards)}...")
            card = cards[i]
            job_data = await self.parse_card_detail(card) # Hàm bóc tách chi tiết đã viết
            if(job_data.exp in self.find_level and job_data.address.find("Hồ Chí Minh") != -1): # Hồ Chí Minh Hà Nội
                jobs.append(job_data)
        return jobs
    
    async def parse_card_detail(self, card):
        anchor =  card.locator("a.text-brand-500").first
        title = await anchor.inner_text() # Lấy tiêu đề công việc
        cleaned_title = title.rsplit(' (', 1)[0]
        company = await card.locator("span.text-text-500").first.inner_text() # Lấy tên công ty
        link = "https://topdev.vn" + await anchor.get_attribute("href") # Lấy link chi tiết công việc
        details = await card.locator("div.grid span.line-clamp-1").all_inner_texts() # Lấy các chi tiết như địa chỉ, cấp bậc, loại hình, kinh nghiệm
        
        address = details[0].strip() if len(details) > 0 else "N/A"
        exp = details[1].split(",") if len(details) > 1 else "N/A"      
        level = exp[0].strip() if len(exp) > 1 else "N/A"
       
        date_locator = card.locator("div.border-t span.text-text-500").first
        
        # Nếu tìm thấy ít nhất 1 phần tử thì lấy text, ngược lại gán N/A
        if await date_locator.count() > 0:
            posted_date = await date_locator.inner_text()
        else:
            posted_date = "N/A"
        salary = "Deal"
        image = await card.locator("img[alt='job-image']").get_attribute("src")      
        job = Job.Job(
            title=cleaned_title,
            company=company,
            link=link,
            address=address,
            exp=level,
            salary=salary,
            posted_date=posted_date,
            image=image
        )
        return job
    
    async def crawl_all_pages(self, today = False):
        current_page = 1
        await self.page.goto(self.url)
        await self.page.get_by_role("button", name="All Categories").click()
        await self.page.locator("ul li span").filter(has_text="IT").first.click()
        await self.page.locator("ul li span").filter(has_text="IT").first.click()

        roles = ["Software Developer", "Data Engineer / Scientist / Analyst", "Machine Learning / AI Engineer", "DevOps Engineer"]
        for role in roles:
            await self.page.locator('div[style*="width:600px"] button').filter(has_text=role).click()
        all_jobs = []
        await self.page.get_by_role("button", name="Apply", exact=True).click() 
        while True:
            print(f"🚅 Crawling page {current_page}...")
            if(today):
                all_jobs.extend(await self.crawl_today())
            else:
                all_jobs.extend(await self.crawl()) 
            
            next_button = self.page.get_by_label("Go to next page")
            
            # Kiểm tra nếu nút Next còn tồn tại và có thể click được
            # (Nút Next cuối cùng thường có class opacity-0 hoặc hidden)
            if await next_button.count() > 0 and await next_button.is_visible() and await next_button.is_enabled():
                # Lấy class để kiểm tra xem có bị ẩn (trang cuối) không
                class_attr = await next_button.get_attribute("class")
                
                # Nếu KHÔNG chứa 'opacity-0' thì mới là nút bấm được
                if "opacity-0" not in class_attr:
                    print("➡️ Next button is visible and enabled. Clicking to go to the next page...")
                    await next_button.click(force=True)  # Dùng force để đảm bảo click dù có phần tử nào đó chồng lên
                    current_page += 1
                    # Đợi dữ liệu mới nạp xong
                    await self.page.wait_for_load_state("networkidle")
                    # Đợi thêm 1s để chắc chắn các card cũ đã bị thay thế (tránh cào trùng)
                    await self.page.wait_for_timeout(1000)
                else:
                    print("🏁 Last page reached.")
                    return all_jobs
                
    async def crawl_today(self):
        jobs = []
        container = self.page.locator("div.flex-col.gap-2").first
        cards = await container.locator(".text-card-foreground").all()        
        print(f"🔍 Found {len(cards)} job cards")
        for i in range(len(cards)):
            # print(f"📄 Processing card {i+1}/{len(cards)}...")
            card = cards[i]
            job_data = await self.parse_card_detail(card) # Hàm bóc tách chi tiết đã viết 
            if(job_data.exp in self.find_level and job_data.address.find("Hồ Chí Minh") != -1 and job_data.posted_date.find("hours") != -1): # Hồ Chí Minh  Hà Nội
                jobs.append(job_data)
        return jobs
    
    def send_to_discord(self, job_data):
        super().send_to_discord(job_data)