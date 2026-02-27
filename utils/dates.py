from datetime import datetime, date


def format_date(dt) -> str:
    """Format a date for display."""
    if isinstance(dt, datetime):
        return dt.strftime("%d/%m/%Y %H:%M")
    elif isinstance(dt, date):
        return dt.strftime("%d/%m/%Y")
    return str(dt) if dt else "N/A"


def parse_date(s: str):
    """Try to parse a date string."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None
