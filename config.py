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

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

ITEMS_PER_PAGE = 5

# Cache TTLs (seconds)
CACHE_TTL_PRICES = 300          # 5 min
CACHE_TTL_FUNDAMENTALS = 14400  # 4 hours
CACHE_TTL_PROFILE = 86400       # 24 hours

# Rate limits
RATE_LIMIT_GROUP_PER_USER = 3   # queries per window
RATE_LIMIT_WINDOW = 60          # window in seconds

# Disclaimer
DISCLAIMER = "No es asesoramiento financiero."

# Button styles (Bot API 9.4, experimental — via api_kwargs)
# Set env ENABLE_BUTTON_STYLES=1 to activate; ignored by older Telegram clients.
ENABLE_BUTTON_STYLES = os.getenv("ENABLE_BUTTON_STYLES", "").lower() in ("1", "true", "yes")

def btn_style(style: str) -> dict:
    """Return api_kwargs dict for button style if enabled.

    Usage: InlineKeyboardButton("Buy", callback_data="x", **btn_style("success"))
    Valid styles: "success" (green), "danger" (red), "primary" (blue).
    """
    if ENABLE_BUTTON_STYLES and style:
        return {"api_kwargs": {"style": style}}
    return {}
