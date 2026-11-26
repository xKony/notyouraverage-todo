"""Animated pill primitives and crisp vector glyphs for nyatodo's Morph Pills UI."""

import math

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QEnterEvent, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from nyatodo.domain import TaskStatus
from nyatodo.ui.theme import DARK_TOKENS, ColorTokens


def draw_vector_glyph(
    painter: QPainter,
    kind: str,
    center: QPointF,
    size: float,
    color: QColor,
    *,
    stroke: float = 1.6,
) -> None:
    """Render minimal crisp vector glyphs without text clutter."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    cx, cy = center.x(), center.y()
    r = size * 0.42

    if kind == "play":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        path = QPainterPath()
        path.moveTo(cx - r * 0.45, cy - r * 0.72)
        path.lineTo(cx + r * 0.78, cy)
        path.lineTo(cx - r * 0.45, cy + r * 0.72)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "stop":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        side = r * 1.38
        painter.drawRoundedRect(QRectF(cx - side / 2, cy - side / 2, side, side), 1.8, 1.8)
    elif kind == "pause":
        dx = r * 0.34
        dy = r * 0.54
        painter.drawLine(QPointF(cx - dx, cy - dy), QPointF(cx - dx, cy + dy))
        painter.drawLine(QPointF(cx + dx, cy - dy), QPointF(cx + dx, cy + dy))
    elif kind == "check":
        painter.drawLine(QPointF(cx - r * 0.55, cy + r * 0.05), QPointF(cx - r * 0.1, cy + r * 0.5))
        painter.drawLine(QPointF(cx - r * 0.1, cy + r * 0.5), QPointF(cx + r * 0.65, cy - r * 0.45))
    elif kind == "all":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        s = r * 0.62
        painter.drawRoundedRect(QRectF(cx - r * 0.78, cy - r * 0.78, s, s), 2.0, 2.0)
        painter.drawRoundedRect(QRectF(cx + r * 0.16, cy - r * 0.78, s, s), 2.0, 2.0)
        painter.drawRoundedRect(QRectF(cx - r * 0.78, cy + r * 0.16, s, s), 2.0, 2.0)
        painter.drawRoundedRect(QRectF(cx + r * 0.16, cy + r * 0.16, s, s), 2.0, 2.0)
    elif kind == "chart":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        w = r * 0.42
        painter.drawRoundedRect(QRectF(cx - r * 0.85, cy - r * 0.1, w, r * 0.9), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(cx - w * 0.5, cy - r * 0.8, w, r * 1.6), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(cx + r * 0.43, cy - r * 0.42, w, r * 1.22), 1.5, 1.5)
    painter.restore()


class PulsingDot(QWidget):
    """Breathing halo dot indicating a live running Task Timer without words."""

    def __init__(
        self,
        color: QColor,
        *,
        size: int = 12,
        active: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = color
        self._active = active
        self._phase = 0.0
        self.setFixedSize(size, size)

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(1800)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._on_tick)
        if active:
            self._anim.start()

    def set_state(self, color: QColor, active: bool) -> None:
        """Update dot color and whether the halo pulse animation is running."""
        self._color = color
        if active and not self._active:
            self._active = True
            self._anim.start()
        elif not active and self._active:
            self._active = False
            self._anim.stop()
            self._phase = 0.0
        self.update()

    def _on_tick(self, value: object) -> None:
        self._phase = float(value) if isinstance(value, (int, float)) else 0.0
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)

        if self._active:
            pulse = 0.5 - 0.5 * math.cos(self._phase * math.tau)
            halo_r = 3.5 + 2.5 * pulse
            halo_col = QColor(self._color)
            halo_col.setAlphaF(0.28 * (1.0 - 0.55 * pulse))
            painter.setBrush(halo_col)
            painter.drawEllipse(center, halo_r, halo_r)

        painter.setBrush(self._color)
        painter.drawEllipse(center, 3.0, 3.0)
        painter.end()


class AnimatedStatusOrb(QAbstractButton):
    """Animated Task Status orb supporting button clicks and breathing Doing halo."""

    def __init__(
        self,
        status: TaskStatus = TaskStatus.TODO,
        tokens: ColorTokens = DARK_TOKENS,
        *,
        size: int = 20,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._status = status
        self._tokens = tokens
        self._hovered = False
        self._pressed = False
        self._pulse = 0.0
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(1800)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._on_pulse)
        if status == TaskStatus.DOING:
            self._anim.start()

    def set_state(self, status: TaskStatus, tokens: ColorTokens) -> None:
        """Update rendered TaskStatus and theme tokens."""
        self._status = status
        self._tokens = tokens
        if status == TaskStatus.DOING and self._anim.state() != QVariantAnimation.State.Running:
            self._anim.start()
        elif status != TaskStatus.DOING and self._anim.state() == QVariantAnimation.State.Running:
            self._anim.stop()
            self._pulse = 0.0
        self.update()

    def _on_pulse(self, value: object) -> None:
        self._pulse = float(value) if isinstance(value, (int, float)) else 0.0
        self.update()

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        scale = 0.88 if self._pressed else (1.07 if self._hovered else 1.0)
        painter.translate(center)
        painter.scale(scale, scale)
        painter.translate(-center)

        radius = 7.4
        if self._status == TaskStatus.DOING:
            accent = QColor(self._tokens.status_doing)
            breath = 0.5 - 0.5 * math.cos(self._pulse * math.tau)
            halo = QColor(accent)
            halo.setAlphaF(0.22 * (1.0 - 0.5 * breath))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(center, radius + 2.2 * breath, radius + 2.2 * breath)
            painter.setPen(QPen(accent, 1.6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius - 0.8, radius - 0.8)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent)
            painter.drawEllipse(center, 3.0, 3.0)
        elif self._status == TaskStatus.WAITING:
            amber = QColor(self._tokens.status_waiting)
            tint = QColor(amber)
            tint.setAlphaF(0.18)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tint)
            painter.drawEllipse(center, radius, radius)
            draw_vector_glyph(painter, "pause", center, 10.0, amber, stroke=1.7)
        elif self._status == TaskStatus.DONE:
            green = QColor(self._tokens.status_done)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(green)
            painter.drawEllipse(center, radius, radius)
            draw_vector_glyph(painter, "check", center, 10.0, QColor("#FFFFFF"), stroke=1.8)
        else:
            ring_color = QColor(
                self._tokens.text_secondary if self._hovered else self._tokens.text_muted
            )
            painter.setPen(QPen(ring_color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius - 0.8, radius - 0.8)
        painter.end()


class HoverOrbButton(QAbstractButton):
    """Circular 24px pill action orb with pointer-down squash animation."""

    def __init__(
        self,
        glyph: str,
        *,
        fg: QColor,
        bg: QColor,
        hover_bg: QColor,
        hover_fg: QColor | None = None,
        size: int = 24,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._glyph = glyph
        self._fg = fg
        self._bg = bg
        self._hover_bg = hover_bg
        self._hover_fg = hover_fg or QColor("#FFFFFF")
        self._hovered = False
        self._scale = 1.0
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._scale_anim = QVariantAnimation(self)
        self._scale_anim.setDuration(120)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_anim.valueChanged.connect(self._on_scale)

    def configure(
        self,
        *,
        glyph: str,
        fg: QColor,
        bg: QColor,
        hover_bg: QColor,
        hover_fg: QColor | None = None,
    ) -> None:
        """Update orb glyph and colors cleanly."""
        self._glyph = glyph
        self._fg = fg
        self._bg = bg
        self._hover_bg = hover_bg
        self._hover_fg = hover_fg or QColor("#FFFFFF")
        self.update()

    def _on_scale(self, value: object) -> None:
        self._scale = float(value) if isinstance(value, (int, float)) else 1.0
        self.update()

    def _animate_scale(self, target: float) -> None:
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(target)
        self._scale_anim.start()

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = False
        self._animate_scale(1.0)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._animate_scale(0.90)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._animate_scale(1.0)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        painter.translate(center)
        painter.scale(self._scale, self._scale)
        painter.translate(-center)

        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._hover_bg if self._hovered else self._bg)
        painter.drawEllipse(rect)
        draw_vector_glyph(
            painter,
            self._glyph,
            center,
            11.0,
            self._hover_fg if self._hovered else self._fg,
        )
        painter.end()
