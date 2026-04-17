import asyncio
from playwright.async_api import async_playwright
from crawl.TopDevJob import TopDevJobScraper # Import class của bạn
from crawl.ITviecJob import ITviecJob # Import class của bạn
from crawl.TopCVJob import TopCVJob # Import class của bạn
from crawl.VietnamWorksJob import VietnamWorksJob
from crawl.IndeedJob import IndeedJob
from crawl.JobsGoJob import JobsGoJob
from dotenv import load_dotenv
import os
from playwright_stealth import Stealth
from datetime import datetime
load_dotenv()

async def test_scraper():
    async with async_playwright() as p:
        crawlers = (TopDevJobScraper,
                    JobsGoJob,
                    IndeedJob,
                    VietnamWorksJob,
                    ITviecJob,
                    TopCVJob,
                    ) 
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
                    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"    ,
                    viewport={'width': 1280, 'height': 800} ,
                    locale="vi-VN",
                    timezone_id="Asia/Ho_Chi_Minh"  
                )
        stealth = Stealth(init_scripts_only=True)
        page = await context.new_page()
               
        for crawler_class in crawlers:
            print(f"\n\n================ Crawling {crawler_class.__name__} ================\n")

            
            await page.wait_for_timeout(2000)
            await page.mouse.move(200, 300)
            await page.mouse.wheel(0, 500)
                                                             
            await stealth.apply_stealth_async(context)
            scraper = crawler_class(page = page,webhook_url=webhook_url)

            print("🚀 Start crawling... ")
            
            try:
                jobs = await scraper.crawl_all_pages(today = True) # Nếu bạn chỉ muốn crawl hôm nay thì truyền today=True)
                
                print(f"✅ Crawled {len(jobs)} jobs from {crawler_class.__name__}")
                scraper.print_jobs(jobs) 
                
                # for job in jobs:
                #     scraper.send_to_discord(job)
                
            except Exception as e:
                print(f"❌ Error: {e}")
                
            await asyncio.sleep(5)
            
        await browser.close()
    
if __name__ == "__main__":
    asyncio.run(test_scraper())