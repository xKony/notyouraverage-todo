"""Non-modal Idle Check top banner for Keep / Trim resolution."""

from datetime import datetime

from PySide6.QtCore import Qt, Signal
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
        self.icon_label.setPixmap(create_clock_pixmap(QColor(tokens.status_waiting), 14))

    def show_idle_gap(self, gap: IdleGap, task_titles: list[str]) -> None:
        """Populate and display the Idle Check banner without stealing keyboard focus."""
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
        self.setVisible(True)

    def dismiss(self) -> None:
        """Hide the Idle Check banner and clear pending state."""
        self._idle_started_at = None
        self.setVisible(False)

    def _on_keep_clicked(self) -> None:
        self.dismiss()
        self.keep_requested.emit()

    def _on_trim_clicked(self) -> None:
        started_at = self._idle_started_at
        self.dismiss()
        if started_at is not None:
            self.trim_requested.emit(started_at)
