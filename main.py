import asyncio
from playwright.async_api import async_playwright
from crawl.TopDevJob import TopDevJobScraper # Import class của bạn
from dotenv import load_dotenv
import os

load_dotenv()

async def test_scraper():
    async with async_playwright() as p:
        # 1. Mở trình duyệt (để headless=False để tận mắt xem nó click)
        browser = await p.chromium.launch(headless=True)
        
        # 2. Tạo một trang mới
        page = await browser.new_page()
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        # 3. Khởi tạo scraper và truyền page vào
        scraper = TopDevJobScraper(page = page,webhook_url=webhook_url)
        # Gán page vào scraper (vì trong __init__ bạn dùng super().__init__(page=...))
        
        print("🚀 Start crawling... ")
        
        try:
            # 4. Gọi hàm crawl
            jobs = await scraper.crawl_all_pages(today=True) # Nếu bạn chỉ muốn crawl hôm nay thì truyền today=True)
            print(f"✅ Crawled {len(jobs)} jobs from TopDev.vn")
            # 5. In kết quả ra màn hình để kiểm tra
            for job in jobs:
                scraper.send_to_discord(job)
        except Exception as e:
            print(f"❌ Error: {e}")
            
        # Đợi một chút để bạn kịp nhìn giao diện trước khi đóng
        await asyncio.sleep(5)
        await browser.close()
    
if __name__ == "__main__":
    asyncio.run(test_scraper())