import asyncio
from datetime import datetime, time as dtime, timedelta
from typing import Optional

from core.config import get_logger

logger = get_logger("DailyScheduler")


class DailyScheduler:
    """
    Automated daily background scheduler for FindMyBoss & Career-Ops:
    1. Triggers daily crawler at configured time (default 08:00 AM).
    2. Enriches & filters jobs matching target roles/levels.
    3. Auto-routes all qualified jobs to Career-Ops pipeline:
       - Computes ATS Match Score
       - Generates tailored ATS CV (PDF)
       - Updates data/applications.md
       - Dispatches Job Embeds + attached CV PDFs to Discord
    4. Uploads updated applications.md summary to Discord channel.
    """

    def __init__(
        self,
        daily_time_str: str = "08:00",
        enabled: bool = True,
    ):
        self.daily_time_str = daily_time_str
        self.enabled = enabled
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def parse_daily_time(self) -> dtime:
        """Parses 'HH:MM' string to datetime.time."""
        try:
            parts = [int(p) for p in self.daily_time_str.split(":")]
            return dtime(hour=parts[0], minute=parts[1] if len(parts) > 1 else 0)
        except Exception:
            return dtime(hour=8, minute=0)

    def seconds_until_next_run(self) -> float:
        """Calculates seconds until the next scheduled daily run."""
        target_time = self.parse_daily_time()
        now = datetime.now()
        target_today = datetime.combine(now.date(), target_time)

        if now >= target_today:
            # Scheduled time has passed today; schedule for tomorrow
            target_next = target_today + timedelta(days=1)
        else:
            target_next = target_today

        diff = (target_next - now).total_seconds()
        logger.info(
            f"⏰ Next automated daily harvest scheduled at: {target_next.strftime('%Y-%m-%d %H:%M:%S')} (in {round(diff / 3600, 2)} hours)"
        )
        return max(5.0, diff)

    async def run_harvest_pipeline(self) -> int:
        """Executes the complete daily crawl and auto Career-Ops intake."""
        logger.info("🌅 Starting scheduled automated Daily Job Harvest & Career-Ops Intake...")
        try:
            from crawl.orchestrator import main_orchestrator

            # Run crawler with today_only=True
            jobs = await main_orchestrator(today_only=True)
            logger.info(f"✅ Daily harvest completed. {len(jobs)} qualified jobs processed and delivered to Discord.")
            return len(jobs)
        except Exception as e:
            logger.error(f"❌ Error during automated daily harvest: {e}", exc_info=True)
            return 0

    async def _scheduler_loop(self):
        """Infinite loop sleeping until daily time, then executing pipeline."""
        self._running = True
        logger.info(f"🚀 DailyScheduler service started (target time: {self.daily_time_str} daily).")

        while self._running:
            delay = self.seconds_until_next_run()
            try:
                await asyncio.sleep(delay)
                if not self._running:
                    break
                await self.run_harvest_pipeline()
            except asyncio.CancelledError:
                logger.info("DailyScheduler task was cancelled.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    def start(self):
        """Starts the scheduler in the current asyncio event loop."""
        if not self.enabled:
            logger.info("DailyScheduler is disabled by configuration.")
            return

        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._scheduler_loop())

    def stop(self):
        """Stops the scheduler."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()


# Global scheduler instance
daily_scheduler = DailyScheduler(daily_time_str="08:00", enabled=True)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("🚀 Chạy thử nghiệm ngay lập tức quy trình cào việc & Career-Ops...")
    asyncio.run(daily_scheduler.run_harvest_pipeline())
