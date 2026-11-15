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
        self.assertEqual(embed["color"], 2001125)  # Modern Bot Blue
        self.assertIn("Tech Corp", embed["description"])
        self.assertIn("Quận 1, Hồ Chí Minh", embed["description"])
        self.assertIn("Xem chi tiết", embed["description"])
        self.assertEqual(embed["thumbnail"]["url"], "https://example.com/logo.png")
        self.assertIn("FindMyBoss", embed["footer"]["text"])
        self.assertIn("Data Engineer", embed["footer"]["text"])
        self.assertIn("React ✅ nhận thông báo · ❌ tắt", embed["footer"]["text"])
        self.assertNotIn("Career-Ops", embed["footer"]["text"])

        # Clean 2 columns when no ATS score (Ngày đăng removed per user request)
        self.assertEqual(len(embed["fields"]), 2)
        field_dict = {f["name"]: f["value"] for f in embed["fields"]}
        self.assertIn("💰 Mức lương", field_dict)
        self.assertEqual(field_dict["💰 Mức lương"], "20 - 30 Triệu")
        self.assertIn("🎯 Level", field_dict)
        self.assertEqual(field_dict["🎯 Level"], "Junior")
        self.assertNotIn("📅 Ngày đăng", field_dict)

        # Verify all fields are inline for horizontal rendering
        for f in embed["fields"]:
            self.assertTrue(f.get("inline", False))

        # Verify to_dict preserves 100% full JD data for AI / CV tailoring
        job_dict = job.to_dict()
        self.assertEqual(job_dict["requirements"], "• 1 năm kinh nghiệm Python/SQL\n• Biết Docker và Git")
        self.assertEqual(job_dict["benefits"], "• Thưởng tháng 13\n• Laptop MacBook Pro")
        self.assertEqual(len(job_dict["skills"]), 4)

    def test_job_discord_embed_ats_score_tiers(self):
        # 1. High score >= 80: Green / 🟢 Tốt
        job_good = Job(title="Dev", company="Co", link="http://co", match_score=85, cv_generated=True)
        embed_good = job_good.to_discord_embed()
        self.assertEqual(embed_good["color"], 3066993)  # Green
        self.assertEqual(len(embed_good["fields"]), 3)  # Mức lương, Level, ATS Score
        ats_field = next(f for f in embed_good["fields"] if f["name"] == "🎯 ATS Score")
        self.assertIn("🟢 Tốt", ats_field["value"])
        self.assertIn("85%", ats_field["value"])

        # Check CV attachment notification text and ngày đăng are removed
        field_names = [f["name"] for f in embed_good["fields"]]
        self.assertNotIn("📎 CV Tối Ưu ATS", field_names)
        self.assertNotIn("📅 Ngày đăng", field_names)

        # 2. Mid score 60-79: Yellow / 🟡 Có thể
        job_mid = Job(title="Dev", company="Co", link="http://co", match_score=65)
        embed_mid = job_mid.to_discord_embed()
        self.assertEqual(embed_mid["color"], 15844367)  # Yellow
        ats_field_mid = next(f for f in embed_mid["fields"] if f["name"] == "🎯 ATS Score")
        self.assertIn("🟡 Có thể", ats_field_mid["value"])
        self.assertIn("65%", ats_field_mid["value"])

        # 3. Low score < 60: Red / 🔴 Không hợp
        job_low = Job(title="Dev", company="Co", link="http://co", match_score=45)
        embed_low = job_low.to_discord_embed()
        self.assertEqual(embed_low["color"], 15158332)  # Red
        ats_field_low = next(f for f in embed_low["fields"] if f["name"] == "🎯 ATS Score")
        self.assertIn("🔴 Không hợp", ats_field_low["value"])
        self.assertIn("45%", ats_field_low["value"])

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
        self.assertNotIn("thumbnail", embed)  # When company is Unknown and no image, omit thumbnail
        self.assertEqual(len(embed["fields"]), 2)

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
