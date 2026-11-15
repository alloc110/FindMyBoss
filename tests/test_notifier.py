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

    async def test_notifier_send_with_cv_attachment(self):
        import tempfile
        from pathlib import Path

        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/mock")
        job = Job(title="Test Job", company="Test Co", link="https://example.com")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 mock content")
            tmp_pdf = f.name

        try:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response

            success = await notifier.send_job(job, client=mock_client, cv_pdf_path=tmp_pdf)
            self.assertTrue(success)
            mock_client.post.assert_awaited_once()
            _, kwargs = mock_client.post.call_args
            self.assertIn("files", kwargs)
            self.assertIn("data", kwargs)
        finally:
            Path(tmp_pdf).unlink(missing_ok=True)

    async def test_notifier_send_text_message(self):
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/mock")
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        success = await notifier.send_message("Test message", client=mock_client)
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
