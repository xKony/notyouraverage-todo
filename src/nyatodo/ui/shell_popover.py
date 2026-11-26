"""Shared animated floating popover base class inside MainWindow.shell."""

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QFrame, QWidget

from nyatodo.ui.theme import DARK_TOKENS, ColorTokens


class AnimatedShellPopover(QFrame):
    """Floating shell-owned popover with smooth height reveal and outside-click dismissal."""

    closed = Signal()

    def __init__(self, parent: QWidget | None = None, *, width: int) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(width)
        self.setVisible(False)

        self._tokens: ColorTokens = DARK_TOKENS
        self._closing = False
        self._toggle_button: QWidget | None = None
        self._filter_installed = False

        self._height_anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._height_anim.setDuration(160)
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._height_anim.valueChanged.connect(self._on_anim_value_changed)
        self._height_anim.finished.connect(self._on_anim_finished)

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Refresh stored theme tokens."""
        self._tokens = tokens
        self.update()

    def set_toggle_button(self, button: QWidget | None) -> None:
        """Register the toggle button so outside-click dismissal ignores it."""
        self._toggle_button = button

    def reposition(self, anchor_widget: QWidget) -> None:
        """Position popover cleanly inside parent shell below anchor_widget."""
        parent = self.parentWidget()
        if parent is None:
            return
        anchor_bottom_right = anchor_widget.mapTo(
            parent, QPoint(anchor_widget.width(), anchor_widget.height())
        )
        x = anchor_bottom_right.x() - self.width()
        x = max(12, min(x, parent.width() - self.width() - 12))
        y = anchor_bottom_right.y() + 6
        self.move(x, y)

    def _start_open_animation(self, anchor_widget: QWidget, *, min_height: int = 80) -> None:
        self._height_anim.stop()
        self._closing = False
        self.setMaximumHeight(16777215)
        if (layout := self.layout()) is not None:
            layout.activate()
        target_height = max(min_height, self.sizeHint().height())
        self.reposition(anchor_widget)
        self.setMaximumHeight(0)
        self.resize(self.width(), 0)
        self.setVisible(True)
        self.raise_()
        self._install_outside_filter()

        self._height_anim.setStartValue(0)
        self._height_anim.setEndValue(target_height)
        self._height_anim.start()

    def _fit_open_height(self) -> None:
        if self.isVisible() and not self._closing:
            if self._height_anim.state() == QAbstractAnimation.State.Running:
                self._height_anim.stop()
            self.setMaximumHeight(16777215)
            self.adjustSize()

    def close_popover(self) -> None:
        """Animate-collapse and hide the popover."""
        self._remove_outside_filter()
        if not self.isVisible():
            self._height_anim.stop()
            self._closing = False
            self.setMaximumHeight(16777215)
            return
        if self._closing:
            return
        self._height_anim.stop()
        self._closing = True
        start_height = max(self.height(), 1)
        self._height_anim.setStartValue(start_height)
        self._height_anim.setEndValue(0)
        self._height_anim.start()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_popover()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            self.isVisible()
            and not self._closing
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
        ):
            if QApplication.activePopupWidget() is not None:
                return False
            global_pos = event.globalPosition().toPoint()
            local_pos = self.mapFromGlobal(global_pos)
            in_popover = self.rect().contains(local_pos)
            in_toggle = False
            if self._toggle_button is not None:
                toggle_pos = self._toggle_button.mapFromGlobal(global_pos)
                in_toggle = self._toggle_button.rect().contains(toggle_pos)
            if not in_popover and not in_toggle:
                self.close_popover()
        return super().eventFilter(watched, event)

    def _install_outside_filter(self) -> None:
        if self._filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._filter_installed = True

    def _remove_outside_filter(self) -> None:
        if not self._filter_installed:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._filter_installed = False

    def _on_anim_value_changed(self, value: object) -> None:
        if isinstance(value, int):
            self.resize(self.width(), max(0, value))

    def _on_anim_finished(self) -> None:
        if self._closing:
            self._closing = False
            self.setVisible(False)
            self.setMaximumHeight(16777215)
            self.closed.emit()
            return
        self.setMaximumHeight(16777215)
        self.adjustSize()
