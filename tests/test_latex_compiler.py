import json
import tempfile
import unittest
from pathlib import Path

from services.gemini_service import GeminiService
from services.latex_engine import LatexEngine, escape_latex


class TestLatexCompilerAndAI(unittest.TestCase):
    def test_escape_latex(self):
        self.assertEqual(escape_latex("C++ & Python"), r"C++ \& Python")
        self.assertEqual(escape_latex("100% discount on $50"), r"100\% discount on \$50")
        self.assertEqual(escape_latex("snake_case_var"), r"snake\_case\_var")
        self.assertEqual(escape_latex("{curly}"), r"\{curly\}")
        self.assertEqual(escape_latex(None), "")

    def test_gemini_service_heuristic_fallback(self):
        service = GeminiService(api_key="")
        job = {
            "title": "Backend Python Developer",
            "company": "VNG",
            "skills": ["Python", "FastAPI", "Docker", "Kafka"],
            "requirements": "Proficient in Python and microservices.",
            "full_jd_raw": "Seeking backend developer with Docker and FastAPI experience.",
        }
        profile = {
            "name": "Nguyen Van B",
            "title": "Software Engineer",
            "skills": {
                "Languages": ["Python", "JavaScript"],
                "Frameworks": ["FastAPI", "PostgreSQL"],
            },
        }

        result = service.tailor_cv_for_job(job, profile)
        self.assertGreaterEqual(result.match_score, 60)
        self.assertTrue(len(result.tailored_summary) > 20)
        self.assertTrue(len(result.tailored_bullets) > 0)
        self.assertIn("Backend Python Developer", result.tailored_summary)

    def test_latex_engine_code_generation(self):
        engine = LatexEngine(template_path="templates/cv_template.tex")
        profile = {
            "name": "Trần Văn C",
            "title": "Junior Data Engineer",
            "email": "tranvanc@example.com",
            "phone": "0987654321",
            "location": "Hồ Chí Minh",
            "summary": "Data engineer with Python skills.",
            "skills": {"Languages": ["Python", "SQL"]},
            "experiences": [
                {
                    "role": "Data Engineer Intern",
                    "company": "Tech Vietnam",
                    "location": "HCM",
                    "date": "2023",
                    "bullets": ["Processed ETL pipelines & data lakes"],
                }
            ],
            "projects": [],
            "education": [],
        }

        latex_code = engine.generate_latex_code(
            profile=profile,
            tailored_summary="Specialized in big data & automated pipelines.",
            tailored_bullets=["Accelerated ETL processing by 40% using Python & Spark"],
            ats_keywords=["Airflow", "Kafka"],
        )

        self.assertIn("Trần Văn C", latex_code)
        self.assertIn("Specialized in big data", latex_code)
        self.assertIn("Accelerated ETL processing by 40\\%", latex_code)
        self.assertIn("Target Role Keywords", latex_code)
        self.assertNotIn("{{ CANDIDATE_NAME }}", latex_code)


if __name__ == "__main__":
    unittest.main()
