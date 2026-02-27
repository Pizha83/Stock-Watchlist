TAG_KEYWORDS = {
    "DCF": ["dcf", "discounted cash flow", "flujo de caja descontado"],
    "Multiplos": ["multiplo", "múltiplo", "p/e", "ev/ebitda", "ev/sales", "price to earnings"],
    "Estados financieros": [
        "income statement", "balance sheet", "cash flow statement",
        "cuenta de resultados", "balance general", "estado de resultados",
    ],
    "Valoracion": ["valoracion", "valoración", "valuation", "fair value", "valor intrinseco"],
    "Analisis fundamental": ["analisis fundamental", "análisis fundamental", "fundamental analysis"],
    "Analisis tecnico": ["analisis tecnico", "análisis técnico", "technical analysis", "chartismo"],
    "Riesgos": ["riesgo", "risk", "downside", "bear case"],
    "Management": ["management", "directiva", "ceo", "gestion", "governance"],
    "Macro": ["macro", "gdp", "pib", "inflacion", "inflation", "tipos de interes", "interest rate"],
    "Sector": ["sector", "industria", "industry", "competencia", "peers"],
    "Dividendos": ["dividendo", "dividend", "yield", "payout"],
    "Crecimiento": ["crecimiento", "growth", "cagr", "revenue growth"],
    "Deuda": ["deuda", "debt", "leverage", "apalancamiento", "net debt"],
    "Moat": ["moat", "ventaja competitiva", "competitive advantage", "barriers to entry"],
    "SaaS": ["saas", "software as a service", "arr", "mrr", "churn", "nrr"],
    "Banca": ["banco", "bank", "nim", "net interest", "provisiones"],
    "Energia": ["energia", "energía", "energy", "petroleo", "oil", "gas", "renovable"],
    "Inmobiliario": ["inmobiliario", "real estate", "reit", "propiedad"],
    "M&A": ["m&a", "merger", "acquisition", "fusion", "adquisicion"],
    "Buyback": ["buyback", "recompra", "share repurchase"],
}


def auto_tag(text: str, title: str = "") -> list[str]:
    """Automatically tag an article based on keyword matching."""
    combined = f"{title} {text}".lower()
    tags = []

    for tag, keywords in TAG_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                tags.append(tag)
                break

    return tags


def get_all_tags() -> list[str]:
    """Return all possible tag names."""
    return sorted(TAG_KEYWORDS.keys())
