# INSTALL.md — CyberWatch

Guide d'installation complet de CyberWatch.

---

## Prerequis systeme

- **Python 3.11 ou superieur** — [python.org](https://www.python.org/downloads/)
- **Git** — [git-scm.com](https://git-scm.com/)
- **Ollama** (optionnel, pour l'analyse IA) — [ollama.ai](https://ollama.ai/)

Verifier les versions :

```bash
python --version    # >= 3.11
git --version
ollama --version    # optionnel
```

---

## Etape 1 — Cloner le depot

```bash
git clone https://github.com/Vinceadr/cyberwatch.git
cd cyberwatch
```

---

## Etape 2 — Environnement virtuel

### Windows

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Le prompt doit afficher `(.venv)` pour confirmer l'activation.

---

## Etape 3 — Installer les dependances

```bash
pip install -r requirements.txt
```

Dependances principales installees :
- `PySide6` — Interface graphique
- `feedparser` — Lecture flux RSS
- `requests` — Requetes HTTP
- `deep-translator` — Traduction EN -> FR
- `sqlite3` — Base de donnees (stdlib)
- `PyYAML` — Lecture config
- `apscheduler` — Planification automatique
- `pytest` — Tests

---

## Etape 4 — Configurer l'application

### 4a. Configuration generale

Editer `config/config.yaml` :

```yaml
app:
  name: "CyberWatch"
  log_level: "INFO"   # DEBUG pour plus de details

llm:
  provider: "ollama"
  base_url: "http://localhost:11434"
  model: "llama3.1:8b"   # ou mistral:7b

email:
  enabled: false   # true pour activer les alertes
```

### 4b. Variables d'environnement (optionnel — alertes email)

Creer un fichier `.env` a la racine du projet :

```env
CYBERWATCH_SMTP_USER=votre@gmail.com
CYBERWATCH_SMTP_PASS=votre_mot_de_passe_application
```

> Utiliser un **mot de passe d'application** Gmail (pas votre mot de passe principal).
> Menu Google : Compte > Securite > Verification en 2 etapes > Mots de passe des applications

---

## Etape 5 — Installer Ollama (optionnel)

Sans Ollama, CyberWatch collecte les articles mais ne les resume pas automatiquement.

### Windows

Telecharger et installer depuis [ollama.ai/download](https://ollama.ai/download)

### Linux

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### Telecharger un modele

```bash
# Modele recommande (8B, ~5 Go)
ollama pull llama3.1:8b

# Alternative plus legere (7B, ~4 Go)
ollama pull mistral:7b
```

Demarrer le serveur Ollama (deja automatique sur Windows apres installation) :

```bash
ollama serve
```

---

## Etape 6 — Lancer CyberWatch

### Interface graphique

```bash
python src/main.py
```

### Premier lancement

Au premier lancement, CyberWatch :
1. Cree la base SQLite dans `data/db/cyberwatch.db`
2. Initialise les categories et sources
3. Lance une collecte automatique initiale
4. Affiche le dashboard

---

## Lancement en mode CLI (sans GUI)

```bash
# Pipeline complet : collecte + traduction + enrichissement
python src/main.py --pipeline

# Collecte seule
python src/main.py --fetch

# Enrichissement des articles sans description
python src/main.py --enrich
```

---

## Automatisation (tache planifiee)

### Windows — Planificateur de taches

Creer une tache pointant vers :

```cmd
C:\chemin\vers\.venv\Scripts\python.exe C:\chemin\vers\cyberwatch\src\main.py --pipeline
```

Frequence recommandee : toutes les 30 minutes.

### Linux — cron

```bash
*/30 * * * * /chemin/vers/.venv/bin/python /chemin/vers/cyberwatch/src/main.py --pipeline
```

---

## Mise a jour

```bash
git pull origin main
pip install -r requirements.txt
```

---

## Desinstallation

```bash
# Supprimer le venv
rm -rf .venv

# Supprimer la base de donnees
rm -rf data/db/

# Supprimer les logs
rm -rf logs/
```

---


## Digest Email Quotidien via GitHub Actions

CyberWatch peut envoyer un **digest HTML** chaque matin a 7h directement depuis les serveurs GitHub.
**Le PC n'a pas besoin d'etre allume.**

### Prerequis

- Compte GitHub avec le depot CyberWatch (github.com/Vinceadr/cyberwatch)
- Adresse Gmail avec la **validation en 2 etapes** activee

### Etape 1 — Creer un mot de passe d'application Gmail

1. Aller sur https://myaccount.google.com/apppasswords
2. Taper un nom (ex : CyberWatch Digest) → **Creer**
3. Google affiche un code de **16 caracteres** — noter ce code (affiché une seule fois)

### Etape 2 — Ajouter les Secrets dans GitHub

Aller sur :
`
https://github.com/Vinceadr/cyberwatch/settings/secrets/actions
`

Ajouter deux secrets :

| Name | Value |
|------|-------|
| SMTP_USER | Votre adresse Gmail |
| SMTP_PASSWORD | Code 16 caracteres (sans espaces) |

### Etape 3 — Le workflow est deja configure

Le fichier .github/workflows/daily-digest.yml est present dans le depot.
Il se declenche automatiquement a **5h00 UTC = 7h00 Paris (CEST)**.

### Tester manuellement

`
https://github.com/Vinceadr/cyberwatch/actions/workflows/daily-digest.yml
`
→ Cliquer **"Run workflow"** → verifier la reception de l'email en 1-2 minutes.

### Contenu du digest

- Top 5 articles des dernieres 24h par categorie
- Classe par score de confiance de la source
- Categories : Cybersecurite, Hacks, IA, Systemes, Reseaux, Developpement
- Format HTML dark theme

---

## Problemes courants

| Probleme | Solution |
|----------|----------|
| `ModuleNotFoundError: PySide6` | `pip install PySide6` |
| `ConnectionError: ollama` | Verifier que `ollama serve` est demarre |
| Dashboard vide | Lancer `python src/main.py --fetch` pour une collecte manuelle |
| Logs d'erreur SSL | Mettre `verify_ssl: false` dans config (non recommande en prod) |
| Traduction trop lente | Desactiver `deep-translator` en limitant le volume d'articles |

---

## Support

Ouvrir une issue sur [github.com/Vinceadr/cyberwatch/issues](https://github.com/Vinceadr/cyberwatch/issues)

