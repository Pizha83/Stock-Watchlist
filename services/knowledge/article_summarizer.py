import re
import logging
from config import OPENAI_API_KEY

logger = logging.getLogger("stockbot")


def summarize_text(text: str, max_bullets: int = 8) -> str:
    """Generate a summary. Uses OpenAI if available, otherwise heuristic."""
    if OPENAI_API_KEY:
        result = _summarize_llm(text, max_bullets)
        if result:
            return result

    return _summarize_heuristic(text, max_bullets)


def _summarize_heuristic(text: str, max_bullets: int = 8) -> str:
    """Simple extractive summary based on first sentences of paragraphs."""
    if not text:
        return "Sin contenido para resumir."

    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]
    selected = []

    for para in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", para)
        if sentences and len(sentences[0]) > 20:
            selected.append(sentences[0])
        if len(selected) >= max_bullets:
            break

    if len(selected) < 3:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        selected = [s.strip() for s in sentences if len(s.strip()) > 25][:max_bullets]

    if not selected:
        return text[:500]

    bullets = "\n".join(f"  - {s}" for s in selected[:max_bullets])
    concepts = _extract_concepts(text)
    concepts_str = ", ".join(concepts[:10]) if concepts else "N/A"

    return (
        f"Resumen:\n{bullets}\n\n"
        f"Conceptos clave: {concepts_str}\n\n"
        f"Utilidad: Articulo relevante para el analisis de inversiones."
    )


def _extract_concepts(text: str) -> list:
    """Extract key financial concepts mentioned in text."""
    keywords = [
        "DCF", "ROIC", "ROE", "ROA", "EBITDA", "P/E", "EV/EBITDA",
        "margen bruto", "margen operativo", "margen neto",
        "flujo de caja", "FCF", "dividendo", "deuda",
        "crecimiento", "valoracion", "multiplo", "balance",
        "income statement", "cash flow", "revenue", "earnings",
        "moat", "ventaja competitiva", "buyback", "M&A",
        "free cash flow", "gross margin", "operating margin",
        "capex", "working capital", "WACC", "SBC",
    ]
    found = []
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower and kw not in found:
            found.append(kw)
    return found


def _summarize_llm(text: str, max_bullets: int = 8) -> str | None:
    """Summarize using OpenAI API."""
    try:
        import requests as req

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        prompt = (
            f"Resume el siguiente articulo financiero en {max_bullets} puntos clave en espanol. "
            "Al final indica conceptos clave y por que es util para un inversor.\n\n"
            f"{text[:4000]}"
        )
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800,
        }
        resp = req.post(
            "https://api.openai.com/v1/chat/completions",
            json=data,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"LLM summary error: {e}")
        return None
