import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_admin_ids = os.getenv("ADMIN_USER_IDS", "")
ADMIN_USER_IDS = [int(x.strip()) for x in _admin_ids.split(",") if x.strip().isdigit()]

ITEMS_PER_PAGE = 5
