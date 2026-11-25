"""Collapsed Task Row widget for the unified Task List."""

from datetime import datetime

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QMouseEvent, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from nyatodo.domain import Task, TaskStatus
from nyatodo.ui.icons import create_status_icon
from nyatodo.ui.theme import (
    DARK_TOKENS,
    ColorTokens,
    format_compact_duration,
    format_hms,
    make_mono_font,
    make_ui_font,
)


class _ElidedLabel(QLabel):
    """Single-line QLabel that cleanly elides overflowing text on the right."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(40)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self._update_elided()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._update_elided()

    def _update_elided(self) -> None:
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, max(10, self.width())
        )
        super().setText(elided)


class TaskRowWidget(QFrame):
    """40px-min-height Task row with status, timer, title, @Requester, and Sub-steps."""

    clicked = Signal(str)
    double_clicked = Signal(str)
    status_clicked = Signal(str)

    def __init__(
        self,
        task: Task,
        *,
        now: datetime,
        tokens: ColorTokens = DARK_TOKENS,
        selected: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TaskRow")
        self.setMinimumHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._task = task
        self._tokens = tokens
        self._selected = selected

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        self.status_button = QPushButton(self)
        self.status_button.setObjectName("TaskStatusButton")
        self.status_button.setFixedSize(20, 20)
        self.status_button.setIconSize(QSize(16, 16))
        self.status_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.status_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_button.clicked.connect(lambda: self.status_clicked.emit(self._task.id))
        layout.addWidget(self.status_button)

        self.timer_label = QLabel(self)
        self.timer_label.setObjectName("TaskTimerLabel")
        self.timer_label.setFont(make_mono_font(12, make_mono_font().weight()))
        layout.addWidget(self.timer_label)

        self.title_label = _ElidedLabel(task.title, self)
        self.title_label.setObjectName("TaskTitleLabel")
        layout.addWidget(self.title_label, 1)

        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        self.requester_pill = QLabel(self)
        self.requester_pill.setObjectName("RequesterPill")
        self.requester_pill.setFont(make_ui_font(11))
        self.requester_pill.setFixedHeight(20)
        self.requester_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.requester_pill.setMaximumWidth(108)
        meta_layout.addWidget(self.requester_pill)

        self.sub_step_label = QLabel(self)
        self.sub_step_label.setObjectName("SubStepCountLabel")
        self.sub_step_label.setFont(make_mono_font(10))
        meta_layout.addWidget(self.sub_step_label)

        layout.addLayout(meta_layout)

        self.update_task(task, now=now, tokens=tokens)
        self.set_selected(selected)

    @property
    def task_id(self) -> str:
        """Return the Task ID rendered by this row."""
        return self._task.id

    def is_selected(self) -> bool:
        """Return True if this row is keyboard-selected."""
        return self._selected

    def set_selected(self, selected: bool) -> None:
        """Update selection highlight and left 2px accent indicator."""
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def update_task(self, task: Task, *, now: datetime, tokens: ColorTokens) -> None:
        """Refresh all Task fields and styling."""
        self._task = task
        self._tokens = tokens

        self.status_button.setIcon(create_status_icon(task.status, tokens, 16))

        is_done = task.status == TaskStatus.DONE
        title_font = make_ui_font(13, make_ui_font().weight())
        title_font.setWeight(title_font.Weight.Medium)
        title_font.setStrikeOut(is_done)
        self.title_label.setFont(title_font)
        self.title_label.set_full_text(task.title)
        self.title_label.setProperty("done", is_done)
        self.title_label.style().unpolish(self.title_label)
        self.title_label.style().polish(self.title_label)

        if task.requester:
            metrics = QFontMetrics(self.requester_pill.font())
            pill_text = metrics.elidedText(f"@{task.requester}", Qt.TextElideMode.ElideRight, 94)
            self.requester_pill.setText(pill_text)
            self.requester_pill.setToolTip(f"@{task.requester}")
            self.requester_pill.setVisible(True)
        else:
            self.requester_pill.setVisible(False)

        total_steps = len(task.sub_steps)
        if total_steps > 0:
            self.sub_step_label.setText(f"{task.completed_sub_steps_count}/{total_steps}")
            self.sub_step_label.setVisible(True)
        else:
            self.sub_step_label.setVisible(False)

        self.refresh_timer(now=now)

    def refresh_timer(self, *, now: datetime) -> None:
        """Update only the timer readout on 1s ticks without rebuilding widgets."""
        total_seconds = self._task.total_logged_seconds(now=now)
        if self._task.is_timer_running:
            self.timer_label.setText(format_hms(total_seconds))
            self.timer_label.setProperty("paused", False)
            self.timer_label.setVisible(True)
        elif total_seconds > 0:
            self.timer_label.setText(format_compact_duration(total_seconds))
            self.timer_label.setProperty("paused", True)
            self.timer_label.setVisible(True)
        else:
            self.timer_label.setVisible(False)
        self.timer_label.style().unpolish(self.timer_label)
        self.timer_label.style().polish(self.timer_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._task.id)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._task.id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event: object) -> None:
        super().paintEvent(event)  # type: ignore[arg-type]
        if not self._selected:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._tokens.accent_primary))
        bar_rect = QRectF(1.0, 6.0, 2.0, max(8.0, float(self.height()) - 12.0))
        painter.drawRoundedRect(bar_rect, 1.0, 1.0)
        painter.end()
