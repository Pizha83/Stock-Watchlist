from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from services.models import Alert, Article, Company, Watchlist, WatchlistItem


def create_alert(
    session: Session,
    user_id: int,
    message: str,
    due_date: datetime = None,
    company_id: int = None,
    alert_type: str = "manual",
) -> Alert:
    alert = Alert(
        user_id=user_id,
        company_id=company_id,
        alert_type=alert_type,
        message=message,
        due_date=due_date,
    )
    session.add(alert)
    session.commit()
    return alert


def get_active_alerts(session: Session, user_id: int) -> list[Alert]:
    return (
        session.query(Alert)
        .filter(Alert.user_id == user_id, Alert.is_active == True)
        .order_by(Alert.due_date.asc().nullslast())
        .all()
    )


def get_upcoming_alerts(session: Session, user_id: int, days: int = 7) -> list[Alert]:
    limit = datetime.now(timezone.utc) + timedelta(days=days)
    return (
        session.query(Alert)
        .filter(
            Alert.user_id == user_id,
            Alert.is_active == True,
            Alert.due_date != None,
            Alert.due_date <= limit,
        )
        .order_by(Alert.due_date.asc())
        .all()
    )


def deactivate_alert(session: Session, alert_id: int):
    alert = session.get(Alert, alert_id)
    if alert:
        alert.is_active = False
        session.commit()


def get_weekly_summary(session: Session, user_id: int) -> dict:
    """Generate weekly summary data."""
    upcoming = get_upcoming_alerts(session, user_id, days=7)

    watchlists = session.query(Watchlist).filter(Watchlist.user_id == user_id).all()
    wl_summary = []
    for wl in watchlists:
        items = session.query(WatchlistItem).filter(WatchlistItem.watchlist_id == wl.id).all()
        tickers = [item.company.ticker for item in items]
        wl_summary.append({"name": wl.name, "count": len(items), "tickers": tickers})

    recent_articles = (
        session.query(Article).order_by(Article.ingested_at.desc()).limit(5).all()
    )

    return {
        "upcoming_alerts": upcoming,
        "watchlists": wl_summary,
        "recent_articles": recent_articles,
    }
