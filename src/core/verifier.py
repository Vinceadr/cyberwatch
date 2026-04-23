"""Verifier — scoring de fiabilité des sources et articles."""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from src.models.database import Database

logger = logging.getLogger(__name__)

CROSS_REF_WINDOW_HOURS: int = 72
TITLE_SIMILARITY_THRESHOLD: float = 0.5
ANCIENNETE_CAP_DAYS: int = 180

SENSATIONALIST_MARKERS: list[str] = [
    "breaking", "urgent", "exclusive", "shocking", "unprecedented",
    "alerte", "incroyable", "exclusif", "choc", "catastrophe",
    "!!!", "???", "🚨🚨", "BREAKING",
]

DEFAULT_SOURCE_REPUTATION: dict[str, int] = {
    "CERT-FR Alertes": 95,
    "CERT-FR Avis": 95,
    "ANSSI": 95,
    "CISA Advisories": 90,
    "CVE Recent": 85,
    "The Hacker News": 70,
    "BleepingComputer": 72,
    "Krebs on Security": 80,
}


@dataclass
class Alert:
    level: str
    type: str
    message: str


@dataclass
class VerificationResult:
    article_uid: str
    score: float
    source_score: float
    cross_ref_count: int
    cross_ref_articles: list[str] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    method: str = "heuristic"


class SourceVerifier:
    """Évalue la fiabilité des sources et des articles."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._source_cache: dict[str, float] = {}

    def verify_article(self, article: dict, candidates: list[dict] | None = None) -> VerificationResult:
        source_score = self.compute_source_score(article.get("source_name", ""))

        if candidates is None:
            candidates = self._load_recent_articles(article)

        cross_refs = self.find_cross_references(article, candidates)
        cross_ref_count = len(cross_refs)
        cross_ref_uids = [c["uid"] for c in cross_refs]

        a_src = source_score
        a_xref = self._compute_xref_score(cross_ref_count)
        a_qual = self._compute_quality_score(article)
        a_ref = self._compute_reference_score(article)
        a_mat = self._compute_maturity_score(article, cross_ref_count)

        score = (
            0.25 * a_src
            + 0.30 * a_xref
            + 0.20 * a_qual
            + 0.15 * a_ref
            + 0.10 * a_mat
        )
        score = max(0.0, min(100.0, score))

        method = "cross_ref" if cross_ref_count >= 2 else ("source_only" if cross_ref_count == 0 else "heuristic")

        alerts = self.generate_alerts(article, score, source_score, cross_ref_count)

        result = VerificationResult(
            article_uid=article.get("uid", ""),
            score=round(score, 2),
            source_score=round(source_score, 2),
            cross_ref_count=cross_ref_count,
            cross_ref_articles=cross_ref_uids,
            alerts=alerts,
            method=method,
        )

        logger.debug(
            "Verification %s: score=%.1f src=%.1f xref=%d method=%s",
            article.get("uid", "?"), score, source_score, cross_ref_count, method,
        )
        return result

    def compute_source_score(self, source_name: str) -> float:
        if source_name in self._source_cache:
            return self._source_cache[source_name]

        r0 = DEFAULT_SOURCE_REPUTATION.get(source_name, 50)
        h = self._compute_history_score(source_name)
        spec = self._compute_specialisation_score(source_name)
        reg = self._compute_regularity_score(source_name)
        anc = self._compute_anciennete_score(source_name)

        score = 0.25 * r0 + 0.30 * h + 0.15 * spec + 0.10 * reg + 0.20 * anc
        score = max(0.0, min(100.0, score))

        self._source_cache[source_name] = score
        return score

    def find_cross_references(self, article: dict, candidates: list[dict]) -> list[dict]:
        title = article.get("title", "")
        source = article.get("source_name", "")
        uid = article.get("uid", "")

        if not title:
            return []

        published = self._parse_datetime(article.get("published"))
        window_start = published - timedelta(hours=CROSS_REF_WINDOW_HOURS)
        window_end = published + timedelta(hours=CROSS_REF_WINDOW_HOURS)

        matches: list[dict] = []
        seen_sources: set[str] = set()

        for candidate in candidates:
            if candidate.get("uid") == uid:
                continue
            c_source = candidate.get("source_name", "")
            if c_source == source or c_source in seen_sources:
                continue

            c_published = self._parse_datetime(candidate.get("published"))
            if not (window_start <= c_published <= window_end):
                continue

            c_title = candidate.get("title", "")
            similarity = SequenceMatcher(None, title.lower(), c_title.lower()).ratio()

            if similarity >= TITLE_SIMILARITY_THRESHOLD:
                matches.append(candidate)
                seen_sources.add(c_source)

        return matches

    def generate_alerts(
        self,
        article: dict,
        score: float,
        source_score: float | None = None,
        cross_ref_count: int | None = None,
    ) -> list[Alert]:
        if source_score is None:
            source_score = self.compute_source_score(article.get("source_name", ""))
        if cross_ref_count is None:
            cross_ref_count = 0

        alerts: list[Alert] = []
        source_name = article.get("source_name", "unknown")

        if source_name not in DEFAULT_SOURCE_REPUTATION:
            alerts.append(Alert(
                level="WARNING",
                type="source_unknown",
                message=f"Source inconnue: {source_name}",
            ))

        if source_score < 40:
            alerts.append(Alert(
                level="WARNING",
                type="low_source_score",
                message=f"Source peu fiable ({source_name}): score {source_score:.0f}/100",
            ))

        if score < 30:
            alerts.append(Alert(
                level="CRITICAL",
                type="low_score",
                message=f"Article score critique: {score:.0f}/100 — {article.get('title', '')[:80]}",
            ))

        if cross_ref_count == 0:
            alerts.append(Alert(
                level="INFO",
                type="isolated",
                message=f"Info isolée (0 cross-ref): {article.get('title', '')[:80]}",
            ))

        return alerts

    # ── Sous-scores source ──────────────────────────────────────

    def _compute_history_score(self, source_name: str) -> float:
        try:
            rows = self.db.get_articles(limit=500)
            source_articles = [r for r in rows if r.get("source_name") == source_name]
            if not source_articles:
                return 50.0
            with_summary = sum(1 for a in source_articles if a.get("ai_summary"))
            return min(100.0, (with_summary / len(source_articles)) * 100)
        except Exception:
            logger.debug("Impossible de calculer l'historique pour %s", source_name)
            return 50.0

    def _compute_specialisation_score(self, source_name: str) -> float:
        try:
            rows = self.db.get_articles(limit=500)
            source_articles = [r for r in rows if r.get("source_name") == source_name]
            if not source_articles:
                return 50.0
            categories = [a.get("category", "unknown") for a in source_articles]
            if not categories:
                return 50.0
            from collections import Counter
            counts = Counter(categories)
            dominant_ratio = counts.most_common(1)[0][1] / len(categories)
            return min(100.0, dominant_ratio * 100)
        except Exception:
            return 50.0

    def _compute_regularity_score(self, source_name: str) -> float:
        try:
            rows = self.db.get_articles(limit=500)
            source_articles = [r for r in rows if r.get("source_name") == source_name]
            if len(source_articles) < 3:
                return 50.0

            dates = sorted(
                self._parse_datetime(a.get("fetched_at")) for a in source_articles
            )
            intervals = [
                (dates[i + 1] - dates[i]).total_seconds()
                for i in range(len(dates) - 1)
            ]
            if not intervals:
                return 50.0

            mean = sum(intervals) / len(intervals)
            if mean == 0:
                return 50.0

            variance = sum((x - mean) ** 2 for x in intervals) / len(intervals)
            cv = math.sqrt(variance) / mean
            return min(100.0, max(0.0, (1 - cv) * 100))
        except Exception:
            return 50.0

    def _compute_anciennete_score(self, source_name: str) -> float:
        try:
            rows = self.db.get_articles(limit=1000)
            source_articles = [r for r in rows if r.get("source_name") == source_name]
            if not source_articles:
                return 0.0

            oldest = min(
                self._parse_datetime(a.get("fetched_at")) for a in source_articles
            )
            age_days = (datetime.now(tz=timezone.utc) - oldest).total_seconds() / 86400

            if age_days <= 0:
                return 0.0
            score = (math.log(1 + age_days) / math.log(1 + ANCIENNETE_CAP_DAYS)) * 100
            return min(100.0, score)
        except Exception:
            return 0.0

    # ── Sous-scores article ─────────────────────────────────────

    def _compute_xref_score(self, cross_ref_count: int) -> float:
        if cross_ref_count == 0:
            return 10.0
        if cross_ref_count == 1:
            return 45.0
        if cross_ref_count == 2:
            return 75.0
        return min(100.0, 75.0 + (cross_ref_count - 2) * 10)

    def _compute_quality_score(self, article: dict) -> float:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        if not text.strip():
            return 50.0

        marker_count = sum(1 for m in SENSATIONALIST_MARKERS if m.lower() in text)
        exclamation_density = text.count("!") / max(len(text), 1) * 1000
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)

        penalty = marker_count * 10 + exclamation_density * 5 + max(0, (caps_ratio - 0.3)) * 100
        return max(0.0, min(100.0, 80.0 - penalty))

    def _compute_reference_score(self, article: dict) -> float:
        content = f"{article.get('content', '')} {article.get('summary', '')}"
        if not content.strip():
            return 30.0

        link_count = content.lower().count("http://") + content.lower().count("https://")
        cve_count = content.upper().count("CVE-")
        ref_indicators = link_count + cve_count

        if ref_indicators == 0:
            return 20.0
        if ref_indicators <= 2:
            return 50.0
        if ref_indicators <= 5:
            return 75.0
        return 90.0

    def _compute_maturity_score(self, article: dict, cross_ref_count: int) -> float:
        published = self._parse_datetime(article.get("published"))
        age_hours = (datetime.now(tz=timezone.utc) - published).total_seconds() / 3600

        if age_hours < 6:
            base = 20.0
        elif age_hours < 24:
            base = 40.0
        elif age_hours < 72:
            base = 60.0
        else:
            base = 80.0

        if cross_ref_count >= 2:
            base = min(100.0, base + 20)
        elif cross_ref_count == 0 and age_hours < 12:
            base = max(0.0, base - 15)

        return base

    # ── Utilitaires ─────────────────────────────────────────────

    @staticmethod
    def _parse_datetime(value: str | datetime | None) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str) and value:
            try:
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass
        return datetime.now(tz=timezone.utc)

    def _load_recent_articles(self, article: dict) -> list[dict]:
        try:
            return self.db.get_articles(limit=500)
        except Exception:
            logger.debug("Impossible de charger les articles récents pour cross-ref")
            return []
