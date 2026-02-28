from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone


def _utcnow():
    """Return current UTC time (timezone-aware safe for Python 3.12+)."""
    return datetime.now(timezone.utc)

Base = declarative_base()


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), default="")
    url = Column(String(1000), unique=True)
    publish_date = Column(String(50), default="")
    language = Column(String(10), default="")
    source_domain = Column(String(200), default="")
    summary = Column(Text, default="")
    full_text = Column(Text, default="")
    ingested_at = Column(DateTime, default=_utcnow)
    is_favorite = Column(Boolean, default=False)

    tags = relationship("ArticleTag", back_populates="article", cascade="all, delete-orphan")
    companies = relationship("LinkCompanyArticle", back_populates="article")


class ArticleTag(Base):
    __tablename__ = "article_tags"

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"))
    tag = Column(String(100))

    article = relationship("Article", back_populates="tags")


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    source_type = Column(String(100))
    coverage = Column(String(500), default="")
    data_offered = Column(Text, default="")
    access_type = Column(String(50), default="web")
    limitations = Column(Text, default="")
    url = Column(String(1000), default="")
    reliability = Column(String(20), default="media")
    notes = Column(Text, default="")
    is_recommended = Column(Boolean, default=False)
    verified = Column(Boolean, default=True)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20))
    isin = Column(String(20), default="")
    exchange = Column(String(50), default="")
    country = Column(String(50), default="")
    currency = Column(String(10), default="")
    sector = Column(String(100), default="")
    industry = Column(String(100), default="")
    created_at = Column(DateTime, default=_utcnow)

    watchlist_items = relationship("WatchlistItem", back_populates="company")
    notes = relationship("CompanyNote", back_populates="company", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="company", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="company")
    articles = relationship("LinkCompanyArticle", back_populates="company")


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    user_id = Column(Integer)
    created_at = Column(DateTime, default=_utcnow)

    items = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"))
    company_id = Column(Integer, ForeignKey("companies.id"))
    notes = Column(Text, default="")
    added_at = Column(DateTime, default=_utcnow)

    watchlist = relationship("Watchlist", back_populates="items")
    company = relationship("Company", back_populates="watchlist_items")


class CompanyNote(Base):
    __tablename__ = "company_notes"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    note_type = Column(String(50))
    content = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    company = relationship("Company", back_populates="notes")


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    business = Column(Float, default=0)
    finances = Column(Float, default=0)
    valuation = Column(Float, default=0)
    risk = Column(Float, default=0)
    management = Column(Float, default=0)
    total = Column(Float, default=0)
    comment = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    company = relationship("Company", back_populates="scores")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    user_id = Column(Integer)
    alert_type = Column(String(50), default="manual")
    message = Column(Text, default="")
    due_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    company = relationship("Company", back_populates="alerts")


class LinkCompanyArticle(Base):
    __tablename__ = "link_company_article"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    article_id = Column(Integer, ForeignKey("articles.id"))

    company = relationship("Company", back_populates="articles")
    article = relationship("Article", back_populates="companies")


# ══════════════════════════════════════════════════════════════════
# PORTFOLIO (v2 — per-user)
# ══════════════════════════════════════════════════════════════════

class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(200), default="Mi cartera")
    base_currency = Column(String(10), default="EUR")
    created_at = Column(DateTime, default=_utcnow)

    positions = relationship("Position", back_populates="portfolio", cascade="all, delete-orphan")


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    ticker = Column(String(20), nullable=False)
    shares = Column(Float, default=0)
    avg_price = Column(Float, default=0)
    realized_pnl = Column(Float, default=0)
    currency = Column(String(10), default="EUR")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    portfolio = relationship("Portfolio", back_populates="positions")
    transactions = relationship("Transaction", back_populates="position", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)
    tx_type = Column(String(10), nullable=False)  # buy, sell, dividend
    shares = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    commission = Column(Float, default=0)
    date = Column(DateTime, default=_utcnow)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    position = relationship("Position", back_populates="transactions")


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    ticker = Column(String(20), nullable=False)
    condition = Column(String(10), nullable=False)  # above, below
    target_price = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
