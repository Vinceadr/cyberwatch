"""WeeklyScheduler — purge hebdomadaire des articles (dimanche 00h00).

Utilise la lib ``schedule`` (déjà dans requirements.txt) dans un thread daemon
pour ne jamais bloquer le thread GUI Qt.

Usage::

    scheduler = WeeklyScheduler(db, retention_days=7)
    scheduler.start()          # démarre le thread daemon
    scheduler.run_now()        # purge manuelle
    scheduler.stop()           # arrêt propre
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

import schedule  # schedule>=1.2.2

from src.models.database import Database

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────

def get_next_sunday_midnight() -> datetime:
    """Calcule la prochaine occurrence du dimanche a 00h00."""
    now = datetime.now()
    # weekday(): lundi = 0, dimanche = 6
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and (now.hour > 0 or (now.hour == 0 and now.minute >= 1)):
        # on est dimanche mais apres 00h00 — prochain dimanche dans 7 jours
        days_until_sunday = 7
    next_sunday = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
    return next_sunday


def format_next_purge_label() -> str:
    """Retourne une chaine lisible du type 'Prochain refresh: dimanche 14/07 a 00h00'."""
    next_sunday = get_next_sunday_midnight()
    return "Prochain refresh: dimanche {} a 00h00".format(next_sunday.strftime("%d/%m"))


# ── Scheduler ─────────────────────────────────────────────────

class WeeklyScheduler:
    """Planifie la purge hebdomadaire des articles dans un thread daemon séparé.

    Les articles marqués comme favoris (``favori = 1``) ne sont jamais
    supprimés, quelle que soit leur ancienneté — cette protection est assurée
    par la clause ``AND favori = 0`` dans ``Database.purge_old_articles``.
    """

    def __init__(self, db: Database, retention_days: int = 7) -> None:
        self.db = db
        self.retention_days = retention_days
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Instance de scheduler isolée pour ne pas interférer avec d'autres jobs
        self._scheduler = schedule.Scheduler()

    # ── Purge ──────────────────────────────────────────────────

    def _run_purge(self) -> None:
        """Callback interne appelé par le scheduler."""
        try:
            deleted = self.db.purge_old_articles(days=self.retention_days)
            logger.info(
                "Purge hebdomadaire executee — %d articles supprimes (retention %d j, favoris preserves)",
                deleted,
                self.retention_days,
            )
        except Exception as exc:
            logger.exception("Erreur lors de la purge hebdomadaire: %s", exc)

    # ── Thread loop ────────────────────────────────────────────

    def _scheduler_loop(self) -> None:
        """Boucle principale du thread daemon — verifie toutes les 60 s."""
        self._scheduler.every().sunday.at("00:00").do(self._run_purge)
        logger.debug("WeeklyScheduler: job enregistre (dimanche 00:00)")

        while not self._stop_event.is_set():
            self._scheduler.run_pending()
            # Attendre 60 secondes ou jusqu'à ce que stop() soit appelé
            self._stop_event.wait(timeout=60)

        logger.debug("WeeklyScheduler: loop terminee proprement")

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        """Démarre le thread daemon de planification (idempotent)."""
        if self._thread and self._thread.is_alive():
            logger.debug("WeeklyScheduler deja demarre, skip")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._scheduler_loop,
            name="CW-WeeklyPurge",
            daemon=True,  # s'arrête automatiquement à la fermeture de l'app
        )
        self._thread.start()
        logger.info(
            "WeeklyScheduler demarre — purge chaque dimanche 00:00 (retention %d j)",
            self.retention_days,
        )

    def stop(self) -> None:
        """Arrete proprement le thread de planification."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("WeeklyScheduler arrete")

    # ── Purge manuelle ─────────────────────────────────────────

    def run_now(self) -> int:
        """Exécute la purge immédiatement (hors scheduler).

        Returns:
            Nombre d'articles supprimés.
        """
        try:
            deleted = self.db.purge_old_articles(days=self.retention_days)
            logger.info(
                "Purge manuelle executee — %d articles supprimes (favoris preserves)",
                deleted,
            )
            return deleted
        except Exception as exc:
            logger.exception("Erreur purge manuelle: %s", exc)
            return 0

