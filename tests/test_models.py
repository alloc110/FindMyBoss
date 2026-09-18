import unittest
from models.Job import Job
from crawl.base_crawl import JobScraper


class DummyScraper(JobScraper):
    """Dummy scraper subclass for unit testing base functionality."""

    async def crawl_all_pages(self, today: bool = False):
        return []

    async def parse_card_detail(self, card):
        return None


class TestJobModelAndScraper(unittest.TestCase):
    def test_job_discord_embed_rich_structure(self):
        job = Job(
            title="Junior Data Engineer",
            company="Tech Corp",
            link="https://example.com/job/123",
            address="Quận 1, Hồ Chí Minh",
            exp="Junior",
            salary="20 - 30 Triệu",
            posted_date="Hôm nay",
            image="https://example.com/logo.png",
            time="2026-09-18T20:00:00+07:00",
            skills=["Python", "SQL", "Docker", "AWS"],
            requirements="• 1 năm kinh nghiệm Python/SQL\n• Biết Docker và Git",
            benefits="• Thưởng tháng 13\n• Laptop MacBook Pro",
        )

        embed = job.to_discord_embed()

        # Basic fields
        self.assertEqual(embed["title"], "Junior Data Engineer")
        self.assertEqual(embed["url"], "https://example.com/job/123")
        self.assertEqual(embed["color"], 3066993)
        self.assertIn("Tech Corp", embed["description"])
        self.assertIn("20 - 30 Triệu", embed["description"])
        self.assertIn("Quận 1, Hồ Chí Minh", embed["description"])
        self.assertEqual(embed["thumbnail"]["url"], "https://example.com/logo.png")

        # Clean Discord Embed Fields (No bulky JD/Requirements/Benefits in Discord)
        self.assertEqual(len(embed["fields"]), 1)
        field_names = [f["name"] for f in embed["fields"]]
        self.assertIn("🛠️ Tech Stack", field_names)
        self.assertNotIn("📋 Yêu cầu ứng viên", field_names)
        self.assertNotIn("🎁 Quyền lợi nổi bật", field_names)

        # Check skills formatting
        skills_field = embed["fields"][0]
        self.assertIn("`Python`", skills_field["value"])
        self.assertIn("`Docker`", skills_field["value"])

        # Verify to_dict preserves 100% full JD data for AI / CV tailoring
        job_dict = job.to_dict()
        self.assertEqual(job_dict["requirements"], "• 1 năm kinh nghiệm Python/SQL\n• Biết Docker và Git")
        self.assertEqual(job_dict["benefits"], "• Thưởng tháng 13\n• Laptop MacBook Pro")
        self.assertEqual(len(job_dict["skills"]), 4)

    def test_job_discord_embed_fallback(self):
        job = Job(
            title="",
            company="Unknown",
            link="N/A",
            image=None,
        )
        embed = job.to_discord_embed()
        self.assertEqual(embed["title"], "Job Alert")
        self.assertIsNone(embed["url"])
        self.assertNotIn("thumbnail", embed)
        self.assertEqual(len(embed["fields"]), 0)

    def test_filter_unwanted_titles(self):
        scraper = DummyScraper()
        jobs = [
            Job(title="Junior Data Engineer", company="Co A", link="http://a"),
            Job(title="Senior Data Engineer", company="Co B", link="http://b"),
            Job(title="Tech Lead Python", company="Co C", link="http://c"),
            Job(title="Intern Data Analyst", company="Co D", link="http://d"),
            Job(title="Trưởng phòng IT", company="Co E", link="http://e"),
            Job(title="Fresher Software Engineer", company="Co F", link="http://f"),
        ]

        filtered = scraper.filter_unwanted_titles(jobs)
        titles = [j.title for j in filtered]

        self.assertIn("Junior Data Engineer", titles)
        self.assertIn("Intern Data Analyst", titles)
        self.assertIn("Fresher Software Engineer", titles)
        self.assertNotIn("Senior Data Engineer", titles)
        self.assertNotIn("Tech Lead Python", titles)
        self.assertNotIn("Trưởng phòng IT", titles)
        self.assertEqual(len(filtered), 3)

    def test_clean_bullet_points(self):
        raw = "1. First requirement\n- Second requirement\n* Third requirement\n short\n"
        cleaned = JobScraper.clean_bullet_points(raw, max_points=3)
        self.assertIn("• First requirement", cleaned)
        self.assertIn("• Second requirement", cleaned)
        self.assertIn("• Third requirement", cleaned)


if __name__ == "__main__":
    unittest.main()
