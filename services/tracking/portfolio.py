"""Portfolio management: positions, transactions, P&L."""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from services.models import Portfolio, Position, Transaction
from services.market_data.yahoo_finance import get_current_price


def get_or_create_portfolio(session: Session, user_id: int) -> Portfolio:
    p = session.query(Portfolio).filter_by(user_id=user_id).first()
    if not p:
        p = Portfolio(user_id=user_id, name="Mi cartera", base_currency="EUR")
        session.add(p)
        session.commit()
    return p


def list_positions(session: Session, user_id: int) -> list[dict]:
    """Return positions with live P&L data."""
    p = get_or_create_portfolio(session, user_id)
    results = []
    for pos in p.positions:
        if pos.shares <= 0:
            continue
        current = get_current_price(pos.ticker)
        unrealized = 0.0
        if current and pos.avg_price:
            unrealized = (current - pos.avg_price) * pos.shares
        results.append({
            "id": pos.id,
            "ticker": pos.ticker,
            "shares": pos.shares,
            "avg_price": pos.avg_price,
            "currency": pos.currency,
            "current_price": current,
            "unrealized_pnl": unrealized,
            "realized_pnl": pos.realized_pnl,
            "total_pnl": unrealized + pos.realized_pnl,
            "cost_basis": pos.avg_price * pos.shares,
            "market_value": (current or 0) * pos.shares,
        })
    return results


def add_position(session: Session, user_id: int, ticker: str,
                 shares: float, price: float, currency: str = "EUR") -> Position:
    """Create a new position (initial buy)."""
    p = get_or_create_portfolio(session, user_id)
    # Check if position already exists
    existing = session.query(Position).filter_by(
        portfolio_id=p.id, ticker=ticker.upper()
    ).first()
    if existing:
        return record_buy(session, user_id, existing.id, shares, price)

    pos = Position(
        portfolio_id=p.id,
        ticker=ticker.upper(),
        shares=shares,
        avg_price=price,
        currency=currency,
    )
    session.add(pos)
    session.flush()
    tx = Transaction(
        position_id=pos.id, tx_type="buy",
        shares=shares, price=price, date=datetime.now(timezone.utc),
    )
    session.add(tx)
    session.commit()
    return pos


def record_buy(session: Session, user_id: int, position_id: int,
               shares: float, price: float, commission: float = 0) -> Position:
    pos = _get_user_position(session, user_id, position_id)
    if not pos:
        return None
    # Weighted average
    total_cost = pos.avg_price * pos.shares + price * shares
    pos.shares += shares
    pos.avg_price = total_cost / pos.shares if pos.shares else 0
    pos.updated_at = datetime.now(timezone.utc)

    tx = Transaction(
        position_id=pos.id, tx_type="buy",
        shares=shares, price=price, commission=commission,
        date=datetime.now(timezone.utc),
    )
    session.add(tx)
    session.commit()
    return pos


def record_sell(session: Session, user_id: int, position_id: int,
                shares: float, price: float, commission: float = 0) -> tuple[Position | None, str]:
    """Record a sell transaction.

    Returns (position, error_message). On success error_message is empty.
    """
    pos = _get_user_position(session, user_id, position_id)
    if not pos:
        return None, "position_not_found"
    if shares > pos.shares:
        return None, "insufficient_shares"
    # Realized P&L
    pos.realized_pnl += (price - pos.avg_price) * shares - commission
    pos.shares -= shares
    pos.updated_at = datetime.now(timezone.utc)

    tx = Transaction(
        position_id=pos.id, tx_type="sell",
        shares=shares, price=price, commission=commission,
        date=datetime.now(timezone.utc),
    )
    session.add(tx)
    session.commit()
    return pos, ""


def calc_total_pnl(session: Session, user_id: int) -> dict:
    positions = list_positions(session, user_id)
    total_cost = sum(p["cost_basis"] for p in positions)
    total_value = sum(p["market_value"] for p in positions)
    total_unrealized = sum(p["unrealized_pnl"] for p in positions)
    total_realized = sum(p["realized_pnl"] for p in positions)
    currencies = list({p["currency"] for p in positions if p.get("currency")})
    return {
        "total_cost": total_cost,
        "total_value": total_value,
        "unrealized_pnl": total_unrealized,
        "realized_pnl": total_realized,
        "total_pnl": total_unrealized + total_realized,
        "pct": ((total_value - total_cost) / total_cost * 100) if total_cost else 0,
        "num_positions": len(positions),
        "currencies": currencies,
    }


def get_position(session: Session, user_id: int, position_id: int) -> Position | None:
    return _get_user_position(session, user_id, position_id)


def get_positions_for_selection(session: Session, user_id: int) -> list[Position]:
    p = get_or_create_portfolio(session, user_id)
    return [pos for pos in p.positions if pos.shares > 0]


def _get_user_position(session: Session, user_id: int, position_id: int) -> Position | None:
    pos = session.get(Position, position_id)
    if not pos:
        return None
    portfolio = session.get(Portfolio, pos.portfolio_id)
    if not portfolio or portfolio.user_id != user_id:
        return None
    return pos
