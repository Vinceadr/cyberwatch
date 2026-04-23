"""Constantes de style et QSS — theme Bioluminescent Etch pour CyberWatch."""

# ═══════════════════════════════════════════════════════════════
#  COLOR PALETTE — Bioluminescent Cyberpunk
# ═══════════════════════════════════════════════════════════════

COLORS: dict[str, str] = {
    # Backgrounds
    "bg_main": "#020408",
    "bg_sidebar": "#050810",
    "bg_card": "#0A0E14",
    "bg_card_hover": "#0F1620",
    "bg_header": "#040710",
    "bg_panel": "#060A12",
    # Borders
    "border": "#0C2A30",
    "border_active": "#00F2FF",
    "border_subtle": "#091E23",
    # Text
    "text_primary": "#E2E8F0",
    "text_secondary": "#94A3B8",
    "text_muted": "#475569",
    "text_cyan": "#22D3EE",
    # Accent — Cyan bioluminescent
    "accent": "#00F2FF",
    "accent_dim": "#007A80",
    "accent_bg": "#001A1E",
    # Category colors
    "cyber": "#F85149",
    "systemes": "#38BDF8",
    "reseaux": "#34D399",
    "dev": "#FBBF24",
    "ia": "#C084FC",
    "gaming": "#FB923C",
    "hacks": "#F87171",
    "favoris": "#FACC15",
    # Score
    "score_high": "#34D399",
    "score_medium": "#FBBF24",
    "score_low": "#F85149",
}

CATEGORY_META: dict[str, dict[str, str]] = {
    "favoris": {"label": "Favoris", "icon": "★", "color": COLORS["favoris"]},
    "cyber": {"label": "Cybersecurite", "icon": "●", "color": COLORS["cyber"]},
    "systemes": {"label": "Systemes", "icon": "●", "color": COLORS["systemes"]},
    "reseaux": {"label": "Reseaux", "icon": "●", "color": COLORS["reseaux"]},
    "dev": {"label": "Developpement", "icon": "●", "color": COLORS["dev"]},
    "ia": {"label": "IA", "icon": "●", "color": COLORS["ia"]},
    "gaming": {"label": "Gaming", "icon": "●", "color": COLORS["gaming"]},
    "hacks": {"label": "Hacks", "icon": "●", "color": COLORS["hacks"]},
    "unknown": {"label": "Autre", "icon": "●", "color": COLORS["text_muted"]},
}

SIDEBAR_CATEGORIES = ["favoris", "cyber", "systemes", "reseaux", "dev", "ia", "gaming", "hacks"]

SEVERITY_SCORE: dict[str, int] = {
    "CRITIQUE": 95,
    "HAUTE": 75,
    "MOYENNE": 50,
    "BASSE": 25,
    "INFO": 10,
}


def score_color(score: int) -> str:
    if score >= 70:
        return COLORS["score_high"]
    if score >= 40:
        return COLORS["score_medium"]
    return COLORS["score_low"]


def category_color(cat: str) -> str:
    return CATEGORY_META.get(cat, CATEGORY_META["unknown"])["color"]


FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"

# ═══════════════════════════════════════════════════════════════
#  GLOBAL QSS — Bioluminescent Etch Theme
#  Matches the HTML "Bioluminescent Etch" reference design:
#    --bg-deep: #020408  --etch-cyan: #00f2ff
#    --surface: #0a0e14  --etch-glow: rgba(0,242,255,0.15)
# ═══════════════════════════════════════════════════════════════

GLOBAL_QSS: str = f"""

/* ── Base reset ──────────────────────────────────────────── */
* {{
    font-family: "{FONT_FAMILY}";
    color: {COLORS["text_primary"]};
    outline: none;
}}

/* ── Main window  (--bg-deep) ────────────────────────────── */
QMainWindow {{
    background: {COLORS["bg_main"]};
}}

/* ── Scroll area ─────────────────────────────────────────── */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

/* ── Scrollbar — 4px thin, cyan luminous thumb ───────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: rgba(0, 242, 255, 0.18);
    min-height: 48px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(0, 242, 255, 0.55);
    border-radius: 3px;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
    border: none;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 4px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: rgba(0, 242, 255, 0.20);
    min-width: 40px;
    border-radius: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(0, 242, 255, 0.40);
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: transparent;
    width: 0;
    border: none;
}}

/* ── QFrame — etch-border panels (bg-white/5 + border white/10) */
QFrame {{
    background: transparent;
    border: none;
}}
QFrame[frameShape="4"],  /* HLine */
QFrame[frameShape="5"] {{ /* VLine */
    background: rgba(0, 242, 255, 0.08);
    max-height: 1px;
    border: none;
}}
QFrame#etchPanel {{
    background: rgba(10, 14, 20, 0.80);
    border: 1px solid rgba(0, 242, 255, 0.10);
    border-radius: 16px;
    padding: 24px;
}}
QFrame#sidebarFrame {{
    background: rgba(0, 0, 0, 0.40);
    border-right: 1px solid rgba(0, 242, 255, 0.10);
}}
QFrame#headerFrame {{
    background: rgba(0, 0, 0, 0.20);
    border-bottom: 1px solid rgba(0, 242, 255, 0.10);
}}
QFrame#rightPanel {{
    background: rgba(0, 0, 0, 0.60);
    border-left: 1px solid rgba(0, 242, 255, 0.10);
}}
QFrame#panelSection {{
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    padding: 16px;
}}

/* ── Search field — rounded-full, monospace, wide tracking ── */
QLineEdit {{
    background: rgba(15, 23, 42, 0.50);
    border: 1px solid {COLORS["border_subtle"]};
    border-radius: 20px;
    padding: 8px 20px;
    color: {COLORS["text_primary"]};
    font-family: "{FONT_MONO}";
    font-size: 11px;
    letter-spacing: 3px;
    selection-background-color: {COLORS["accent_dim"]};
}}
QLineEdit:focus {{
    border-color: rgba(0, 242, 255, 0.45);
}}
QLineEdit:hover {{
    border-color: rgba(0, 242, 255, 0.25);
}}
QLineEdit::placeholder {{
    color: {COLORS["text_muted"]};
}}

/* ── ComboBox — rounded-xl ───────────────────────────────── */
QComboBox {{
    background: rgba(10, 14, 20, 0.60);
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 6px 30px 6px 14px;
    color: {COLORS["text_primary"]};
    font-size: 10px;
    letter-spacing: 1px;
    min-width: 100px;
}}
QComboBox:hover {{
    border-color: rgba(0, 242, 255, 0.25);
}}
QComboBox:focus {{
    border-color: rgba(0, 242, 255, 0.45);
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}
QComboBox::down-arrow {{
    image: none;
    border: none;
}}
QComboBox QAbstractItemView {{
    background: {COLORS["bg_card"]};
    border: 1px solid rgba(0, 242, 255, 0.10);
    border-radius: 12px;
    padding: 4px;
    selection-background-color: rgba(0, 242, 255, 0.10);
    selection-color: {COLORS["accent"]};
    color: {COLORS["text_primary"]};
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 12px;
    border-radius: 8px;
}}
QComboBox QAbstractItemView::item:hover {{
    background: rgba(0, 242, 255, 0.08);
}}

/* ── Buttons — rounded-xl, secondary style by default ────── */
QPushButton {{
    background: transparent;
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 7px 18px;
    color: {COLORS["text_secondary"]};
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 2px;
}}
QPushButton:hover {{
    background: rgba(0, 242, 255, 0.06);
    border-color: rgba(0, 242, 255, 0.25);
    color: {COLORS["text_primary"]};
}}
QPushButton:pressed {{
    background: rgba(0, 242, 255, 0.10);
    border-color: rgba(0, 242, 255, 0.40);
}}
QPushButton:disabled {{
    color: {COLORS["text_muted"]};
    border-color: rgba(255, 255, 255, 0.05);
}}
/* Primary CTA — bg-cyan-500 text-black */
QPushButton#primaryButton {{
    background: {COLORS["accent"]};
    border: none;
    color: #000000;
    font-weight: bold;
}}
QPushButton#primaryButton:hover {{
    background: #33F5FF;
    color: #000000;
}}
QPushButton#primaryButton:pressed {{
    background: #00C4CC;
    color: #000000;
}}

/* ── Slider — 14px luminous handle ───────────────────────── */
QSlider::groove:horizontal {{
    background: rgba(0, 242, 255, 0.08);
    height: 3px;
    border-radius: 1px;
}}
QSlider::handle:horizontal {{
    background: {COLORS["accent"]};
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    border: 2px solid rgba(0, 242, 255, 0.30);
}}
QSlider::handle:horizontal:hover {{
    border: 2px solid rgba(0, 242, 255, 0.60);
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS["accent"]}, stop:1 {COLORS["accent_dim"]});
    border-radius: 1px;
}}

/* ── Tooltip — dark surface, cyan border, rounded ────────── */
QToolTip {{
    background: {COLORS["bg_card"]};
    color: {COLORS["text_primary"]};
    border: 1px solid rgba(0, 242, 255, 0.15);
    padding: 8px 14px;
    border-radius: 10px;
    font-size: 11px;
}}

/* ── Labels ──────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    border: none;
}}
QLabel#sectionLabel {{
    font-size: 8px;
    font-weight: bold;
    letter-spacing: 3px;
    color: rgba(0, 242, 255, 0.50);
    text-transform: uppercase;
}}

/* ── Tab bar ─────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid rgba(0, 242, 255, 0.10);
    border-radius: 12px;
    background: rgba(10, 14, 20, 0.80);
}}
QTabBar::tab {{
    background: transparent;
    border: 1px solid transparent;
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    padding: 8px 20px;
    color: {COLORS["text_muted"]};
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 2px;
}}
QTabBar::tab:selected {{
    background: rgba(0, 242, 255, 0.10);
    color: {COLORS["accent"]};
    border-color: rgba(0, 242, 255, 0.20);
}}
QTabBar::tab:hover:!selected {{
    color: {COLORS["text_secondary"]};
    background: rgba(0, 242, 255, 0.04);
}}

/* ── Menu / Context menu ─────────────────────────────────── */
QMenu {{
    background: {COLORS["bg_card"]};
    border: 1px solid rgba(0, 242, 255, 0.10);
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 24px 8px 16px;
    border-radius: 8px;
    color: {COLORS["text_secondary"]};
    font-size: 10px;
}}
QMenu::item:selected {{
    background: rgba(0, 242, 255, 0.10);
    color: {COLORS["accent"]};
}}
QMenu::separator {{
    height: 1px;
    background: rgba(0, 242, 255, 0.08);
    margin: 4px 8px;
}}

/* ── CheckBox / RadioButton ──────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: {COLORS["text_secondary"]};
    font-size: 10px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    background: rgba(10, 14, 20, 0.60);
}}
QCheckBox::indicator:checked {{
    background: {COLORS["accent"]};
    border-color: {COLORS["accent"]};
}}
QCheckBox::indicator:hover {{
    border-color: rgba(0, 242, 255, 0.40);
}}

/* ── ProgressBar ─────────────────────────────────────────── */
QProgressBar {{
    background: rgba(0, 242, 255, 0.06);
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS["accent"]}, stop:1 {COLORS["accent_dim"]});
    border-radius: 3px;
}}

/* ── GroupBox ─────────────────────────────────────────────── */
QGroupBox {{
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(0, 242, 255, 0.08);
    border-radius: 12px;
    margin-top: 20px;
    padding: 20px 16px 16px 16px;
    font-size: 10px;
    font-weight: bold;
    color: {COLORS["text_secondary"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: rgba(0, 242, 255, 0.60);
    letter-spacing: 2px;
}}

/* ── SpinBox ─────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background: rgba(10, 14, 20, 0.60);
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 4px 8px;
    color: {COLORS["text_primary"]};
    font-size: 10px;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    border: none;
    width: 16px;
}}

/* ── TextEdit / PlainTextEdit ────────────────────────────── */
QTextEdit, QPlainTextEdit {{
    background: rgba(10, 14, 20, 0.60);
    border: 1px solid rgba(0, 242, 255, 0.08);
    border-radius: 12px;
    padding: 12px;
    color: {COLORS["text_primary"]};
    font-family: "{FONT_MONO}";
    font-size: 11px;
    selection-background-color: {COLORS["accent_dim"]};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: rgba(0, 242, 255, 0.35);
}}

/* ── Status bar ──────────────────────────────────────────── */
QStatusBar {{
    background: rgba(0, 0, 0, 0.30);
    border-top: 1px solid rgba(0, 242, 255, 0.06);
    color: {COLORS["text_muted"]};
    font-size: 9px;
    letter-spacing: 1px;
}}
"""
