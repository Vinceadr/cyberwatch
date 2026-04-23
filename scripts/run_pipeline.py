"""Point d'entrée pour Windows Task Scheduler."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.pipeline import Pipeline
from src.utils.config import load_config


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    config = load_config(project_root / "config" / "config.yaml")

    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=str(log_dir / "pipeline.log"),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)

    pipeline = Pipeline(config)
    result = pipeline.run()

    if result.success:
        logging.info(
            "Pipeline OK: %d articles, %d nouveaux",
            result.articles_scraped,
            result.articles_new,
        )
    else:
        logging.error("Pipeline FAILED: %s", result.errors)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
