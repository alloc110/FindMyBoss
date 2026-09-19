import tempfile
import unittest
from pathlib import Path

from models.Job import Job
from services.storage import JobStorage


class TestSQLiteStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.storage = JobStorage(db_path=str(self.db_path), legacy_jsonl="")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_retrieve_jobs(self):
        job1 = Job(
            title="Junior Python Engineer",
            company="Tech Corp",
            link="https://techcorp.example.com/job/1",
            address="TP. Hồ Chí Minh",
            salary="20 - 30 Triệu",
            skills=["Python", "FastAPI", "Docker"],
            full_jd_raw="We need Python developer with FastAPI.",
        )
        job2 = Job(
            title="Frontend React Developer",
            company="Web Solution",
            link="https://websolution.example.com/job/2",
            address="Hà Nội",
            salary="15 - 25 Triệu",
            skills=["React", "TypeScript", "Tailwind"],
            full_jd_raw="React and TypeScript experience required.",
        )

        inserted = self.storage.save_jobs([job1, job2])
        self.assertEqual(inserted, 2)
        self.assertEqual(self.storage.count_total_jobs(), 2)

        # Duplicate should be ignored
        inserted_again = self.storage.save_jobs([job1])
        self.assertEqual(inserted_again, 0)
        self.assertEqual(self.storage.count_total_jobs(), 2)

        # Search query
        jobs, total = self.storage.get_jobs(query="Python")
        self.assertEqual(total, 1)
        self.assertEqual(jobs[0]["title"], "Junior Python Engineer")
        self.assertEqual(jobs[0]["company"], "Tech Corp")
        self.assertIn("Python", jobs[0]["skills"])

        # Retrieve single job
        single = self.storage.get_job_by_id(jobs[0]["id"])
        self.assertIsNotNone(single)
        self.assertEqual(single["company"], "Tech Corp")

    def test_tailored_cv_workflow(self):
        job = Job(
            title="AI Engineer",
            company="Open Lab",
            link="https://openlab.example.com/job/ai",
            skills=["PyTorch", "LLM"],
        )
        self.storage.save_jobs([job])
        jobs, _ = self.storage.get_jobs(query="Open Lab")
        job_id = jobs[0]["id"]

        # Save tailored CV
        cv_id = self.storage.save_tailored_cv(
            job_id=job_id,
            match_score=92,
            missing_skills=["LangChain"],
            tailored_summary="Experienced AI Engineer with deep LLM focus.",
            tailored_bullets=["Fine-tuned Llama 3 model", "Deployed FastAPI inference service"],
            latex_code="\\documentclass{article}...",
            pdf_path="data/cvs/cv_1.pdf",
            status="completed",
        )
        self.assertGreater(cv_id, 0)

        # Retrieve job with CV metadata
        detailed = self.storage.get_job_by_id(job_id)
        self.assertEqual(detailed["match_score"], 92)
        self.assertIn("LangChain", detailed["missing_skills"])
        self.assertEqual(len(detailed["tailored_bullets"]), 2)
        self.assertEqual(detailed["cv_status"], "completed")

        # Check stats
        stats = self.storage.get_stats()
        self.assertEqual(stats["total_jobs"], 1)
        self.assertEqual(stats["total_cvs"], 1)
        self.assertEqual(stats["total_companies"], 1)

    def test_job_status_and_deletion(self):
        job = Job(
            title="DevOps Engineer",
            company="Cloud Nine",
            link="https://cloudnine.example.com/job/devops",
            skills=["Kubernetes", "Terraform"],
        )
        self.storage.save_jobs([job])
        jobs, _ = self.storage.get_jobs(query="Cloud Nine")
        job_id = jobs[0]["id"]
        self.assertEqual(jobs[0]["status"], "saved")

        # Update status
        self.assertTrue(self.storage.update_job_status(job_id, "interviewing"))
        job_updated = self.storage.get_job_by_id(job_id)
        self.assertEqual(job_updated["status"], "interviewing")

        # Filter by status
        saved_jobs, saved_count = self.storage.get_jobs(status="saved")
        self.assertEqual(saved_count, 0)

        interviewing_jobs, int_count = self.storage.get_jobs(status="interviewing")
        self.assertEqual(int_count, 1)
        self.assertEqual(interviewing_jobs[0]["id"], job_id)

        # Delete job
        self.assertTrue(self.storage.delete_job(job_id))
        self.assertIsNone(self.storage.get_job_by_id(job_id))
        self.assertEqual(self.storage.count_total_jobs(), 0)


if __name__ == "__main__":
    unittest.main()

