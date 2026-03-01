import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(level=logging.INFO):
    """Configure logging for the application (stdout + file)."""
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_dir = Path(__file__).resolve().parent.parent / "data"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "stockbot.log"

    logging.basicConfig(
        format=fmt,
        level=level,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.handlers.RotatingFileHandler(
                log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8",
            ),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    return logging.getLogger("stockbot")
