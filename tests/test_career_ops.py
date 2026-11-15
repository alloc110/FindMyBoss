import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient

from models.Job import Job
from services.career_ops_service import CareerOpsService
from services.storage import JobStorage
from web.app import app


class TestCareerOpsIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_career_ops.db"
        self.storage = JobStorage(db_path=str(self.db_path), legacy_jsonl="")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_infer_company(self):
        service = CareerOpsService(storage=self.storage)
        # Test "at Company"
        c1 = service._infer_company("Backend Engineer at TechCorp", "", "example.com")
        self.assertEqual(c1, "TechCorp")

        # Test "- Company"
        c2 = service._infer_company("Data Scientist - AI Labs", "", "example.com")
        self.assertEqual(c2, "AI Labs")

        # Test domain fallback
        c3 = service._infer_company("Senior Engineer", "", "greenhouse.io")
        self.assertEqual(c3, "Greenhouse")

        # Test ITviec layout (line after title or before Company type)
        itviec_text = "Data Science Intern (On-site)\nFINPROS\nSign in to view salary\n...\nCÔNG TY CỔ PHẦN ĐẦU TƯ FINPROS\n\nCompany type"
        c4 = service._infer_company("Data Science Intern (On-site)", itviec_text, "itviec.com")
        self.assertEqual(c4, "CÔNG TY CỔ PHẦN ĐẦU TƯ FINPROS")

        # Test ITviec line after title
        itviec_text2 = "Data Science Intern (On-site)\nFINPROS\nSign in to view salary"
        c5 = service._infer_company("Data Science Intern (On-site)", itviec_text2, "itviec.com")
        self.assertEqual(c5, "FINPROS")

        # Test portal domain is never returned as company
        c6 = service._infer_company("DevOps Engineer", "No explicit company here", "itviec.com")
        self.assertNotEqual(c6.lower(), "itviec")
        self.assertEqual(c6, "Công ty Tuyển Dụng")

        # Test TopDev Recruiting pattern
        c7 = service._infer_company(
            "Recruiting Remote Data Engineer at SalesNow Inc. | Saramin",
            "",
            "topdev.vn",
            url="https://topdev.vn/detail-jobs/remote-data-engineer-salesnow-inc-2141955",
        )
        self.assertEqual(c7, "SalesNow Inc.")

        # Test TopDev slug fallback
        c8 = service._infer_company(
            "Data Services Specialist",
            "",
            "topdev.vn",
            url="https://topdev.vn/detail-jobs/data-services-specialist-antsomi-2143923",
        )
        self.assertEqual(c8, "Antsomi")

    def test_build_job_dict(self):
        service = CareerOpsService(storage=self.storage)
        text = "We are hiring a Python and FastAPI developer with Docker and React experience."
        job_dict = service._build_job_dict("Python Dev", "Company ABC", "https://example.com/job/1", text)

        self.assertEqual(job_dict["title"], "Python Dev")
        self.assertEqual(job_dict["company"], "Company ABC")
        self.assertIn("Python", job_dict["skills"])
        self.assertIn("FastAPI", job_dict["skills"])
        self.assertIn("Docker", job_dict["skills"])

    async def test_process_job_url_end_to_end(self):
        mock_ai = MagicMock()
        mock_tailor = MagicMock()
        mock_tailor.match_score = 88
        mock_tailor.match_analysis = "Ứng viên rất phù hợp với vị trí."
        mock_tailor.missing_skills = ["Kubernetes"]
        mock_tailor.tailored_summary = "Software Engineer với kinh nghiệm Python & AI."
        mock_tailor.tailored_bullets = ["Xây dựng hệ thống phân tán đạt 99.9% uptime."]
        mock_ai.tailor_cv_for_job.return_value = mock_tailor

        mock_notifier = MagicMock()
        mock_notifier.send_job = AsyncMock(return_value=True)

        service = CareerOpsService(
            storage=self.storage,
            ai_service=mock_ai,
            notifier=mock_notifier,
        )

        with patch.object(service, "extract_jd_from_url", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = {
                "title": "Senior Python Engineer",
                "company": "VNG Corporation",
                "link": "https://vng.com.vn/jobs/123",
                "skills": ["Python", "FastAPI", "Docker"],
                "description": "Develop scalable backend services.",
                "requirements": "3+ years Python experience.",
                "benefits": "MacBook Pro, healthcare.",
                "full_jd_raw": "Full JD text content here.",
            }

            result = await service.process_job_url("https://vng.com.vn/jobs/123", send_to_discord=True)

            self.assertTrue(result["success"])
            self.assertEqual(result["match_score"], 88)
            self.assertTrue(result["discord_sent"])
            self.assertIn("pdf_path", result)

            # Check persisted in DB
            saved_job = self.storage.get_job_by_link("https://vng.com.vn/jobs/123")
            self.assertIsNotNone(saved_job)
            self.assertEqual(saved_job["title"], "Senior Python Engineer")
            self.assertEqual(saved_job["match_score"], 88)

            # Check notifier called with attachment
            mock_notifier.send_job.assert_awaited_once()


class TestCareerOpsAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_career_ops_status_endpoint(self):
        res = self.client.get("/api/career-ops/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("workspace_installed", data)
        self.assertIn("supported_features", data)

    def test_career_ops_invalid_url(self):
        res = self.client.post("/api/career-ops/process", json={"url": "not-a-valid-url"})
        self.assertEqual(res.status_code, 400)

    def test_get_applications_tracker_endpoint(self):
        res = self.client.get("/api/career-ops/applications")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("content", data)
        self.assertIn("Applications Tracker", data["content"])

    def test_trigger_daily_harvest_endpoint(self):
        with patch("services.daily_scheduler.daily_scheduler.run_harvest_pipeline", new_callable=AsyncMock) as mock_harvest:
            mock_harvest.return_value = 5
            res = self.client.post("/api/career-ops/trigger-daily-harvest")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["success"])


class TestApplicationsTracker(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_tracker.db"
        self.storage = JobStorage(db_path=str(self.db_path), legacy_jsonl="")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_generate_applications_markdown(self):
        from services.applications_tracker import generate_applications_markdown

        # Insert test jobs
        j1 = Job(title="Backend Dev", company="Tech A", link="https://a.com/job1")
        self.storage.save_jobs([j1])
        job_row = self.storage.get_job_by_link("https://a.com/job1")

        self.storage.save_tailored_cv(
            job_id=job_row["id"],
            match_score=85,
            missing_skills=["Docker"],
            tailored_summary="Python dev",
            tailored_bullets=["Did X"],
            latex_code="% latex",
            pdf_path="data/cvs/cv_test.pdf",
        )

        md = generate_applications_markdown(self.storage)
        self.assertIn("Backend Dev", md)
        self.assertIn("Tech A", md)
        self.assertIn("85%", md)


if __name__ == "__main__":
    unittest.main()
