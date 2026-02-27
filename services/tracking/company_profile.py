from sqlalchemy.orm import Session
from services.models import Company, CompanyNote, LinkCompanyArticle


def create_company(session: Session, ticker: str, **kwargs) -> Company:
    company = Company(ticker=ticker.upper(), **kwargs)
    session.add(company)
    session.commit()
    return company


def get_company(session: Session, company_id: int) -> Company | None:
    return session.query(Company).get(company_id)


def get_company_by_ticker(session: Session, ticker: str) -> Company | None:
    return session.query(Company).filter(Company.ticker == ticker.upper()).first()


def get_all_companies(session: Session) -> list[Company]:
    return session.query(Company).order_by(Company.ticker).all()


def search_companies(session: Session, query: str) -> list[Company]:
    q = f"%{query}%"
    return (
        session.query(Company)
        .filter((Company.ticker.ilike(q)) | (Company.sector.ilike(q)) | (Company.industry.ilike(q)))
        .all()
    )


def update_company(session: Session, company_id: int, **kwargs):
    company = session.query(Company).get(company_id)
    if company:
        for k, v in kwargs.items():
            if hasattr(company, k):
                setattr(company, k, v)
        session.commit()


def add_note(session: Session, company_id: int, note_type: str, content: str) -> CompanyNote:
    note = CompanyNote(company_id=company_id, note_type=note_type, content=content)
    session.add(note)
    session.commit()
    return note


def get_notes(session: Session, company_id: int, note_type: str = None) -> list[CompanyNote]:
    q = session.query(CompanyNote).filter(CompanyNote.company_id == company_id)
    if note_type:
        q = q.filter(CompanyNote.note_type == note_type)
    return q.order_by(CompanyNote.created_at.desc()).all()


def link_article(session: Session, company_id: int, article_id: int):
    existing = (
        session.query(LinkCompanyArticle)
        .filter_by(company_id=company_id, article_id=article_id)
        .first()
    )
    if not existing:
        link = LinkCompanyArticle(company_id=company_id, article_id=article_id)
        session.add(link)
        session.commit()


def delete_company(session: Session, company_id: int):
    company = session.query(Company).get(company_id)
    if company:
        session.delete(company)
        session.commit()
