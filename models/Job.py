from dataclasses import dataclass
from datetime import datetime

@dataclass
class Job:
    title: str
    company: str
    link: str
    address: str
    exp: str
    salary: str 
    posted_date: str
    image: str 
