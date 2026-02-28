"""Yahoo Finance data provider using yfinance, with cache."""

import logging
from datetime import datetime

import yfinance as yf

from config import CACHE_TTL_PRICES, CACHE_TTL_FUNDAMENTALS, CACHE_TTL_PROFILE
from services.cache import cache_get, cache_set

logger = logging.getLogger("stockbot")


def get_company_data(ticker: str) -> dict | None:
    """Fetch comprehensive company data (cached: fundamentals TTL)."""
    key = f"company:{ticker}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    data = _fetch_company_data(ticker)
    if data:
        cache_set(key, data, CACHE_TTL_FUNDAMENTALS)
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
            "employees": g("fullTimeEmployees", 0),
            "website": g("website", ""),
            "price": g("currentPrice", g("regularMarketPrice", 0)),
            "previous_close": g("previousClose", 0),
            "change_pct": _calc_change_pct(
                g("currentPrice", g("regularMarketPrice", 0)),
                g("previousClose", 0),
            ),
            "high_52w": g("fiftyTwoWeekHigh", 0),
            "low_52w": g("fiftyTwoWeekLow", 0),
            "avg_volume": g("averageVolume", 0),
            "market_cap": g("marketCap", 0),
            "enterprise_value": g("enterpriseValue", 0),
            "revenue": g("totalRevenue", 0),
            "gross_profit": g("grossProfits", 0),
            "ebitda": g("ebitda", 0),
            "net_income": g("netIncomeToCommon", 0),
            "eps": g("trailingEps", 0),
            "forward_eps": g("forwardEps", 0),
            "free_cash_flow": g("freeCashflow", 0),
            "operating_cash_flow": g("operatingCashflow", 0),
            "gross_margin": g("grossMargins", 0),
            "operating_margin": g("operatingMargins", 0),
            "net_margin": g("profitMargins", 0),
            "pe_trailing": g("trailingPE", 0),
            "pe_forward": g("forwardPE", 0),
            "ev_ebitda": g("enterpriseToEbitda", 0),
            "ev_revenue": g("enterpriseToRevenue", 0),
            "pb": g("priceToBook", 0),
            "ps": g("priceToSalesTrailing12Months", 0),
            "roe": g("returnOnEquity", 0),
            "roa": g("returnOnAssets", 0),
            "total_debt": g("totalDebt", 0),
            "total_cash": g("totalCash", 0),
            "debt_to_equity": g("debtToEquity", 0),
            "dividend_yield": g("dividendYield", 0),
            "dividend_rate": g("dividendRate", 0),
            "payout_ratio": g("payoutRatio", 0),
            "ex_dividend_date": _ts_to_str(g("exDividendDate")),
            "target_mean": g("targetMeanPrice", 0),
            "target_high": g("targetHighPrice", 0),
            "target_low": g("targetLowPrice", 0),
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

        # Try to get name from company cache (no extra HTTP call)
        cached_company = cache_get(f"company:{ticker}")
        name = cached_company.get("name", ticker) if cached_company else ticker
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
