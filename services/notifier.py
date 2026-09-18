import asyncio
from typing import List, Optional
import httpx

from config import config, get_logger
from models.Job import Job

logger = get_logger("DiscordNotifier")


class DiscordNotifier:
    """Asynchronous notification service for Discord webhooks with rate-limiting support."""

    def __init__(self, webhook_url: Optional[str] = None):
        if webhook_url is not None:
            self.webhook_url = webhook_url
        else:
            self.webhook_url = config.discord_webhook_url

        self.avatar_url = (
            "https://www.shutterstock.com/image-vector/"
            "beautiful-mole-illustration-vector-art-600nw-2721821771.jpg"
        )
        self.bot_username = "Find My Boss Bot"
        self._disabled = not bool(self.webhook_url)

        if self._disabled:
            logger.warning(
                "⚠️ DISCORD_WEBHOOK_URL is not set. Job alerts will be logged to console only."
            )

    async def send_job(self, job: Job, client: Optional[httpx.AsyncClient] = None) -> bool:
        """Sends a single job embed to Discord, respecting rate limits."""
        if self._disabled or not self.webhook_url:
            return False

        payload = {
            "username": self.bot_username,
            "avatar_url": self.avatar_url,
            "embeds": [job.to_discord_embed()],
        }

        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            should_close_client = True

        max_retries = 3
        try:
            for attempt in range(1, max_retries + 1):
                try:
                    response = await client.post(self.webhook_url, json=payload)

                    if response.status_code == 429:
                        retry_after = 2.0
                        try:
                            rate_data = response.json()
                            retry_after = float(rate_data.get("retry_after", 2.0))
                        except Exception:
                            retry_after = float(response.headers.get("Retry-After", 2.0))

                        logger.warning(
                            f"⏳ Rate limited by Discord. Backing off for {retry_after:.2f}s (attempt {attempt}/{max_retries})"
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    if 200 <= response.status_code < 300:
                        # Polite throttle to respect Discord webhook guidelines
                        await asyncio.sleep(0.4)
                        return True

                    logger.error(
                        f"❌ Failed to dispatch Discord embed: HTTP {response.status_code} - {response.text}"
                    )
                    return False

                except httpx.RequestError as exc:
                    logger.warning(
                        f"⚠️ Network exception when dispatching alert (attempt {attempt}/{max_retries}): {exc}"
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(1.0 * attempt)
                    else:
                        logger.error(f"❌ Aborting Discord delivery for '{job.title}' after {max_retries} attempts.")
                        return False
            return False

        finally:
            if should_close_client:
                await client.aclose()

    async def send_jobs(self, jobs: List[Job]) -> int:
        """Dispatches a list of jobs sequentially via an async client session."""
        if self._disabled or not jobs:
            return 0

        success_count = 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            for job in jobs:
                success = await self.send_job(job, client=client)
                if success:
                    success_count += 1

        logger.info(f"📬 Dispatched {success_count}/{len(jobs)} jobs successfully to Discord.")
        return success_count
