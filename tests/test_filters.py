import unittest
from crawl.filters import filter_jobs_by_web_config, is_location_matched, is_title_blacklisted
from models.Job import Job


class TestFilters(unittest.TestCase):
    def test_is_title_blacklisted(self):
        blocked, kw = is_title_blacklisted("Senior Python Developer", "5 years", ["senior", "lead"])
        self.assertTrue(blocked)
        self.assertEqual(kw, "senior")

        blocked, kw = is_title_blacklisted("Junior React Developer", "1 year", ["senior", "lead"])
        self.assertFalse(blocked)
        self.assertIsNone(kw)

    def test_is_location_matched(self):
        self.assertTrue(is_location_matched("Quận 1, Hồ Chí Minh", ["Hồ Chí Minh", "Hà Nội"]))
        self.assertTrue(is_location_matched("Cầu Giấy, Hà Nội", ["Hồ Chí Minh", "Hà Nội"]))
        self.assertTrue(is_location_matched("Toàn quốc", ["Hồ Chí Minh"]))
        self.assertTrue(is_location_matched("Remote", ["Hồ Chí Minh"]))
        self.assertFalse(is_location_matched("Đà Nẵng", ["Hồ Chí Minh", "Hà Nội"]))

    def test_filter_jobs_by_web_config(self):
        jobs = [
            Job(title="Junior Python Dev", company="Co A", link="http://a", address="Hồ Chí Minh"),
            Job(title="Senior Backend Dev", company="Co B", link="http://b", address="Hồ Chí Minh"),
            Job(title="Junior Golang Dev", company="Co C", link="http://c", address="Đà Nẵng"),
        ]
        cfg = {
            "blacklisted_keywords": ["senior", "lead"],
            "locations": ["Hồ Chí Minh"],
        }
        passed, rejected = filter_jobs_by_web_config(jobs, cfg)
        self.assertEqual(len(passed), 1)
        self.assertEqual(passed[0].title, "Junior Python Dev")
        self.assertEqual(len(rejected), 2)


if __name__ == "__main__":
    unittest.main()
