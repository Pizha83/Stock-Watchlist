import logging
import requests
from config import SERPAPI_KEY

logger = logging.getLogger("stockbot")


def has_search_provider() -> bool:
    """Check if a web search provider is configured."""
    return bool(SERPAPI_KEY)


def search_web(query: str, language: str = "es", num_results: int = 10) -> list | None:
    """Search the web using SerpAPI. Returns None if no API key configured."""
    if not SERPAPI_KEY:
        return None

    try:
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": num_results,
            "hl": language,
            "gl": "es" if language == "es" else "us",
        }
        resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic_results", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                }
            )
        return results
    except Exception as e:
        logger.error(f"SerpAPI error: {e}")
        return None
