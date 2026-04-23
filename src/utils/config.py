"""Config loader — charge et valide config.yaml + .env."""

import os
import re
import sys
from pathlib import Path

import yaml


def _get_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def _get_user_dir() -> Path:
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return Path(appdata) / "CyberWatch"
    return Path(__file__).resolve().parent.parent.parent


ROOT_DIR = _get_root_dir()
USER_DIR = _get_user_dir()


def load_config(config_path: Path | str) -> dict:
    config_path = Path(config_path)

    if not config_path.exists():
        msg = f"Config introuvable: {config_path}"
        raise FileNotFoundError(msg)

    _load_dotenv()

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        msg = f"Config invalide (pas un dict): {config_path}"
        raise ValueError(msg)

    _resolve_env_vars(config)
    _validate_required_keys(config)

    return config


def _load_dotenv() -> None:
    env_file = USER_DIR / ".env"
    if not env_file.exists():
        return
    with env_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)


def _resolve_env_vars(obj: dict | list | str) -> dict | list | str:
    if isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = _resolve_env_vars(value)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            obj[i] = _resolve_env_vars(value)
    elif isinstance(obj, str):
        pattern = re.compile(r"\$\{(\w+)\}")
        match = pattern.search(obj)
        if match:
            env_key = match.group(1)
            env_val = os.environ.get(env_key, "")
            obj = pattern.sub(env_val, obj)
    return obj


def _validate_required_keys(config: dict) -> None:
    required = ["app", "sources", "database", "llm"]
    missing = [k for k in required if k not in config]
    if missing:
        msg = f"Cles manquantes dans config: {', '.join(missing)}"
        raise KeyError(msg)


def get_db_path(config: dict) -> Path:
    return USER_DIR / config["database"]["path"]
