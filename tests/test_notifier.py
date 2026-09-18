import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from models.Job import Job
from services.notifier import DiscordNotifier


class TestDiscordNotifier(unittest.IsolatedAsyncioTestCase):
    async def test_notifier_disabled_when_empty_webhook(self):
        notifier = DiscordNotifier(webhook_url="")
        self.assertTrue(notifier._disabled)

        job = Job(title="Test Job", company="Test Co", link="https://example.com")
        result = await notifier.send_job(job)
        self.assertFalse(result)

        count = await notifier.send_jobs([job])
        self.assertEqual(count, 0)

    async def test_notifier_send_success(self):
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/mock")
        job = Job(title="Test Job", company="Test Co", link="https://example.com")

        mock_response = MagicMock()
        mock_response.status_code = 204

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        success = await notifier.send_job(job, client=mock_client)
        self.assertTrue(success)
        mock_client.post.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
