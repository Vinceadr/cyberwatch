"""Pipeline — orchestrateur séquentiel fault-tolerant."""

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.core.emailer import Emailer
from src.core.scraper import Article, Scraper
from src.core.verifier import SourceVerifier
from src.models.database import Database

logger = logging.getLogger(__name__)


def _get_user_dir() -> Path:
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return Path(appdata) / "CyberWatch"
    return Path(__file__).resolve().parent.parent.parent


USER_DIR = _get_user_dir()


@dataclass
class PipelineResult:
    started_at: datetime
    completed_at: datetime | None = None
    articles_scraped: int = 0
    articles_new: int = 0
    articles_verified: int = 0
    emails_sent: int = 0
    errors: list[str] = field(default_factory=list)
    success: bool = False


class Pipeline:
    """Orchestre le pipeline : Scraper → Verifier → Summarizer → Storage → Emailer."""

    def __init__(self, config: dict) -> None:
        self.config = config
        db_path = USER_DIR / config["database"]["path"]
        self.db = Database(db_path)
        self.scraper = Scraper(config)
        self.verifier = SourceVerifier(self.db)
        self.emailer = Emailer(config)

    def run(self) -> PipelineResult:
        result = PipelineResult(started_at=datetime.now(tz=timezone.utc))
        logger.info("Pipeline démarré")

        # ── 1. Scraping ─────────────────────────────────────────
        articles = self._step_scrape(result)
        if not articles:
            logger.warning("0 articles collectés — arrêt du pipeline")
            result.completed_at = datetime.now(tz=timezone.utc)
            result.success = True
            return result

        # ── 2. Storage (insertion brute) ────────────────────────
        new_articles = self._step_store(articles, result)

        if not new_articles:
            logger.info("Aucun nouvel article — rien à traiter")
            result.completed_at = datetime.now(tz=timezone.utc)
            result.success = True
            return result

        # ── 3. Vérification ─────────────────────────────────────
        all_candidates = self._load_candidates()
        verified_articles = self._step_verify(new_articles, all_candidates, result)

        # ── 4. Keyword scoring (no AI) ──────────────────────────
        self._step_keyword_score(verified_articles)

        # ── 5. Emailer ──────────────────────────────────────────
        self._step_email(verified_articles, result)

        result.completed_at = datetime.now(tz=timezone.utc)
        result.success = True
        logger.info(
            "Pipeline terminé — scraped=%d new=%d verified=%d emails=%d errors=%d",
            result.articles_scraped,
            result.articles_new,
            result.articles_verified,
            result.emails_sent,
            len(result.errors),
        )
        return result

    def health_check(self) -> dict[str, bool]:
        checks: dict[str, bool] = {}

        try:
            self.db.get_stats()
            checks["database"] = True
        except Exception:
            checks["database"] = False

        checks["smtp"] = self.emailer.test_connection() if self.emailer.enabled else True

        try:
            sources = self.config.get("sources", {})
            rss_active = sum(1 for s in sources.get("rss", []) if s.get("enabled"))
            web_active = sum(1 for s in sources.get("web_scraping", []) if s.get("enabled"))
            checks["sources"] = (rss_active + web_active) > 0
        except Exception:
            checks["sources"] = False

        logger.info("Health check: %s", checks)
        return checks

    # ── Étapes du pipeline ──────────────────────────────────────

    def _step_scrape(self, result: PipelineResult) -> list[Article]:
        try:
            articles = self.scraper.fetch_all()
            result.articles_scraped = len(articles)
            logger.info("Scraping: %d articles collectés", len(articles))
            return articles
        except Exception as exc:
            error = f"Scraping échoué: {exc}"
            logger.exception(error)
            result.errors.append(error)
            return []

    def _step_store(self, articles: list[Article], result: PipelineResult) -> list[dict]:
        new_articles: list[dict] = []
        for article in articles:
            try:
                article_dict = article.to_dict()
                inserted = self.db.insert_article(article_dict)
                if inserted:
                    new_articles.append(article_dict)
            except Exception as exc:
                error = f"Storage erreur ({article.uid}): {exc}"
                logger.warning(error)
                result.errors.append(error)

        result.articles_new = len(new_articles)
        logger.info("Storage: %d nouveaux articles sur %d", len(new_articles), len(articles))
        return new_articles

    def _step_verify(
        self,
        articles: list[dict],
        candidates: list[dict],
        result: PipelineResult,
    ) -> list[dict]:
        verified: list[dict] = []
        for article in articles:
            try:
                vr = self.verifier.verify_article(article, candidates)
                article["verification_score"] = vr.score
                article["verification_method"] = vr.method
                article["cross_ref_count"] = vr.cross_ref_count

                for alert in vr.alerts:
                    if alert.level == "CRITICAL":
                        logger.warning("ALERTE %s: %s", alert.type, alert.message)
                    else:
                        logger.debug("Alerte %s: %s", alert.type, alert.message)

                result.articles_verified += 1
                verified.append(article)
            except Exception as exc:
                error = f"Verification erreur ({article.get('uid', '?')}): {exc}"
                logger.warning(error)
                result.errors.append(error)
                verified.append(article)

        logger.info("Verification: %d articles traités", result.articles_verified)
        return verified

    # Mots-clés par catégorie de sévérité — scoring sans IA
    _CRITICAL_KW = {"ransomware","zero-day","0day","rce","critical","breach","exploit",
                    "backdoor","rootkit","cve","vulnerability","malware","apt","phishing"}
    _HIGH_KW     = {"patch","update","alert","warning","attack","hack","leak","trojan",
                    "botnet","ddos","injection","overflow","privilege"}
    _MEDIUM_KW   = {"security","threat","risk","incident","bug","flaw","weakness"}

    def _step_keyword_score(self, articles: list[dict]) -> None:
        """Score articles with keyword heuristics, no AI needed."""
        for article in articles:
            text = ((article.get("title") or "") + " " +
                    (article.get("summary") or "")).lower()
            if any(k in text for k in self._CRITICAL_KW):
                severity, score = "CRITIQUE", 90
            elif any(k in text for k in self._HIGH_KW):
                severity, score = "ELEVE", 70
            elif any(k in text for k in self._MEDIUM_KW):
                severity, score = "MOYEN", 50
            else:
                severity, score = "INFO", 30
            try:
                self.db.update_ai_summary(article["uid"], "", severity, score)
                article["severity"] = severity
                article["score_fiabilite"] = score
            except Exception:
                pass
        logger.info("Keyword scoring: %d articles scores", len(articles))

    def _step_email(self, articles: list[dict], result: PipelineResult) -> None:
        if not self.emailer.enabled:
            logger.info("Email désactivé — skip")
            return

        if not articles:
            return

        criticals = [a for a in articles if a.get("severity") == "CRITIQUE"]
        for article in criticals:
            try:
                if self.emailer.send_critical_alert(article):
                    result.emails_sent += 1
            except Exception as exc:
                error = f"Email alerte critique erreur: {exc}"
                logger.warning(error)
                result.errors.append(error)

        try:
            if self.emailer.send_digest(articles):
                result.emails_sent += 1
        except Exception as exc:
            error = f"Email digest erreur: {exc}"
            logger.warning(error)
            result.errors.append(error)

        logger.info("Emailer: %d emails envoyés", result.emails_sent)

    # ── Helpers ──────────────────────────────────────────────────

    def _load_candidates(self) -> list[dict]:
        try:
            return self.db.get_articles(limit=500)
        except Exception:
            logger.debug("Impossible de charger les candidats pour cross-ref")
            return []
