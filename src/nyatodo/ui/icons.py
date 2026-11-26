"""Programmatic crisp vector QPainter icons for nyatodo (zero external binary image assets)."""

import math
from collections.abc import Callable
from typing import Literal

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QIconEngine,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from nyatodo.domain import TaskStatus
from nyatodo.ui.pill_widgets import draw_vector_glyph
from nyatodo.ui.theme import ColorTokens


def _resolve_dpr(dpr: float | None) -> float:
    if dpr is not None:
        return max(1.0, float(dpr))
    screen = QGuiApplication.primaryScreen()
    return max(1.0, float(screen.devicePixelRatio())) if screen is not None else 1.0


def _blank_pixmap(size: int, *, dpr: float | None = None) -> QPixmap:
    resolved_dpr = _resolve_dpr(dpr)
    pixel_size = max(1, round(size * resolved_dpr))
    pixmap = QPixmap(pixel_size, pixel_size)
    pixmap.setDevicePixelRatio(resolved_dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    return pixmap


def _stroke_pen(color: QColor, width: float = 1.5) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


class _VectorIconEngine(QIconEngine):
    """Resolution-independent QIconEngine rendering vector strokes at target DPR."""

    def __init__(self, base_size: float, draw_fn: Callable[[QPainter], None]) -> None:
        super().__init__()
        self._base_size = base_size
        self._draw_fn = draw_fn

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        if rect.isEmpty():
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(rect.x(), rect.y())
        painter.scale(rect.width() / self._base_size, rect.height() / self._base_size)
        self._draw_fn(painter)
        painter.restore()

    def actualSize(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QSize:
        return size

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return self.scaledPixmap(size, mode, state, 1.0)

    def scaledPixmap(
        self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float
    ) -> QPixmap:
        dpr = max(1.0, float(scale))
        w = max(1, round(size.width() * dpr))
        h = max(1, round(size.height() * dpr))
        pixmap = QPixmap(w, h)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)
        painter.end()
        return pixmap

    def clone(self) -> QIconEngine:
        return _VectorIconEngine(self._base_size, self._draw_fn)


def _render_pixmap(
    size: int,
    base_size: float,
    draw_fn: Callable[[QPainter], None],
    *,
    dpr: float | None = None,
) -> QPixmap:
    pixmap = _blank_pixmap(size, dpr=dpr)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / base_size
    painter.scale(scale, scale)
    draw_fn(painter)
    painter.end()
    return pixmap


def create_cat_monogram_pixmap(
    size: int,
    color: QColor,
    *,
    badge_color: QColor | None = None,
    dpr: float | None = None,
) -> QPixmap:
    """Render minimalist geometric cat-ear and whisker monogram at size x size."""
    col = QColor(color)
    badge = QColor(badge_color) if badge_color is not None else None

    def _draw(painter: QPainter) -> None:
        painter.setPen(_stroke_pen(col, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        head_path = QPainterPath()
        head_path.moveTo(3.2, 13.0)
        head_path.lineTo(3.2, 5.2)
        head_path.lineTo(6.6, 8.2)
        head_path.lineTo(11.4, 8.2)
        head_path.lineTo(14.8, 5.2)
        head_path.lineTo(14.8, 13.0)
        painter.drawPath(head_path)

        painter.drawLine(QPointF(1.6, 11.2), QPointF(4.8, 11.2))
        painter.drawLine(QPointF(1.8, 13.6), QPointF(5.0, 13.2))
        painter.drawLine(QPointF(13.2, 11.2), QPointF(16.4, 11.2))
        painter.drawLine(QPointF(13.0, 13.2), QPointF(16.2, 13.6))

        if badge is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(badge)
            painter.drawEllipse(QRectF(12.4, 12.4, 4.6, 4.6))

    return _render_pixmap(size, 18.0, _draw, dpr=dpr)


def create_cat_tray_icon(
    *,
    foreground: QColor,
    active_timer: bool = False,
    badge_color: QColor | None = None,
) -> QIcon:
    """Create multi-resolution QIcon for system tray with optional active timer badge."""
    icon = QIcon()
    dot = badge_color if active_timer else None
    for sz in (16, 24, 32, 48):
        icon.addPixmap(create_cat_monogram_pixmap(sz, foreground, badge_color=dot, dpr=1.0))
    return icon


def create_gear_icon(color: QColor, size: int = 16) -> QIcon:
    """Render minimal outline gear icon."""
    col = QColor(color)

    def _draw(painter: QPainter) -> None:
        painter.setPen(_stroke_pen(col, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        center = QPointF(8.0, 8.0)
        painter.drawEllipse(center, 2.3, 2.3)
        painter.drawEllipse(center, 4.8, 4.8)

        for idx in range(8):
            angle = idx * (math.pi / 4.0)
            x1 = 8.0 + math.cos(angle) * 4.8
            y1 = 8.0 + math.sin(angle) * 4.8
            x2 = 8.0 + math.cos(angle) * 6.5
            y2 = 8.0 + math.sin(angle) * 6.5
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    return QIcon(_VectorIconEngine(16.0, _draw))


def create_plus_pixmap(color: QColor, size: int = 16, *, dpr: float | None = None) -> QPixmap:
    """Render crisp '+' glyph."""
    col = QColor(color)

    def _draw(painter: QPainter) -> None:
        painter.setPen(_stroke_pen(col, 1.5))
        painter.drawLine(QPointF(8.0, 3.5), QPointF(8.0, 12.5))
        painter.drawLine(QPointF(3.5, 8.0), QPointF(12.5, 8.0))

    return _render_pixmap(size, 16.0, _draw, dpr=dpr)


def create_search_pixmap(color: QColor, size: int = 16, *, dpr: float | None = None) -> QPixmap:
    """Render crisp magnifying glass glyph for '/' search mode."""
    col = QColor(color)

    def _draw(painter: QPainter) -> None:
        painter.setPen(_stroke_pen(col, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(6.8, 6.8), 3.8, 3.8)
        painter.drawLine(QPointF(9.7, 9.7), QPointF(13.0, 13.0))

    return _render_pixmap(size, 16.0, _draw, dpr=dpr)


def _draw_check(painter: QPainter, color: QColor) -> None:
    painter.setPen(_stroke_pen(color, 1.6))
    painter.drawLine(QPointF(3.0, 7.2), QPointF(5.8, 10.0))
    painter.drawLine(QPointF(5.8, 10.0), QPointF(11.2, 4.2))


def create_check_pixmap(color: QColor, size: int = 14, *, dpr: float | None = None) -> QPixmap:
    """Render crisp geometric checkmark."""
    col = QColor(color)
    return _render_pixmap(size, 14.0, lambda p: _draw_check(p, col), dpr=dpr)


def create_check_icon(color: QColor, size: int = 14) -> QIcon:
    """Return checkmark QIcon."""
    col = QColor(color)
    return QIcon(_VectorIconEngine(14.0, lambda p: _draw_check(p, col)))


def create_chevron_icon(
    direction: Literal["left", "right", "up", "down"],
    color: QColor,
    size: int = 14,
) -> QIcon:
    """Render directional chevron QIcon."""
    col = QColor(color)

    def _draw(painter: QPainter) -> None:
        painter.setPen(_stroke_pen(col, 1.5))
        if direction == "left":
            painter.drawLine(QPointF(8.8, 3.5), QPointF(5.0, 7.0))
            painter.drawLine(QPointF(5.0, 7.0), QPointF(8.8, 10.5))
        elif direction == "right":
            painter.drawLine(QPointF(5.2, 3.5), QPointF(9.0, 7.0))
            painter.drawLine(QPointF(9.0, 7.0), QPointF(5.2, 10.5))
        elif direction == "up":
            painter.drawLine(QPointF(3.5, 8.8), QPointF(7.0, 5.0))
            painter.drawLine(QPointF(7.0, 5.0), QPointF(10.5, 8.8))
        else:
            painter.drawLine(QPointF(3.5, 5.2), QPointF(7.0, 9.0))
            painter.drawLine(QPointF(7.0, 9.0), QPointF(10.5, 5.2))

    return QIcon(_VectorIconEngine(14.0, _draw))


def create_close_icon(color: QColor, size: int = 12) -> QIcon:
    """Render minimal 'x' close icon."""
    col = QColor(color)

    def _draw(painter: QPainter) -> None:
        painter.setPen(_stroke_pen(col, 1.5))
        painter.drawLine(QPointF(3.0, 3.0), QPointF(9.0, 9.0))
        painter.drawLine(QPointF(9.0, 3.0), QPointF(3.0, 9.0))

    return QIcon(_VectorIconEngine(12.0, _draw))


def create_clock_pixmap(color: QColor, size: int = 14, *, dpr: float | None = None) -> QPixmap:
    """Render crisp 14x14 clock icon for Idle Check banner."""
    col = QColor(color)

    def _draw(painter: QPainter) -> None:
        painter.setPen(_stroke_pen(col, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(7.0, 7.0), 5.2, 5.2)
        painter.drawLine(QPointF(7.0, 4.2), QPointF(7.0, 7.2))
        painter.drawLine(QPointF(7.0, 7.2), QPointF(9.2, 8.5))

    return _render_pixmap(size, 14.0, _draw, dpr=dpr)


def create_play_icon(color: QColor, size: int = 12) -> QIcon:
    """Render crisp play triangle icon."""
    col = QColor(color)

    def _draw(painter: QPainter) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(col)
        path = QPainterPath()
        path.moveTo(3.2, 2.2)
        path.lineTo(9.8, 6.0)
        path.lineTo(3.2, 9.8)
        path.closeSubpath()
        painter.drawPath(path)

    return QIcon(_VectorIconEngine(12.0, _draw))


def create_stop_icon(color: QColor, size: int = 12) -> QIcon:
    """Render crisp rounded stop square icon."""
    col = QColor(color)

    def _draw(painter: QPainter) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(col)
        painter.drawRoundedRect(QRectF(2.8, 2.8, 6.4, 6.4), 1.4, 1.4)

    return QIcon(_VectorIconEngine(12.0, _draw))


def create_status_icon(status: TaskStatus, tokens: ColorTokens, size: int = 16) -> QIcon:
    """Render semantic 14x14 TaskStatus glyph centered in a 16x16 icon."""

    def _draw(painter: QPainter) -> None:
        if status == TaskStatus.TODO:
            painter.setPen(_stroke_pen(QColor(tokens.text_muted), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(8.0, 8.0), 5.6, 5.6)
        elif status == TaskStatus.DOING:
            doing_color = QColor(tokens.status_doing)
            painter.setPen(_stroke_pen(doing_color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(8.0, 8.0), 5.6, 5.6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(doing_color)
            painter.drawEllipse(QPointF(8.0, 8.0), 2.8, 2.8)
        elif status == TaskStatus.WAITING:
            waiting_color = QColor(tokens.status_waiting)
            painter.setPen(_stroke_pen(waiting_color, 1.3))
            painter.setBrush(QColor(tokens.tint_waiting))
            painter.drawRoundedRect(QRectF(2.2, 2.2, 11.6, 11.6), 3.2, 3.2)
            painter.setPen(_stroke_pen(waiting_color, 1.5))
            painter.drawLine(QPointF(6.2, 5.2), QPointF(6.2, 10.8))
            painter.drawLine(QPointF(9.8, 5.2), QPointF(9.8, 10.8))
        else:
            done_color = QColor(tokens.status_done)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(done_color)
            painter.drawEllipse(QPointF(8.0, 8.0), 6.2, 6.2)
            painter.setPen(_stroke_pen(QColor("#FFFFFF"), 1.6))
            painter.drawLine(QPointF(5.0, 8.2), QPointF(7.1, 10.3))
            painter.drawLine(QPointF(7.1, 10.3), QPointF(11.1, 5.8))

    return QIcon(_VectorIconEngine(16.0, _draw))


def create_filter_icon(
    color: QColor,
    *,
    active_dot_color: QColor | None = None,
    size: int = 14,
) -> QIcon:
    """Render crisp 3-bar filter icon with optional active indicator dot."""
    col = QColor(color)
    dot = QColor(active_dot_color) if active_dot_color is not None else None

    def _draw(painter: QPainter) -> None:
        painter.setPen(_stroke_pen(col, 1.5))
        painter.drawLine(QPointF(2.2, 4.0), QPointF(11.8, 4.0))
        painter.drawLine(QPointF(4.0, 7.2), QPointF(10.0, 7.2))
        painter.drawLine(QPointF(5.8, 10.4), QPointF(8.2, 10.4))

        if dot is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot)
            painter.drawEllipse(QRectF(10.2, 0.8, 3.4, 3.4))

    return QIcon(_VectorIconEngine(14.0, _draw))


def create_calendar_icon(color: QColor, size: int = 14) -> QIcon:
    """Render minimalist outline calendar icon for period selector cue."""
    col = QColor(color)

    def _draw(painter: QPainter) -> None:
        painter.setPen(_stroke_pen(col, 1.3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(2.2, 3.2, 9.6, 8.6), 2.0, 2.0)
        painter.drawLine(QPointF(2.4, 6.0), QPointF(11.6, 6.0))
        painter.drawLine(QPointF(4.8, 1.8), QPointF(4.8, 3.6))
        painter.drawLine(QPointF(9.2, 1.8), QPointF(9.2, 3.6))

    return QIcon(_VectorIconEngine(14.0, _draw))


def create_glyph_icon(kind: str, color: QColor, size: int = 12) -> QIcon:
    """Render centered vector glyph QIcon scaling cleanly across DPI ratios."""
    col = QColor(color)
    base = float(size)
    center = QPointF(base / 2.0, base / 2.0)

    def _draw(painter: QPainter) -> None:
        draw_vector_glyph(painter, kind, center, base, col)

    return QIcon(_VectorIconEngine(base, _draw))
