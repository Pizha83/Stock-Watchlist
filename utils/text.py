import re


def escape_html(text: str) -> str:
    """Escape special characters for Telegram HTML."""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def truncate(text: str, max_len: int = 200) -> str:
    """Truncate text to max_len characters."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def clean_text(text: str) -> str:
    """Remove excessive whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def format_number(n, currency: str = "") -> str:
    """Format large numbers: 1234567890 -> 1.23B"""
    if n is None or n == 0:
        return "N/A"
    prefix = f"{currency} " if currency else ""
    sign = "-" if n < 0 else ""
    a = abs(n)
    if a >= 1e12:
        return f"{sign}{prefix}{a / 1e12:.2f}T"
    if a >= 1e9:
        return f"{sign}{prefix}{a / 1e9:.2f}B"
    if a >= 1e6:
        return f"{sign}{prefix}{a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}{prefix}{a / 1e3:.1f}K"
    return f"{sign}{prefix}{a:.2f}"


def format_pct(n) -> str:
    """Format a decimal as percentage: 0.462 -> 46.2%"""
    if n is None or n == 0:
        return "N/A"
    return f"{n * 100:.1f}%"


def format_ratio(n) -> str:
    """Format a ratio: 30.5 -> 30.5x"""
    if n is None or n == 0:
        return "N/A"
    return f"{n:.1f}x"


def format_price(n, currency: str = "") -> str:
    """Format a price."""
    if n is None or n == 0:
        return "N/A"
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{n:,.2f}"


def safe_truncate_html(text: str, max_len: int = 4000, suffix: str = "...") -> str:
    """Truncate text at line boundaries to avoid breaking HTML tags.

    Cuts at the last complete line that fits within max_len - len(suffix).
    """
    if len(text) <= max_len:
        return text
    budget = max_len - len(suffix)
    lines = text.split("\n")
    result = []
    total = 0
    for line in lines:
        needed = len(line) + (1 if result else 0)
        if total + needed > budget:
            break
        result.append(line)
        total += needed
    return "\n".join(result) + suffix
