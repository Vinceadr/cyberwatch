"""CyberWatch — Point d'entree principal.

Lance le dashboard PySide6 ou le pipeline CLI selon les arguments.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _get_root_dir()
CONFIG_PATH = ROOT_DIR / "config" / "config.yaml"


def _get_user_dir() -> Path:
    if getattr(sys, "frozen", False):
        # %LOCALAPPDATA%\CyberWatch — standard Windows user data location
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return Path(appdata) / "CyberWatch"
    return Path(__file__).resolve().parent.parent


USER_DIR = _get_user_dir()


def setup_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log_dir = USER_DIR / "logs"
    os.makedirs(str(log_dir), exist_ok=True)

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "cyberwatch.log", encoding="utf-8"),
    ]
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)-7s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cyberwatch",
        description="CyberWatch — Agent IA de veille informatique",
    )
    parser.add_argument("--cli", action="store_true", help="Mode CLI (sans GUI)")
    parser.add_argument("--pipeline", action="store_true", help="Lancer le pipeline complet")
    parser.add_argument("--fetch", action="store_true", help="Fetch immediat des sources")
    parser.add_argument("--enrich", action="store_true", help="Enrichir les articles sans description")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="Chemin config")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
    )
    return parser.parse_args()


def run_gui(config: dict) -> int:
    from PySide6.QtWidgets import QApplication

    from src.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(config["app"]["name"])
    app.setApplicationVersion(config["app"]["version"])

    window = MainWindow(config)
    window.show()

    return app.exec()


def run_pipeline(config: dict) -> int:
    from src.core.pipeline import Pipeline

    logger.info("Lancement du pipeline complet...")
    pipeline = Pipeline(config)
    result = pipeline.run()

    if result.success:
        logger.info(
            "Pipeline OK — %d scrapes, %d nouveaux, %d traduits, %d emails",
            result.articles_scraped, result.articles_new,
            result.articles_translated, result.emails_sent,
        )
        return 0
    else:
        logger.error("Pipeline ECHEC — erreurs: %s", result.errors)
        return 1


def run_fetch(config: dict) -> int:
    from src.core.scraper import Scraper
    from src.models.database import Database
    from src.utils.config import get_db_path

    logger.info("Mode fetch — collecte des sources...")
    scraper = Scraper(config)
    articles = scraper.fetch_all()
    logger.info("Fetch termine. %d articles recuperes.", len(articles))

    if not articles:
        return 0

    db = Database(get_db_path(config))

    # Register sources from config into DB
    categories = {c["nom"]: c["id"] for c in db.get_categories()}
    sources_list = config.get("sources", {})
    if isinstance(sources_list, dict):
        sources_list = sources_list.get("rss", [])
    for src_cfg in sources_list:
        cat_id = categories.get(src_cfg.get("category"))
        db.insert_source({
            "nom": src_cfg["name"],
            "url_flux": src_cfg["url"],
            "type": "rss",
            "categorie_id": cat_id,
            "score_confiance": src_cfg.get("score_confiance", src_cfg.get("confidence", 50)),
            "langue": src_cfg.get("langue", src_cfg.get("language", "en")),
            "actif": 1,
        })

    # Insert articles
    dicts = [a.to_dict() for a in articles]
    inserted = db.insert_articles(dicts)
    logger.info("Stockage termine. %d nouveaux articles inseres en DB.", inserted)

    # Translate untranslated articles (en → fr)
    translated = _translate_new_articles(db)
    logger.info("Traduction termine. %d articles traduits.", translated)

    # Enrich articles missing descriptions
    from src.core.content_fetcher import enrich_missing_descriptions
    enriched = enrich_missing_descriptions(get_db_path(config))
    logger.info("Enrichissement termine. %d articles enrichis.", enriched)

    return 0


def run_enrich(config: dict) -> int:
    """Enrich articles that have no description by scraping their URLs."""
    from src.core.content_fetcher import enrich_missing_descriptions
    from src.utils.config import get_db_path

    logger.info("Mode enrichissement — scraping des articles sans description...")
    enriched = enrich_missing_descriptions(get_db_path(config))
    logger.info("Enrichissement termine. %d articles enrichis.", enriched)
    return 0


def _translate_new_articles(db) -> int:
    """Translate titles and summaries of untranslated English articles.
    For French articles, copy titre → titre_fr directly."""

    import datetime
    current_year = str(datetime.datetime.now().year)

    # First: copy French articles' titles directly (no translation needed)
    with db._connect() as conn:
        fr_updated = conn.execute(
            "UPDATE articles SET titre_fr = titre, resume_fr = SUBSTR(contenu_brut, 1, 500) "
            "WHERE (titre_fr IS NULL OR titre_fr = '') "
            "AND langue_originale = 'fr' "
            "AND date_publication LIKE ? || '%'",
            (current_year,),
        ).rowcount
        if fr_updated:
            logger.info("Articles FR %s copies directement: %d", current_year, fr_updated)

    # Then: translate English articles (current year only)
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        logger.warning("deep_translator non installe, traduction ignoree.")
        return fr_updated

    translator = GoogleTranslator(source="en", target="fr")

    with db._connect() as conn:
        rows = conn.execute(
            "SELECT id, titre, contenu_brut, langue_originale FROM articles "
            "WHERE (titre_fr IS NULL OR titre_fr = '') "
            "AND langue_originale = 'en' "
            "AND date_publication LIKE ? || '%' "
            "ORDER BY id DESC",
            (current_year,),
        ).fetchall()

    if not rows:
        return fr_updated

    logger.info("Traduction auto: %d articles EN a traduire en FR...", len(rows))
    count = 0
    BATCH_SIZE = 20  # small batches to avoid rate limits

    for start in range(0, len(rows), BATCH_SIZE):
        chunk = rows[start : start + BATCH_SIZE]
        chunk_ids = [r[0] for r in chunk]
        chunk_titles = [r[1] or "" for r in chunk]
        chunk_summaries = [(r[2] or "")[:500] for r in chunk]

        # Translate titles
        title_map = {}
        non_empty_titles = [(i, t) for i, t in enumerate(chunk_titles) if t.strip()]
        if non_empty_titles:
            try:
                texts = [t for _, t in non_empty_titles]
                results = translator.translate_batch(texts)
                for j, (i, _) in enumerate(non_empty_titles):
                    title_map[i] = results[j] if results[j] else chunk_titles[i]
            except Exception:
                # Fallback: translate one by one
                for i, t in non_empty_titles:
                    try:
                        title_map[i] = translator.translate(t)
                    except Exception:
                        title_map[i] = t

        # Translate summaries
        summary_map = {}
        non_empty_sums = [(i, s) for i, s in enumerate(chunk_summaries) if s.strip()]
        if non_empty_sums:
            try:
                texts = [s for _, s in non_empty_sums]
                results = translator.translate_batch(texts)
                for j, (i, _) in enumerate(non_empty_sums):
                    summary_map[i] = results[j] if results[j] else ""
            except Exception:
                for i, s in non_empty_sums:
                    try:
                        summary_map[i] = translator.translate(s)
                    except Exception:
                        summary_map[i] = ""

        # Update DB
        with db._connect() as conn:
            for i, art_id in enumerate(chunk_ids):
                titre_fr = title_map.get(i, chunk_titles[i])
                resume_fr = summary_map.get(i, "")
                conn.execute(
                    "UPDATE articles SET titre_fr = ?, resume_fr = ? WHERE id = ?",
                    (titre_fr, resume_fr, art_id),
                )
                count += 1

        logger.info("Traduction batch %d-%d OK (%d articles)", start, start + len(chunk), len(chunk))

    return fr_updated + count


def main() -> int:
    args = parse_args()

    from src.utils.config import load_config
    config = load_config(args.config)
    log_level = args.log_level or config.get("app", {}).get("log_level", "INFO")
    setup_logging(log_level)

    logger.info("CyberWatch v%s — demarrage", config["app"]["version"])

    if args.pipeline:
        return run_pipeline(config)
    if args.fetch:
        return run_fetch(config)
    if args.enrich:
        return run_enrich(config)
    if args.cli:
        return run_fetch(config)

    return run_gui(config)


if __name__ == "__main__":
    sys.exit(main())
