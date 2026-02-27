from sqlalchemy.orm import Session
from services.models import Score


def create_score(
    session: Session,
    company_id: int,
    business: float = 0,
    finances: float = 0,
    valuation: float = 0,
    risk: float = 0,
    management: float = 0,
    comment: str = "",
) -> Score:
    total = round((business + finances + valuation + risk + management) / 5, 2)
    score = Score(
        company_id=company_id,
        business=business,
        finances=finances,
        valuation=valuation,
        risk=risk,
        management=management,
        total=total,
        comment=comment,
    )
    session.add(score)
    session.commit()
    return score


def get_scores(session: Session, company_id: int) -> list[Score]:
    return (
        session.query(Score)
        .filter(Score.company_id == company_id)
        .order_by(Score.created_at.desc())
        .all()
    )


def get_latest_score(session: Session, company_id: int) -> Score | None:
    return (
        session.query(Score)
        .filter(Score.company_id == company_id)
        .order_by(Score.created_at.desc())
        .first()
    )


SCORING_CATEGORIES = [
    ("business", "Negocio", "Calidad del modelo de negocio, moat, posicion competitiva"),
    ("finances", "Finanzas", "Solidez financiera, margenes, crecimiento, deuda"),
    ("valuation", "Valoracion", "Atractivo de la valoracion actual vs. valor intrinseco"),
    ("risk", "Riesgo", "Nivel de riesgo (5=bajo riesgo, 0=alto riesgo)"),
    ("management", "Management", "Calidad del equipo directivo, alineacion, track record"),
]
