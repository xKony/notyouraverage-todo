"""Programmatic crisp QPainter icons for nyatodo (zero external binary image assets)."""

import math
from typing import Literal

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from nyatodo.domain import TaskStatus
from nyatodo.ui.theme import ColorTokens


def _blank_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    return pixmap


def _stroke_pen(color: QColor, width: float = 1.5) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def create_cat_monogram_pixmap(
    size: int,
    color: QColor,
    *,
    badge_color: QColor | None = None,
) -> QPixmap:
    """Render minimalist geometric cat-ear and whisker monogram at size x size."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    scale = size / 18.0
    painter.scale(scale, scale)
    painter.setPen(_stroke_pen(color, 1.5))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Geometric cat ears + brow contour
    head_path = QPainterPath()
    head_path.moveTo(3.2, 13.0)
    head_path.lineTo(3.2, 5.2)
    head_path.lineTo(6.6, 8.2)
    head_path.lineTo(11.4, 8.2)
    head_path.lineTo(14.8, 5.2)
    head_path.lineTo(14.8, 13.0)
    painter.drawPath(head_path)

    # Two horizontal whisker ticks on left and right
    painter.drawLine(QPointF(1.6, 11.2), QPointF(4.8, 11.2))
    painter.drawLine(QPointF(1.8, 13.6), QPointF(5.0, 13.2))
    painter.drawLine(QPointF(13.2, 11.2), QPointF(16.4, 11.2))
    painter.drawLine(QPointF(13.0, 13.2), QPointF(16.2, 13.6))

    if badge_color is not None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(badge_color)
        painter.drawEllipse(QRectF(12.4, 12.4, 4.6, 4.6))

    painter.end()
    return pixmap


def create_cat_tray_icon(
    *,
    foreground: QColor,
    active_timer: bool = False,
    badge_color: QColor | None = None,
) -> QIcon:
    """Create multi-resolution QIcon for system tray with optional active timer badge."""
    icon = QIcon()
    dot = badge_color if active_timer else None
    for sz in (16, 24, 32):
        icon.addPixmap(create_cat_monogram_pixmap(sz, foreground, badge_color=dot))
    return icon


def create_gear_icon(color: QColor, size: int = 16) -> QIcon:
    """Render minimal outline gear icon."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 16.0
    painter.scale(scale, scale)
    painter.setPen(_stroke_pen(color, 1.4))
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

    painter.end()
    return QIcon(pixmap)


def create_plus_pixmap(color: QColor, size: int = 16) -> QPixmap:
    """Render crisp '+' glyph."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 16.0
    painter.scale(scale, scale)
    painter.setPen(_stroke_pen(color, 1.5))
    painter.drawLine(QPointF(8.0, 3.5), QPointF(8.0, 12.5))
    painter.drawLine(QPointF(3.5, 8.0), QPointF(12.5, 8.0))
    painter.end()
    return pixmap


def create_search_pixmap(color: QColor, size: int = 16) -> QPixmap:
    """Render crisp magnifying glass glyph for '/' search mode."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 16.0
    painter.scale(scale, scale)
    painter.setPen(_stroke_pen(color, 1.5))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(6.8, 6.8), 3.8, 3.8)
    painter.drawLine(QPointF(9.7, 9.7), QPointF(13.0, 13.0))
    painter.end()
    return pixmap


def create_check_pixmap(color: QColor, size: int = 14) -> QPixmap:
    """Render crisp geometric checkmark."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 14.0
    painter.scale(scale, scale)
    painter.setPen(_stroke_pen(color, 1.6))
    painter.drawLine(QPointF(3.0, 7.2), QPointF(5.8, 10.0))
    painter.drawLine(QPointF(5.8, 10.0), QPointF(11.2, 4.2))
    painter.end()
    return pixmap


def create_check_icon(color: QColor, size: int = 14) -> QIcon:
    """Return checkmark QIcon."""
    return QIcon(create_check_pixmap(color, size))


def create_chevron_icon(
    direction: Literal["left", "right", "up", "down"],
    color: QColor,
    size: int = 14,
) -> QIcon:
    """Render directional chevron QIcon."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 14.0
    painter.scale(scale, scale)
    painter.setPen(_stroke_pen(color, 1.5))
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
    painter.end()
    return QIcon(pixmap)


def create_close_icon(color: QColor, size: int = 12) -> QIcon:
    """Render minimal 'x' close icon."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 12.0
    painter.scale(scale, scale)
    painter.setPen(_stroke_pen(color, 1.5))
    painter.drawLine(QPointF(3.0, 3.0), QPointF(9.0, 9.0))
    painter.drawLine(QPointF(9.0, 3.0), QPointF(3.0, 9.0))
    painter.end()
    return QIcon(pixmap)


def create_clock_pixmap(color: QColor, size: int = 14) -> QPixmap:
    """Render crisp 14x14 clock icon for Idle Check banner."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 14.0
    painter.scale(scale, scale)
    painter.setPen(_stroke_pen(color, 1.4))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(7.0, 7.0), 5.2, 5.2)
    painter.drawLine(QPointF(7.0, 4.2), QPointF(7.0, 7.2))
    painter.drawLine(QPointF(7.0, 7.2), QPointF(9.2, 8.5))
    painter.end()
    return pixmap


def create_play_icon(color: QColor, size: int = 12) -> QIcon:
    """Render crisp play triangle icon."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 12.0
    painter.scale(scale, scale)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    path = QPainterPath()
    path.moveTo(3.2, 2.2)
    path.lineTo(9.8, 6.0)
    path.lineTo(3.2, 9.8)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def create_stop_icon(color: QColor, size: int = 12) -> QIcon:
    """Render crisp rounded stop square icon."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 12.0
    painter.scale(scale, scale)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawRoundedRect(QRectF(2.8, 2.8, 6.4, 6.4), 1.4, 1.4)
    painter.end()
    return QIcon(pixmap)


def create_status_icon(status: TaskStatus, tokens: ColorTokens, size: int = 16) -> QIcon:
    """Render semantic 14x14 TaskStatus glyph centered in a 16x16 icon."""
    pixmap = _blank_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 16.0
    painter.scale(scale, scale)

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

    painter.end()
    return QIcon(pixmap)
