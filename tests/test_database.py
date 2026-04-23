"""Tests — Database model enrichi."""

from pathlib import Path

import pytest

from src.models.database import Database


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


@pytest.fixture()
def sample_article() -> dict:
    return {
        "uid": "abc123",
        "title": "CVE-2024-9999 - Critical RCE",
        "url": "https://example.com/cve-2024-9999",
        "source_name": "CERT-FR",
        "category": "Cybersecurite",
        "published": "2024-12-01T10:00:00+00:00",
        "summary": "Remote code execution in XYZ",
        "content": "",
        "fetched_at": "2024-12-01T12:00:00+00:00",
    }


def test_init_categories(db: Database) -> None:
    cats = db.get_categories()
    assert len(cats) == 7
    noms = [c["nom"] for c in cats]
    assert "Cybersecurite" in noms
    assert "IA" in noms


def test_insert_article(db: Database, sample_article: dict) -> None:
    assert db.insert_article(sample_article) is True


def test_insert_duplicate(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    assert db.insert_article(sample_article) is False


def test_get_articles(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    articles = db.get_articles()
    assert len(articles) == 1
    assert articles[0]["titre"] == sample_article["title"]


def test_get_articles_filter_category(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    assert len(db.get_articles(category="Cybersecurite")) == 1
    assert len(db.get_articles(category="Gaming")) == 0


def test_update_ai_summary(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    db.update_ai_summary("abc123", "Résumé IA test", "CRITIQUE")
    articles = db.get_articles()
    assert articles[0]["resume_fr"] == "Résumé IA test"
    assert articles[0]["severite"] == "CRITIQUE"


def test_mark_read(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    db.mark_read("abc123")
    articles = db.get_articles()
    assert articles[0]["lu"] == 1


def test_mark_starred(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    db.mark_starred("abc123", True)
    articles = db.get_articles()
    assert articles[0]["favori"] == 1


def test_get_stats_empty(db: Database) -> None:
    stats = db.get_stats()
    assert stats["total"] == 0
    assert stats["unread"] == 0
    assert stats["critical"] == 0


def test_insert_articles_batch(db: Database) -> None:
    articles = [
        {
            "uid": f"uid-{i}",
            "title": f"Article {i}",
            "url": f"https://example.com/{i}",
            "source_name": "Test",
            "category": "Cybersecurite",
            "published": "2024-12-01T10:00:00+00:00",
            "summary": "",
            "content": "",
            "fetched_at": "2024-12-01T12:00:00+00:00",
        }
        for i in range(5)
    ]
    count = db.insert_articles(articles)
    assert count == 5


def test_get_article_by_uid(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    art = db.get_article_by_uid("abc123")
    assert art is not None
    assert art["titre"] == "CVE-2024-9999 - Critical RCE"
    assert db.get_article_by_uid("nonexistent") is None


def test_search_articles_fts(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    results = db.search_articles("CVE-2024")
    assert len(results) >= 1
    assert results[0]["uid"] == "abc123"


def test_insert_source(db: Database) -> None:
    cat = db.get_categories()[0]
    sid = db.insert_source({
        "nom": "TestSource",
        "url_flux": "https://example.com/rss",
        "categorie_id": cat["id"],
        "score_confiance": 85,
    })
    assert sid > 0
    sources = db.get_sources()
    noms = [s["nom"] for s in sources]
    assert "TestSource" in noms


def test_update_source(db: Database) -> None:
    sid = db.insert_source({"nom": "Src", "url_flux": "https://src.test/rss"})
    db.update_source(sid, {"score_confiance": 99})
    sources = db.get_sources()
    src = next(s for s in sources if s["id"] == sid)
    assert src["score_confiance"] == 99


def test_delete_source(db: Database) -> None:
    sid = db.insert_source({"nom": "ToDelete", "url_flux": "https://del.test/rss"})
    db.delete_source(sid)
    sources = db.get_sources(actives_only=False)
    assert not any(s["id"] == sid for s in sources)


def test_insert_verification(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    art = db.get_article_by_uid("abc123")
    vid = db.insert_verification({
        "article_id": art["id"],
        "methode": "heuristique",
        "score": 75,
    })
    assert vid > 0
    verifs = db.get_verifications(art["id"])
    assert len(verifs) == 1
    assert verifs[0]["score"] == 75


def test_insert_alerte(db: Database) -> None:
    aid = db.insert_alerte({
        "niveau": "WARNING",
        "type": "test",
        "message": "Alerte de test",
    })
    assert aid > 0
    alertes = db.get_alertes(non_lues_only=True)
    assert len(alertes) == 1
    assert alertes[0]["message"] == "Alerte de test"


def test_pipeline_run(db: Database) -> None:
    run_id = db.log_pipeline_run({"articles_scrapes": 10, "succes": 1})
    assert run_id > 0
    last = db.get_last_pipeline_run()
    assert last is not None
    assert last["articles_scrapes"] == 10


def test_count_by_category(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    counts = db.count_by_category()
    assert counts.get("Cybersecurite", 0) == 1


def test_update_article_score(db: Database, sample_article: dict) -> None:
    db.insert_article(sample_article)
    db.update_article_score("abc123", 85, "HAUTE")
    art = db.get_article_by_uid("abc123")
    assert art["score_fiabilite"] == 85
    assert art["severite"] == "HAUTE"


def test_purge_old_articles(db: Database) -> None:
    old_article = {
        "uid": "old-001",
        "title": "Old Article",
        "url": "https://example.com/old",
        "source_name": "Test",
        "category": "Cybersecurite",
        "published": "2020-01-01T00:00:00+00:00",
        "summary": "",
        "content": "",
        "fetched_at": "2020-01-01T00:00:00+00:00",
    }
    db.insert_article(old_article)
    purged = db.purge_old_articles(days=1)
    assert purged == 1
    assert db.get_article_by_uid("old-001") is None
