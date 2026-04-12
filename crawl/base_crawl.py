import requests
from bs4 import BeautifulSoup

class JobScraper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.found_jobs = []

    def get_soup(self, url):
        response = requests.get(url, headers=self.headers)
        return BeautifulSoup(response.content, 'html.parser')

    def scrape(self):
        """Hàm này sẽ được viết đè ở lớp con"""
        raise NotImplementedError("Bạn phải thực hiện hàm này ở lớp con!")