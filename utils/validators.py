import re
from urllib.parse import urlparse


def is_valid_url(url: str) -> bool:
    """Validate a URL."""
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def is_valid_ticker(ticker: str) -> bool:
    """Validate a stock ticker symbol."""
    return bool(re.match(r"^[A-Za-z0-9.\-]{1,10}$", ticker.strip()))
