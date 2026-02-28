import csv
import io
from sqlalchemy.orm import Session
from services.models import Watchlist, WatchlistItem, Company


def create_watchlist(session: Session, name: str, user_id: int) -> Watchlist:
    wl = Watchlist(name=name, user_id=user_id)
    session.add(wl)
    session.commit()
    return wl


def get_watchlists(session: Session, user_id: int) -> list[Watchlist]:
    return session.query(Watchlist).filter(Watchlist.user_id == user_id).order_by(Watchlist.created_at.desc()).all()


def get_watchlist(session: Session, wl_id: int) -> Watchlist | None:
    return session.get(Watchlist, wl_id)


def add_to_watchlist(session: Session, wl_id: int, company_id: int, notes: str = "") -> WatchlistItem:
    existing = session.query(WatchlistItem).filter_by(watchlist_id=wl_id, company_id=company_id).first()
    if existing:
        return existing
    item = WatchlistItem(watchlist_id=wl_id, company_id=company_id, notes=notes)
    session.add(item)
    session.commit()
    return item


def remove_from_watchlist(session: Session, wl_id: int, company_id: int):
    item = session.query(WatchlistItem).filter_by(watchlist_id=wl_id, company_id=company_id).first()
    if item:
        session.delete(item)
        session.commit()


def get_watchlist_items(session: Session, wl_id: int) -> list[WatchlistItem]:
    return session.query(WatchlistItem).filter(WatchlistItem.watchlist_id == wl_id).all()


def delete_watchlist(session: Session, wl_id: int):
    wl = session.get(Watchlist, wl_id)
    if wl:
        session.delete(wl)
        session.commit()


def export_watchlist_csv(session: Session, wl_id: int) -> str:
    """Export watchlist to CSV string."""
    items = get_watchlist_items(session, wl_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticker", "Exchange", "Sector", "Industria", "Pais", "Notas"])
    for item in items:
        c = item.company
        writer.writerow([c.ticker, c.exchange, c.sector, c.industry, c.country, item.notes])
    return output.getvalue()
