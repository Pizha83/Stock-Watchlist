from sqlalchemy.orm import Session
from services.models import Source

REGIONS = {
    "usa": "Estados Unidos",
    "europa": "Europa",
    "uk": "Reino Unido",
    "espana": "Espana",
    "latam": "Latinoamerica",
    "asia": "Asia",
    "global": "Global",
}

SOURCE_TYPES = {
    "regulador": "Regulador",
    "bolsa": "Bolsa",
    "banco_central": "Banco Central",
    "open_data": "Open Data",
    "precios": "Precios",
    "fx": "Divisas (FX)",
    "macro": "Macro",
    "filings": "Filings",
}


def get_sources_by_region(session: Session, region: str) -> list[Source]:
    return session.query(Source).filter(Source.coverage.ilike(f"%{region}%")).all()


def get_sources_by_type(session: Session, source_type: str) -> list[Source]:
    return session.query(Source).filter(Source.source_type == source_type).all()


def search_sources(session: Session, query: str) -> list[Source]:
    q = f"%{query}%"
    return (
        session.query(Source)
        .filter((Source.name.ilike(q)) | (Source.data_offered.ilike(q)) | (Source.notes.ilike(q)))
        .all()
    )


def get_source_detail(session: Session, source_id: int) -> Source | None:
    return session.get(Source, source_id)


def toggle_recommended(session: Session, source_id: int):
    source = session.get(Source, source_id)
    if source:
        source.is_recommended = not source.is_recommended
        session.commit()


def update_notes(session: Session, source_id: int, notes: str):
    source = session.get(Source, source_id)
    if source:
        source.notes = notes
        session.commit()


def add_source(session: Session, **kwargs) -> Source:
    source = Source(**kwargs)
    session.add(source)
    session.commit()
    return source
