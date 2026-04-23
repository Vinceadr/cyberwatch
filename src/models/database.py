"""Database — modèle SQLite enrichi pour CyberWatch."""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nom         TEXT NOT NULL UNIQUE,
    couleur     TEXT NOT NULL DEFAULT '#6B7280',
    icone       TEXT DEFAULT '',
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nom             TEXT NOT NULL,
    url_flux        TEXT NOT NULL UNIQUE,
    type            TEXT NOT NULL DEFAULT 'rss' CHECK (type IN ('rss', 'web', 'api')),
    categorie_id    INTEGER REFERENCES categories(id),
    score_confiance INTEGER NOT NULL DEFAULT 50 CHECK (score_confiance BETWEEN 0 AND 100),
    langue          TEXT DEFAULT 'fr',
    actif           INTEGER DEFAULT 1,
    derniere_collecte TEXT,
    nb_articles_total INTEGER DEFAULT 0,
    nb_articles_confirmes INTEGER DEFAULT 0,
    nb_articles_contredits INTEGER DEFAULT 0,
    date_ajout      TEXT DEFAULT (datetime('now')),
    UNIQUE(nom)
);

CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    uid             TEXT NOT NULL UNIQUE,
    titre           TEXT NOT NULL,
    url_original    TEXT NOT NULL UNIQUE,
    source_id       INTEGER NOT NULL REFERENCES sources(id),
    categorie_id    INTEGER REFERENCES categories(id),
    langue_originale TEXT DEFAULT 'en',
    titre_fr        TEXT DEFAULT '',
    resume_fr       TEXT DEFAULT '',
    contenu_brut    TEXT DEFAULT '',
    date_publication TEXT,
    date_collecte   TEXT NOT NULL DEFAULT (datetime('now')),
    score_fiabilite INTEGER DEFAULT -1,
    severite        TEXT DEFAULT 'INFO' CHECK (severite IN ('CRITIQUE','HAUTE','MOYENNE','BASSE','INFO')),
    lu              INTEGER DEFAULT 0,
    favori          INTEGER DEFAULT 0,
    notifie         INTEGER DEFAULT 0,
    traite_ia       INTEGER DEFAULT 0,
    ai_summary      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS verifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id      INTEGER NOT NULL REFERENCES articles(id),
    methode         TEXT NOT NULL CHECK (methode IN ('cross_ref','heuristique','source_only')),
    score           INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    nb_sources_croisees INTEGER DEFAULT 0,
    details_json    TEXT DEFAULT '{}',
    date_verification TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cross_references (
    article_id_1    INTEGER NOT NULL REFERENCES articles(id),
    article_id_2    INTEGER NOT NULL REFERENCES articles(id),
    similarite      REAL NOT NULL CHECK (similarite BETWEEN 0 AND 1),
    date_detection  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (article_id_1, article_id_2)
);

CREATE TABLE IF NOT EXISTS alertes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  INTEGER REFERENCES articles(id),
    source_id   INTEGER REFERENCES sources(id),
    niveau      TEXT NOT NULL CHECK (niveau IN ('CRITICAL','WARNING','INFO')),
    type        TEXT NOT NULL,
    message     TEXT NOT NULL,
    lue         INTEGER DEFAULT 0,
    date_alerte TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS envois_email (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date_envoi  TEXT NOT NULL DEFAULT (datetime('now')),
    sujet       TEXT NOT NULL,
    nb_articles INTEGER DEFAULT 0,
    statut      TEXT DEFAULT 'success'
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    articles_scrapes INTEGER DEFAULT 0,
    articles_nouveaux INTEGER DEFAULT 0,
    articles_traduits INTEGER DEFAULT 0,
    articles_verifies INTEGER DEFAULT 0,
    emails_envoyes  INTEGER DEFAULT 0,
    erreurs_json    TEXT DEFAULT '[]',
    succes          INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS config (
    cle     TEXT PRIMARY KEY,
    valeur  TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    titre, titre_fr, resume_fr, contenu_brut,
    content='articles',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, titre, titre_fr, resume_fr, contenu_brut)
    VALUES (new.id, new.titre, new.titre_fr, new.resume_fr, new.contenu_brut);
END;

CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, titre, titre_fr, resume_fr, contenu_brut)
    VALUES ('delete', old.id, old.titre, old.titre_fr, old.resume_fr, old.contenu_brut);
    INSERT INTO articles_fts(rowid, titre, titre_fr, resume_fr, contenu_brut)
    VALUES (new.id, new.titre, new.titre_fr, new.resume_fr, new.contenu_brut);
END;

CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, titre, titre_fr, resume_fr, contenu_brut)
    VALUES ('delete', old.id, old.titre, old.titre_fr, old.resume_fr, old.contenu_brut);
END;

CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_categorie ON articles(categorie_id);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date_publication);
CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(score_fiabilite);
CREATE INDEX IF NOT EXISTS idx_articles_severite ON articles(severite);
CREATE INDEX IF NOT EXISTS idx_verifications_article ON verifications(article_id);
CREATE INDEX IF NOT EXISTS idx_alertes_article ON alertes(article_id);

CREATE TABLE IF NOT EXISTS summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    type         TEXT NOT NULL CHECK (type IN ('morning', 'evening')),
    content      TEXT NOT NULL DEFAULT '{}',
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date, type)
);

CREATE INDEX IF NOT EXISTS idx_summaries_date ON summaries(date);
CREATE INDEX IF NOT EXISTS idx_summaries_type_date ON summaries(type, date);
"""

DEFAULT_CATEGORIES = [
    {"nom": "Cybersecurite", "couleur": "#F85149", "icone": "shield", "description": "CVE, breaches, threat intel"},
    {"nom": "Systemes", "couleur": "#58A6FF", "icone": "server", "description": "Windows, Linux, cloud"},
    {"nom": "Reseaux", "couleur": "#3FB950", "icone": "network", "description": "Cisco, protocoles, SDN"},
    {"nom": "Developpement", "couleur": "#D29922", "icone": "code", "description": "Frameworks, langages, outils"},
    {"nom": "IA", "couleur": "#BC8CFF", "icone": "brain", "description": "Machine Learning, modeles, recherche"},
    {"nom": "Gaming", "couleur": "#F78166", "icone": "gamepad", "description": "Industrie, tech, hacks gaming"},
    {"nom": "Hacks", "couleur": "#FF7B72", "icone": "alert", "description": "Incidents securite transversal"},
]


class Database:

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        import os
        os.makedirs(str(self.db_path.parent), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            # Migration: add ai_summary column for DBs created before this version
            try:
                conn.execute("ALTER TABLE articles ADD COLUMN ai_summary TEXT DEFAULT ''")
            except Exception:
                pass  # Column already exists
        self.init_categories()
        logger.info("DB initialisée: %s", self.db_path)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Categories ──────────────────────────────────────────────

    def init_categories(self) -> None:
        with self._connect() as conn:
            for cat in DEFAULT_CATEGORIES:
                conn.execute(
                    "INSERT OR IGNORE INTO categories (nom, couleur, icone, description) VALUES (?, ?, ?, ?)",
                    (cat["nom"], cat["couleur"], cat["icone"], cat["description"]),
                )

    def get_categories(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
            return [dict(r) for r in rows]

    # ── Sources ─────────────────────────────────────────────────

    def insert_source(self, source_data: dict) -> int:
        sql = """
            INSERT OR IGNORE INTO sources
                (nom, url_flux, type, categorie_id, score_confiance, langue, actif)
            VALUES
                (:nom, :url_flux, :type, :categorie_id, :score_confiance, :langue, :actif)
        """
        defaults: dict[str, Any] = {
            "type": "rss", "categorie_id": None,
            "score_confiance": 50, "langue": "fr", "actif": 1,
        }
        data = {**defaults, **source_data}
        with self._connect() as conn:
            cursor = conn.execute(sql, data)
            if cursor.lastrowid:
                return cursor.lastrowid
            row = conn.execute(
                "SELECT id FROM sources WHERE url_flux = ?", (data["url_flux"],)
            ).fetchone()
            return row["id"] if row else 0

    def get_sources(self, actives_only: bool = True) -> list[dict]:
        sql = (
            "SELECT s.*, c.nom AS categorie_nom "
            "FROM sources s LEFT JOIN categories c ON s.categorie_id = c.id"
        )
        if actives_only:
            sql += " WHERE s.actif = 1"
        sql += " ORDER BY s.id"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]

    def update_source(self, source_id: int, data: dict) -> None:
        allowed = {
            "nom", "url_flux", "type", "categorie_id", "score_confiance",
            "langue", "actif", "derniere_collecte",
            "nb_articles_total", "nb_articles_confirmes", "nb_articles_contredits",
        }
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = source_id
        with self._connect() as conn:
            conn.execute(f"UPDATE sources SET {set_clause} WHERE id = :id", fields)

    def delete_source(self, source_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))

    # ── Articles ────────────────────────────────────────────────

    def _resolve_source_id(self, conn: sqlite3.Connection, source_name: str) -> int:
        row = conn.execute("SELECT id FROM sources WHERE nom = ?", (source_name,)).fetchone()
        if row:
            return row["id"]
        cursor = conn.execute(
            "INSERT INTO sources (nom, url_flux, score_confiance) VALUES (?, ?, 50)",
            (source_name, f"auto://{source_name}"),
        )
        return cursor.lastrowid  # type: ignore[return-value]

    def _resolve_categorie_id(self, conn: sqlite3.Connection, cat_name: str) -> int | None:
        row = conn.execute("SELECT id FROM categories WHERE nom = ?", (cat_name,)).fetchone()
        return row["id"] if row else None

    def _normalize_article(self, conn: sqlite3.Connection, article: dict) -> dict:
        if "titre" in article:
            return article
        source_id = article.get("source_id") or None
        if not source_id:
            source_id = self._resolve_source_id(conn, article.get("source_name", "Unknown"))
        categorie_id = article.get("categorie_id") or None
        if not categorie_id and "category" in article:
            categorie_id = self._resolve_categorie_id(conn, article["category"])
        return {
            "uid": article["uid"],
            "titre": article.get("title", ""),
            "url_original": article.get("url", ""),
            "source_id": source_id,
            "categorie_id": categorie_id,
            "date_publication": article.get("published"),
            "date_collecte": article.get("fetched_at", datetime.now(tz=timezone.utc).isoformat()),
            "contenu_brut": article.get("content", ""),
            "resume_fr": article.get("summary", ""),
        }

    def insert_article(self, article: dict) -> bool:
        sql = """
            INSERT OR IGNORE INTO articles
                (uid, titre, url_original, source_id, categorie_id,
                 date_publication, date_collecte, contenu_brut, resume_fr)
            VALUES
                (:uid, :titre, :url_original, :source_id, :categorie_id,
                 :date_publication, :date_collecte, :contenu_brut, :resume_fr)
        """
        with self._connect() as conn:
            data = self._normalize_article(conn, article)
            cursor = conn.execute(sql, data)
            return cursor.rowcount > 0

    def insert_articles(self, articles: list[dict]) -> int:
        sql = """
            INSERT OR IGNORE INTO articles
                (uid, titre, url_original, source_id, categorie_id,
                 date_publication, date_collecte, contenu_brut, resume_fr)
            VALUES
                (:uid, :titre, :url_original, :source_id, :categorie_id,
                 :date_publication, :date_collecte, :contenu_brut, :resume_fr)
        """
        inserted = 0
        with self._connect() as conn:
            for article in articles:
                data = self._normalize_article(conn, article)
                cursor = conn.execute(sql, data)
                if cursor.rowcount > 0:
                    inserted += 1
        return inserted

    def get_articles(
        self,
        category: str | None = None,
        severity: str | None = None,
        limit: int = 2000,
        offset: int = 0,
        unread_only: bool = False,
        score_min: int | None = None,
        favoris_only: bool = False,
        order: str = "DESC",
        date_since: str | None = None,
    ) -> list[dict]:
        conditions: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if date_since:
            conditions.append("a.date_collecte >= :date_since")
            params["date_since"] = date_since
        if category:
            conditions.append("c.nom = :category")
            params["category"] = category
        if severity:
            conditions.append("a.severite = :severity")
            params["severity"] = severity
        if unread_only:
            conditions.append("a.lu = 0")
        if score_min is not None:
            conditions.append("a.score_fiabilite >= :score_min")
            params["score_min"] = score_min
        if favoris_only:
            conditions.append("a.favori = 1")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        direction = "ASC" if order.upper() == "ASC" else "DESC"

        sql = f"""
            SELECT a.*, s.nom AS source_nom, c.nom AS categorie_nom
            FROM articles a
            LEFT JOIN sources s ON a.source_id = s.id
            LEFT JOIN categories c ON a.categorie_id = c.id
            {where}
            ORDER BY a.date_collecte {direction}, a.date_publication {direction}
            LIMIT :limit OFFSET :offset
        """
        with self._connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        return [self._add_gui_aliases(r) for r in rows]

    _CATEGORY_KEY_MAP: dict[str, str] = {
        "Cybersecurite": "cyber",
        "Systemes": "systemes",
        "Reseaux": "reseaux",
        "Developpement": "dev",
        "IA": "ia",
        "Gaming": "gaming",
        "Hacks": "hacks",
    }

    def _add_gui_aliases(self, r: dict) -> dict:
        r.setdefault("title", r.get("titre_fr") or r.get("titre", ""))
        r.setdefault("url", r.get("url_original", ""))
        r.setdefault("source_name", r.get("source_nom", ""))
        cat_nom = r.get("categorie_nom", "unknown") or "unknown"
        r.setdefault("category", self._CATEGORY_KEY_MAP.get(cat_nom, cat_nom.lower()))
        r.setdefault("description", r.get("resume_fr", ""))  # raw RSS description (never translated)
        r.setdefault("summary", r.get("resume_fr", ""))      # backward-compat alias
        r.setdefault("content", r.get("contenu_brut", ""))
        r["ai_summary"] = r.get("ai_summary", "")             # LLM summary (separate field)
        r.setdefault("score", r.get("score_fiabilite", 0))
        r.setdefault("published", r.get("date_publication", ""))
        r.setdefault("read", r.get("lu", 0))
        r.setdefault("starred", r.get("favori", 0))
        return r

    def get_article_by_uid(self, uid: str) -> dict | None:
        sql = """
            SELECT a.*, s.nom AS source_nom, c.nom AS categorie_nom
            FROM articles a
            LEFT JOIN sources s ON a.source_id = s.id
            LEFT JOIN categories c ON a.categorie_id = c.id
            WHERE a.uid = ?
        """
        with self._connect() as conn:
            row = conn.execute(sql, (uid,)).fetchone()
            return self._add_gui_aliases(dict(row)) if row else None

    def search_articles(self, query: str, limit: int = 50) -> list[dict]:
        safe_query = '"' + query.replace('"', '""') + '"'
        sql = """
            SELECT a.*, s.nom AS source_nom, c.nom AS categorie_nom
            FROM articles_fts fts
            JOIN articles a ON a.id = fts.rowid
            LEFT JOIN sources s ON a.source_id = s.id
            LEFT JOIN categories c ON a.categorie_id = c.id
            WHERE articles_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        with self._connect() as conn:
            return [self._add_gui_aliases(dict(r)) for r in conn.execute(sql, (safe_query, limit)).fetchall()]

    def update_article_score(self, uid: str, score: int, severite: str = "INFO") -> None:
        sql = "UPDATE articles SET score_fiabilite = ?, severite = ? WHERE uid = ?"
        with self._connect() as conn:
            conn.execute(sql, (score, severite, uid))

    def update_ai_summary(self, uid: str, ai_summary: str, severity: str = "INFO", score: int | None = None) -> None:
        """Update severity/score; raw description in resume_fr is preserved."""
        if score is not None:
            sql = "UPDATE articles SET ai_summary = ?, severite = ?, score_fiabilite = ?, traite_ia = 1 WHERE uid = ?"
            with self._connect() as conn:
                conn.execute(sql, (ai_summary, severity, score, uid))
        else:
            sql = "UPDATE articles SET ai_summary = ?, severite = ?, traite_ia = 1 WHERE uid = ?"
            with self._connect() as conn:
                conn.execute(sql, (ai_summary, severity, uid))

    def mark_read(self, uid: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE articles SET lu = 1 WHERE uid = ?", (uid,))

    def mark_starred(self, uid: str, starred: bool = True) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE articles SET favori = ? WHERE uid = ?", (int(starred), uid))

    def get_articles_for_crossref(self, hours: int = 72) -> list[dict]:
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=hours)).isoformat()
        sql = """
            SELECT a.*, s.nom AS source_nom
            FROM articles a
            LEFT JOIN sources s ON a.source_id = s.id
            WHERE a.date_collecte >= ?
            ORDER BY a.date_collecte DESC
        """
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, (cutoff,)).fetchall()]

    # ── Verifications ───────────────────────────────────────────

    def insert_verification(self, verification_data: dict) -> int:
        sql = """
            INSERT INTO verifications
                (article_id, methode, score, nb_sources_croisees, details_json)
            VALUES
                (:article_id, :methode, :score, :nb_sources_croisees, :details_json)
        """
        defaults: dict[str, Any] = {"nb_sources_croisees": 0, "details_json": "{}"}
        data = {**defaults, **verification_data}
        with self._connect() as conn:
            cursor = conn.execute(sql, data)
            return cursor.lastrowid  # type: ignore[return-value]

    def get_verifications(self, article_id: int) -> list[dict]:
        sql = "SELECT * FROM verifications WHERE article_id = ? ORDER BY date_verification DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, (article_id,)).fetchall()]

    # ── Alertes ─────────────────────────────────────────────────

    def insert_alerte(self, alerte_data: dict) -> int:
        sql = """
            INSERT INTO alertes (article_id, source_id, niveau, type, message)
            VALUES (:article_id, :source_id, :niveau, :type, :message)
        """
        defaults: dict[str, Any] = {"article_id": None, "source_id": None}
        data = {**defaults, **alerte_data}
        with self._connect() as conn:
            cursor = conn.execute(sql, data)
            return cursor.lastrowid  # type: ignore[return-value]

    def get_alertes(self, non_lues_only: bool = True) -> list[dict]:
        sql = "SELECT * FROM alertes"
        if non_lues_only:
            sql += " WHERE lue = 0"
        sql += " ORDER BY date_alerte DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]

    # ── Pipeline ────────────────────────────────────────────────

    def log_pipeline_run(self, run_data: dict) -> int:
        sql = """
            INSERT INTO pipeline_runs
                (completed_at, articles_scrapes, articles_nouveaux,
                 articles_traduits, articles_verifies, emails_envoyes,
                 erreurs_json, succes)
            VALUES
                (:completed_at, :articles_scrapes, :articles_nouveaux,
                 :articles_traduits, :articles_verifies, :emails_envoyes,
                 :erreurs_json, :succes)
        """
        defaults: dict[str, Any] = {
            "completed_at": datetime.now(tz=timezone.utc).isoformat(),
            "articles_scrapes": 0, "articles_nouveaux": 0,
            "articles_traduits": 0, "articles_verifies": 0,
            "emails_envoyes": 0, "erreurs_json": "[]", "succes": 0,
        }
        data = {**defaults, **run_data}
        with self._connect() as conn:
            cursor = conn.execute(sql, data)
            return cursor.lastrowid  # type: ignore[return-value]

    def get_last_pipeline_run(self) -> dict | None:
        sql = "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(sql).fetchone()
            return dict(row) if row else None

    # ── Stats ───────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            unread = conn.execute("SELECT COUNT(*) FROM articles WHERE lu = 0").fetchone()[0]
            critical = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE severite = 'CRITIQUE'"
            ).fetchone()[0]
            today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
            today_count = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE date_collecte >= ?", (today,)
            ).fetchone()[0]
            favoris = conn.execute("SELECT COUNT(*) FROM articles WHERE favori = 1").fetchone()[0]
            sources_actives = conn.execute("SELECT COUNT(*) FROM sources WHERE actif = 1").fetchone()[0]
            alertes_non_lues = conn.execute("SELECT COUNT(*) FROM alertes WHERE lue = 0").fetchone()[0]

        return {
            "total": total,
            "unread": unread,
            "critical": critical,
            "today": today_count,
            "favoris": favoris,
            "sources_actives": sources_actives,
            "alertes_non_lues": alertes_non_lues,
        }

    def count_by_category(self) -> dict[str, int]:
        sql = """
            SELECT COALESCE(c.nom, 'Non classé') AS cat, COUNT(*) AS n
            FROM articles a
            LEFT JOIN categories c ON a.categorie_id = c.id
            GROUP BY c.nom
        """
        with self._connect() as conn:
            return {r["cat"]: r["n"] for r in conn.execute(sql).fetchall()}

    # ── Maintenance ─────────────────────────────────────────────

    def purge_old_articles(self, days: int = 7) -> int:
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM verifications WHERE article_id IN "
                "(SELECT id FROM articles WHERE date_collecte < ? AND favori = 0)", (cutoff,),
            )
            conn.execute(
                "DELETE FROM alertes WHERE article_id IN "
                "(SELECT id FROM articles WHERE date_collecte < ? AND favori = 0)", (cutoff,),
            )
            conn.execute(
                "DELETE FROM cross_references WHERE article_id_1 IN "
                "(SELECT id FROM articles WHERE date_collecte < ? AND favori = 0) "
                "OR article_id_2 IN "
                "(SELECT id FROM articles WHERE date_collecte < ? AND favori = 0)", (cutoff, cutoff),
            )
            cursor = conn.execute("DELETE FROM articles WHERE date_collecte < ? AND favori = 0", (cutoff,))
            return cursor.rowcount

    # ── Backward compat (scraper / emailer) ─────────────────────

    def log_fetch(self, source_name: str, count: int, status: str = "success", error: str = "") -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, nb_articles_total FROM sources WHERE nom = ?", (source_name,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE sources SET derniere_collecte = ?, nb_articles_total = ? WHERE id = ?",
                    (datetime.now(tz=timezone.utc).isoformat(), row["nb_articles_total"] + count, row["id"]),
                )
            if status != "success" and error:
                conn.execute(
                    "INSERT INTO alertes (source_id, niveau, type, message) VALUES (?, ?, ?, ?)",
                    (row["id"] if row else None, "WARNING", "fetch_error", f"{source_name}: {error}"),
                )

    # ── Summaries ─────────────────────────────────────────────

    def save_summary(self, date: str, type: str, content_json: str) -> None:
        """Insert or replace a daily summary (morning/evening)."""
        sql = """
            INSERT INTO summaries (date, type, content, generated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(date, type) DO UPDATE SET
                content      = excluded.content,
                generated_at = excluded.generated_at
        """
        with self._connect() as conn:
            conn.execute(sql, (date, type, content_json))
        logger.debug("Résumé %s/%s sauvegardé", type, date)

    def get_summary(self, date: str, type: str) -> dict | None:
        """Return the summary dict for a given date + type, or None."""
        sql = "SELECT * FROM summaries WHERE date = ? AND type = ? LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(sql, (date, type)).fetchone()
            return dict(row) if row else None

    def get_week_summaries(self) -> list[dict]:
        """Return all summaries for the last 7 days, newest first."""
        from datetime import datetime as _dt, timedelta as _td
        since = (_dt.now().date() - _td(days=6)).isoformat()
        sql = "SELECT * FROM summaries WHERE date >= ? ORDER BY date DESC, type DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, (since,)).fetchall()]
