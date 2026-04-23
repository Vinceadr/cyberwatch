"""MainWindow — Dashboard PySide6 — Bioluminescent Etch Theme."""

from __future__ import annotations

import logging
import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal, Slot
from PySide6.QtGui import QFont, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

import json
import threading
from datetime import datetime as _dt, timedelta as _td, timezone as _tz

from src.gui.flow_layout import FlowContainer
from src.gui.styles import CATEGORY_META, COLORS, FONT_FAMILY, FONT_MONO, GLOBAL_QSS, SEVERITY_SCORE, SIDEBAR_CATEGORIES
from src.gui.widgets import ArticleCard, CategoryButton, DetailPanel
from src.models.database import Database
from src.core.weekly_scheduler import WeeklyScheduler, format_next_purge_label

logger = logging.getLogger(__name__)


def _get_user_dir() -> Path:
    if getattr(sys, "frozen", False):
        import os
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return Path(appdata) / "CyberWatch"
    return Path(__file__).resolve().parent.parent.parent


def _get_asset_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent.parent / "assets"


USER_DIR = _get_user_dir()
ASSET_DIR = _get_asset_dir()


def _hex_to_rgb_str(hex_color: str) -> str:
    """Convert '#RRGGBB' to 'R, G, B' string for rgba() usage."""
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"


# ═══════════════════════════════════════════════════════════════
#  SIDEBAR — Bioluminescent Etch  (w-64 ≈ 260px)
# ═══════════════════════════════════════════════════════════════

class _Sidebar(QFrame):
    EXPANDED_WIDTH = 260
    COLLAPSED_WIDTH = 56

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = True
        self.setFixedWidth(self.EXPANDED_WIDTH)
        self.setStyleSheet(
            f"_Sidebar {{ background: {COLORS['bg_sidebar']}; "
            f"border-right: 1px solid rgba(0, 242, 255, 0.1); }}"
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 24, 16, 16)
        self._layout.setSpacing(3)

        # ── Logo row — icon box + CYBER WATCH ──
        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)

        # Icon in etch-glow bordered box
        logo_box = QFrame()
        logo_box.setFixedSize(56, 56)
        logo_box.setStyleSheet("QFrame { background: transparent; border: none; }")
        logo_box_lay = QHBoxLayout(logo_box)
        logo_box_lay.setContentsMargins(0, 0, 0, 0)

        self._logo = QLabel()
        logo_path = ASSET_DIR / "cyberwatch_logo.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaled(
                56, 56, Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._logo.setPixmap(pixmap)
        else:
            self._logo.setText("CW")
            self._logo.setFont(QFont(FONT_MONO, 14, QFont.Weight.Bold))
        self._logo.setStyleSheet("background: transparent;")
        self._logo.setFixedSize(56, 56)
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_box_lay.addWidget(self._logo)
        logo_row.addWidget(logo_box)

        # "CYBER" normal + "WATCH" cyan — tracking-tighter
        self._logo_text = QLabel()
        self._logo_text.setFont(QFont(FONT_MONO, 11, QFont.Weight.Bold))
        self._logo_text.setTextFormat(Qt.TextFormat.RichText)
        self._logo_text.setText(
            f'<span style="color:{COLORS["text_primary"]};letter-spacing:-1px;">CYBER</span>'
            f'<span style="color:{COLORS["accent"]};letter-spacing:-1px;">WATCH</span>'
        )
        self._logo_text.setStyleSheet("background: transparent;")
        logo_row.addWidget(self._logo_text)
        logo_row.addStretch()

        self._collapse_btn = QPushButton("\u2261")
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        self._collapse_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {COLORS['text_muted']}; }}"
            f"QPushButton:hover {{ color: {COLORS['accent']}; }}"
        )
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        logo_row.addWidget(self._collapse_btn)

        self._layout.addLayout(logo_row)

        # ── Categories section ──
        self._add_section_label("CATEGORIES")

        self._cat_buttons: list[CategoryButton] = []

        # "Toutes" button
        all_btn = CategoryButton("all", "Toutes", COLORS["accent"], 0)
        all_btn.set_active(True)
        self._cat_buttons.append(all_btn)
        self._layout.addWidget(all_btn)

        for key in SIDEBAR_CATEGORIES:
            meta = CATEGORY_META[key]
            btn = CategoryButton(key, meta["label"], meta["color"], 0)
            self._cat_buttons.append(btn)
            self._layout.addWidget(btn)

        # ── Resume navigation ──
        self._add_section_label("RÉSUMÉ")

        self._resume_btn = QPushButton("  ▦  Résumé du jour")
        self._resume_btn.setFixedHeight(42)
        self._resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._resume_btn.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Medium))
        self._resume_btn.setCheckable(True)
        self._resume_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid transparent; "
            f"border-radius: 8px; color: {COLORS['text_secondary']}; text-align: left; "
            f"padding-left: 16px; }}"
            f"QPushButton:hover {{ background: rgba(0, 242, 255, 0.05); "
            f"border-color: {COLORS['border']}; color: {COLORS['text_cyan']}; }}"
            f"QPushButton:checked {{ background: rgba(0, 242, 255, 0.08); "
            f"border: 1px solid rgba(0, 242, 255, 0.18); color: {COLORS['accent']}; }}"
        )
        self._layout.addWidget(self._resume_btn)

        # ── Score filter ──
        self._add_section_label("SCORE MIN.")

        self._score_slider = QSlider(Qt.Orientation.Horizontal)
        self._score_slider.setRange(0, 100)
        self._score_slider.setValue(0)
        self._score_slider.setFixedHeight(20)
        self._layout.addWidget(self._score_slider)

        self._score_value = QLabel("0")
        self._score_value.setFont(QFont(FONT_MONO, 10))
        self._score_value.setStyleSheet(f"color: {COLORS['text_cyan']}; background: transparent;")
        self._score_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._score_value)
        self._score_slider.valueChanged.connect(lambda v: self._score_value.setText(str(v)))

        # ── Statistics ──
        self._add_section_label("STATISTIQUES")

        self._stat_labels: dict[str, QLabel] = {}
        for stat_key, stat_label in [("total", "Total"), ("unread", "Non lus"), ("critical", "Critiques"), ("today", "Aujourd'hui")]:
            lbl = QLabel(f"{stat_label} : 0")
            lbl.setFont(QFont(FONT_MONO, 9))
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
            self._stat_labels[stat_key] = lbl
            self._layout.addWidget(lbl)

        # ── Operator card — pushed to bottom ──
        self._layout.addStretch()

        self._op_card = QFrame()
        self._op_card.setFixedHeight(60)
        self._op_card.setStyleSheet(
            f"QFrame {{ background: rgba(0, 242, 255, 0.03); "
            f"border: 1px solid rgba(0, 242, 255, 0.1); border-radius: 12px; }}"
        )
        op_lay = QHBoxLayout(self._op_card)
        op_lay.setContentsMargins(12, 8, 12, 8)
        op_lay.setSpacing(10)

        avatar = QLabel("\u2b21")
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont(FONT_MONO, 16))
        avatar.setStyleSheet(
            f"color: {COLORS['accent']}; background: rgba(0, 242, 255, 0.08); "
            f"border: 1px solid rgba(0, 242, 255, 0.2); border-radius: 18px;"
        )
        op_lay.addWidget(avatar)

        op_info = QVBoxLayout()
        op_info.setSpacing(1)
        op_name = QLabel("OPERATOR")
        op_name.setFont(QFont(FONT_MONO, 9, QFont.Weight.Bold))
        op_name.setStyleSheet(f"color: {COLORS['text_primary']}; background: transparent;")
        op_id = QLabel("CW-2026-PX")
        op_id.setFont(QFont(FONT_MONO, 7))
        op_id.setStyleSheet(f"color: rgba(0, 242, 255, 0.4); background: transparent;")
        op_info.addWidget(op_name)
        op_info.addWidget(op_id)
        op_lay.addLayout(op_info)
        op_lay.addStretch()

        self._layout.addWidget(self._op_card)

    # ── Section label helper — etch style ──
    def _add_section_label(self, text: str) -> None:
        spacer = QSpacerItem(0, 14, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._layout.addItem(spacer)
        lbl = QLabel(text)
        lbl.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color: rgba(0, 242, 255, 0.35); letter-spacing: 4px; background: transparent;"
        )
        self._layout.addWidget(lbl)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        self._layout.addWidget(sep)

    # ── Collapse / Expand ──
    def _toggle_collapse(self) -> None:
        self._expanded = not self._expanded
        w = self.EXPANDED_WIDTH if self._expanded else self.COLLAPSED_WIDTH
        self.setFixedWidth(w)
        for btn in self._cat_buttons:
            btn.setVisible(self._expanded)
        self._resume_btn.setVisible(self._expanded)
        self._score_slider.setVisible(self._expanded)
        self._score_value.setVisible(self._expanded)
        for lbl in self._stat_labels.values():
            lbl.setVisible(self._expanded)
        self._logo_text.setVisible(self._expanded)
        self._op_card.setVisible(self._expanded)

    # ── Public API ──
    def update_stats(self, stats: dict) -> None:
        mapping = {"total": "Total", "unread": "Non lus", "critical": "Critiques", "today": "Aujourd'hui"}
        for key, label_text in mapping.items():
            if key in self._stat_labels:
                self._stat_labels[key].setText(f"{label_text} : {stats.get(key, 0)}")

    def update_category_counts(self, counts: dict[str, int]) -> None:
        for btn in self._cat_buttons:
            if btn.key == "all":
                btn.set_count(sum(v for k, v in counts.items() if k != "favoris"))
            else:
                btn.set_count(counts.get(btn.key, 0))

    @property
    def category_buttons(self) -> list[CategoryButton]:
        return self._cat_buttons

    @property
    def score_slider(self) -> QSlider:
        return self._score_slider

    @property
    def resume_button(self) -> QPushButton:
        return self._resume_btn


# ═══════════════════════════════════════════════════════════════
#  HEADER — Bioluminescent Etch  (h-20 ≈ 72px)
# ═══════════════════════════════════════════════════════════════

class _Header(QFrame):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setStyleSheet(
            f"_Header {{ background: {COLORS['bg_header']}; "
            f"border-bottom: 1px solid {COLORS['border']}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(16)

        # Search bar — rounded pill style (w-96 ≈ 380px)
        self._search = QLineEdit()
        self._search.setPlaceholderText("QUERY SYSTEM DATABASE...")
        self._search.setFixedWidth(380)
        self._search.setFixedHeight(38)
        layout.addWidget(self._search)

        # System link indicator — pulse-dot frame
        dot_frame = QFrame()
        dot_frame.setFixedSize(160, 28)
        dot_frame.setStyleSheet(
            f"background: rgba(0, 242, 255, 0.04); "
            f"border: 1px solid rgba(0, 242, 255, 0.15); border-radius: 4px;"
        )
        dot_lay = QHBoxLayout(dot_frame)
        dot_lay.setContentsMargins(8, 0, 8, 0)
        dot_lay.setSpacing(6)
        dot = QLabel("\u25cf")
        dot.setFont(QFont(FONT_FAMILY, 5))
        dot.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        dot_lay.addWidget(dot)
        sys_lbl = QLabel("SYSTEM LINK ACTIVE")
        sys_lbl.setFont(QFont(FONT_MONO, 7, QFont.Weight.Bold))
        sys_lbl.setStyleSheet(f"color: {COLORS['text_cyan']}; background: transparent; letter-spacing: 1px;")
        dot_lay.addWidget(sys_lbl)
        layout.addWidget(dot_frame)

        layout.addStretch()

        # Date filter
        lbl_date = QLabel("PERIODE")
        lbl_date.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        lbl_date.setStyleSheet(f"color: {COLORS['text_muted']}; letter-spacing: 3px; background: transparent;")
        layout.addWidget(lbl_date)

        self._date_filter = QComboBox()
        self._date_filter.addItems(["Tout", "Aujourd'hui", "7 jours", "30 jours"])
        self._date_filter.setFixedHeight(34)
        layout.addWidget(self._date_filter)

        # Sort order
        lbl_sort = QLabel("TRI")
        lbl_sort.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        lbl_sort.setStyleSheet(f"color: {COLORS['text_muted']}; letter-spacing: 3px; background: transparent;")
        layout.addWidget(lbl_sort)

        self._sort_order = QComboBox()
        self._sort_order.addItems(["Plus recent", "Plus ancien"])
        self._sort_order.setFixedHeight(34)
        layout.addWidget(self._sort_order)

        # Refresh button — cyan CTA
        self._refresh_btn = QPushButton("REFRESH")
        self._refresh_btn.setFixedHeight(38)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setFont(QFont(FONT_MONO, 9, QFont.Weight.Bold))
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ background: {COLORS['accent']}; color: #020408; border: none; "
            f"border-radius: 12px; font-weight: 700; padding: 0 24px; letter-spacing: 2px; }}"
            f"QPushButton:hover {{ background: #33F5FF; }}"
        )
        layout.addWidget(self._refresh_btn)

    @property
    def search_input(self) -> QLineEdit:
        return self._search

    @property
    def date_filter(self) -> QComboBox:
        return self._date_filter

    @property
    def refresh_button(self) -> QPushButton:
        return self._refresh_btn

    @property
    def sort_order(self) -> QComboBox:
        return self._sort_order


# ═══════════════════════════════════════════════════════════════
#  RESUME VIEW — Daily digest panel
# ═══════════════════════════════════════════════════════════════

_CAT_NOM_TO_KEY_GUI: dict = {
    "Cybersecurite": "cyber", "Systemes": "systemes", "Reseaux": "reseaux",
    "Developpement": "dev",   "IA": "ia",             "Gaming": "gaming",
    "Hacks": "hacks",
}


class _ResumeView(QScrollArea):
    generate_requested = Signal(str, bool)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(
            f"QScrollArea {{ background: {COLORS['bg_main']}; border: none; }}"
        )
        self._build_ui()

    def _build_ui(self):
        container = QWidget()
        container.setStyleSheet(f"background: {COLORS['bg_main']};")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(28, 28, 28, 40)
        vbox.setSpacing(16)
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(container)
        self._vbox = vbox

        # Title row
        title_row = QHBoxLayout()
        self._title_lbl = QLabel("Resume du jour")
        self._title_lbl.setFont(QFont(FONT_FAMILY, 20, QFont.Weight.Light))
        self._title_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; background: transparent;"
        )
        title_row.addWidget(self._title_lbl)
        title_row.addStretch()

        day_lbl = QLabel("Semaine :")
        day_lbl.setFont(QFont(FONT_MONO, 8))
        day_lbl.setStyleSheet(
            f"color: {COLORS['text_muted']}; background: transparent;"
        )
        title_row.addWidget(day_lbl)

        self._day_combo = QComboBox()
        self._day_combo.setFixedHeight(32)
        self._day_combo.setMinimumWidth(165)
        title_row.addWidget(self._day_combo)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["Resume du matin", "Resume du soir"])
        self._type_combo.setFixedHeight(32)
        self._type_combo.setMinimumWidth(165)
        title_row.addWidget(self._type_combo)

        self._gen_btn = QPushButton("\u27f3  Generer maintenant")
        self._gen_btn.setFixedHeight(36)
        self._gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gen_btn.setFont(QFont(FONT_MONO, 9, QFont.Weight.Bold))
        self._gen_btn.setStyleSheet(
            f"QPushButton {{ background: {COLORS['accent']}; color: #020408; border: none; "
            f"border-radius: 10px; font-weight: 700; padding: 0 20px; letter-spacing: 1px; }}"
            f"QPushButton:hover {{ background: #33F5FF; }}"
        )
        title_row.addWidget(self._gen_btn)
        vbox.addLayout(title_row)

        # Status label
        self._status_lbl = QLabel("")
        self._status_lbl.setFont(QFont(FONT_MONO, 9))
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(
            f"color: {COLORS['text_muted']}; background: transparent;"
        )
        self._status_lbl.setVisible(False)
        vbox.addWidget(self._status_lbl)

        # Content area
        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        vbox.addWidget(self._content_widget)

        self._gen_btn.clicked.connect(self._on_generate_clicked)
        self._day_combo.currentIndexChanged.connect(self._on_day_changed)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)

    # -- Public API -------------------------------------------

    def refresh(self):
        from datetime import datetime as _ddt, timedelta as _ttd, timezone as _ttz
        today = _ddt.now(tz=_ttz.utc)
        self._day_combo.blockSignals(True)
        self._day_combo.clear()
        for i in range(7):
            d = today - _ttd(days=i)
            label = ("Aujourd'hui " + d.strftime("%d/%m")) if i == 0 else d.strftime("%A %d/%m")
            self._day_combo.addItem(label.capitalize(), d.strftime("%Y-%m-%d"))
        self._day_combo.blockSignals(False)
        self._load_current()

    def set_status(self, msg: str, is_error: bool = False):
        if msg:
            color = COLORS["score_low"] if is_error else COLORS["text_cyan"]
            self._status_lbl.setStyleSheet(
                f"color: {color}; background: transparent; padding: 8px; "
                f"border: 1px solid {COLORS['border']}; border-radius: 6px;"
            )
            self._status_lbl.setText(msg)
            self._status_lbl.setVisible(True)
        else:
            self._status_lbl.setVisible(False)

    def set_generating(self, active: bool):
        self._gen_btn.setEnabled(not active)
        self._gen_btn.setText(
            "\u23f3  Generation en cours..." if active else "\u27f3  Generer maintenant"
        )

    def reload_content(self):
        self._load_current()

    # -- Internal -----------------------------------------------

    def _current_date_str(self) -> str:
        from datetime import datetime as _ddt, timezone as _ttz
        return self._day_combo.currentData() or _ddt.now(tz=_ttz.utc).strftime("%Y-%m-%d")

    def _current_type(self) -> str:
        return "morning" if self._type_combo.currentIndex() == 0 else "evening"

    def _load_current(self):
        date = self._current_date_str()
        stype = self._current_type()

        # Update title
        type_label = "matin" if stype == "morning" else "soir"
        try:
            from datetime import datetime as _ddt
            dt_obj = _ddt.strptime(date, "%Y-%m-%d")
            date_str = dt_obj.strftime("%d/%m/%Y")
        except Exception:
            date_str = date
        self._title_lbl.setText(
            f'<span style="font-weight:300;">Resume du </span>'
            f'<span style="font-weight:700;font-style:italic;color:{COLORS["accent"]};">'
            f'{type_label}</span>'
            f'<span style="font-weight:300;color:{COLORS["text_secondary"]};"> \u2014 {date_str}</span>'
        )
        self._title_lbl.setTextFormat(Qt.TextFormat.RichText)

        # Clear content
        self._clear_content()

        row = self._db.get_summary(date, stype)
        if not row:
            self._show_empty()
            return

        try:
            content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"]
        except Exception:
            self._show_empty("Erreur de lecture du resume.")
            return

        if stype == "morning":
            self._render_morning(content)
        else:
            self._render_evening(content)

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_empty(self, msg: str = ""):
        if not msg:
            msg = (
                "Aucun resume disponible pour cette date.\n"
                "Cliquez sur \u00ab Generer maintenant \u00bb pour en creer un."
            )
        lbl = QLabel(msg)
        lbl.setFont(QFont(FONT_FAMILY, 11))
        lbl.setStyleSheet(
            f"color: {COLORS['text_muted']}; padding: 40px 0;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        self._content_layout.addWidget(lbl)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color: rgba(0, 242, 255, 0.45); letter-spacing: 3px; background: transparent;"
        )
        return lbl

    def _separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        return sep


    # ── Breakdown par categorie ────────────────────────────────

    _CAT_DESC: dict = {
        "cyber":    "Vulnerabilites, malwares, ransomwares, CERT et alertes de securite.",
        "systemes": "OS, serveurs, mises a jour systeme et infrastructure.",
        "reseaux":  "Protocoles, firewalls, VPN, DDoS et securite reseau.",
        "dev":      "Developpement logiciel, DevSecOps, frameworks et outils.",
        "ia":       "Intelligence artificielle, LLM, machine learning et ethique IA.",
        "gaming":   "Securite gaming, exploits, mods et actualites jeux video.",
        "hacks":    "Nouvelles techniques d'attaque, exploits zero-day, CTF et red team.",
    }

    def _render_category_breakdown(self) -> None:
        """Affiche un bloc par categorie avec nb d articles + top 3 titres."""
        from datetime import datetime, timedelta, timezone
        from collections import defaultdict
        from src.gui.styles import SIDEBAR_CATEGORIES
        today = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
        try:
            all_arts = self._db.get_articles(limit=2000, date_since=today)
        except Exception:
            return
        if not all_arts:
            return
        by_cat: dict = defaultdict(list)
        for art in all_arts:
            cat = art.get("categorie") or art.get("category") or "unknown"
            by_cat[cat].append(art)
        active = [(k, by_cat[k]) for k in SIDEBAR_CATEGORIES if k in by_cat and k != "favoris"]
        if not active:
            return
        self._content_layout.addWidget(self._section_label("PAR CATEGORIE — AUJOURD’HUI"))
        self._content_layout.addWidget(self._separator())
        for cat_key, arts in active:
            self._content_layout.addWidget(self._make_category_block(cat_key, arts))

    def _make_category_block(self, cat_key: str, arts: list) -> "QFrame":
        from src.gui.styles import CATEGORY_META
        meta = CATEGORY_META.get(cat_key, CATEGORY_META["unknown"])
        color = meta["color"]
        label = meta["label"]
        desc = self._CAT_DESC.get(cat_key, "")

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: rgba(10,14,20,0.6); "
            f"border-left: 3px solid {color}; border-radius: 8px; margin-bottom: 4px; }}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(5)

        header = QHBoxLayout()
        cat_lbl = QLabel(label.upper())
        cat_lbl.setFont(QFont(FONT_MONO, 9, QFont.Weight.Bold))
        cat_lbl.setStyleSheet(f"color: {color}; letter-spacing: 2px; background: transparent;")
        header.addWidget(cat_lbl)
        header.addStretch()
        count_lbl = QLabel(f"{len(arts)} article{'s' if len(arts)>1 else ''}")
        count_lbl.setFont(QFont(FONT_MONO, 8))
        count_lbl.setStyleSheet("color: rgba(255,255,255,0.35); background: transparent;")
        header.addWidget(count_lbl)
        lay.addLayout(header)

        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setFont(QFont(FONT_FAMILY, 9))
            desc_lbl.setStyleSheet("color: rgba(255,255,255,0.30); background: transparent;")
            desc_lbl.setWordWrap(True)
            lay.addWidget(desc_lbl)

        for art in arts[:3]:
            title = art.get("titre_fr") or art.get("titre") or art.get("title", "")
            if not title:
                continue
            t = title[:95] + ("…" if len(title) > 95 else "")
            art_lbl = QLabel(f"• {t}")
            art_lbl.setFont(QFont(FONT_FAMILY, 9))
            art_lbl.setStyleSheet("color: rgba(255,255,255,0.55); background: transparent;")
            art_lbl.setWordWrap(True)
            lay.addWidget(art_lbl)

        if len(arts) > 3:
            more = QLabel(f"+ {len(arts)-3} autre{'s' if len(arts)-3>1 else ''}…")
            more.setFont(QFont(FONT_MONO, 8))
            more.setStyleSheet("color: rgba(255,255,255,0.20); background: transparent;")
            lay.addWidget(more)

        return frame

    def _render_morning(self, content: dict):
        articles = content.get("articles", [])
        if not articles:
            self._show_empty("Aucun article dans ce resume.")
            return
        self._content_layout.addWidget(self._section_label("ARTICLES SELECTIONNES"))
        self._content_layout.addWidget(self._separator())
        for art in articles:
            self._content_layout.addWidget(self._make_summary_card(art))
        self._render_category_breakdown()

    def _render_evening(self, content: dict):
        highlights = content.get("highlights", [])
        if highlights:
            self._content_layout.addWidget(self._section_label("\u2605  HIGHLIGHTS DU JOUR"))
            self._content_layout.addWidget(self._separator())
            for art in highlights:
                self._content_layout.addWidget(self._make_summary_card(art, highlight=True))

        trend = content.get("category_trend", {})
        if trend and trend.get("count", 0) > 0:
            self._content_layout.addWidget(self._make_trend_block(trend))

        morning = content.get("morning_articles", [])
        if morning:
            self._content_layout.addWidget(self._section_label("ARTICLES DU MATIN"))
            self._content_layout.addWidget(self._separator())
            for art in morning:
                self._content_layout.addWidget(self._make_summary_card(art))

        afternoon = content.get("afternoon_articles", [])
        if afternoon:
            self._content_layout.addWidget(self._section_label("ARTICLES DE L\u2019APRES-MIDI"))
            self._content_layout.addWidget(self._separator())
            for art in afternoon:
                self._content_layout.addWidget(self._make_summary_card(art))

        self._render_category_breakdown()
        if not highlights and not morning and not afternoon:
            self._show_empty()

    def _make_trend_block(self, trend: dict) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: rgba(0, 242, 255, 0.03); "
            f"border: 1px solid rgba(0, 242, 255, 0.12); border-radius: 12px; }}"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(16)

        icon_lbl = QLabel("\ud83d\udcca")
        icon_lbl.setFont(QFont(FONT_FAMILY, 18))
        icon_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(icon_lbl)

        text_col = QVBoxLayout()
        trend_title = QLabel("TENDANCE DU JOUR")
        trend_title.setFont(QFont(FONT_MONO, 8, QFont.Weight.Bold))
        trend_title.setStyleSheet(
            f"color: rgba(0, 242, 255, 0.45); letter-spacing: 3px; background: transparent;"
        )
        from src.gui.styles import CATEGORY_META as _CM
        cat_key = trend.get("category_key", "unknown")
        cat_color = _CM.get(cat_key, _CM["unknown"])["color"]
        cat_label = _CM.get(cat_key, _CM["unknown"])["label"]
        trend_val = QLabel(
            f'<span style="color:{cat_color}; font-weight:700;">{cat_label}</span>'
            f'<span style="color:{COLORS["text_secondary"]};"> \u00b7 {trend["count"]} articles</span>'
        )
        trend_val.setFont(QFont(FONT_FAMILY, 13))
        trend_val.setTextFormat(Qt.TextFormat.RichText)
        trend_val.setStyleSheet("background: transparent;")
        text_col.addWidget(trend_title)
        text_col.addWidget(trend_val)
        lay.addLayout(text_col)
        lay.addStretch()
        return frame

    def _make_summary_card(self, art: dict, highlight: bool = False) -> QFrame:
        frame = QFrame()
        border_color = "rgba(0, 242, 255, 0.25)" if highlight else COLORS["border"]
        bg_color = "rgba(0, 242, 255, 0.025)" if highlight else COLORS["bg_card"]
        frame.setStyleSheet(
            f"QFrame {{ background: {bg_color}; "
            f"border: 1px solid {border_color}; border-radius: 12px; }}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(8)

        # Top row: category badge + score
        top = QHBoxLayout()
        top.setSpacing(8)
        from src.gui.widgets import CategoryBadge, ScoreBadge
        cat_key = art.get("category_key", "unknown")
        top.addWidget(CategoryBadge(cat_key))
        if highlight:
            star_lbl = QLabel("\u2605")
            star_lbl.setFont(QFont(FONT_FAMILY, 14))
            star_lbl.setStyleSheet(
                f"color: {COLORS['favoris']}; background: transparent;"
            )
            top.addWidget(star_lbl)
        top.addStretch()
        score = art.get("score", 0) or 0
        top.addWidget(ScoreBadge(score, 28))
        lay.addLayout(top)

        # Title
        title_txt = art.get("title", "") or ""
        title_lbl = QLabel(title_txt[:200] + ("..." if len(title_txt) > 200 else ""))
        title_lbl.setWordWrap(True)
        title_lbl.setFont(QFont(FONT_FAMILY, 12, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; background: transparent;"
        )
        lay.addWidget(title_lbl)

        # 2-sentence summary
        summ = art.get("summary_2sentences", "") or ""
        if summ:
            summ_lbl = QLabel(summ)
            summ_lbl.setWordWrap(True)
            summ_lbl.setFont(QFont(FONT_FAMILY, 10))
            summ_lbl.setStyleSheet(
                f"color: {COLORS['text_secondary']}; background: transparent;"
            )
            lay.addWidget(summ_lbl)

        # URL link
        url = art.get("url", "") or ""
        if url:
            link_btn = QPushButton("\u2197 Ouvrir l\u2019article")
            link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            link_btn.setFont(QFont(FONT_MONO, 8))
            link_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; "
                f"color: {COLORS['text_cyan']}; text-align: left; padding: 0; }}"
                f"QPushButton:hover {{ color: {COLORS['accent']}; }}"
            )
            link_btn.clicked.connect(lambda _checked=False, u=url: webbrowser.open(u))
            lay.addWidget(link_btn)

        return frame

    # -- Slots --------------------------------------------------

    def _on_generate_clicked(self):
        stype = self._current_type()
        self.generate_requested.emit(stype, True)

    def _on_day_changed(self, _idx: int):
        self._load_current()

    def _on_type_changed(self, _idx: int):
        self._load_current()



# ═══════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config
        gui_config = config.get("gui", {})

        self.setWindowTitle(f"{config['app']['name']} v{config['app']['version']}")
        self.resize(
            gui_config.get("window_width", 1200),
            gui_config.get("window_height", 800),
        )

        icon_path = ASSET_DIR / "cyberwatch.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setStyleSheet(GLOBAL_QSS)

        db_path = USER_DIR / config.get("database", {}).get("path", "data/db/cyberwatch.db")
        self._db = Database(db_path)

        self._articles: list[dict] = []
        self._cards: list[ArticleCard] = []
        self._active_category: str = "all"
        self._search_text: str = ""
        self._min_score: int = 0
        self._sort_desc: bool = True

        # Track collapsed category groups
        self._collapsed_categories: set[str] = set()

        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._setup_refresh_timer(gui_config.get("refresh_interval_seconds", 300))
        self._load_data()

        # ── Weekly purge scheduler ──────────────────────────────────────────
        retention_days = config.get("retention", {}).get("days", 7)
        self._weekly_scheduler = WeeklyScheduler(self._db, retention_days=retention_days)
        self._weekly_scheduler.start()

        # Show next purge date in status bar
        self._status_label.setText(
            f"▸ {len(self._articles)} ARTICLES  │  {format_next_purge_label()}"
        )

        # ── Daily summary generator ─────────────────────────────────────────
        from src.core.summary_generator import SummaryGenerator
        self._summary_gen = SummaryGenerator(config, self._db)
        self._setup_summary_timers()
        QTimer.singleShot(3000, self._check_startup_summary)

        # ── Auto-collect RSS (every 2h) ─────────────────────────────────────
        fetch_interval_min = config.get('scheduler', {}).get('fetch_interval_minutes', 30)
        self._collect_timer = QTimer(self)
        self._collect_timer.timeout.connect(self._on_auto_collect)
        self._collect_timer.start(fetch_interval_min * 60 * 1000)
        QTimer.singleShot(10000, self._on_auto_collect)

        logger.info("GUI initialisee")

    # ── Layout ──

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = _Header()
        root.addWidget(self._header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = _Sidebar()
        body.addWidget(self._sidebar)

        # Scroll area for article grid
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"QScrollArea {{ background: {COLORS['bg_main']}; border: none; }}")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet(f"background: {COLORS['bg_main']};")
        self._grid_layout = QVBoxLayout(self._grid_container)
        self._grid_layout.setContentsMargins(28, 28, 28, 28)
        self._grid_layout.setSpacing(4)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._grid_container)

        # Smooth scroll: finer step + kinetic grabber when available
        self._scroll.verticalScrollBar().setSingleStep(20)
        try:
            from PySide6.QtWidgets import QScroller
            QScroller.grabGesture(
                self._scroll.viewport(),
                QScroller.ScrollerGestureType.LeftMouseButtonGesture,
            )
        except Exception:
            pass

        body.addWidget(self._scroll, stretch=1)

        # Resume view (initially hidden)
        self._resume_view = _ResumeView(self._db)
        self._resume_view.setVisible(False)
        body.addWidget(self._resume_view, stretch=1)

        self._detail_panel = DetailPanel()
        body.addWidget(self._detail_panel)

        root.addLayout(body, stretch=1)

        # Status bar — etch style (frame: label + purge button)
        status_frame = QFrame()
        status_frame.setFixedHeight(32)
        status_frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg_header']}; "
            f"border-top: 1px solid {COLORS['border']}; }}"
        )
        status_lay = QHBoxLayout(status_frame)
        status_lay.setContentsMargins(16, 0, 12, 0)
        status_lay.setSpacing(12)

        self._status_label = QLabel("SYSTEM READY")
        self._status_label.setFont(QFont(FONT_MONO, 8))
        self._status_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; background: transparent; letter-spacing: 1px;"
        )
        status_lay.addWidget(self._status_label, stretch=1)

        self._purge_btn = QPushButton("⚡ PURGER MAINTENANT")
        self._purge_btn.setFixedHeight(22)
        self._purge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._purge_btn.setFont(QFont(FONT_MONO, 7, QFont.Weight.Bold))
        self._purge_btn.setStyleSheet(
            "QPushButton { background: rgba(248,81,73,0.12); color: #F85149; "
            "border: 1px solid rgba(248,81,73,0.3); border-radius: 4px; "
            "padding: 0 10px; letter-spacing: 1px; }"
            "QPushButton:hover { background: rgba(248,81,73,0.28); "
            "border-color: rgba(248,81,73,0.65); }"
        )
        self._purge_btn.clicked.connect(self._on_purge_now)
        status_lay.addWidget(self._purge_btn)

        root.addWidget(status_frame)

    # ── Signals ──

    def _connect_signals(self) -> None:
        self._header.search_input.textChanged.connect(self._on_search_changed)
        self._header.date_filter.currentIndexChanged.connect(lambda _: self._apply_filters())
        self._header.sort_order.currentIndexChanged.connect(self._on_sort_changed)
        self._header.refresh_button.clicked.connect(self._on_refresh)

        for btn in self._sidebar.category_buttons:
            btn.filter_clicked.connect(self._on_category_filter)

        self._sidebar.score_slider.valueChanged.connect(self._on_score_filter)

        self._detail_panel.close_requested.connect(self._close_detail)
        self._detail_panel.mark_read_requested.connect(self._on_mark_read)
        self._detail_panel.toggle_star_requested.connect(self._on_toggle_star)

        # Resume view signals
        self._sidebar.resume_button.clicked.connect(self._on_resume_nav)
        self._resume_view.generate_requested.connect(self._on_summary_generate)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self._close_detail)
        QShortcut(QKeySequence(Qt.Key.Key_F5), self).activated.connect(self._on_refresh)

    def _setup_refresh_timer(self, interval_sec: int) -> None:
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_refresh)
        self._timer.start(interval_sec * 1000)

    # ── Data loading ──

    def _load_data(self) -> None:
        from datetime import datetime, timedelta, timezone
        order = "DESC" if self._sort_desc else "ASC"
        # Show only articles from this week (since last Sunday 00:00)
        now = datetime.now(tz=timezone.utc)
        days_since_sunday = (now.weekday() + 1) % 7  # Mon=0 … Sun=6
        week_start = (now - timedelta(days=days_since_sunday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        date_since = week_start.isoformat()
        try:
            self._articles = self._db.get_articles(limit=2000, order=order, date_since=date_since)
        except Exception:
            logger.exception("Erreur chargement articles")
            self._articles = []

        self._rebuild_grid()
        self._update_sidebar()
        week_label = week_start.strftime("%d/%m")
        self._status_label.setText(
            f"\u25b8 {len(self._articles)} ARTICLES (semaine du {week_label})  \u2502  {format_next_purge_label()}"
        )

    # ── Grid rebuild ──

    def _rebuild_grid(self) -> None:
        self._cards.clear()

        # Clear existing grid widgets
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        visible = self._filtered_articles()

        # Dashboard title row
        title_row = QWidget()
        title_row.setStyleSheet("background: transparent;")
        title_lay = QVBoxLayout(title_row)
        title_lay.setContentsMargins(4, 0, 0, 20)
        title_lay.setSpacing(4)

        main_title = QLabel()
        main_title.setFont(QFont(FONT_FAMILY, 22, QFont.Weight.Light))
        main_title.setStyleSheet(f"color: {COLORS['text_primary']}; background: transparent;")
        cat_label = self._active_category
        if cat_label == "all":
            main_title.setText(
                f'<span style="font-weight:300;">Cyber</span> '
                f'<span style="font-weight:700;font-style:italic;color:{COLORS["accent"]};">Watch</span>'
            )
        elif cat_label == "favoris":
            main_title.setText(
                f'<span style="font-weight:300;">Mes</span> '
                f'<span style="font-weight:700;font-style:italic;color:{COLORS["favoris"]};">Favoris</span>'
            )
        else:
            meta = CATEGORY_META.get(cat_label, CATEGORY_META.get("unknown", {"label": cat_label, "color": COLORS["accent"]}))
            main_title.setText(
                f'<span style="font-weight:300;">{meta["label"]}</span> '
                f'<span style="font-weight:700;font-style:italic;color:{meta["color"]};">Feed</span>'
            )
        main_title.setTextFormat(Qt.TextFormat.RichText)
        title_lay.addWidget(main_title)

        sub_title = QLabel(f"{len(visible)} articles \u2022 Real-time tech intelligence monitoring")
        sub_title.setFont(QFont(FONT_FAMILY, 10))
        sub_title.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent; letter-spacing: 1px;")
        title_lay.addWidget(sub_title)

        self._grid_layout.addWidget(title_row)

        if not visible:
            empty = QLabel("Aucun article pour cette selection")
            empty.setFont(QFont(FONT_FAMILY, 13))
            empty.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid_layout.addWidget(empty)
            self._grid_layout.addStretch()
            return

        # ── Group articles by CATEGORY (ordered) ──
        _CAT_ORDER = ["cyber", "systemes", "reseaux", "dev", "ia", "gaming", "hacks", "unknown"]
        groups: dict[str, list[dict]] = {}
        for article in visible:
            cat = article.get("category", "unknown") or "unknown"
            groups.setdefault(cat, []).append(article)

        sorted_cats = sorted(
            groups.keys(),
            key=lambda k: _CAT_ORDER.index(k) if k in _CAT_ORDER else 999,
        )

        for cat_key in sorted_cats:
            # Sort within category: score DESC, then date DESC
            articles = sorted(
                groups[cat_key],
                key=lambda a: (
                    a.get("score", 0) or 0,
                    a.get("published", "") or "",
                ),
                reverse=True,
            )

            n = len(articles)
            unread = sum(1 for a in articles if not a.get("read"))
            meta = CATEGORY_META.get(cat_key, CATEGORY_META["unknown"])
            cat_color = meta["color"]
            cat_label_text = meta["label"]
            cat_icon = meta["icon"]
            is_collapsed = cat_key in self._collapsed_categories
            arrow = "\u25b8" if is_collapsed else "\u25be"
            hex_rgb = _hex_to_rgb_str(cat_color)

            # ── Category header row: collapsible button + reading progress badge ──
            header_widget = QWidget()
            header_widget.setStyleSheet("background: transparent;")
            header_hlay = QHBoxLayout(header_widget)
            header_hlay.setContentsMargins(0, 4, 0, 4)
            header_hlay.setSpacing(8)

            header_btn = QPushButton(
                f"  {arrow}  {cat_icon}  {cat_label_text.upper()}"
                f"  \u2500\u2500  {n} article{'s' if n > 1 else ''}"
            )
            header_btn.setFixedHeight(40)
            header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            header_btn.setFont(QFont(FONT_MONO, 10, QFont.Weight.Bold))
            header_btn.setStyleSheet(
                f"QPushButton {{ color: {cat_color}; "
                f"background: rgba({hex_rgb}, 0.06); "
                f"border: 1px solid rgba({hex_rgb}, 0.20); "
                f"border-radius: 8px; text-align: left; "
                f"padding-left: 12px; letter-spacing: 2px; }}"
                f"QPushButton:hover {{ background: rgba({hex_rgb}, 0.12); "
                f"border-color: rgba({hex_rgb}, 0.35); }}"
            )
            header_hlay.addWidget(header_btn, stretch=1)

            # Reading progress badge — "X non lu / total"
            unread_text = f"  {unread} non lu{'s' if unread > 1 else ''} / {n}  "
            progress_lbl = QLabel(unread_text)
            progress_lbl.setFont(QFont(FONT_MONO, 9))
            if unread > 0:
                progress_lbl.setStyleSheet(
                    f"color: {COLORS['accent']}; "
                    f"background: rgba(0, 242, 255, 0.08); "
                    f"border: 1px solid rgba(0, 242, 255, 0.22); "
                    f"border-radius: 6px; padding: 2px 6px;"
                )
            else:
                progress_lbl.setStyleSheet(
                    f"color: {COLORS['text_muted']}; "
                    f"background: rgba(255, 255, 255, 0.03); "
                    f"border: 1px solid rgba(255, 255, 255, 0.06); "
                    f"border-radius: 6px; padding: 2px 6px;"
                )
            header_hlay.addWidget(progress_lbl)

            self._grid_layout.addWidget(header_widget)

            container = FlowContainer(h_spacing=12, v_spacing=14)
            container.setStyleSheet("background: transparent;")
            container.flow_layout.setContentsMargins(0, 6, 0, 16)
            for article in articles:
                card = ArticleCard(article)
                card.clicked.connect(self._on_card_clicked)
                card.double_clicked.connect(self._on_card_double_clicked)
                container.flow_layout.addWidget(card)
                self._cards.append(card)

            if is_collapsed:
                container.setVisible(False)

            self._grid_layout.addWidget(container)

            header_btn.clicked.connect(
                lambda checked=False, c=container, h=header_btn, ck=cat_key,
                       cnt=n, ci=cat_icon, cl=cat_label_text, cc=cat_color:
                    self._toggle_category_group(c, h, ck, cnt, ci, cl, cc)
            )

        self._grid_layout.addStretch()
        self._grid_container.updateGeometry()
    def _toggle_category_group(
        self,
        container: QWidget,
        header: QPushButton,
        cat_key: str,
        count: int,
        cat_icon: str,
        cat_label_text: str,
        cat_color: str,
    ) -> None:
        is_visible = container.isVisible()
        container.setVisible(not is_visible)

        if is_visible:
            self._collapsed_categories.add(cat_key)
        else:
            self._collapsed_categories.discard(cat_key)

        arrow = "\u25b8" if is_visible else "\u25be"
        suffix = "s" if count > 1 else ""
        header.setText(
            f"  {arrow}  {cat_icon}  {cat_label_text.upper()}"
            f"  \u2500\u2500  {count} article{suffix}"
        )

        # Force layout recalculation
        container.updateGeometry()
        self._grid_layout.invalidate()
        self._grid_layout.activate()
        self._grid_container.adjustSize()
        QApplication.processEvents()

    # ── Filtering ──

    def _filtered_articles(self) -> list[dict]:
        from datetime import datetime, timedelta, timezone
        from src.gui.styles import SEVERITY_SCORE
        result = self._articles

        if self._active_category == "favoris":
            result = [a for a in result if a.get("favori") or a.get("starred")]
        elif self._active_category != "all":
            result = [a for a in result if a.get("category", "unknown") == self._active_category]

        if self._search_text:
            q = self._search_text.lower()
            result = [
                a for a in result
                if q in (a.get("title") or "").lower()
                or q in (a.get("summary") or "").lower()
                or q in (a.get("source_name") or "").lower()
            ]

        if self._min_score > 0:
            result = [
                a for a in result
                if SEVERITY_SCORE.get(a.get("severity", "INFO"), 10) >= self._min_score
            ]

        date_idx = self._header.date_filter.currentIndex()
        if date_idx > 0:
            now = datetime.now(tz=timezone.utc)
            days = {1: 1, 2: 7, 3: 30}.get(date_idx, 9999)
            cutoff = (now - timedelta(days=days)).isoformat()
            result = [a for a in result if (a.get("published") or "") >= cutoff]

        return result

    # ── Sidebar update ──

    def _update_sidebar(self) -> None:
        from datetime import datetime, timezone
        today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        # Compute real counts from filtered year data
        total = len(self._articles)
        unread = sum(1 for a in self._articles if not a.get("read"))
        critical = sum(1 for a in self._articles if (a.get("severite") or a.get("severity", "")) == "CRITIQUE")
        today = sum(1 for a in self._articles if (a.get("published") or "").startswith(today_str))
        self._sidebar.update_stats({"total": total, "unread": unread, "critical": critical, "today": today})

        # Accurate per-category counts
        counts: dict[str, int] = {}
        fav_count = 0
        for a in self._articles:
            cat = a.get("category", "unknown")
            counts[cat] = counts.get(cat, 0) + 1
            if a.get("favori") or a.get("starred"):
                fav_count += 1
        counts["favoris"] = fav_count
        self._sidebar.update_category_counts(counts)

    # ── Event handlers ──

    @Slot(str)
    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip()
        self._apply_filters()

    @Slot(str)
    def _on_category_filter(self, key: str) -> None:
        self._active_category = key
        for btn in self._sidebar.category_buttons:
            btn.set_active(btn.key == key)
        self._apply_filters()

    @Slot(int)
    def _on_score_filter(self, value: int) -> None:
        self._min_score = value
        self._apply_filters()

    @Slot(int)
    def _on_sort_changed(self, index: int) -> None:
        self._sort_desc = (index == 0)
        self._load_data()

    def _apply_filters(self) -> None:
        self._rebuild_grid()

    @Slot(dict)
    def _on_card_clicked(self, article: dict) -> None:
        self._detail_panel.show_article(article)
        uid = article.get("uid")
        if uid:
            try:
                self._db.mark_read(uid)
                article["read"] = 1
            except Exception:
                logger.exception("Erreur mark_read")

    @Slot(str)
    def _on_card_double_clicked(self, url: str) -> None:
        webbrowser.open(url)

    @Slot()
    def _close_detail(self) -> None:
        self._detail_panel.slide_out()

    @Slot(str)
    def _on_mark_read(self, uid: str) -> None:
        try:
            self._db.mark_read(uid)
            for a in self._articles:
                if a.get("uid") == uid:
                    a["read"] = 1
                    break
            self._update_sidebar()
        except Exception:
            logger.exception("Erreur mark_read")

    @Slot(str, bool)
    def _on_toggle_star(self, uid: str, starred: bool) -> None:
        try:
            self._db.mark_starred(uid, starred)
            for a in self._articles:
                if a.get("uid") == uid:
                    a["starred"] = int(starred)
                    a["favori"] = int(starred)
                    break
            self._update_sidebar()
            if self._active_category == "favoris":
                self._rebuild_grid()
        except Exception:
            logger.exception("Erreur toggle star")

    @Slot()
    def _on_refresh(self) -> None:
        self._status_label.setText("\u25b8 REFRESHING...")
        QApplication.processEvents()
        self._load_data()

    @Slot()
    def _on_auto_collect(self) -> None:
        """Lance la collecte RSS en thread daemon — ne bloque pas l'UI."""
        from src.core.pipeline import Pipeline
        self._status_label.setText("\u25b8 COLLECTE EN COURS...")
        QApplication.processEvents()

        def _worker():
            try:
                pipeline = Pipeline(self.config)
                result = pipeline.run()
                new = result.articles_new
                def _done():
                    self._load_data()
                    from datetime import datetime
                    hm = datetime.now().strftime("%H:%M")
                    self._status_label.setText(
                        f"\u25b8 {len(self._articles)} ARTICLES  "
                        f"\u2502  +{new} nouveaux ({hm})  "
                        f"\u2502  {format_next_purge_label()}"
                    )
                QTimer.singleShot(0, _done)
            except Exception as exc:
                logger.exception("Auto-collect erreur: %s", exc)
                QTimer.singleShot(0, lambda: self._status_label.setText(
                    f"\u25b8 Collecte echouee: {exc}  \u2502  {format_next_purge_label()}"
                ))

        t = threading.Thread(target=_worker, name="CW-AutoCollect", daemon=True)
        t.start()

    # -- Resume view navigation ------------------------------------------

    @Slot()
    def _on_resume_nav(self) -> None:
        """Toggle between article feed and resume view."""
        is_resume_active = not self._scroll.isVisible()
        if is_resume_active:
            self._resume_view.setVisible(False)
            self._scroll.setVisible(True)
            self._sidebar.resume_button.setChecked(False)
            self._detail_panel.setVisible(True)
        else:
            self._detail_panel.slide_out()
            self._scroll.setVisible(False)
            self._resume_view.setVisible(True)
            self._sidebar.resume_button.setChecked(True)
            self._resume_view.refresh()

    @Slot(str, bool)
    def _on_summary_generate(self, summary_type: str, force: bool) -> None:
        """Async generation of a daily summary - runs in daemon thread."""
        self._resume_view.set_generating(True)
        self._resume_view.set_status("Generation du resume en cours...", is_error=False)

        def _worker():
            try:
                result = self._summary_gen.generate_summary(summary_type, force=force)
                if result is None:
                    msg = "Aucun article disponible pour generer le resume."
                    QTimer.singleShot(0, lambda: self._resume_view.set_status(msg, is_error=False))
                    QTimer.singleShot(0, lambda: self._resume_view.set_generating(False))
                else:
                    def _update():
                        self._resume_view.set_generating(False)
                        self._resume_view.set_status("", is_error=False)
                        self._resume_view.reload_content()
                    QTimer.singleShot(0, _update)
            except Exception as exc:
                logger.exception("Erreur generation resume: %s", exc)
                err = str(exc)
                QTimer.singleShot(0, lambda: self._resume_view.set_status(f"Erreur: {err}", is_error=True))
                QTimer.singleShot(0, lambda: self._resume_view.set_generating(False))

        t = threading.Thread(target=_worker, name="CW-SummaryGen", daemon=True)
        t.start()

    def _check_startup_summary(self) -> None:
        """Auto-generate missing summaries on startup (morning always, evening if past 18h)."""
        now = _dt.now()
        today = now.strftime("%Y-%m-%d")
        if not self._db.get_summary(today, "morning"):
            logger.info("Startup: pas de resume matin pour %s -- generation auto", today)
            self._on_summary_generate("morning", False)
        if now.hour >= 18 and not self._db.get_summary(today, "evening"):
            logger.info("Startup: pas de resume soir pour %s -- generation auto", today)
            QTimer.singleShot(5000, lambda: self._on_summary_generate("evening", False))

    def _setup_summary_timers(self) -> None:
        """Check every minute whether it is 07:00 or 18:00 to auto-generate summaries."""
        self._summary_clock = QTimer(self)
        self._summary_clock.timeout.connect(self._on_summary_clock_tick)
        self._summary_clock.start(60_000)

    def _on_summary_clock_tick(self) -> None:
        now = _dt.now()
        today = now.strftime("%Y-%m-%d")
        if now.hour >= 7 and now.hour < 18:
            if not self._db.get_summary(today, "morning"):
                logger.info("Auto-generate resume matin pour %s", today)
                self._on_summary_generate("morning", False)
        if now.hour >= 18:
            if not self._db.get_summary(today, "evening"):
                logger.info("Auto-generate resume soir pour %s", today)
                self._on_summary_generate("evening", False)


    @Slot()
    def _on_purge_now(self) -> None:
        """Purge manuelle avec confirmation QMessageBox."""
        retention = self.config.get("retention", {}).get("days", 7)
        reply = QMessageBox.question(
            self,
            "Confirmer la purge",
            f"Supprimer tous les articles de plus de {retention} jour(s) ?\n\n"
            "Les articles marques comme favoris seront preserves.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._status_label.setText("\u25b8 PURGE EN COURS...")
        QApplication.processEvents()

        try:
            deleted = self._weekly_scheduler.run_now()
            self._load_data()
            self._status_label.setText(
                f"\u25b8 PURGE OK \u2014 {deleted} article(s) supprime(s)  "
                f"\u2502  {format_next_purge_label()}"
            )
            QMessageBox.information(
                self,
                "Purge terminee",
                f"{deleted} article(s) supprime(s).\nLes favoris ont ete preserves.",
            )
        except Exception as exc:
            logger.exception("Erreur purge manuelle GUI")
            QMessageBox.critical(self, "Erreur purge", str(exc))


