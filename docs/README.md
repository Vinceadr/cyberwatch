# CyberWatch

Agent IA de veille cybersecurite automatisee.

## Fonctionnalites

- Collecte RSS/scraping de sources cyber (CERT-FR, ANSSI, CVE, 60+ sources)
- Synthese et classification par LLM local (Ollama)
- Dashboard temps reel (PySide6)
- Alertes email automatiques
- **Digest email quotidien a 7h via GitHub Actions** (aucun PC requis)
- Base SQLite locale
- Purge automatique hebdomadaire (favoris proteges)

## Setup

```bash
git clone https://github.com/Vinceadr/cyberwatch.git
cd cyberwatch
python -m venv .venv
.venv\Scripts\activate    # Windows

pip install -r requirements.txt

python src/main.py
```

## Digest Email Quotidien

Le digest est envoye chaque matin a 7h via GitHub Actions.
Configuration : ajouter `SMTP_USER` et `SMTP_PASSWORD` dans les Secrets du depot GitHub.
Voir [INSTALL.md](../INSTALL.md) pour le guide complet.

## Configuration

Editer `config/config.yaml` pour les sources, le modele LLM, et les parametres email.

## Tests

```bash
pytest
```
