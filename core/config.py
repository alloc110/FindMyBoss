import logging
import os
import zoneinfo
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Timezone standard (with Windows tzdata fallback)
try:
    VN_TIMEZONE = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    VN_TIMEZONE = timezone(timedelta(hours=7))


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Provides a standardized logger across all components without duplicate handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        try:
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_dir / "crawl_log.txt", encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass

    return logger


@dataclass(frozen=True)
class ScraperConfig:
    """Central configuration for scraper orchestrator and crawlers."""

    discord_webhook_url: Optional[str] = os.getenv("DISCORD_WEBHOOK_URL")
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    element_timeout_ms: float = 1500.0
    navigation_timeout_ms: float = 25000.0
    throttle_delay_seconds: float = 5.0

    # Default keyword blacklists for senior/lead positions
    unwanted_titles: tuple[str, ...] = (
        "senior",
        "lead",
        "middle",
        "mid",
        "sr",
        "supervisor",
        "manager",
        "director",
        "head",
        "chief",
        "trưởng",
        "phó",
        "giám đốc",
        "quản lý",
        "trưởng phòng",
        "phó phòng",
        "trưởng ban",
        "phó ban",
        "trưởng nhóm",
        "phó nhóm",
        "trưởng dự án",
    )

    # Allowed target levels
    target_levels: tuple[str, ...] = ("intern", "fresher", "junior")


config = ScraperConfig()
