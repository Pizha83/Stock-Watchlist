"""Local QA verification script — runs without Telegram."""

import time

def main():
    print("=" * 60)
    print("  LOCAL VERIFICATION SCRIPT")
    print("=" * 60)
    all_pass = True

    # == 2.1 QA Router: parse_query tests ==
    from services.qa.router import parse_query

    tests = [
        ("AAPL", ["AAPL"], "SUMMARY"),
        ("SAN.MC", ["SAN.MC"], "SUMMARY"),
        ("AAPL valoracion", ["AAPL"], "VALUATION"),
        ("NVDA margenes", ["NVDA"], "MARGINS"),
        ("MSFT deuda", ["MSFT"], "DEBT"),
        ("ASML dividendo", ["ASML"], "DIVIDEND"),
        ("AAPL precio", ["AAPL"], "PRICE"),
        ("AAPL analistas", ["AAPL"], "ANALYSTS"),
        ("/q AAPL", ["AAPL"], "SUMMARY"),
        ("/q@stockbot AAPL valoracion", ["AAPL"], "VALUATION"),
        ("hola", [], "SUMMARY"),
        ("", [], "SUMMARY"),
        ("ETF", [], "SUMMARY"),
        ("CEO", [], "SUMMARY"),
        ("AIR.PA", ["AIR.PA"], "SUMMARY"),
        ("BMW.DE", ["BMW.DE"], "SUMMARY"),
    ]

    print("\n-- 2.1 parse_query tests --")
    for text, exp_tickers, exp_intent in tests:
        result = parse_query(text)
        t_ok = result["tickers"] == exp_tickers
        i_ok = result["intent"] == exp_intent
        status = "PASS" if (t_ok and i_ok) else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f'  [{status}] parse_query("{text}")')
        if not t_ok:
            print(f"         tickers: got {result['tickers']}, expected {exp_tickers}")
        if not i_ok:
            print(f"         intent: got {result['intent']}, expected {exp_intent}")

    # == 2.1b Template render ==
    from services.qa.templates import render

    mock_data = {
        "name": "Apple Inc.", "ticker": "AAPL",
        "price": 178.50, "previous_close": 175.0, "change_pct": 2.0,
        "currency": "USD", "market_cap": 2800000000000,
        "pe_trailing": 28.5, "pe_forward": 25.0,
        "ev_ebitda": 22.0, "pb": 45.0, "ps": 7.5,
        "gross_margin": 0.45, "operating_margin": 0.30, "net_margin": 0.25,
        "roe": 0.15, "roa": 0.08,
        "sector": "Technology", "industry": "Consumer Electronics",
        "free_cash_flow": 100000000000, "operating_cash_flow": 120000000000,
        "enterprise_value": 2900000000000,
        "dividend_yield": 0.005, "dividend_rate": 0.96,
        "payout_ratio": 0.15, "ex_dividend_date": "2024-02-09",
        "recommendation": "buy", "num_analysts": 40,
        "target_mean": 200.0, "target_low": 170.0, "target_high": 230.0,
        "total_debt": 100000000000, "total_cash": 60000000000,
        "debt_to_equity": 180.5, "revenue": 380000000000,
        "open": 176.0, "high_52w": 200.0, "low_52w": 140.0,
        "avg_volume": 50000000, "eps": 6.2, "forward_eps": 7.0,
        "gross_profit": 170000000000, "ebitda": 130000000000,
        "net_income": 95000000000, "ev_revenue": 7.6,
    }

    print("\n-- 2.1b Template render tests --")
    intents = ["SUMMARY", "PRICE", "VALUATION", "MARGINS", "DEBT", "DIVIDEND", "CASHFLOW", "ANALYSTS"]
    for intent in intents:
        html = render(intent, mock_data, "AAPL")
        ok = len(html) > 50 and "AAPL" in html and "asesoramiento" in html
        status = "PASS" if ok else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] render({intent}): {len(html)} chars")

    # == 2.1c Error rendering ==
    print("\n-- 2.1c Error data rendering --")
    err_data = {"error": "No data found"}
    html = render("SUMMARY", err_data, "FAKE")
    ok = "No data found" in html and "FAKE" in html
    status = "PASS" if ok else "FAIL"
    if status == "FAIL":
        all_pass = False
    print(f"  [{status}] render with error data")

    # == 2.2 Formatters: zero vs None ==
    from utils.text import format_pct, format_ratio, format_price, format_number

    print("\n-- 2.2 Formatter tests (zero vs None) --")
    fmt_tests = [
        ("format_pct(None)", format_pct(None), "N/A"),
        ("format_pct(0)", format_pct(0), "0.0%"),
        ("format_pct(0.462)", format_pct(0.462), "46.2%"),
        ("format_ratio(None)", format_ratio(None), "N/A"),
        ("format_ratio(0)", format_ratio(0), "0.0x"),
        ("format_ratio(30.5)", format_ratio(30.5), "30.5x"),
        ("format_price(None)", format_price(None), "N/A"),
        ("format_price(0)", format_price(0), "0.00"),
        ("format_price(178.5, 'USD')", format_price(178.5, "USD"), "USD 178.50"),
        ("format_number(None)", format_number(None), "N/A"),
        ("format_number(0)", format_number(0), "0"),
        ("format_number(2.8e12, 'USD')", format_number(2.8e12, "USD"), "USD 2.80T"),
    ]
    for label, got, expected in fmt_tests:
        status = "PASS" if got == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f'  [{status}] {label} -> "{got}" (expected "{expected}")')

    # == 2.3 safe_truncate_html ==
    from utils.text import safe_truncate_html

    print("\n-- 2.3 safe_truncate_html tests --")
    short = "<b>Hello</b>\nWorld"
    ok = safe_truncate_html(short) == short
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] Short text passes through unchanged")

    long_text = "\n".join(f"Line {i} with <b>HTML</b> tags" for i in range(200))
    truncated = safe_truncate_html(long_text, 200)
    ok = len(truncated) <= 200 and truncated.endswith("...")
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] Long text truncated to {len(truncated)} chars (limit 200)")

    html_text = "<b>Bold text</b>\n<i>Italic</i>\n<b>More bold</b>"
    trunc = safe_truncate_html(html_text, 30)
    ok = len(trunc) <= 30
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f'  [{status}] HTML text truncated safely: "{trunc}"')

    # == 2.4 Cache operations ==
    from services.cache import cache_get, cache_set, cache_clear, _instance

    print("\n-- 2.4 Cache tests --")
    cache_clear()

    cache_set("test:1", {"data": 42}, 60)
    got = cache_get("test:1")
    ok = got == {"data": 42}
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] cache_set + cache_get")

    cache_set("test:expired", "old", 0)
    time.sleep(0.01)
    got = cache_get("test:expired")
    ok = got is None
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] Expired entry returns None")

    cache_clear()
    for i in range(2010):
        cache_set(f"evict:{i}", i, 3600)
    ok = len(_instance._store) <= 2000
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] Max size enforced: {len(_instance._store)} entries <= 2000")
    cache_clear()

    # == 2.5 Rate limiter ==
    from services.rate_limit import rate_limit_allow

    print("\n-- 2.5 Rate limiter tests --")
    key = "test:ratelimit:unique"
    r1 = rate_limit_allow(key, 3, 60)
    r2 = rate_limit_allow(key, 3, 60)
    r3 = rate_limit_allow(key, 3, 60)
    r4 = rate_limit_allow(key, 3, 60)
    ok = r1 and r2 and r3 and not r4
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] 3/60s limit: 3 allowed, 4th rejected (got {r1},{r2},{r3},{r4})")

    # == 2.6 Portfolio logic ==
    from services.tracking.portfolio import record_sell
    from services.models import Base, Portfolio, Position
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    print("\n-- 2.6 Portfolio logic tests --")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    ts = TestSession()

    p = Portfolio(user_id=999, name="Test", base_currency="EUR")
    ts.add(p)
    ts.commit()

    pos = Position(portfolio_id=p.id, ticker="AAPL", shares=10, avg_price=150.0, currency="USD")
    ts.add(pos)
    ts.commit()

    # Sell more than held
    result, err = record_sell(ts, 999, pos.id, 20, 160.0)
    ok = result is None and err == "insufficient_shares"
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] record_sell: insufficient_shares error")

    # Valid sell
    result, err = record_sell(ts, 999, pos.id, 5, 160.0)
    ok = result is not None and err == "" and result.shares == 5.0
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] record_sell: 5 shares sold, {getattr(result, 'shares', '?')} remaining")

    # Wrong user
    result, err = record_sell(ts, 888, pos.id, 1, 160.0)
    ok = result is None and err == "position_not_found"
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] record_sell: wrong user gets position_not_found")

    # Multi-currency
    pos2 = Position(portfolio_id=p.id, ticker="SAN.MC", shares=100, avg_price=3.5, currency="EUR")
    ts.add(pos2)
    ts.commit()
    positions = [pp for pp in p.positions if pp.shares > 0]
    currencies = list({pp.currency for pp in positions if pp.currency})
    ok = len(currencies) == 2
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status}] Multi-currency detected: {currencies}")

    ts.close()

    # == SUMMARY ==
    print("\n" + "=" * 60)
    if all_pass:
        print("  ALL LOCAL TESTS PASSED")
    else:
        print("  SOME TESTS FAILED (see above)")
    print("=" * 60)
    return 0 if all_pass else 1


if __name__ == "__main__":
    exit(main())
