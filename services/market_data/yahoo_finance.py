"""Yahoo Finance data provider using yfinance, with cache."""

import logging
from datetime import datetime

import yfinance as yf

from config import CACHE_TTL_PRICES, CACHE_TTL_FUNDAMENTALS, CACHE_TTL_PROFILE
from services.cache import cache_get, cache_set

logger = logging.getLogger("stockbot")


def get_company_data(ticker: str) -> dict | None:
    """Fetch comprehensive company data.

    Uses two cache layers:
    - Profile (name, sector, etc.): 24h TTL
    - Full data (fundamentals + price): 4h TTL
    """
    key = f"company:{ticker}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    data = _fetch_company_data(ticker)
    if data:
        cache_set(key, data, CACHE_TTL_FUNDAMENTALS)
        # Also cache profile separately with longer TTL
        profile = {
            k: data[k]
            for k in ("name", "sector", "industry", "country", "currency",
                       "exchange", "description", "website")
            if k in data
        }
        cache_set(f"profile:{ticker}", profile, CACHE_TTL_PROFILE)
    return data


def get_quick_quote(ticker: str) -> dict | None:
    """Fetch price + basic info (cached: prices TTL)."""
    key = f"quote:{ticker}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    data = _fetch_quick_quote(ticker)
    if data:
        cache_set(key, data, CACHE_TTL_PRICES)
    return data


def get_watchlist_quotes(tickers: list[str]) -> dict[str, dict]:
    """Fetch quick quotes for multiple tickers."""
    results = {}
    for ticker in tickers:
        data = get_quick_quote(ticker)
        if data:
            results[ticker] = data
    return results


def get_current_price(ticker: str) -> float | None:
    """Get just the current price for a ticker (uses quick quote cache)."""
    q = get_quick_quote(ticker)
    if q:
        return q.get("price")
    return None


# ── Internal fetch functions ─────────────────────────────────────

def _fetch_company_data(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        info = t.info

        if not info or info.get("quoteType") == "NONE" or "symbol" not in info:
            return None

        def g(key, default=None):
            v = info.get(key)
            return v if v is not None else default

        return {
            "name": g("longName", g("shortName", ticker)),
            "sector": g("sector", ""),
            "industry": g("industry", ""),
            "country": g("country", ""),
            "currency": g("currency", "USD"),
            "exchange": g("exchange", ""),
            "description": g("longBusinessSummary", ""),
            "employees": g("fullTimeEmployees"),
            "website": g("website", ""),
            "price": g("currentPrice", g("regularMarketPrice")),
            "open": g("open"),
            "previous_close": g("previousClose"),
            "change_pct": _calc_change_pct(
                g("currentPrice", g("regularMarketPrice")),
                g("previousClose"),
            ),
            "high_52w": g("fiftyTwoWeekHigh"),
            "low_52w": g("fiftyTwoWeekLow"),
            "avg_volume": g("averageVolume"),
            "market_cap": g("marketCap"),
            "enterprise_value": g("enterpriseValue"),
            "revenue": g("totalRevenue"),
            "gross_profit": g("grossProfits"),
            "ebitda": g("ebitda"),
            "net_income": g("netIncomeToCommon"),
            "eps": g("trailingEps"),
            "forward_eps": g("forwardEps"),
            "free_cash_flow": g("freeCashflow"),
            "operating_cash_flow": g("operatingCashflow"),
            "gross_margin": g("grossMargins"),
            "operating_margin": g("operatingMargins"),
            "net_margin": g("profitMargins"),
            "pe_trailing": g("trailingPE"),
            "pe_forward": g("forwardPE"),
            "ev_ebitda": g("enterpriseToEbitda"),
            "ev_revenue": g("enterpriseToRevenue"),
            "pb": g("priceToBook"),
            "ps": g("priceToSalesTrailing12Months"),
            "roe": g("returnOnEquity"),
            "roa": g("returnOnAssets"),
            "total_debt": g("totalDebt"),
            "total_cash": g("totalCash"),
            "debt_to_equity": g("debtToEquity"),
            "dividend_yield": g("dividendYield"),
            "dividend_rate": g("dividendRate"),
            "payout_ratio": g("payoutRatio"),
            "ex_dividend_date": _ts_to_str(g("exDividendDate")),
            "target_mean": g("targetMeanPrice"),
            "target_high": g("targetHighPrice"),
            "target_low": g("targetLowPrice"),
            "recommendation": g("recommendationKey", ""),
            "num_analysts": g("numberOfAnalystOpinions", 0),
        }
    except Exception as e:
        logger.error(f"yfinance error for {ticker}: {e}")
        return None


def _fetch_quick_quote(ticker: str) -> dict | None:
    """Fetch price data using ONLY fast_info (single fast HTTP call).

    Name and PE are not available from fast_info; they come from
    the full company data cache when needed.
    """
    try:
        t = yf.Ticker(ticker)
        fast = t.fast_info

        price = getattr(fast, "last_price", 0) or 0
        prev = getattr(fast, "previous_close", 0) or 0

        # Try to get name from profile or company cache (no extra HTTP call)
        cached_profile = cache_get(f"profile:{ticker}")
        cached_company = cache_get(f"company:{ticker}")
        ref = cached_company or cached_profile or {}
        name = ref.get("name", ticker)
        pe = cached_company.get("pe_trailing") if cached_company else None

        return {
            "name": name,
            "price": price,
            "previous_close": prev,
            "change_pct": _calc_change_pct(price, prev),
            "market_cap": getattr(fast, "market_cap", 0) or 0,
            "currency": getattr(fast, "currency", "USD") or "USD",
            "pe_trailing": pe or 0,
        }
    except Exception as e:
        logger.error(f"yfinance quick quote error for {ticker}: {e}")
        return None


def _calc_change_pct(current, previous) -> float:
    if not current or not previous:
        return 0
    return ((current - previous) / previous) * 100


def _ts_to_str(ts) -> str:
    if not ts:
        return ""
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts).strftime("%d/%m/%Y")
        return str(ts)
    except Exception:
        return ""
