"""Tests — Scraper (Article model + unit tests sans réseau)."""

from datetime import datetime, timezone

from src.core.scraper import Article


def test_article_creation() -> None:
    """Article se crée correctement avec les champs obligatoires."""
    article = Article(
        title="Test CVE",
        url="https://example.com/cve-1",
        source_name="TestSource",
        category="cert",
    )
    assert article.title == "Test CVE"
    assert article.url == "https://example.com/cve-1"
    assert article.source_name == "TestSource"
    assert article.category == "cert"
    assert isinstance(article.uid, str)
    assert len(article.uid) == 16


def test_article_uid_deterministic() -> None:
    """Même URL → même UID."""
    a1 = Article(title="A", url="https://x.com/1", source_name="S", category="c")
    a2 = Article(title="B", url="https://x.com/1", source_name="S", category="c")
    assert a1.uid == a2.uid


def test_article_uid_different_urls() -> None:
    """URLs différentes → UIDs différents."""
    a1 = Article(title="A", url="https://x.com/1", source_name="S", category="c")
    a2 = Article(title="A", url="https://x.com/2", source_name="S", category="c")
    assert a1.uid != a2.uid


def test_article_to_dict() -> None:
    """to_dict retourne un dict sérialisable."""
    article = Article(
        title="Test",
        url="https://example.com/test",
        source_name="Src",
        category="news",
        published=datetime(2024, 12, 1, tzinfo=timezone.utc),
    )
    d = article.to_dict()
    assert d["title"] == "Test"
    assert d["url"] == "https://example.com/test"
    assert "uid" in d
    assert "fetched_at" in d


def test_article_default_published() -> None:
    """published par défaut = None quand pas fourni."""
    article = Article(title="T", url="https://x.com", source_name="S", category="c")
    assert article.published is None
