import json
import os
from pathlib import Path
from typing import Dict, List, Set

from config import get_logger
from models.Job import Job

logger = get_logger("JobStorage")


class JobStorage:
    """Persistent storage for jobs and raw full JDs for downstream AI / CV matching tasks."""

    def __init__(self, data_file: str = "data/jobs.jsonl"):
        self.data_path = Path(data_file)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self._existing_links: Set[str] = self._load_existing_links()

    def _load_existing_links(self) -> Set[str]:
        """Loads already persisted job URLs to avoid duplicates."""
        links = set()
        if not self.data_path.exists():
            return links

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            link = record.get("link")
                            if link:
                                links.add(link)
                        except Exception:
                            continue
        except Exception as e:
            logger.warning(f"Could not load existing dataset links: {e}")

        return links

    def save_jobs(self, jobs: List[Job]) -> int:
        """Appends new jobs with their full raw JD into the JSONL dataset."""
        if not jobs:
            return 0

        new_count = 0
        with open(self.data_path, "a", encoding="utf-8") as f:
            for job in jobs:
                if job.link and job.link != "N/A" and job.link in self._existing_links:
                    continue

                record = job.to_dict()
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                if job.link and job.link != "N/A":
                    self._existing_links.add(job.link)
                new_count += 1

        if new_count > 0:
            logger.info(f"💾 Persisted {new_count} new full-JD job records to: {self.data_path}")
        return new_count

    def count_total_jobs(self) -> int:
        """Returns the total number of saved jobs in dataset."""
        return len(self._existing_links)
