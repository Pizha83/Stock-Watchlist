"""Response templates for Q&A intents."""

from config import DISCLAIMER
from utils.text import (
    escape_html, format_number, format_pct, format_ratio, format_price,
)


def render(intent: str, data: dict, ticker: str) -> str:
    """Render a compact response for a given intent and data dict.

    Returns HTML-formatted string.
    """
    if data.get("error"):
        return (
            f"❌ <b>{escape_html(ticker)}</b>: {escape_html(data['error'])}\n"
            f"\n<i>{DISCLAIMER}</i>"
        )

    renderer = _RENDERERS.get(intent, _render_summary)
    return renderer(data, ticker)


# ── Individual renderers ─────────────────────────────────────────

def _header(data: dict, ticker: str) -> str:
    name = escape_html(data.get("name", ticker))
    cur = data.get("currency", "USD")
    price = format_price(data.get("price"), cur)
    chg = data.get("change_pct") or 0
    emoji = "🟢" if chg > 0 else ("🔴" if chg < 0 else "⚪")
    return f"<b>{escape_html(ticker)}</b> | {name} | {price} {emoji}{chg:+.2f}%"


def _render_price(data: dict, ticker: str) -> str:
    cur = data.get("currency", "USD")
    open_price = data.get("open")
    prev_close = data.get("previous_close")
    price_line = ""
    if open_price is not None:
        price_line += f"Apertura: {format_price(open_price, cur)} | "
    price_line += f"Cierre ant.: {format_price(prev_close, cur)}"
    lines = [
        _header(data, ticker),
        f"{price_line} | "
        f"52s: {format_price(data.get('low_52w'), cur)} – {format_price(data.get('high_52w'), cur)}",
        f"Vol medio: {format_number(data.get('avg_volume'))} | MCap: {format_number(data.get('market_cap'), cur)}",
    ]
    return _finalize(lines)


def _render_valuation(data: dict, ticker: str) -> str:
    lines = [
        _header(data, ticker),
        f"P/E: {format_ratio(data.get('pe_trailing'))} | Fwd P/E: {format_ratio(data.get('pe_forward'))}",
        f"EV/EBITDA: {format_ratio(data.get('ev_ebitda'))} | P/B: {format_ratio(data.get('pb'))} | P/S: {format_ratio(data.get('ps'))}",
        f"MCap: {format_number(data.get('market_cap'), data.get('currency', 'USD'))} | "
        f"EV: {format_number(data.get('enterprise_value'), data.get('currency', 'USD'))}",
    ]
    return _finalize(lines)


def _render_margins(data: dict, ticker: str) -> str:
    lines = [
        _header(data, ticker),
        f"Margen bruto: {format_pct(data.get('gross_margin'))} | "
        f"Operativo: {format_pct(data.get('operating_margin'))} | "
        f"Neto: {format_pct(data.get('net_margin'))}",
        f"ROE: {format_pct(data.get('roe'))} | ROA: {format_pct(data.get('roa'))}",
    ]
    return _finalize(lines)


def _render_debt(data: dict, ticker: str) -> str:
    cur = data.get("currency", "USD")
    d2e = data.get("debt_to_equity")
    d2e_str = f"{d2e:.1f}%" if d2e else "N/A"
    lines = [
        _header(data, ticker),
        f"Deuda: {format_number(data.get('total_debt'), cur)} | "
        f"Cash: {format_number(data.get('total_cash'), cur)}",
        f"Debt/Equity: {d2e_str} | "
        f"Net debt: {format_number((data.get('total_debt', 0) or 0) - (data.get('total_cash', 0) or 0), cur)}",
    ]
    return _finalize(lines)


def _render_dividend(data: dict, ticker: str) -> str:
    cur = data.get("currency", "USD")
    lines = [
        _header(data, ticker),
        f"Yield: {format_pct(data.get('dividend_yield'))} | "
        f"Tasa: {format_price(data.get('dividend_rate'), cur)}",
        f"Payout: {format_pct(data.get('payout_ratio'))} | "
        f"Ex-div: {data.get('ex_dividend_date', 'N/A')}",
    ]
    return _finalize(lines)


def _render_cashflow(data: dict, ticker: str) -> str:
    cur = data.get("currency", "USD")
    lines = [
        _header(data, ticker),
        f"FCF: {format_number(data.get('free_cash_flow'), cur)} | "
        f"Op. CF: {format_number(data.get('operating_cash_flow'), cur)}",
        f"Margen neto: {format_pct(data.get('net_margin'))} | "
        f"MCap: {format_number(data.get('market_cap'), cur)}",
    ]
    return _finalize(lines)


def _render_analysts(data: dict, ticker: str) -> str:
    cur = data.get("currency", "USD")
    rec = data.get("recommendation", "")
    rec_str = rec.upper() if rec else "N/A"
    lines = [
        _header(data, ticker),
        f"Recomendación: <b>{escape_html(rec_str)}</b> ({data.get('num_analysts', 0)} analistas)",
        f"Target: {format_price(data.get('target_mean'), cur)} "
        f"({format_price(data.get('target_low'), cur)} – {format_price(data.get('target_high'), cur)})",
    ]
    return _finalize(lines)


def _render_summary(data: dict, ticker: str) -> str:
    cur = data.get("currency", "USD")
    sector = escape_html(data.get("sector", ""))
    rec = data.get("recommendation", "")
    rec_str = rec.upper() if rec else "–"
    lines = [
        _header(data, ticker),
        f"{sector} | MCap: {format_number(data.get('market_cap'), cur)}",
        f"P/E: {format_ratio(data.get('pe_trailing'))} | EV/EBITDA: {format_ratio(data.get('ev_ebitda'))} | "
        f"Mg neto: {format_pct(data.get('net_margin'))}",
        f"FCF: {format_number(data.get('free_cash_flow'), cur)} | "
        f"Div: {format_pct(data.get('dividend_yield'))} | "
        f"Analistas: {escape_html(rec_str)}",
    ]
    return _finalize(lines)


def _render_compare(data: dict, ticker: str) -> str:
    # Compare is handled at the handler level (two calls)
    return _render_summary(data, ticker)


def _finalize(lines: list[str]) -> str:
    return "\n".join(lines) + f"\n\n<i>⚠️ {DISCLAIMER}</i>"


_RENDERERS = {
    "PRICE": _render_price,
    "VALUATION": _render_valuation,
    "MARGINS": _render_margins,
    "DEBT": _render_debt,
    "DIVIDEND": _render_dividend,
    "CASHFLOW": _render_cashflow,
    "ANALYSTS": _render_analysts,
    "SUMMARY": _render_summary,
    "COMPARE": _render_compare,
}
