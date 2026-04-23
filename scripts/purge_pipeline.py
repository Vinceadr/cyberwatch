"""Purge headless - Windows Task Scheduler (dimanche 00h00).

Supprime les articles plus anciens que retention_days SAUF les favoris.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.weekly_scheduler import WeeklyScheduler
from src.models.database import Database
from src.utils.config import load_config


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    config = load_config(project_root / "config" / "config.yaml")

    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_dir / "purge.log"),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)

    from src.utils.config import get_db_path
    db_path = get_db_path(config)
    db = Database(db_path)

    retention_days = config.get("retention", {}).get("days", 7)
    scheduler = WeeklyScheduler(db, retention_days=retention_days)
    deleted = scheduler.run_now()

    logging.info("Purge terminee: %d articles supprimes (favoris preserves)", deleted)
    sys.exit(0)


if __name__ == "__main__":
    main()
