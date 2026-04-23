"""Emailer — envoi de digests et alertes par email."""

import logging
import smtplib
import sys
from collections import defaultdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


def _get_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


TEMPLATES_DIR = _get_root_dir() / "templates"

CATEGORY_COLORS = {
    "Cybersecurite": "#F85149",
    "Systemes": "#58A6FF",
    "Reseaux": "#3FB950",
    "Developpement": "#D29922",
    "IA": "#BC8CFF",
    "Gaming": "#F78166",
    "Hacks": "#FF7B72",
}


class Emailer:
    def __init__(self, config: dict) -> None:
        self.config = config.get("email", {})
        self.enabled = self.config.get("enabled", False)
        self.smtp_config = self.config.get("smtp", {})
        self.sender = self.config.get("sender", "cyberwatch@localhost")
        self.recipients = self.config.get("recipients", [])

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    def send_digest(self, articles: list[dict]) -> bool:
        if not self.enabled:
            logger.info("Email desactive — skip digest")
            return False

        if not articles:
            logger.info("Aucun article — skip digest")
            return False

        articles_by_category = defaultdict(list)
        for article in articles:
            cat = article.get("category", "Autre")
            article["couleur"] = CATEGORY_COLORS.get(cat, "#6B7280")
            articles_by_category[cat].append(article)

        critical_count = sum(
            1 for a in articles if a.get("severity", a.get("severite", "INFO")) == "CRITIQUE"
        )

        context = {
            "articles": articles,
            "articles_by_category": dict(articles_by_category),
            "categories": list(articles_by_category.keys()),
            "critical_count": critical_count,
            "generation_date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }

        subject = f"[CyberWatch] Digest — {len(articles)} articles"
        if critical_count:
            subject = f"[CyberWatch] ⚠ {critical_count} critiques — {len(articles)} articles"

        html_body = self._render_template("digest.html", context)
        return self._send(subject, html_body)

    def send_critical_alert(self, article: dict) -> bool:
        if not self.enabled:
            return False

        subject = f"[CyberWatch] CRITIQUE — {article.get('title', article.get('titre', 'Alerte'))}"
        html_body = self._render_template("critical_alert.html", {"article": article})
        return self._send(subject, html_body)

    def _render_template(self, template_name: str, context: dict) -> str:
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception:
            logger.exception("Erreur template: %s", template_name)
            return str(context)

    def _send(self, subject: str, html_body: str) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.recipients)
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            host = self.smtp_config.get("host", "localhost")
            port = self.smtp_config.get("port", 587)

            with smtplib.SMTP(host, port, timeout=30) as server:
                if self.smtp_config.get("use_tls", True):
                    server.starttls()

                username = self.smtp_config.get("username")
                password = self.smtp_config.get("password")
                if username and password:
                    server.login(username, password)

                server.sendmail(self.sender, self.recipients, msg.as_string())

            logger.info("Email envoye: %s → %s", subject, self.recipients)
            return True

        except Exception:
            logger.exception("Erreur envoi email: %s", subject)
            return False

    def test_connection(self) -> bool:
        try:
            host = self.smtp_config.get("host", "localhost")
            port = self.smtp_config.get("port", 587)

            with smtplib.SMTP(host, port, timeout=10) as server:
                if self.smtp_config.get("use_tls", True):
                    server.starttls()
                server.noop()

            return True
        except Exception:
            logger.exception("Connexion SMTP echouee")
            return False
