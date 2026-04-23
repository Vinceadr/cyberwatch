#!/usr/bin/env python3
"""
CyberWatch — Daily Digest (Cloud Version)
Fetches RSS articles from the last 24h and sends a formatted HTML email.
Designed to run in GitHub Actions (no local DB required).

Usage:
    python scripts/daily_digest_cloud.py

Environment variables required:
    SMTP_USER      -- Gmail address (sender + recipient)
    SMTP_PASSWORD  -- Gmail App Password (16-char, no spaces)
"""

import os
import sys
import smtplib
import logging
import re
import calendar
import concurrent.futures
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import feedparser
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("digest")

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR.parent / "config" / "config.yaml"

def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

@dataclass
class Article:
    title: str
    url: str
    summary: str
    source: str
    category: str
    score: int
    published: Optional[datetime] = None

    def age_label(self):
        if not self.published:
            return ""
        delta = datetime.now(timezone.utc) - self.published
        h = int(delta.total_seconds() / 3600)
        if h < 1:
            return "il y a moins d1h"
        return f"il y a {h}h"

CATEGORY_ICONS = {
    "Cybersecurite": "🔐", "Systemes": "🖥️", "Reseaux": "🌐",
    "Developpement": "💻", "IA": "🤖", "Gaming": "🎮", "Hacks": "⚠️",
}
CATEGORY_COLORS = {
    "Cybersecurite": "#e74c3c", "Systemes": "#2980b9", "Reseaux": "#27ae60",
    "Developpement": "#8e44ad", "IA": "#f39c12", "Gaming": "#16a085", "Hacks": "#c0392b",
}

def _parse_published(entry):
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                ts = calendar.timegm(t)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass
    return None

def fetch_source(source, cutoff):
    articles = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:20]:
            pub = _parse_published(entry)
            if pub and pub < cutoff:
                continue
            title = getattr(entry, "title", "").strip()
            url = getattr(entry, "link", "").strip()
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            summary = re.sub(r"<[^>]+>", " ", summary)
            summary = re.sub(r"\s+", " ", summary).strip()
            summary = summary[:300] + "..." if len(summary) > 300 else summary
            if title and url:
                articles.append(Article(
                    title=title, url=url, summary=summary,
                    source=source["name"], category=source["category"],
                    score=source.get("score_confiance", 80), published=pub,
                ))
    except Exception as e:
        log.warning("Erreur source %s : %s", source.get("name", "?"), e)
    return articles

def fetch_all_sources(config):
    sources = [s for s in config["sources"]["rss"] if s.get("enabled", True)]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    log.info("Fetching %d sources...", len(sources))
    all_articles = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(fetch_source, s, cutoff): s for s in sources}
        for f in concurrent.futures.as_completed(futures):
            all_articles.extend(f.result())
    by_cat = {}
    for art in all_articles:
        by_cat.setdefault(art.category, []).append(art)
    for cat in by_cat:
        by_cat[cat].sort(key=lambda a: a.score, reverse=True)
    total = sum(len(v) for v in by_cat.values())
    log.info("Articles collected: %d across %d categories", total, len(by_cat))
    return by_cat

TOP_N = 5

def _article_html(art, idx):
    age = art.age_label()
    meta = f'<span style="color:#888;font-size:12px;">{art.source}'
    if age:
        meta += f" · {age}"
    meta += "</span>"
    summary_html = f"<p style='color:#aaa;font-size:13px;margin:6px 0 0;line-height:1.5;'>{art.summary}</p>" if art.summary else ""
    return f"""
    <div style="margin-bottom:16px;padding:12px 14px;background:#1e1e2e;border-left:3px solid #4a9eff;border-radius:4px;">
      <div style="font-size:13px;margin-bottom:4px;">{meta}</div>
      <a href="{art.url}" style="color:#e0e0ff;font-weight:600;font-size:15px;text-decoration:none;line-height:1.4;">{idx}. {art.title}</a>
      {summary_html}
    </div>"""

def _category_section(cat, articles):
    icon = CATEGORY_ICONS.get(cat, "📰")
    color = CATEGORY_COLORS.get(cat, "#4a9eff")
    top = articles[:TOP_N]
    arts_html = "".join(_article_html(a, i + 1) for i, a in enumerate(top))
    more = len(articles) - TOP_N
    more_html = f'<p style="color:#888;font-size:12px;margin:4px 0 0;">+ {more} autres articles</p>' if more > 0 else ""
    count_label = f"{len(top)} article" + ("s" if len(top) > 1 else "")
    return f"""
    <div style="margin-bottom:32px;">
      <h2 style="color:{color};font-size:18px;margin:0 0 12px;border-bottom:2px solid {color};padding-bottom:6px;">
        {icon} {cat} <span style="font-size:13px;font-weight:normal;color:#888;">— {count_label} du jour</span>
      </h2>
      {arts_html}
      {more_html}
    </div>"""

def build_html(by_cat):
    today = datetime.now().strftime("%A %d %B %Y").capitalize()
    total = sum(len(v) for v in by_cat.values())
    order = ["Cybersecurite", "Hacks", "IA", "Systemes", "Reseaux", "Developpement", "Gaming"]
    sorted_cats = [c for c in order if c in by_cat] + [c for c in by_cat if c not in order]
    if by_cat:
        sections = "".join(_category_section(cat, by_cat[cat]) for cat in sorted_cats)
    else:
        sections = '<div style="text-align:center;padding:40px;color:#888;"><p>Aucun article trouve au cours des dernieres 24h.</p></div>'
    total_label = f"{total} article" + ("s" if total > 1 else "")
    cat_count = len(by_cat)
    cat_label = f"{cat_count} categorie" + ("s" if cat_count > 1 else "")
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>CyberWatch Digest</title></head>
<body style="margin:0;padding:0;background:#0d0d1a;font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#e0e0ff;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0d0d1a;">
  <tr><td align="center" style="padding:24px 16px;">
    <table width="680" cellpadding="0" cellspacing="0" style="background:#13132a;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.4);">
      <tr><td style="background:linear-gradient(135deg,#1a1a3e 0%,#0d2060 100%);padding:28px 32px;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#ffffff;letter-spacing:1px;">🛡️ CyberWatch</div>
        <div style="font-size:14px;color:#8899cc;margin-top:6px;">Digest quotidien · {today}</div>
        <div style="display:inline-block;background:#1e2d6e;color:#7fa8ff;font-size:13px;padding:4px 12px;border-radius:20px;margin-top:10px;">{total_label} collectes · {cat_label}</div>
      </td></tr>
      <tr><td style="padding:28px 32px;">{sections}</td></tr>
      <tr><td style="background:#0d0d1a;padding:20px 32px;text-align:center;border-top:1px solid #1e1e3e;">
        <p style="color:#555;font-size:12px;margin:0;">CyberWatch — Veille informatique automatisee · <a href="https://github.com/Vinceadr/cyberwatch" style="color:#4a6fa5;text-decoration:none;">GitHub</a></p>
      </td></tr>
    </table>
  </td></tr>
</table></body></html>"""

def send_digest(html, recipient, smtp_user, smtp_pass):
    today = datetime.now().strftime("%d/%m/%Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"CyberWatch — Digest IT du {today}"
    msg["From"] = f"CyberWatch <{smtp_user}>"
    msg["To"] = recipient
    msg.attach(MIMEText(f"CyberWatch digest du {today}\nhttps://github.com/Vinceadr/cyberwatch", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        log.info("Connexion SMTP smtp.gmail.com:587...")
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [recipient], msg.as_bytes())
        log.info("Email envoye a %s", recipient)
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("Erreur d'authentification SMTP. Verifiez SMTP_USER et SMTP_PASSWORD.")
        return False
    except Exception as e:
        log.error("Erreur SMTP : %s", e)
        return False

def main():
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()
    if not smtp_user or not smtp_pass:
        log.error("SMTP_USER et/ou SMTP_PASSWORD manquants.")
        return 1
    recipient = os.getenv("DIGEST_RECIPIENT", smtp_user)
    try:
        config = load_config()
    except FileNotFoundError:
        log.error("config.yaml introuvable : %s", CONFIG_PATH)
        return 1
    by_cat = fetch_all_sources(config)
    html = build_html(by_cat)
    ok = send_digest(html, recipient, smtp_user, smtp_pass)
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
