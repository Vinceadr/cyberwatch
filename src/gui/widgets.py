"""Widgets custom — theme Bioluminescent Etch pour CyberWatch."""

from __future__ import annotations

import webbrowser
from datetime import datetime
from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import (
    CATEGORY_META,
    COLORS,
    FONT_FAMILY,
    FONT_MONO,
    SEVERITY_SCORE,
    category_color,
    score_color,
)


def _severity_to_score(severity: str) -> int:
    return SEVERITY_SCORE.get(severity, 10)


def _format_date(raw: str | None) -> str:
    if not raw:
        return "Date inconnue"
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            continue
    return raw[:16] if len(raw) > 16 else raw


# ═══════════════════════════════════════════════════════════════
#  SCORE BADGE — Glowing circle
# ═══════════════════════════════════════════════════════════════

class ScoreBadge(QWidget):
    """Circular score indicator with glow effect."""

    def __init__(self, score: int, size: int = 32, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._score = score
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(score_color(self._score))

        # Outer glow ring
        glow = QColor(color)
        glow.setAlphaF(0.08)
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, self._size, self._size)

        # Inner filled circle
        inner = QColor(color)
        inner.setAlphaF(0.18)
        p.setBrush(inner)
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 80), 1.0))
        margin = 3
        p.drawEllipse(margin, margin, self._size - 2 * margin, self._size - 2 * margin)

        # Text
        p.setPen(QPen(color))
        p.setFont(QFont(FONT_MONO, self._size // 4, QFont.Weight.Bold))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self._score))
        p.end()


# ═══════════════════════════════════════════════════════════════
#  CATEGORY BADGE — Etched pill  (HTML: text-[10px] mono bg-*/10 px-2 py-1 rounded)
# ═══════════════════════════════════════════════════════════════

class CategoryBadge(QWidget):
    """Colored pill showing category name with etch border."""

    def __init__(self, category: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        meta = CATEGORY_META.get(category, CATEGORY_META["unknown"])
        self._color = QColor(meta["color"])
        self._label = meta["label"]
        self.setFixedHeight(24)
        self.setFixedWidth(max(len(self._label) * 8 + 24, 52))

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background with subtle fill — bg-cyan-500/10
        bg = QColor(self._color)
        bg.setAlphaF(0.10)
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, float(self.width() - 1), float(self.height() - 1), 8.0, 8.0)
        p.fillPath(path, bg)

        # Etch border
        border = QColor(self._color)
        border.setAlphaF(0.30)
        p.setPen(QPen(border, 1.0))
        p.drawPath(path)

        # Text — mono, uppercase, letter-spacing 1px
        p.setPen(QPen(self._color))
        font = QFont(FONT_MONO, 8)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._label.upper())
        p.end()


# ═══════════════════════════════════════════════════════════════
#  ARTICLE CARD — Etch-border with gradient and glow  (HTML: etch-border rounded-2xl p-6)
# ═══════════════════════════════════════════════════════════════

class ArticleCard(QFrame):
    """Card representing a single article — bioluminescent etch style."""

    clicked = Signal(dict)
    double_clicked = Signal(str)

    CARD_WIDTH = 360
    CARD_HEIGHT = 260

    def __init__(self, article: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._article = article
        self._hovered = False
        self._hover_alpha = 0.0
        self._hover_dir   = 0
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(16)
        self._hover_timer.timeout.connect(self._tick_hover)
        self._cat_color = category_color(article.get("category", "unknown"))
        self._score = article.get("score", 0) or 0
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._build_ui()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 16, 14)
        lay.setSpacing(4)

        # Row 1: category badge + star + score
        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(CategoryBadge(self._article.get("category", "unknown")))

        if self._article.get("starred") or self._article.get("favori"):
            star = QLabel("★")
            star.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
            star.setStyleSheet(f"color: {COLORS['favoris']}; background: transparent;")
            star.setFixedWidth(16)
            top.addWidget(star)

        top.addStretch()
        top.addWidget(ScoreBadge(self._score, 26))
        lay.addLayout(top)

        # Row 2: title (max 2 lines)
        title_text = self._article.get("title", "") or ""
        title = QLabel(title_text[:160] + ("..." if len(title_text) > 160 else ""))
        title.setWordWrap(True)
        title.setMaximumHeight(56)
        title.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {COLORS['text_primary']}; background: transparent;")
        lay.addWidget(title)

        # Row 3: raw description (never translated)
        summary_text = self._article.get("description") or self._article.get("summary") or self._article.get("content") or ""
        if len(summary_text) > 320:
            summary_text = summary_text[:320].rstrip() + "..."
        summary = QLabel(summary_text)
        summary.setWordWrap(True)
        summary.setMaximumHeight(88)
        summary.setFont(QFont(FONT_FAMILY, 10))
        summary.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(summary, stretch=1)

        # Row 4: source + date (mono font)
        foot = QHBoxLayout()
        foot.setSpacing(4)
        src = QLabel(self._article.get("source_name", ""))
        src.setFont(QFont(FONT_MONO, 8))
        src.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        foot.addWidget(src)
        foot.addStretch()
        date_lbl = QLabel(_format_date(self._article.get("published")))
        date_lbl.setFont(QFont(FONT_MONO, 8))
        date_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        foot.addWidget(date_lbl)
        lay.addLayout(foot)

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())

        # Card gradient background — smooth hover interpolation
        a = self._hover_alpha
        def _lc(ha, hb, t):
            ca, cb = QColor(ha), QColor(hb)
            return QColor(int(ca.red()+(cb.red()-ca.red())*t), int(ca.green()+(cb.green()-ca.green())*t), int(ca.blue()+(cb.blue()-ca.blue())*t))
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, _lc(COLORS["bg_card"], "#101822", a))
        grad.setColorAt(1.0, _lc("#070B11", "#0A1018", a))

        body = QPainterPath()
        body.addRoundedRect(5.0, 0.0, w - 5.0, h, 16.0, 16.0)
        p.fillPath(body, grad)

        # Etch border — smooth alpha interpolation
        p.setPen(QPen(QColor(0, 242, 255, int(26 + 51 * a)), 1.0 + 0.2 * a))
        p.drawPath(body)

        # Left color stripe — smooth alpha + glow on hover
        stripe = QPainterPath()
        stripe.addRoundedRect(0.0, 6.0, 4.0, h - 12.0, 2.0, 2.0)
        stripe_color = QColor(self._cat_color)
        stripe_color.setAlphaF(0.6 + 0.4 * a)
        if a > 0.05:
            glow_stripe = QColor(self._cat_color)
            glow_stripe.setAlphaF(0.3 * a)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(-1.0, 4.0, 6.0, h - 8.0, 3.0, 3.0)
            p.fillPath(glow_path, glow_stripe)
        p.fillPath(stripe, stripe_color)

        # Unread dot (cyan glow)
        if not self._article.get("read"):
            dot_color = QColor(COLORS["accent"])
            # Outer glow
            glow = QColor(COLORS["accent"])
            glow.setAlphaF(0.25)
            p.setBrush(glow)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(w) - 16, 4, 10, 10)
            # Inner dot
            p.setBrush(dot_color)
            p.drawEllipse(int(w) - 14, 6, 6, 6)

        p.end()

    def _tick_hover(self) -> None:
        self._hover_alpha = max(0.0, min(1.0, self._hover_alpha + self._hover_dir * 0.09))
        self.update()
        if self._hover_alpha in (0.0, 1.0):
            self._hover_timer.stop()

    def enterEvent(self, _event: Any) -> None:  # noqa: N802
        self._hovered = True
        self._hover_dir = 1
        self._hover_timer.start()

    def leaveEvent(self, _event: Any) -> None:  # noqa: N802
        self._hovered = False
        self._hover_dir = -1
        self._hover_timer.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._article)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        url = self._article.get("url", "")
        if url:
            self.double_clicked.emit(url)
        super().mouseDoubleClickEvent(event)

    @property
    def article(self) -> dict:
        return self._article


# ═══════════════════════════════════════════════════════════════
#  CATEGORY BUTTON — Etch sidebar button  (HTML: flex items-center gap-4 px-4 py-3 rounded-lg)
# ═══════════════════════════════════════════════════════════════

class CategoryButton(QPushButton):
    """Sidebar button for a category filter — etch glow style."""

    filter_clicked = Signal(str)

    def __init__(self, key: str, label: str, color: str, count: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._label_text = label
        self._color = color
        self._active = False
        self._count = count
        self._icon = CATEGORY_META.get(key, CATEGORY_META["unknown"])["icon"]
        self._refresh_text()
        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        font = QFont(FONT_FAMILY, 10, QFont.Weight.Medium)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        self.setFont(font)
        self._apply_style()
        self.pressed.connect(self._emit)

    def _refresh_text(self) -> None:
        self.setText(f"  {self._icon}  {self._label_text}  ({self._count})")

    def set_count(self, count: int) -> None:
        self._count = count
        self._refresh_text()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def _apply_style(self) -> None:
        if self._active:
            self.setStyleSheet(
                f"QPushButton {{ background: rgba({self._hex_to_rgb(self._color)}, 0.1); "
                f"border: 1px solid rgba({self._hex_to_rgb(self._color)}, 0.2); "
                f"border-radius: 8px; color: {self._color}; text-align: left; padding-left: 16px; "
                f"font-weight: 500; }}"
                f"QPushButton:hover {{ background: rgba({self._hex_to_rgb(self._color)}, 0.15); }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1px solid transparent; "
                f"border-radius: 8px; color: {COLORS['text_secondary']}; text-align: left; "
                f"padding-left: 16px; }}"
                f"QPushButton:hover {{ background: rgba(0, 242, 255, 0.05); "
                f"border-color: {COLORS['border']}; color: {COLORS['text_cyan']}; }}"
            )

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> str:
        """Convert '#RRGGBB' to 'R, G, B' for use in rgba()."""
        h = hex_color.lstrip("#")
        return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"

    def _emit(self) -> None:
        self.filter_clicked.emit(self._key)

    @property
    def key(self) -> str:
        return self._key


# ═══════════════════════════════════════════════════════════════
#  DETAIL PANEL — Slide-in etch panel  (HTML: aside w-80 border-l border-cyan-900/30 bg-black/60)
# ═══════════════════════════════════════════════════════════════

class DetailPanel(QFrame):
    """Slide-in panel showing full article details — etch glass style."""

    close_requested = Signal()
    mark_read_requested = Signal(str)
    toggle_star_requested = Signal(str, bool)

    PANEL_WIDTH = 480

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._article: dict | None = None
        self.setFixedWidth(0)
        self.setStyleSheet(
            f"DetailPanel {{ background: #040810; "
            f"border-left: 1px solid {COLORS['border']}; }}"
        )
        self._anim = QPropertyAnimation(self, b"minimumWidth")
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_max = QPropertyAnimation(self, b"maximumWidth")
        self._anim_max.setDuration(250)
        self._anim_max.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # ── Header row: title + close button ──
        top_bar = QHBoxLayout()
        self._panel_title = QLabel("ARTICLE DETAILS")
        title_font = QFont(FONT_MONO, 9, QFont.Weight.Bold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
        self._panel_title.setFont(title_font)
        self._panel_title.setStyleSheet(
            f"color: {COLORS['accent']}; background: transparent;"
        )
        top_bar.addWidget(self._panel_title)
        top_bar.addStretch()

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(32, 32)
        self._close_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border-radius: 16px; "
            f"color: {COLORS['text_muted']}; border: 1px solid {COLORS['border']}; }}"
            f"QPushButton:hover {{ background: {COLORS['accent_bg']}; "
            f"color: {COLORS['accent']}; border-color: rgba(0,242,255,0.3); }}"
        )
        self._close_btn.clicked.connect(self.close_requested.emit)
        top_bar.addWidget(self._close_btn)
        layout.addLayout(top_bar)

        # ── Meta section — etch-border subsection ──
        self._meta_frame = QFrame()
        self._meta_frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,0.04); "
            "border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; }"
        )
        meta_layout = QVBoxLayout(self._meta_frame)
        meta_layout.setContentsMargins(16, 12, 16, 12)
        meta_layout.setSpacing(8)

        # "CLASSIFICATION" label
        cls_label = QLabel("CLASSIFICATION")
        cls_font = QFont(FONT_MONO, 8)
        cls_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        cls_label.setFont(cls_font)
        cls_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; background: transparent; border: none;"
        )
        meta_layout.addWidget(cls_label)

        # Badge + score + date row
        self._meta_row = QHBoxLayout()
        self._meta_row.setSpacing(10)
        self._cat_badge = CategoryBadge("unknown")
        self._meta_row.addWidget(self._cat_badge)
        self._score_badge = ScoreBadge(10, 32)
        self._meta_row.addWidget(self._score_badge)
        self._date_label = QLabel()
        date_font = QFont(FONT_MONO, 9)
        self._date_label.setFont(date_font)
        self._date_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; background: transparent; border: none;"
        )
        self._meta_row.addWidget(self._date_label)
        self._meta_row.addStretch()
        meta_layout.addLayout(self._meta_row)

        layout.addWidget(self._meta_frame)

        # ── Title ──
        self._title_label = QLabel()
        self._title_label.setWordWrap(True)
        self._title_label.setFont(QFont(FONT_FAMILY, 16, QFont.Weight.Bold))
        self._title_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; background: transparent;"
        )
        layout.addWidget(self._title_label)

        # ── Source section — metadata-style ──
        src_header = QLabel("SOURCE")
        src_hdr_font = QFont(FONT_MONO, 8)
        src_hdr_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        src_header.setFont(src_hdr_font)
        src_header.setStyleSheet(
            "color: rgba(0,242,255,0.35); background: transparent;"
        )
        layout.addWidget(src_header)

        self._source_label = QLabel()
        self._source_label.setFont(QFont(FONT_MONO, 10))
        self._source_label.setStyleSheet(
            f"color: {COLORS['text_cyan']}; background: transparent;"
        )
        layout.addWidget(self._source_label)

        # ── Separator — etch line ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        layout.addWidget(sep)

        # ── Scrollable summary ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        cw = QWidget()
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(0, 0, 0, 0)
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setFont(QFont(FONT_FAMILY, 11))
        self._summary_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent; line-height: 1.7;"
        )
        self._summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cl.addWidget(self._summary_label)
        cl.addStretch()
        scroll.setWidget(cw)
        layout.addWidget(scroll, stretch=1)

        # ── Action buttons — etch style ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._open_btn = QPushButton("OUVRIR SOURCE")
        self._open_btn.setFixedHeight(40)
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_font = QFont(FONT_MONO, 10, QFont.Weight.Bold)
        open_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        self._open_btn.setFont(open_font)
        self._open_btn.setStyleSheet(
            f"QPushButton {{ background: {COLORS['accent']}; color: #020408; border: none; "
            f"border-radius: 12px; padding: 0 20px; }}"
            f"QPushButton:hover {{ background: #33F5FF; }}"
        )
        self._open_btn.clicked.connect(self._open_url)
        btn_row.addWidget(self._open_btn)

        self._read_btn = QPushButton("MARQUER LU")
        self._read_btn.setFixedHeight(40)
        self._read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        read_font = QFont(FONT_FAMILY, 10)
        read_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        self._read_btn.setFont(read_font)
        self._read_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {COLORS['text_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 12px; }}"
            f"QPushButton:hover {{ color: {COLORS['accent']}; border-color: rgba(0,242,255,0.3); }}"
        )
        self._read_btn.clicked.connect(self._mark_read)
        btn_row.addWidget(self._read_btn)

        self._star_btn = QPushButton("FAVORIS")
        self._star_btn.setFixedHeight(40)
        self._star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        star_font = QFont(FONT_FAMILY, 10)
        star_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        self._star_btn.setFont(star_font)
        self._star_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {COLORS['text_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 12px; }}"
            f"QPushButton:hover {{ color: {COLORS['favoris']}; "
            f"border-color: rgba(250,204,21,0.25); }}"
        )
        self._star_btn.clicked.connect(self._toggle_star)
        btn_row.addWidget(self._star_btn)

        layout.addLayout(btn_row)

    def show_article(self, article: dict) -> None:
        self._article = article
        cat = article.get("category", "unknown")

        # Remove old badge and score from layout before adding new ones
        self._meta_row.removeWidget(self._cat_badge)
        self._cat_badge.setParent(None)
        self._cat_badge.deleteLater()

        self._meta_row.removeWidget(self._score_badge)
        self._score_badge.setParent(None)
        self._score_badge.deleteLater()

        self._cat_badge = CategoryBadge(cat)
        self._meta_row.insertWidget(0, self._cat_badge)

        score = article.get("score", 0) or 0
        self._score_badge = ScoreBadge(score, 32)
        self._meta_row.insertWidget(1, self._score_badge)

        self._date_label.setText(_format_date(article.get("published")))
        self._title_label.setText(article.get("title", ""))
        self._source_label.setText(article.get("source_name", "Inconnue"))

        summary = article.get("summary") or article.get("content") or ""
        self._summary_label.setText(summary)

        starred = bool(article.get("starred") or article.get("favori"))
        self._star_btn.setText("[ ★ ] FAVORI" if starred else "FAVORIS")
        self._slide_in()

    def _slide_in(self) -> None:
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(self.PANEL_WIDTH)
        self._anim_max.setStartValue(self.width())
        self._anim_max.setEndValue(self.PANEL_WIDTH)
        self._anim.start()
        self._anim_max.start()
        self.show()

    def slide_out(self) -> None:
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(0)
        self._anim_max.setStartValue(self.width())
        self._anim_max.setEndValue(0)
        self._anim.start()
        self._anim_max.start()

    def _open_url(self) -> None:
        if self._article and self._article.get("url"):
            webbrowser.open(self._article["url"])

    def _mark_read(self) -> None:
        if self._article:
            self.mark_read_requested.emit(self._article["uid"])

    def _toggle_star(self) -> None:
        if self._article:
            current = bool(self._article.get("starred"))
            new_state = not current
            self._article["starred"] = int(new_state)
            self._article["favori"] = int(new_state)
            self._star_btn.setText("[ ★ ] FAVORI" if new_state else "FAVORIS")
            self.toggle_star_requested.emit(self._article["uid"], new_state)

