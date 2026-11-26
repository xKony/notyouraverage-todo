"""Non-modal Idle Check top banner for Keep / Trim resolution."""

from datetime import datetime

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from nyatodo.domain import IdleGap
from nyatodo.ui.icons import create_clock_pixmap
from nyatodo.ui.theme import DARK_TOKENS, ColorTokens, make_ui_font


class IdleBanner(QFrame):
    """Calm non-modal banner surfaced when idle duration exceeds configured threshold."""

    keep_requested = Signal()
    trim_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("IdleBanner")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVisible(False)

        self._tokens: ColorTokens = DARK_TOKENS
        self._idle_started_at: datetime | None = None
        self._dismissing = False

        self._height_anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._height_anim.setDuration(160)
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._height_anim.finished.connect(self._on_height_anim_finished)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(14, 14)
        layout.addWidget(self.icon_label)

        self.message_label = QLabel(self)
        self.message_label.setObjectName("IdleBannerText")
        self.message_label.setFont(make_ui_font(12))
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)

        self.keep_button = QPushButton("Keep", self)
        self.keep_button.setObjectName("IdleKeepButton")
        self.keep_button.setFixedHeight(24)
        self.keep_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.keep_button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.keep_button)

        self.trim_button = QPushButton("Trim", self)
        self.trim_button.setObjectName("IdleTrimButton")
        self.trim_button.setFixedHeight(24)
        self.trim_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.trim_button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.trim_button)

        self.keep_button.clicked.connect(self._on_keep_clicked)
        self.trim_button.clicked.connect(self._on_trim_clicked)

        self.apply_theme(DARK_TOKENS)

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Refresh icon tint for current theme."""
        self._tokens = tokens
        self.icon_label.setPixmap(
            create_clock_pixmap(QColor(tokens.status_waiting), 14, dpr=self.devicePixelRatioF())
        )

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            self.icon_label.setPixmap(
                create_clock_pixmap(
                    QColor(self._tokens.status_waiting), 14, dpr=self.devicePixelRatioF()
                )
            )

    def show_idle_gap(self, gap: IdleGap, task_titles: list[str]) -> None:
        """Populate and reveal the Idle Check banner without stealing keyboard focus."""
        self._idle_started_at = gap.idle_started_at
        idle_minutes = max(1, gap.idle_seconds // 60)

        if not task_titles:
            target = "active timer"
        elif len(task_titles) == 1:
            target = f"'{task_titles[0]}'"
        else:
            target = f"'{task_titles[0]}' (+{len(task_titles) - 1} more)"

        self.message_label.setText(f"Idle for {idle_minutes}m on {target}. Keep or trim?")
        self.trim_button.setText(f"Trim {idle_minutes}m")

        self._height_anim.stop()
        self._dismissing = False
        self.setMaximumHeight(16777215)
        target_height = max(40, self.sizeHint().height())
        self.setMaximumHeight(0)
        self.setVisible(True)
        self._height_anim.setStartValue(0)
        self._height_anim.setEndValue(target_height)
        self._height_anim.start()

    def dismiss(self) -> None:
        """Animate-collapse and hide the Idle Check banner, clearing pending state."""
        self._idle_started_at = None
        if not self.isVisible():
            self._height_anim.stop()
            self._dismissing = False
            self.setMaximumHeight(16777215)
            return
        if self._dismissing:
            return
        self._height_anim.stop()
        self._dismissing = True
        start_height = max(self.height(), 1)
        self._height_anim.setStartValue(start_height)
        self._height_anim.setEndValue(0)
        self._height_anim.start()

    def _on_height_anim_finished(self) -> None:
        if self._dismissing:
            self._dismissing = False
            self.setVisible(False)
        self.setMaximumHeight(16777215)

    def _on_keep_clicked(self) -> None:
        self.dismiss()
        self.keep_requested.emit()

    def _on_trim_clicked(self) -> None:
        started_at = self._idle_started_at
        self.dismiss()
        if started_at is not None:
            self.trim_requested.emit(started_at)
