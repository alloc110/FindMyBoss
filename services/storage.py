import contextlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import get_logger
from models.Job import Job

logger = get_logger("JobStorage")


class JobStorage:
    """
    High-performance SQLite persistent storage for scraped jobs, raw JDs,
    and downstream AI/ATS tailored CV documents with WAL mode enabled.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        data_file: Optional[str] = None,
        legacy_jsonl: str = "data/jobs.jsonl",
    ):
        chosen_path = db_path or data_file or "data/jobs.db"
        # If user passed a .jsonl filename for db_path, rename extension to .db
        if chosen_path.endswith(".jsonl"):
            chosen_path = chosen_path.replace(".jsonl", ".db")

        self.db_path = Path(chosen_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.legacy_jsonl = Path(legacy_jsonl) if legacy_jsonl else None

        self._init_db()
        # Only auto-migrate into the default production database to avoid polluting test databases
        if self.legacy_jsonl and self.legacy_jsonl.exists() and self.db_path.resolve() == Path("data/jobs.db").resolve():
            self._auto_migrate_legacy_jsonl()

    @contextlib.contextmanager
    def _get_connection(self):
        """Yields a SQLite connection with Row factory and WAL mode enabled, closing cleanly on exit."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initializes tables and indexes for jobs and tailored CV records."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    link TEXT UNIQUE NOT NULL,
                    address TEXT,
                    exp TEXT,
                    salary TEXT,
                    posted_date TEXT,
                    image TEXT,
                    time TEXT,
                    skills TEXT,
                    description TEXT,
                    requirements TEXT,
                    benefits TEXT,
                    full_jd_raw TEXT,
                    status TEXT DEFAULT 'saved',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # Auto-migrate for existing tables that lack status column
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()]
            if "status" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN status TEXT DEFAULT 'saved';")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tailored_cvs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL UNIQUE,
                    match_score INTEGER DEFAULT 0,
                    missing_skills TEXT,
                    tailored_summary TEXT,
                    tailored_bullets TEXT,
                    latex_code TEXT,
                    pdf_path TEXT,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
                );
                """
            )

            # Indexes for fast lookup and filtering
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tailored_job_id ON tailored_cvs(job_id);")
            conn.commit()

    def _auto_migrate_legacy_jsonl(self) -> None:
        """Imports existing jobs from legacy data/jobs.jsonl if jobs table is empty."""
        if not self.legacy_jsonl.exists():
            return

        try:
            with self._get_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                if count > 0:
                    return

                logger.info(f"🔄 Migrating legacy dataset from {self.legacy_jsonl} into SQLite...")
                migrated_jobs: List[Job] = []
                with open(self.legacy_jsonl, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                job = Job(
                                    title=data.get("title", "N/A"),
                                    company=data.get("company", "N/A"),
                                    link=data.get("link", "N/A"),
                                    address=data.get("address", "Hồ Chí Minh"),
                                    exp=data.get("exp"),
                                    salary=data.get("salary", "Deal"),
                                    posted_date=data.get("posted_date", "N/A"),
                                    image=data.get("image"),
                                    time=data.get("time"),
                                    skills=data.get("skills", []),
                                    description=data.get("description"),
                                    requirements=data.get("requirements"),
                                    benefits=data.get("benefits"),
                                    full_jd_raw=data.get("full_jd_raw"),
                                )
                                migrated_jobs.append(job)
                            except Exception:
                                continue

                if migrated_jobs:
                    self.save_jobs(migrated_jobs)
                    logger.info(f"✅ Migrated {len(migrated_jobs)} legacy jobs into SQLite database!")
        except Exception as e:
            logger.warning(f"Failed to auto-migrate legacy JSONL: {e}")

    def save_jobs(self, jobs: List[Job]) -> int:
        """
        Inserts new jobs into the SQLite database with automatic deduplication via UNIQUE(link).
        Returns the number of newly added jobs.
        """
        if not jobs:
            return 0

        inserted_count = 0
        sql = """
        INSERT OR IGNORE INTO jobs (
            title, company, link, address, exp, salary, posted_date,
            image, time, skills, description, requirements, benefits, full_jd_raw
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for job in jobs:
                if not job.link or job.link == "N/A":
                    continue

                skills_json = json.dumps(job.skills or [], ensure_ascii=False)
                cursor.execute(
                    sql,
                    (
                        job.title,
                        job.company,
                        job.link,
                        job.address,
                        job.exp,
                        job.salary,
                        job.posted_date,
                        job.image,
                        job.time,
                        skills_json,
                        job.description,
                        job.requirements,
                        job.benefits,
                        job.full_jd_raw,
                    ),
                )
                if cursor.rowcount > 0:
                    inserted_count += 1

            conn.commit()

        if inserted_count > 0:
            logger.info(f"💾 Persisted {inserted_count} new job records to SQLite DB: {self.db_path}")
        return inserted_count

    def count_total_jobs(self) -> int:
        """Returns the total number of jobs saved in SQLite."""
        with self._get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    def get_jobs(
        self,
        query: Optional[str] = None,
        skill: Optional[str] = None,
        has_cv: Optional[bool] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieves a paginated list of jobs with optional search filters.
        Returns (list_of_job_dicts, total_matching_count).
        """
        conditions = []
        params: List[Any] = []

        if query and query.strip():
            term = f"%{query.strip().lower()}%"
            conditions.append(
                "(LOWER(j.title) LIKE ? OR LOWER(j.company) LIKE ? OR LOWER(j.address) LIKE ? OR LOWER(j.full_jd_raw) LIKE ?)"
            )
            params.extend([term, term, term, term])

        if skill and skill.strip():
            skill_term = f"%{skill.strip().lower()}%"
            conditions.append("LOWER(j.skills) LIKE ?")
            params.append(skill_term)

        if has_cv is True:
            conditions.append("t.id IS NOT NULL")
        elif has_cv is False:
            conditions.append("t.id IS NULL")

        if status and status.strip():
            conditions.append("j.status = ?")
            params.append(status.strip())

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        count_sql = f"""
        SELECT COUNT(*)
        FROM jobs j
        LEFT JOIN tailored_cvs t ON j.id = t.job_id
        {where_clause}
        """

        select_sql = f"""
        SELECT
            j.*,
            t.id AS cv_id,
            t.match_score,
            t.pdf_path,
            t.status AS cv_status,
            t.created_at AS cv_created_at
        FROM jobs j
        LEFT JOIN tailored_cvs t ON j.id = t.job_id
        {where_clause}
        ORDER BY j.id DESC
        LIMIT ? OFFSET ?
        """

        with self._get_connection() as conn:
            total = conn.execute(count_sql, params).fetchone()[0]

            fetch_params = list(params) + [limit, offset]
            cursor = conn.execute(select_sql, fetch_params)
            rows = cursor.fetchall()

            jobs_list = []
            for row in rows:
                item = dict(row)
                try:
                    item["skills"] = json.loads(item["skills"]) if item["skills"] else []
                except Exception:
                    item["skills"] = []
                jobs_list.append(item)

            return jobs_list, total

    def get_job_by_id(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a single job by its ID, along with any tailored CV metadata."""
        sql = """
        SELECT
            j.*,
            t.id AS cv_id,
            t.match_score,
            t.missing_skills,
            t.tailored_summary,
            t.tailored_bullets,
            t.latex_code,
            t.pdf_path,
            t.status AS cv_status,
            t.created_at AS cv_created_at
        FROM jobs j
        LEFT JOIN tailored_cvs t ON j.id = t.job_id
        WHERE j.id = ?
        """
        with self._get_connection() as conn:
            row = conn.execute(sql, (job_id,)).fetchone()
            if not row:
                return None

            item = dict(row)
            try:
                item["skills"] = json.loads(item["skills"]) if item["skills"] else []
            except Exception:
                item["skills"] = []

            if item.get("missing_skills"):
                try:
                    item["missing_skills"] = json.loads(item["missing_skills"])
                except Exception:
                    pass

            if item.get("tailored_bullets"):
                try:
                    item["tailored_bullets"] = json.loads(item["tailored_bullets"])
                except Exception:
                    pass

            return item

    def update_job_status(self, job_id: int, status: str) -> bool:
        """Updates the tracking status (saved, applied, interviewing, offered, rejected) for a job."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE jobs SET status = ? WHERE id = ?",
                (status, job_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_job(self, job_id: int) -> bool:
        """
        Permanently deletes a job from SQLite.
        Associated tailored_cvs rows are deleted via ON DELETE CASCADE.
        Also deletes generated PDF files if they exist.
        """
        with self._get_connection() as conn:
            # Check for PDF file to unlink
            row = conn.execute("SELECT pdf_path FROM tailored_cvs WHERE job_id = ?", (job_id,)).fetchone()
            if row and row["pdf_path"]:
                pdf_file = Path(row["pdf_path"])
                if pdf_file.exists():
                    try:
                        pdf_file.unlink()
                    except Exception as e:
                        logger.warning(f"Could not remove PDF file for job #{job_id}: {e}")

            cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted job #{job_id} from SQLite database")
            return deleted

    def save_tailored_cv(
        self,
        job_id: int,
        match_score: int,
        missing_skills: List[str],
        tailored_summary: str,
        tailored_bullets: List[str],
        latex_code: str,
        pdf_path: str,
        status: str = "completed",
    ) -> int:
        """Upserts a tailored CV record for a specific job."""
        sql = """
        INSERT INTO tailored_cvs (
            job_id, match_score, missing_skills, tailored_summary,
            tailored_bullets, latex_code, pdf_path, status, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(job_id) DO UPDATE SET
            match_score = excluded.match_score,
            missing_skills = excluded.missing_skills,
            tailored_summary = excluded.tailored_summary,
            tailored_bullets = excluded.tailored_bullets,
            latex_code = excluded.latex_code,
            pdf_path = excluded.pdf_path,
            status = excluded.status,
            updated_at = CURRENT_TIMESTAMP;
        """

        missing_json = json.dumps(missing_skills or [], ensure_ascii=False)
        bullets_json = json.dumps(tailored_bullets or [], ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                sql,
                (
                    job_id,
                    match_score,
                    missing_json,
                    tailored_summary,
                    bullets_json,
                    latex_code,
                    pdf_path,
                    status,
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def get_stats(self) -> Dict[str, Any]:
        """Provides dashboard high-level KPIs."""
        with self._get_connection() as conn:
            total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            total_cvs = conn.execute("SELECT COUNT(*) FROM tailored_cvs").fetchone()[0]
            total_companies = conn.execute("SELECT COUNT(DISTINCT company) FROM jobs").fetchone()[0]

            return {
                "total_jobs": total_jobs,
                "total_cvs": total_cvs,
                "total_companies": total_companies,
            }
