import asyncio
from playwright.async_api import async_playwright
from crawl.TopDevJob import TopDevJobScraper # Import class của bạn
from crawl.ITviecJob import ITviecJob # Import class của bạn
from dotenv import load_dotenv
import os
from playwright_stealth import Stealth
load_dotenv()

async def test_scraper():
    async with async_playwright() as p:
        crawlers = (TopDevJobScraper, ITviecJob,) # Thay bằng class của bạn nếu muốn test cái khác
        for crawler_class in crawlers:
            print(f"\n\n================ Testing {crawler_class.__name__} ================\n")
            # 1. Mở trình duyệt (để headless=False để tận mắt xem nó click)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            custom_languages = ("fr-FR", "fr")
            stealth = Stealth(
                navigator_languages_override=custom_languages,
                init_scripts_only=True
            )

            await stealth.apply_stealth_async(context)

            # 2. Tạo một trang mới
            page = await context.new_page()
            
            webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
            scraper = crawler_class(page = page,webhook_url=webhook_url)
            
            print("🚀 Start crawling... ")
            
            try:
                jobs = await scraper.crawl_all_pages(today = True) # Nếu bạn chỉ muốn crawl hôm nay thì truyền today=True)
                
                print(f"✅ Crawled {len(jobs)} jobs from {crawler_class.__name__}")
                scraper.print_jobs(jobs) 
                
                for job in jobs:
                    scraper.send_to_discord(job)
                
            except Exception as e:
                print(f"❌ Error: {e}")
                
            # Đợi một chút để bạn kịp nhìn giao diện trước khi đóng
            await asyncio.sleep(5)
            await browser.close()
    
if __name__ == "__main__":
    asyncio.run(test_scraper())