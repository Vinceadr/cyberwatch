# CyberWatch

Agent IA de veille cybersécurité automatisée.

## Features

- Collecte RSS/scraping de sources cyber (CERT-FR, ANSSI, CVE, etc.)
- Synthèse et classification par LLM local (Ollama)
- Dashboard temps réel (PySide6)
- Alertes email automatiques
- Base SQLite locale

## Setup

```bash
# Créer un venv
python -m venv .venv
.venv\Scripts\activate    # Windows

# Installer les dépendances
pip install -r requirements.txt

# Lancer
python -m src.main
```

## Configuration

Éditer `config/config.yaml` pour les sources, le modèle LLM, et les paramètres email.

## Tests

```bash
pytest
```
