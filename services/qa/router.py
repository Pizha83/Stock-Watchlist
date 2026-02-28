"""Message router: extract tickers and detect financial intents."""

import re

# Tokens that look like tickers but aren't
_BLACKLIST = {
    "CEO", "CFO", "CTO", "COO", "EPS", "ETF", "IPO", "USA", "EUR", "USD",
    "GBP", "JPY", "CHF", "FCF", "ROE", "ROA", "PER", "DCF", "EBITDA",
    "WACC", "CAPEX", "NYSE", "IBEX", "DAX", "CAC", "FTSE", "MOAT",
    "GDP", "CPI", "FED", "BCE", "ECB", "SEC", "API", "TTM", "YTD",
    "QOQ", "YOY", "MOM", "BPA", "NAV", "AUM", "ESG", "SMA", "EMA",
    "RSI", "MACD", "ADR", "OTC", "SPAC", "REIT", "GAAP", "IFRS",
    "CEO", "THE", "AND", "FOR", "NOT", "ALL", "NEW", "OLD", "BIG",
    "LOW", "HIGH", "BUY", "SELL", "HOLD", "PUT", "CALL", "LONG",
    "SHORT", "BEAR", "BULL", "STOP", "LOSS", "GAIN", "RISK", "DEBT",
    "CASH", "FREE", "NET", "TAX", "FEE", "DIV", "AVG", "MAX", "MIN",
    "TOP", "HOT", "BEST", "GOOD", "BAD", "FAIR", "POOR",
}

# Regex: $AAPL, AAPL, SAN.MC, AIR.PA, BMW.DE, 0700.HK
_TICKER_RE = re.compile(
    r"(?:^|[\s,;:(])"
    r"\$?([A-Z0-9]{1,5}(?:\.[A-Z]{1,2})?)"
    r"(?=[\s,;:)?!.]|$)",
    re.IGNORECASE,
)

# Intent keywords (Spanish + English)
_INTENT_MAP = [
    ("PRICE", re.compile(
        r"precio|cotizaci[oó]n|price|quote|cu[aá]nto\s+vale|current|last",
        re.IGNORECASE,
    )),
    ("VALUATION", re.compile(
        r"valoraci[oó]n|valuation|m[uú]ltiplos|P/?E\b|PER\b|EV/?|price.to.book|P/?B\b|P/?S\b",
        re.IGNORECASE,
    )),
    ("MARGINS", re.compile(
        r"m[aá]rgen|margin|bruto|operativo|neto|gross|operating|net\s+margin|rentabilidad",
        re.IGNORECASE,
    )),
    ("DEBT", re.compile(
        r"deuda|debt|leverage|apalancamiento|balance|solvencia|endeudamiento",
        re.IGNORECASE,
    )),
    ("DIVIDEND", re.compile(
        r"dividendo|dividend|yield|payout|reparto",
        re.IGNORECASE,
    )),
    ("CASHFLOW", re.compile(
        r"FCF|free\s+cash|flujo|cash\s+flow|caja|operating\s+cash",
        re.IGNORECASE,
    )),
    ("ANALYSTS", re.compile(
        r"analista|analyst|target|objetivo|consenso|estimate|recomendaci[oó]n",
        re.IGNORECASE,
    )),
    ("COMPARE", re.compile(
        r"\bvs\b|comparar|compare|versus",
        re.IGNORECASE,
    )),
]


def parse_query(text: str) -> dict:
    """Parse a user query and extract tickers + intent.

    Returns dict with keys: tickers (list[str]), intent (str), raw (str).
    """
    # Clean up command prefixes
    clean = text.strip()
    clean = re.sub(r"^/q(?:@\S+)?\s*", "", clean, flags=re.IGNORECASE)
    clean = clean.strip()

    # Extract tickers
    raw_matches = _TICKER_RE.findall(clean)
    tickers = []
    for m in raw_matches:
        t = m.upper()
        if t not in _BLACKLIST and len(t) >= 1:
            tickers.append(t)
    # Deduplicate preserving order
    seen = set()
    unique_tickers = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique_tickers.append(t)
    tickers = unique_tickers

    # Detect intent
    intent = "SUMMARY"
    for intent_name, pattern in _INTENT_MAP:
        if pattern.search(clean):
            intent = intent_name
            break

    # If COMPARE detected but less than 2 tickers, fall back to SUMMARY
    if intent == "COMPARE" and len(tickers) < 2:
        intent = "SUMMARY"

    return {
        "tickers": tickers,
        "intent": intent,
        "raw": clean,
    }
