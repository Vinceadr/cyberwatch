"""SummaryGenerator - resumes journaliers SANS IA.

Utilise directement les articles RSS (resume_fr) classes par score/date.
Aucune dependance Ollama ou LLM.

Resume matin  (07h ou premier demarrage) : top 5 articles des 24h, 1 par categorie.
Resume soir   (18h ou a la demande)      : articles du jour, top 3 highlights + tendance.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from src.models.database import Database

logger = logging.getLogger(__name__)

_CAT_NOM_TO_KEY: dict[str, str] = {
    "Cybersecurite": "cyber",
    "Systemes":      "systemes",
    "Reseaux":       "reseaux",
    "Developpement": "dev",
    "IA":            "ia",
    "Gaming":        "gaming",
    "Hacks":         "hacks",
}


def _two_sentences(text: str) -> str:
    """Extrait les 2 premieres phrases du texte brut RSS (sans IA)."""
    if not text or not text.strip():
        return ""
    text = text.strip()
    # Decoupe sur point, point d'exclamation, point d'interrogation
    parts = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in parts if len(s.strip()) > 20]
    if sentences:
        return " ".join(sentences[:2])[:400]
    return text[:400]


class SummaryGenerator:
    """Genere les resumes matin/soir a partir des articles RSS, sans IA."""

    def __init__(self, config: dict, db: Database) -> None:
        self.config = config
        self.db = db

    def is_available(self) -> bool:
        return True  # Toujours disponible — pas d'IA requise

    def generate_summary(self, summary_type: str, force: bool = False) -> dict | None:
        if summary_type not in ("morning", "evening"):
            raise ValueError(f"Type de resume inconnu: {summary_type!r}")

        today = datetime.now().strftime("%Y-%m-%d")

        if not force:
            existing = self.db.get_summary(today, summary_type)
            if existing:
                logger.info("Resume %s/%s deja existant -- skip", summary_type, today)
                try:
                    return json.loads(existing["content"])
                except Exception:
                    return existing

        if summary_type == "morning":
            return self._generate_morning(today)
        return self._generate_evening(today)

    def _generate_morning(self, date: str) -> dict | None:
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
        articles = self._query_articles_since(cutoff)

        if not articles:
            # Fallback: prendre les 5 articles les plus recents de la DB
            articles = self._query_recent(20)

        if not articles:
            logger.info("Resume matin -- aucun article disponible")
            return None

        # Meilleur article par categorie (top 5)
        by_cat: dict[str, dict] = {}
        for a in sorted(articles, key=lambda x: (x.get("score_fiabilite") or 0), reverse=True):
            cat = a.get("categorie_nom") or "unknown"
            if cat not in by_cat:
                by_cat[cat] = a

        top_articles = list(by_cat.values())[:5]

        summary_articles = [self._article_payload(a) for a in top_articles]

        content: dict[str, Any] = {
            "type":     "morning",
            "date":     date,
            "articles": summary_articles,
        }
        self.db.save_summary(date, "morning", json.dumps(content, ensure_ascii=False))
        logger.info("Resume matin genere -- %d articles", len(summary_articles))
        return content

    def _generate_evening(self, date: str) -> dict | None:
        day_start  = f"{date}T00:00:00"
        cutoff_18  = f"{date}T18:00:00"

        morning_arts   = self._query_articles_between(day_start, f"{date}T12:00:00")
        afternoon_arts = self._query_articles_between(f"{date}T12:00:00", cutoff_18)
        all_day = morning_arts + afternoon_arts

        if not all_day:
            # Fallback: 10 articles les plus recents
            all_day = self._query_recent(10)

        if not all_day:
            logger.info("Resume soir -- aucun article pour %s", date)
            return None

        top3 = sorted(all_day, key=lambda x: (x.get("score_fiabilite") or 0), reverse=True)[:3]

        cat_counts: dict[str, int] = {}
        for a in all_day:
            cat = a.get("categorie_nom") or "unknown"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        top_cat = max(cat_counts, key=lambda k: cat_counts[k]) if cat_counts else "unknown"

        content: dict[str, Any] = {
            "type":               "evening",
            "date":               date,
            "morning_articles":   [self._article_payload(a) for a in morning_arts],
            "afternoon_articles": [self._article_payload(a) for a in afternoon_arts],
            "highlights":         [self._article_payload(a) for a in top3],
            "category_trend": {
                "category":     top_cat,
                "category_key": _CAT_NOM_TO_KEY.get(top_cat, top_cat.lower()),
                "count":        cat_counts.get(top_cat, 0),
            },
        }
        self.db.save_summary(date, "evening", json.dumps(content, ensure_ascii=False))
        logger.info("Resume soir genere -- %d articles", len(all_day))
        return content

    def _article_payload(self, a: dict[str, Any]) -> dict[str, Any]:
        cat_nom = a.get("categorie_nom") or "unknown"
        raw_desc = a.get("resume_fr") or a.get("contenu_brut", "")
        return {
            "id":               a.get("id"),
            "uid":              a.get("uid"),
            "title":            a.get("titre", ""),
            "url":              a.get("url_original", ""),
            "category_nom":     cat_nom,
            "category_key":     _CAT_NOM_TO_KEY.get(cat_nom, cat_nom.lower()),
            "score":            a.get("score_fiabilite") or 0,
            "description":      _two_sentences(raw_desc),
        }

    def _query_articles_since(self, cutoff: str) -> list[dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, c.nom AS categorie_nom
                FROM   articles a
                LEFT JOIN categories c ON a.categorie_id = c.id
                WHERE  a.date_collecte >= ?
                ORDER  BY a.score_fiabilite DESC, a.date_collecte DESC
                LIMIT 100
                """,
                (cutoff,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _query_articles_between(self, start: str, end: str) -> list[dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, c.nom AS categorie_nom
                FROM   articles a
                LEFT JOIN categories c ON a.categorie_id = c.id
                WHERE  a.date_collecte >= ? AND a.date_collecte < ?
                ORDER  BY a.score_fiabilite DESC, a.date_collecte DESC
                LIMIT 50
                """,
                (start, end),
            ).fetchall()
        return [dict(r) for r in rows]

    def _query_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.db._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, c.nom AS categorie_nom
                FROM   articles a
                LEFT JOIN categories c ON a.categorie_id = c.id
                ORDER  BY a.date_collecte DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def generate_summary(
    config: dict,
    db: Database,
    summary_type: str,
    force: bool = False,
) -> dict | None:
    return SummaryGenerator(config, db).generate_summary(summary_type, force=force)