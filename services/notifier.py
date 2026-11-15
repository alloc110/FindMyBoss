import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from core.config import config, get_logger
from models.Job import Job

logger = get_logger("DiscordNotifier")


class DiscordNotifier:
    """Asynchronous notification service for Discord webhooks with rate-limiting and file attachment support."""

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

    async def send_job(
        self,
        job: Job,
        client: Optional[httpx.AsyncClient] = None,
        cv_pdf_path: Optional[str] = None,
    ) -> bool:
        """Sends a single job embed to Discord, optionally attaching a tailored CV PDF."""
        if self._disabled or not self.webhook_url:
            return False

        payload: Dict[str, Any] = {
            "username": self.bot_username,
            "avatar_url": self.avatar_url,
            "embeds": [job.to_discord_embed()],
        }

        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            should_close_client = True

        has_file = False
        file_bytes = b""
        filename = ""
        if cv_pdf_path and os.path.isfile(cv_pdf_path):
            try:
                with open(cv_pdf_path, "rb") as f:
                    file_bytes = f.read()
                filename = os.path.basename(cv_pdf_path)
                has_file = True
            except Exception as e:
                logger.warning(f"Could not read CV PDF for Discord attachment '{cv_pdf_path}': {e}")

        max_retries = 3
        try:
            for attempt in range(1, max_retries + 1):
                try:
                    params = {"wait": "true"}
                    if has_file:
                        files = {"files[0]": (filename, file_bytes, "application/pdf")}
                        data = {"payload_json": json.dumps(payload)}
                        response = await client.post(self.webhook_url, data=data, files=files, params=params)
                    else:
                        response = await client.post(self.webhook_url, json=payload, params=params)

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
                        # Auto-react ✅ and ❌ if bot token is provided
                        if config.discord_bot_token:
                            try:
                                msg_data = response.json()
                                channel_id = msg_data.get("channel_id")
                                msg_id = msg_data.get("id")
                                if channel_id and msg_id:
                                    auth_headers = {"Authorization": f"Bot {config.discord_bot_token}"}
                                    for emoji in ["%E2%9C%85", "%E2%9D%8C"]:
                                        react_url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{msg_id}/reactions/{emoji}/@me"
                                        await client.put(react_url, headers=auth_headers)
                                        await asyncio.sleep(0.15)
                            except Exception as react_err:
                                logger.debug(f"Could not auto-react to Discord webhook message: {react_err}")

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

    async def send_message(self, message: str, client: Optional[httpx.AsyncClient] = None) -> bool:
        """Sends a text message notification to Discord."""
        if self._disabled or not self.webhook_url:
            return False

        payload = {
            "username": self.bot_username,
            "avatar_url": self.avatar_url,
            "content": message,
        }

        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            should_close_client = True

        try:
            response = await client.post(self.webhook_url, json=payload)
            return 200 <= response.status_code < 300
        except Exception as exc:
            logger.warning(f"Failed to send text message to Discord: {exc}")
            return False
        finally:
            if should_close_client:
                await client.aclose()

    async def send_file(
        self,
        file_path: str,
        content: Optional[str] = None,
        embed: Optional[Dict[str, Any]] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> bool:
        """Uploads an arbitrary file (e.g. applications.md or PDF) with optional text/embed to Discord."""
        if self._disabled or not self.webhook_url:
            return False

        if not os.path.isfile(file_path):
            logger.warning(f"File not found to send to Discord: {file_path}")
            return False

        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        payload: Dict[str, Any] = {
            "username": self.bot_username,
            "avatar_url": self.avatar_url,
        }
        if content:
            payload["content"] = content
        if embed:
            payload["embeds"] = [embed]

        files = {"files[0]": (filename, file_bytes, "application/octet-stream")}
        data = {"payload_json": json.dumps(payload)}

        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            should_close_client = True

        try:
            response = await client.post(self.webhook_url, data=data, files=files)
            return 200 <= response.status_code < 300
        except Exception as e:
            logger.error(f"Failed to upload file '{filename}' to Discord: {e}")
            return False
        finally:
            if should_close_client:
                await client.aclose()

    async def send_applications_tracker(self, client: Optional[httpx.AsyncClient] = None) -> bool:
        """Generates and uploads applications.md directly to Discord webhook."""
        try:
            from services.applications_tracker import generate_applications_markdown, get_applications_markdown_path

            generate_applications_markdown()
            tracker_path = get_applications_markdown_path()

            content = (
                "📋 **Cập Nhật Bảng Theo Dõi Ứng Tuyển & ATS (Applications Tracker)**\n"
                "Toàn bộ dữ liệu JD, điểm số ATS Match và liên kết CV đã được cập nhật vào tệp `applications.md` đính kèm:"
            )
            return await self.send_file(str(tracker_path), content=content, client=client)
        except Exception as e:
            logger.error(f"Failed to send applications tracker to Discord: {e}")
            return False
