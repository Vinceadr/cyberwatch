"""Content Fetcher — scrape article pages to enrich missing descriptions."""

import asyncio
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 20
USER_AGENT = "CyberWatch/0.2 (Tech Monitor; +https://github.com/etykx/cyberwatch)"
MAX_CONCURRENT = 8

# CSS selectors to find article content, ordered by specificity
CONTENT_SELECTORS = [
    "article .entry-content",
    "article .post-content",
    "article .article-body",
    "article .article-content",
    ".post-body",
    ".article-body",
    ".article-content",
    ".entry-content",
    ".post-content",
    ".story-body",
    ".content-body",
    "[itemprop='articleBody']",
    "article",
    "main article",
    "main",
    "#content",
    ".content",
]

# Tags to remove before extracting text
NOISE_TAGS = [
    "script", "style", "nav", "footer", "header", "aside",
    "form", "iframe", "noscript", "svg", "figure", "figcaption",
    ".sidebar", ".ad", ".advertisement", ".social-share",
    ".comments", ".related-posts", ".newsletter", ".popup",
]


def _clean_text(text: str) -> str:
    """Clean extracted text: normalize whitespace, remove junk."""
    text = re.sub(r"\s+", " ", text).strip()
    # Remove common junk patterns
    text = re.sub(r"(Cookie|Accepter|Newsletter|Subscribe|Sign up|Inscri)[^.]{0,100}\.", "", text, flags=re.IGNORECASE)
    return text.strip()


def _extract_content(html: str, url: str) -> str:
    """Extract article main content from HTML page."""
    soup = BeautifulSoup(html, "lxml")

    # Remove noise elements
    for selector in NOISE_TAGS:
        for el in soup.select(selector) if selector.startswith(".") else soup.find_all(selector):
            el.decompose()

    # Try content selectors in order
    for selector in CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el and isinstance(el, Tag):
            paragraphs = el.find_all("p")
            if paragraphs:
                text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
                text = _clean_text(text)
                if len(text) > 100:
                    return text[:5000]

    # Fallback: grab all <p> tags from body
    body = soup.find("body")
    if body and isinstance(body, Tag):
        paragraphs = body.find_all("p")
        texts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        text = _clean_text(" ".join(texts))
        if len(text) > 80:
            return text[:5000]

    # Last resort: meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and isinstance(meta, Tag):
        desc = meta.get("content", "")
        if isinstance(desc, str) and len(desc) > 30:
            return _clean_text(desc)

    # og:description
    og = soup.find("meta", attrs={"property": "og:description"})
    if og and isinstance(og, Tag):
        desc = og.get("content", "")
        if isinstance(desc, str) and len(desc) > 30:
            return _clean_text(desc)

    return ""


async def _fetch_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    article_id: int,
    url: str,
) -> tuple[int, str]:
    """Fetch one URL and return (article_id, extracted_text)."""
    async with semaphore:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            content = _extract_content(resp.text, url)
            return (article_id, content)
        except Exception as exc:
            logger.debug("Fetch failed [%d] %s: %s", article_id, url[:60], exc)
            return (article_id, "")


async def _fetch_all(articles: list[tuple[int, str]]) -> dict[int, str]:
    """Fetch all article URLs concurrently, return {article_id: text}."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    results: dict[int, str] = {}

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(HTTP_TIMEOUT),
        follow_redirects=True,
    ) as client:
        tasks = [
            _fetch_one(client, semaphore, art_id, url)
            for art_id, url in articles
        ]
        for coro in asyncio.as_completed(tasks):
            art_id, text = await coro
            if text:
                results[art_id] = text

    return results


def _detect_language(text: str) -> str:
    """Simple heuristic to detect if text is French or English."""
    fr_words = {"le", "la", "les", "de", "des", "un", "une", "du", "est", "sont",
                "dans", "pour", "avec", "sur", "par", "qui", "que", "cette", "aussi",
                "mais", "nous", "vous", "leur", "entre", "peut", "plus", "tout"}
    words = set(re.findall(r"\b\w{2,6}\b", text.lower()))
    fr_count = len(words & fr_words)
    return "fr" if fr_count >= 5 else "en"


def _translate_batch(texts: list[str], translator) -> list[str]:
    """Translate a batch of texts EN→FR, with fallback per-item."""
    try:
        return translator.translate_batch(texts)
    except Exception:
        results = []
        for t in texts:
            try:
                results.append(translator.translate(t))
            except Exception:
                results.append(t)
        return results


def extract_first_sentences(html: str, url: str = "", n: int = 3) -> str:
    """Extract the first *n* sentences from an article HTML page.

    Uses :func:`_extract_content` for main-content extraction then splits on
    sentence boundaries.  Returns ``""`` gracefully on any failure — never raises.

    Args:
        html: Raw HTML string of the page.
        url:  URL of the page (used for logging and og-description fallback).
        n:    Number of sentences to return (default 3).
    """
    try:
        text = _extract_content(html, url)
        if not text:
            return ""
        # Split on sentence-ending punctuation followed by whitespace
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        first = [s.strip() for s in sentences if s.strip()][:n]
        return " ".join(first)
    except Exception:
        logger.debug("extract_first_sentences failed for %s", url[:60])
        return ""

def enrich_missing_descriptions(db_path: str | Path, progress_cb=None) -> int:
    """Main entry: fetch content for articles missing descriptions, then translate.

    Args:
        db_path: Path to SQLite database
        progress_cb: Optional callback(current, total, message) for progress

    Returns:
        Number of articles enriched
    """
    import datetime
    current_year = str(datetime.datetime.now().year)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Phase 1: Find articles with NO description at all (2026 only)
    rows = conn.execute(
        "SELECT id, url_original FROM articles "
        "WHERE (resume_fr IS NULL OR resume_fr = '') "
        "AND (contenu_brut IS NULL OR contenu_brut = '') "
        "AND date_publication LIKE ? || '%' "
        "ORDER BY id DESC",
        (current_year,),
    ).fetchall()

    total = len(rows)
    if total == 0:
        logger.info("Enrichissement: aucun article sans description.")
        conn.close()
        return 0

    logger.info("Enrichissement: %d articles sans description a scraper...", total)
    if progress_cb:
        progress_cb(0, total, f"Scraping {total} articles...")

    # Phase 2: Fetch content from URLs
    articles_to_fetch = [(r["id"], r["url_original"]) for r in rows]
    fetched = asyncio.run(_fetch_all(articles_to_fetch))

    logger.info("Scraping termine: %d/%d articles ont du contenu.", len(fetched), total)
    if progress_cb:
        progress_cb(len(fetched), total, f"{len(fetched)} pages scrapees")

    if not fetched:
        conn.close()
        return 0

    # Phase 3: Store contenu_brut
    for art_id, text in fetched.items():
        conn.execute(
            "UPDATE articles SET contenu_brut = ? WHERE id = ?",
            (text[:5000], art_id),
        )
    conn.commit()
    logger.info("Contenu brut stocke pour %d articles.", len(fetched))

    # Phase 4: Translate content → resume_fr
    enriched = 0
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="en", target="fr")
    except ImportError:
        logger.warning("deep_translator non installe, resume_fr = contenu_brut[:500]")
        translator = None

    BATCH = 20
    items = list(fetched.items())

    for start in range(0, len(items), BATCH):
        chunk = items[start:start + BATCH]
        chunk_ids = [art_id for art_id, _ in chunk]
        chunk_texts = [text[:500] for _, text in chunk]

        # Detect language and translate only English
        translated = []
        to_translate_idx = []
        to_translate_texts = []

        for i, text in enumerate(chunk_texts):
            lang = _detect_language(text)
            if lang == "fr" or translator is None:
                translated.append((i, text))
            else:
                to_translate_idx.append(i)
                to_translate_texts.append(text)

        if to_translate_texts and translator:
            try:
                results = _translate_batch(to_translate_texts, translator)
                for j, idx in enumerate(to_translate_idx):
                    translated.append((idx, results[j] if results[j] else chunk_texts[idx]))
            except Exception:
                for idx in to_translate_idx:
                    translated.append((idx, chunk_texts[idx]))

        translated.sort(key=lambda x: x[0])

        for (idx, resume_fr), art_id in zip(translated, chunk_ids):
            conn.execute(
                "UPDATE articles SET resume_fr = ? WHERE id = ? AND (resume_fr IS NULL OR resume_fr = '')",
                (resume_fr, art_id),
            )
            enriched += 1

        conn.commit()

        if progress_cb:
            progress_cb(start + len(chunk), total, f"Traduit {start + len(chunk)}/{len(items)}")

        logger.info("Enrichissement batch %d-%d OK", start, start + len(chunk))

    conn.close()
    logger.info("Enrichissement termine: %d articles enrichis sur %d.", enriched, total)
    return enriched
