import json
import tempfile
import unittest
from pathlib import Path

from models.Job import Job
from services.cv_tailor import build_cv_tailor_prompt, load_scraped_jobs
from services.storage import JobStorage


class TestStorageAndCVTailor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_jobs.jsonl"
        self.storage = JobStorage(data_file=str(self.db_path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_deduplicate_jobs(self):
        job1 = Job(
            title="Data Engineer",
            company="Shopee",
            link="https://shopee.vn/job/1",
            full_jd_raw="Full JD content for Data Engineer at Shopee...",
            skills=["Python", "Spark", "Kafka"],
        )
        job2 = Job(
            title="Backend Engineer",
            company="Grab",
            link="https://grab.com/job/2",
            full_jd_raw="Full JD content for Grab...",
            skills=["Go", "Kubernetes"],
        )

        # First save
        saved = self.storage.save_jobs([job1, job2])
        self.assertEqual(saved, 2)
        self.assertEqual(self.storage.count_total_jobs(), 2)

        # Duplicate save should be ignored
        saved_again = self.storage.save_jobs([job1])
        self.assertEqual(saved_again, 0)
        self.assertEqual(self.storage.count_total_jobs(), 2)

    def test_cv_tailor_prompt_builder(self):
        job_dict = {
            "title": "Data Engineer",
            "company": "VNG",
            "skills": ["Python", "Airflow", "ClickHouse"],
            "requirements": "• 2 years with Python & SQL\n• Experience with Airflow",
            "full_jd_raw": "Looking for Data Engineer at VNG...",
        }
        user_cv = "Nguyen Van A - 1 year Python developer."

        prompt = build_cv_tailor_prompt(user_cv, job_dict)
        self.assertIn("Data Engineer", prompt)
        self.assertIn("VNG", prompt)
        self.assertIn("Airflow, ClickHouse", prompt)
        self.assertIn("Nguyen Van A", prompt)
        self.assertIn("ATS Optimization Expert", prompt)


if __name__ == "__main__":
    unittest.main()
