"""Morph-Pill Task Row widget with Poppins weight play and hover action orbs."""

from datetime import datetime, tzinfo

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QEnterEvent, QFont, QFontMetrics, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from nyatodo.domain import (
    Task,
    TaskStatus,
    format_task_added_tooltip,
    format_task_date_pill,
)
from nyatodo.ui.icons import create_close_icon
from nyatodo.ui.pill_widgets import AnimatedStatusOrb, HoverOrbButton
from nyatodo.ui.qt_helpers import set_qss_property
from nyatodo.ui.theme import (
    DARK_TOKENS,
    ColorTokens,
    format_compact_duration,
    format_hms,
    make_ui_font,
)


def _rgba_or_hex(spec: str) -> QColor:
    text = spec.strip()
    if text.startswith("rgba(") and text.endswith(")"):
        parts = [p.strip() for p in text[5:-1].split(",")]
        if len(parts) == 4:
            col = QColor(int(parts[0]), int(parts[1]), int(parts[2]))
            col.setAlphaF(max(0.0, min(1.0, float(parts[3]))))
            return col
    return QColor(text)


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
    """Minimalist pill Task row with animated status orb, timer pill, and hover action orbs."""

    clicked = Signal(str)
    double_clicked = Signal(str)
    status_clicked = Signal(str)
    timer_clicked = Signal(str)
    wait_clicked = Signal(str)
    delete_requested = Signal(str)

    def __init__(
        self,
        task: Task,
        *,
        now: datetime,
        tokens: ColorTokens = DARK_TOKENS,
        selected: bool = False,
        local_tz: tzinfo | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TaskRow")
        self.setMinimumHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._task = task
        self._tokens = tokens
        self._selected = selected
        self._local_tz = local_tz

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 10, 7)
        layout.setSpacing(8)

        self.status_button = AnimatedStatusOrb(task.status, tokens, size=20, parent=self)
        self.status_button.setObjectName("TaskStatusButton")
        self.status_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.status_button.clicked.connect(lambda: self.status_clicked.emit(self._task.id))
        layout.addWidget(self.status_button)

        self.title_label = _ElidedLabel(task.title, self)
        self.title_label.setObjectName("TaskTitleLabel")
        layout.addWidget(self.title_label, 1)

        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        self.date_pill = QLabel(self)
        self.date_pill.setObjectName("TaskDatePill")
        self.date_pill.setFont(make_ui_font(10, QFont.Weight.Medium))
        self.date_pill.setFixedHeight(22)
        self.date_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta_layout.addWidget(self.date_pill)

        self.requester_pill = QLabel(self)
        self.requester_pill.setObjectName("RequesterPill")
        self.requester_pill.setFont(make_ui_font(10, QFont.Weight.Medium))
        self.requester_pill.setFixedHeight(22)
        self.requester_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.requester_pill.setMaximumWidth(116)
        meta_layout.addWidget(self.requester_pill)

        self.sub_step_label = QLabel(self)
        self.sub_step_label.setObjectName("SubStepCountLabel")
        self.sub_step_label.setFont(make_ui_font(10, QFont.Weight.Medium))
        self.sub_step_label.setFixedHeight(22)
        self.sub_step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta_layout.addWidget(self.sub_step_label)

        self.timer_label = QLabel(self)
        self.timer_label.setObjectName("TaskTimerLabel")
        self.timer_label.setFont(make_ui_font(11, QFont.Weight.Bold))
        self.timer_label.setFixedHeight(22)
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta_layout.addWidget(self.timer_label)

        self.timer_orb = HoverOrbButton(
            "play",
            fg=_rgba_or_hex(tokens.accent_primary),
            bg=_rgba_or_hex(tokens.tint_accent),
            hover_bg=_rgba_or_hex(tokens.accent_primary),
            size=24,
            parent=self,
        )
        self.timer_orb.setObjectName("RowTimerOrb")
        self.timer_orb.setToolTip("Toggle timer")
        self.timer_orb.setVisible(False)
        self.timer_orb.clicked.connect(lambda: self.timer_clicked.emit(self._task.id))
        meta_layout.addWidget(self.timer_orb)

        self.wait_orb = HoverOrbButton(
            "pause",
            fg=_rgba_or_hex(tokens.status_waiting),
            bg=_rgba_or_hex(tokens.tint_waiting),
            hover_bg=_rgba_or_hex(tokens.status_waiting),
            size=24,
            parent=self,
        )
        self.wait_orb.setObjectName("RowWaitOrb")
        self.wait_orb.setToolTip("Toggle waiting")
        self.wait_orb.setVisible(False)
        self.wait_orb.clicked.connect(lambda: self.wait_clicked.emit(self._task.id))
        meta_layout.addWidget(self.wait_orb)

        self.delete_button = QToolButton(self)
        self.delete_button.setObjectName("RowDeleteButton")
        self.delete_button.setFixedSize(20, 20)
        self.delete_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setToolTip("Delete task")
        self.delete_button.setVisible(False)
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self._task.id))
        meta_layout.addWidget(self.delete_button)

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
        """Update pill selection highlight."""
        self._selected = selected
        set_qss_property(self, "selected", selected)
        self.update()

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Refresh orb tints and icons for updated theme tokens."""
        self._tokens = tokens
        self.status_button.set_state(self._task.status, tokens)
        self._sync_hover_orbs()
        self.delete_button.setIcon(create_close_icon(QColor(tokens.text_muted), 10))
        self.update()

    def update_task(
        self,
        task: Task,
        *,
        now: datetime,
        tokens: ColorTokens,
        local_tz: tzinfo | None = None,
    ) -> None:
        """Refresh all Task fields and Poppins weight hierarchy."""
        self._task = task
        self._tokens = tokens
        if local_tz is not None:
            self._local_tz = local_tz

        set_qss_property(self, "doing", task.status == TaskStatus.DOING)
        self.status_button.set_state(task.status, tokens)
        self.delete_button.setIcon(create_close_icon(QColor(tokens.text_muted), 10))
        self._sync_hover_orbs()

        is_done = task.status == TaskStatus.DONE
        weight = (
            QFont.Weight.ExtraLight
            if is_done
            else (QFont.Weight.DemiBold if task.status == TaskStatus.DOING else QFont.Weight.Normal)
        )
        title_font = make_ui_font(13, weight)
        title_font.setStrikeOut(is_done)
        self.title_label.setFont(title_font)
        self.title_label.set_full_text(task.title)
        set_qss_property(self.title_label, "done", is_done)

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

        self._refresh_date_pill(now=now)
        self.refresh_timer(now=now)

    def _refresh_date_pill(self, *, now: datetime) -> None:
        label = format_task_date_pill(self._task.created_at, now=now, tz=self._local_tz)
        if self.date_pill.text() != label:
            self.date_pill.setText(label)
        tooltip = format_task_added_tooltip(self._task.created_at, tz=self._local_tz)
        if self.date_pill.toolTip() != tooltip:
            self.date_pill.setToolTip(tooltip)

    def refresh_timer(self, *, now: datetime) -> None:
        """Update only the timer pill readout on 1s ticks without rebuilding widgets."""
        self._refresh_date_pill(now=now)
        if self._task.is_timer_running:
            active_seconds = self._task.active_session_seconds(now=now)
            self.timer_label.setText(format_hms(active_seconds))
            self.timer_label.setFont(make_ui_font(11, QFont.Weight.Bold))
            set_qss_property(self.timer_label, "paused", False)
            self.timer_label.setVisible(True)
            return

        total_seconds = self._task.total_logged_seconds(now=now)
        if total_seconds > 0:
            self.timer_label.setText(format_compact_duration(total_seconds))
            self.timer_label.setFont(make_ui_font(10, QFont.Weight.Medium))
            set_qss_property(self.timer_label, "paused", True)
            self.timer_label.setVisible(True)
        else:
            self.timer_label.setVisible(False)

    def _sync_hover_orbs(self) -> None:
        t = self._tokens
        self.timer_orb.configure(
            glyph="stop" if self._task.is_timer_running else "play",
            fg=_rgba_or_hex(t.accent_primary),
            bg=_rgba_or_hex(t.tint_accent),
            hover_bg=_rgba_or_hex(t.accent_primary),
        )
        self.wait_orb.configure(
            glyph="pause",
            fg=_rgba_or_hex(t.status_waiting),
            bg=_rgba_or_hex(t.tint_waiting),
            hover_bg=_rgba_or_hex(t.status_waiting),
        )

    def enterEvent(self, event: QEnterEvent) -> None:
        if self._task.status != TaskStatus.DONE:
            self.timer_orb.setVisible(True)
            self.wait_orb.setVisible(True)
        self.delete_button.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.timer_orb.setVisible(False)
        self.wait_orb.setVisible(False)
        self.delete_button.setVisible(False)
        super().leaveEvent(event)

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
