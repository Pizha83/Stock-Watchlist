import logging
from urllib.parse import urlparse

logger = logging.getLogger("stockbot")


def fetch_article_content(url: str) -> dict | None:
    """Fetch and extract article content from a URL using trafilatura."""
    try:
        import trafilatura
        from trafilatura import bare_extraction

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            logger.warning(f"Could not download: {url}")
            return None

        text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
        if not text:
            logger.warning(f"Could not extract text from: {url}")
            return None

        result = bare_extraction(downloaded, include_comments=False)

        title = ""
        publish_date = ""
        if result:
            title = result.get("title", "") or ""
            publish_date = result.get("date", "") or ""

        if not title:
            title = urlparse(url).path.strip("/").split("/")[-1] or urlparse(url).netloc

        domain = urlparse(url).netloc.replace("www.", "")

        return {
            "title": title,
            "text": text,
            "publish_date": publish_date,
            "domain": domain,
            "url": url,
        }
    except Exception as e:
        logger.error(f"Error fetching article {url}: {e}")
        return None
