# CyberWatch

**Agent IA de veille cybersecurite automatisee**

CyberWatch est une application de bureau Python qui collecte, analyse et classe automatiquement les actualites cybersecurite depuis plus de 60 sources RSS. Il utilise un LLM local (Ollama) pour resumer et classer les articles par severite, et propose un dashboard temps reel avec alertes email.

---

## Fonctionnalites

- **Collecte automatique** : 60+ flux RSS (cybersecurite, systemes, reseaux, IA, dev, hacks/breaches)
- **Analyse IA locale** : Resume et classification par severite via Ollama (llama3.1, mistral)
- **Dashboard PySide6** : Interface graphique temps reel, filtrage par categorie et severite
- **Traduction automatique** : Articles EN -> FR via deep-translator
- **Alertes email** : Digest quotidien + alertes immediates pour incidents CRITIQUES
- **Pipeline CLI** : Mode headless pour serveurs et automatisation
- **Base SQLite locale** : Historique 7 jours, zero cloud
- **Sources francaises** : CERT-FR, ZATAZ, UnderNews, IT-Connect, Korben, etc.

---

## Architecture

```
cyberwatch/
├── src/
│   ├── core/
│   │   ├── scraper.py          # Collecte RSS
│   │   ├── pipeline.py         # Orchestration complete
│   │   ├── summarizer.py       # Resume LLM via Ollama
│   │   ├── content_fetcher.py  # Enrichissement articles
│   │   ├── emailer.py          # Alertes email
│   │   └── weekly_scheduler.py # Planification automatique
│   ├── gui/
│   │   ├── main_window.py      # Fenetre principale PySide6
│   │   ├── widgets.py          # Composants UI
│   │   └── styles.py           # Theme sombre
│   ├── models/
│   │   └── database.py         # Modele SQLite
│   └── utils/
│       └── config.py           # Chargement configuration
├── config/
│   └── config.yaml             # Configuration principale (sources, LLM, email)
├── data/db/                    # Base SQLite (gitignored)
├── logs/                       # Logs (gitignored)
├── tests/                      # Tests pytest
└── requirements.txt
```

---

## Prerequis

| Outil | Version | Utilite |
|-------|---------|---------|
| Python | 3.11+ | Runtime |
| Ollama | 0.1.x+ | LLM local (optionnel) |
| llama3.1:8b ou mistral:7b | — | Modele IA via Ollama |

> **Ollama est optionnel** : sans LLM, CyberWatch fonctionne en mode collecte pure.

---

## Installation rapide

```bash
git clone https://github.com/Vinceadr/cyberwatch.git
cd cyberwatch

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt

python src/main.py
```

Voir [INSTALL.md](INSTALL.md) pour le guide complet.

---

## Utilisation

```bash
# Mode GUI (interface graphique)
python src/main.py

# Pipeline complet (collecte + traduction + enrichissement)
python src/main.py --pipeline

# Collecte seule
python src/main.py --fetch

# Enrichissement articles sans description
python src/main.py --enrich

# Niveau de log
python src/main.py --log-level DEBUG
```

---

## Configuration

Editer `config/config.yaml` pour les sources, le modele LLM et les parametres email.

Variables d'environnement (fichier `.env`) :

```env
CYBERWATCH_SMTP_USER=votre@email.com
CYBERWATCH_SMTP_PASS=votre_mot_de_passe_app
```

---

## Sources incluses (60+)

| Categorie | Sources principales |
|-----------|---------------------|
| Cybersecurite | CERT-FR, BleepingComputer, Krebs on Security, The Hacker News, Dark Reading, NVD/NIST CVE, ZATAZ |
| Systemes/Infra | Ars Technica, AWS Blog, Azure Blog, Cloudflare Blog, IT-Connect, Korben |
| Reseaux | Cisco, NetworkWorld, PacketPushers, RIPE Labs, IPSpace |
| Developpement | GitHub Blog, InfoQ, Dev.to, The New Stack, Developpez.com |
| IA/ML | MIT Tech Review, Hugging Face, OpenAI Blog, Anthropic, DeepMind |
| Hacks / Breaches | HackRead, DataBreaches.net, The Record, TechCrunch Security |

---

## Tests

```bash
pytest
pytest --cov=src tests/
```

---

## Roadmap

- [ ] Export PDF du digest
- [ ] Integration Slack/Discord/Teams
- [ ] API REST locale
- [ ] Support multi-profils (admin, dev, analyst)

---

## Licence

MIT

---

*Projet realise dans le cadre du BTS SIO SISR — ANDREO Vincent*
