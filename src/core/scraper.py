"""Scraper — collecte les articles depuis RSS et web scraping via httpx async."""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import feedparser
from src.core.content_fetcher import extract_first_sentences
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 30
USER_AGENT = "CyberWatch/0.1 (Security Monitor; +https://github.com/etykx/cyberwatch)"
MAX_CONCURRENT = 10


class Article:
    __slots__ = (
        "uid", "title", "url", "source_name", "source_id", "category",
        "langue", "published", "summary", "content", "fetched_at",
    )

    def __init__(
        self,
        title: str,
        url: str,
        source_name: str,
        category: str,
        source_id: int = 0,
        langue: str = "en",
        published: datetime | None = None,
        summary: str = "",
        content: str = "",
    ) -> None:
        self.title = title
        self.url = url
        self.source_name = source_name
        self.source_id = source_id
        self.category = category
        self.langue = langue
        self.published = published
        self.summary = summary
        self.content = content
        self.fetched_at = datetime.now(tz=timezone.utc)
        self.uid = self._generate_uid()

    def _generate_uid(self) -> str:
        return hashlib.sha256(self.url.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "title": self.title,
            "url": self.url,
            "source_name": self.source_name,
            "source_id": self.source_id,
            "category": self.category,
            "langue": self.langue,
            "published": self.published.isoformat() if self.published else None,
            "summary": self.summary,
            "content": self.content,
            "fetched_at": self.fetched_at.isoformat(),
        }


class ScraperResult:
    def __init__(self) -> None:
        self.articles: list[Article] = []
        self.errors: list[dict[str, str]] = []
        self.sources_ok: int = 0
        self.sources_failed: int = 0

    @property
    def total(self) -> int:
        return len(self.articles)


class Scraper:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.sources_config = config.get("sources", {})
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    def fetch_all(self) -> list[Article]:
        """Synchronous wrapper for async fetch."""
        result = asyncio.run(self.fetch_all_async())
        return result.articles

    async def fetch_all_async(self) -> ScraperResult:
        result = ScraperResult()

        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(HTTP_TIMEOUT),
            follow_redirects=True,
        ) as client:
            tasks = []

            for source in self.sources_config.get("rss", []):
                if not source.get("enabled", True):
                    continue
                tasks.append(self._fetch_rss_safe(client, source, result))

            for source in self.sources_config.get("web_scraping", []):
                if not source.get("enabled", False):
                    continue
                tasks.append(self._fetch_web_safe(client, source, result))

            await asyncio.gather(*tasks)

        logger.info(
            "Scraping termine: %d articles, %d sources OK, %d echecs",
            result.total, result.sources_ok, result.sources_failed,
        )
        return result

    async def _fetch_rss_safe(
        self, client: httpx.AsyncClient, source: dict, result: ScraperResult,
    ) -> None:
        async with self._semaphore:
            try:
                articles = await self._fetch_rss(client, source)
                result.articles.extend(articles)
                result.sources_ok += 1
                logger.info("%s — %d articles", source["name"], len(articles))
            except Exception as exc:
                result.sources_failed += 1
                result.errors.append({"source": source["name"], "error": str(exc)})
                logger.warning("Erreur RSS %s: %s", source["name"], exc)

    async def _fetch_web_safe(
        self, client: httpx.AsyncClient, source: dict, result: ScraperResult,
    ) -> None:
        async with self._semaphore:
            try:
                articles = await self._fetch_web(client, source)
                result.articles.extend(articles)
                result.sources_ok += 1
                logger.info("%s — %d articles", source["name"], len(articles))
            except Exception as exc:
                result.sources_failed += 1
                result.errors.append({"source": source["name"], "error": str(exc)})
                logger.warning("Erreur scraping %s: %s", source["name"], exc)

    async def _fetch_rss(self, client: httpx.AsyncClient, source: dict) -> list[Article]:
        resp = await client.get(source["url"])
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)

        if feed.bozo and not feed.entries:
            logger.warning("RSS invalide: %s — %s", source["name"], feed.bozo_exception)
            return []

        articles = []
        for entry in feed.entries:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    pass

            summary = ""
            if hasattr(entry, "summary"):
                summary = BeautifulSoup(entry.summary, "lxml").get_text(strip=True)

            content = ""
            if hasattr(entry, "content") and entry.content:
                content = BeautifulSoup(
                    entry.content[0].get("value", ""), "lxml"
                ).get_text(strip=True)

            url = entry.get("link", "")
            if not url:
                continue

            # ── Fallback: fetch page if RSS gave no description ────────────────────
            if not summary and url:
                try:
                    fallback_resp = await client.get(url, timeout=httpx.Timeout(15.0))
                    fallback_resp.raise_for_status()
                    summary = extract_first_sentences(fallback_resp.text, url, 3)
                except Exception as _fb_exc:
                    logger.debug("Fallback fetch échoué pour %s: %s", url[:60], _fb_exc)
                    summary = ""

            article = Article(
                title=entry.get("title", "Sans titre"),
                url=url,
                source_name=source["name"],
                source_id=source.get("id", 0),
                category=source.get("category", "unknown"),
                langue=source.get("langue", "en"),
                published=published,
                summary=summary[:1000],
                content=content[:5000],
            )
            articles.append(article)

        return articles

    async def _fetch_web(self, client: httpx.AsyncClient, source: dict) -> list[Article]:
        resp = await client.get(source["url"])
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        elements = soup.select(source.get("selector", "article"))

        articles = []
        for el in elements:
            link_tag = el.find("a", href=True)
            if not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            url = link_tag["href"]
            if url.startswith("/"):
                url = urljoin(source["url"], url)

            article = Article(
                title=title,
                url=url,
                source_name=source["name"],
                source_id=source.get("id", 0),
                category=source.get("category", "unknown"),
                langue=source.get("langue", "en"),
                summary=el.get_text(strip=True)[:500],
            )
            articles.append(article)

        return articles

    def deduplicate(self, articles: list[Article]) -> list[Article]:
        seen_urls: set[str] = set()
        unique: list[Article] = []
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique.append(article)
        logger.info("Deduplication: %d → %d articles", len(articles), len(unique))
        return unique
