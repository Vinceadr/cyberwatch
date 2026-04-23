"""Tests — config loader."""

from pathlib import Path

import pytest

from src.utils.config import load_config

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def valid_config_path(tmp_path: Path) -> Path:
    """Crée un fichier config valide pour les tests."""
    config_content = """
app:
  name: "CyberWatch-Test"
  version: "0.0.1"
  log_level: "DEBUG"

sources:
  rss: []

database:
  path: "data/db/test.db"

llm:
  model: "test-model"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content, encoding="utf-8")
    return config_file


def test_load_config_valid(valid_config_path: Path) -> None:
    """Config valide se charge correctement."""
    config = load_config(valid_config_path)
    assert config["app"]["name"] == "CyberWatch-Test"
    assert config["app"]["version"] == "0.0.1"


def test_load_config_missing_file() -> None:
    """FileNotFoundError si fichier manquant."""
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


def test_load_config_missing_keys(tmp_path: Path) -> None:
    """KeyError si clés obligatoires manquantes."""
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("app:\n  name: test\n", encoding="utf-8")
    with pytest.raises(KeyError, match="sources"):
        load_config(bad_config)
