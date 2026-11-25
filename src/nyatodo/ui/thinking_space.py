"""Expandable Thinking Space accordion for Title, Requester, Notes, Sub-steps, and Work Sessions."""

import re
from datetime import datetime

from PySide6.QtCore import QEvent, QObject, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from nyatodo.domain import SubStep, Task, TaskStatus, WorkSession
from nyatodo.ui.icons import create_close_icon, create_play_icon, create_stop_icon
from nyatodo.ui.theme import (
    DARK_TOKENS,
    ColorTokens,
    format_hms,
    make_mono_font,
    make_ui_font,
)

_DURATION_PART_RE = re.compile(r"^\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?\s*$", re.I)
_COLON_DURATION_RE = re.compile(r"^\s*(\d+):(\d{1,2})\s*$")


def parse_manual_duration(raw: str) -> int | None:
    """Parse manual duration expressions like '25m', '1h15m', '1:15', or '25' into seconds."""
    stripped = raw.strip()
    if not stripped:
        return None

    if stripped.isdigit():
        minutes = int(stripped)
        return minutes * 60 if minutes > 0 else None

    colon_match = _COLON_DURATION_RE.match(stripped)
    if colon_match:
        hours = int(colon_match.group(1))
        minutes = int(colon_match.group(2))
        if minutes >= 60:
            return None
        total = hours * 3600 + minutes * 60
        return total if total > 0 else None

    part_match = _DURATION_PART_RE.match(stripped)
    if part_match:
        h_str, m_str, s_str = part_match.groups()
        if any(part is not None for part in (h_str, m_str, s_str)):
            hours = int(h_str or 0)
            minutes = int(m_str or 0)
            seconds = int(s_str or 0)
            total = hours * 3600 + minutes * 60 + seconds
            return total if total > 0 else None

    return None


def _format_session_duration_short(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        mins, rem = divmod(seconds, 60)
        return f"{mins}m" if rem == 0 else f"{mins}m {rem}s"
    hours, rem = divmod(seconds, 3600)
    mins = rem // 60
    return f"{hours}h" if mins == 0 else f"{hours}h {mins}m"


class _SubStepCheckBox(QAbstractButton):
    """Crisp 14x14 rounded square checkbox with custom-painted checkmark."""

    def __init__(self, checked: bool, tokens: ColorTokens, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tokens = tokens

    def apply_theme(self, tokens: ColorTokens) -> None:
        self._tokens = tokens
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(1.0, 1.0, 14.0, 14.0)
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._tokens.accent_primary))
            painter.drawRoundedRect(box, 4.0, 4.0)
            pen = QPen(QColor("#FFFFFF"), 1.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(4, 8, 7, 11)
            painter.drawLine(7, 11, 12, 5)
        else:
            painter.setPen(QPen(QColor(self._tokens.border_subtle), 1.2))
            painter.setBrush(QColor(self._tokens.bg_window))
            painter.drawRoundedRect(box, 4.0, 4.0)
        painter.end()


class _SubStepRowWidget(QWidget):
    """Single checkable and inline-editable Sub-step row."""

    toggled = Signal(str)
    renamed = Signal(str, str)
    deleted = Signal(str)

    def __init__(
        self,
        step: SubStep,
        *,
        tokens: ColorTokens,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(26)
        self._step = step

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.checkbox = _SubStepCheckBox(step.is_done, tokens, self)
        self.checkbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.checkbox.clicked.connect(lambda: self.toggled.emit(self._step.id))
        layout.addWidget(self.checkbox)

        self.title_edit = QLineEdit(step.title, self)
        self.title_edit.setObjectName("SubStepTitleEdit")
        self.title_edit.setProperty("done", step.is_done)
        font = make_ui_font(12)
        font.setStrikeOut(step.is_done)
        self.title_edit.setFont(font)
        self.title_edit.editingFinished.connect(self._commit_rename)
        layout.addWidget(self.title_edit, 1)

        self.delete_button = QToolButton(self)
        self.delete_button.setObjectName("RowDeleteButton")
        self.delete_button.setFixedSize(20, 20)
        self.delete_button.setIcon(create_close_icon(QColor(tokens.text_muted), 10))
        self.delete_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.clicked.connect(lambda: self.deleted.emit(self._step.id))
        layout.addWidget(self.delete_button)

    def _commit_rename(self) -> None:
        text = " ".join(self.title_edit.text().split())
        if not text:
            self.title_edit.setText(self._step.title)
            return
        if text != self._step.title:
            self.renamed.emit(self._step.id, text)


class ThinkingSpaceWidget(QFrame):
    """Inline Thinking Space container nested under the expanded Task Row."""

    title_changed = Signal(str, str)
    requester_changed = Signal(str, object)
    status_changed = Signal(str, object)
    timer_toggled = Signal(str)
    notes_changed = Signal(str, str)
    sub_step_added = Signal(str, str)
    sub_step_toggled = Signal(str)
    sub_step_renamed = Signal(str, str)
    sub_step_deleted = Signal(str)
    time_adjusted = Signal(str, int)
    manual_session_added = Signal(str, int)
    session_deleted = Signal(str)
    collapse_requested = Signal()

    def __init__(
        self,
        task: Task,
        *,
        now: datetime,
        tokens: ColorTokens = DARK_TOKENS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ThinkingSpace")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._task = task
        self._now = now
        self._tokens = tokens
        self._loading = False
        self._notes_dirty = False

        self._notes_timer = QTimer(self)
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(400)
        self._notes_timer.timeout.connect(self._flush_notes)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Section A: Title + Requester + Status + Timer button
        self.title_edit = QLineEdit(self)
        self.title_edit.setObjectName("ThinkingTitleEdit")
        self.title_edit.setFixedHeight(26)
        title_font = make_ui_font(13, make_ui_font().weight())
        title_font.setWeight(title_font.Weight.DemiBold)
        self.title_edit.setFont(title_font)
        self.title_edit.setPlaceholderText("Task title")
        self.title_edit.editingFinished.connect(self._commit_title)
        root.addWidget(self.title_edit)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(6)

        self.requester_edit = QLineEdit(self)
        self.requester_edit.setObjectName("ThinkingRequesterEdit")
        self.requester_edit.setFont(make_ui_font(11))
        self.requester_edit.setPlaceholderText("+ @requester")
        self.requester_edit.setFixedSize(120, 22)
        self.requester_edit.editingFinished.connect(self._commit_requester)
        controls_row.addWidget(self.requester_edit)

        self._status_buttons: dict[TaskStatus, QPushButton] = {}
        for status_val, label in (
            (TaskStatus.TODO, "Todo"),
            (TaskStatus.WAITING, "Waiting"),
            (TaskStatus.DONE, "Done"),
        ):
            btn = QPushButton(label, self)
            btn.setObjectName("StatusChipButton")
            btn.setFixedHeight(24)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda _checked=False, s=status_val: self.status_changed.emit(self._task.id, s)
            )
            self._status_buttons[status_val] = btn
            controls_row.addWidget(btn)

        controls_row.addStretch(1)

        self.timer_button = QPushButton("Start Timer", self)
        self.timer_button.setObjectName("ThinkingTimerButton")
        self.timer_button.setFixedHeight(26)
        self.timer_button.setIconSize(QSize(12, 12))
        self.timer_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.timer_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timer_button.clicked.connect(lambda: self.timer_toggled.emit(self._task.id))
        controls_row.addWidget(self.timer_button)

        root.addLayout(controls_row)
        root.addWidget(self._make_divider())

        # Section B: Notes
        notes_header = QHBoxLayout()
        notes_header.setContentsMargins(0, 0, 0, 0)
        notes_title = QLabel("Notes", self)
        notes_title.setObjectName("SectionLabel")
        notes_header.addWidget(notes_title)
        notes_header.addStretch(1)
        self.saved_label = QLabel("Saved", self)
        self.saved_label.setObjectName("SavedStatusLabel")
        notes_header.addWidget(self.saved_label)
        root.addLayout(notes_header)

        self.notes_editor = QPlainTextEdit(self)
        self.notes_editor.setObjectName("NotesEditor")
        self.notes_editor.setFont(make_ui_font(13))
        self.notes_editor.setPlaceholderText("Capture context, links, or rough thoughts...")
        self.notes_editor.setFixedHeight(54)
        self.notes_editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.notes_editor.textChanged.connect(self._on_notes_text_changed)
        root.addWidget(self.notes_editor)

        root.addWidget(self._make_divider())

        # Section C: Sub-steps
        self.sub_steps_header = QLabel("Sub-steps", self)
        self.sub_steps_header.setObjectName("SectionLabel")
        root.addWidget(self.sub_steps_header)

        self.sub_steps_container = QWidget(self)
        self.sub_steps_container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.sub_steps_layout = QVBoxLayout(self.sub_steps_container)
        self.sub_steps_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.sub_steps_layout.setContentsMargins(0, 0, 0, 0)
        self.sub_steps_layout.setSpacing(4)
        root.addWidget(self.sub_steps_container)

        self.add_sub_step_input = QLineEdit(self)
        self.add_sub_step_input.setObjectName("AddSubStepInput")
        self.add_sub_step_input.setFont(make_ui_font(12))
        self.add_sub_step_input.setFixedHeight(26)
        self.add_sub_step_input.setPlaceholderText("+ Add sub-step...")
        self.add_sub_step_input.returnPressed.connect(self._on_add_sub_step)
        root.addWidget(self.add_sub_step_input)

        root.addWidget(self._make_divider())

        # Section D: Work Sessions
        sessions_header = QHBoxLayout()
        sessions_header.setContentsMargins(0, 0, 0, 0)
        sessions_header.setSpacing(4)

        self.sessions_header_label = QLabel("Work Sessions · 00:00:00", self)
        self.sessions_header_label.setObjectName("SectionLabel")
        self.sessions_header_label.setFont(make_mono_font(11))
        sessions_header.addWidget(self.sessions_header_label)
        sessions_header.addStretch(1)

        for label, delta in (("-10m", -600), ("+15m", 900), ("+30m", 1800)):
            chip = QPushButton(label, self)
            chip.setObjectName("SessionChip")
            chip.setFixedHeight(22)
            chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(
                lambda _checked=False, d=delta: self.time_adjusted.emit(self._task.id, d)
            )
            sessions_header.addWidget(chip)

        self.manual_toggle_button = QPushButton("+ Manual", self)
        self.manual_toggle_button.setObjectName("SessionChip")
        self.manual_toggle_button.setFixedHeight(22)
        self.manual_toggle_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.manual_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_toggle_button.clicked.connect(self.open_manual_entry)
        sessions_header.addWidget(self.manual_toggle_button)
        root.addLayout(sessions_header)

        self.manual_entry_row = QWidget(self)
        self.manual_entry_row.setVisible(False)
        manual_layout = QHBoxLayout(self.manual_entry_row)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(6)

        self.manual_duration_input = QLineEdit(self.manual_entry_row)
        self.manual_duration_input.setObjectName("ManualDurationInput")
        self.manual_duration_input.setFixedHeight(26)
        self.manual_duration_input.setPlaceholderText("e.g. 25m or 1:15")
        self.manual_duration_input.returnPressed.connect(self._submit_manual_entry)
        manual_layout.addWidget(self.manual_duration_input, 1)

        self.manual_add_button = QPushButton("Add", self.manual_entry_row)
        self.manual_add_button.setObjectName("SessionChip")
        self.manual_add_button.setFixedHeight(26)
        self.manual_add_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.manual_add_button.clicked.connect(self._submit_manual_entry)
        manual_layout.addWidget(self.manual_add_button)
        root.addWidget(self.manual_entry_row)

        self.sessions_scroll = QScrollArea(self)
        self.sessions_scroll.setObjectName("SessionListScroll")
        self.sessions_scroll.setWidgetResizable(True)
        self.sessions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sessions_scroll.setMaximumHeight(96)
        self.sessions_container = QWidget()
        self.sessions_container.setObjectName("SessionListContainer")
        self.sessions_layout = QVBoxLayout(self.sessions_container)
        self.sessions_layout.setContentsMargins(0, 0, 0, 0)
        self.sessions_layout.setSpacing(2)
        self.sessions_scroll.setWidget(self.sessions_container)
        root.addWidget(self.sessions_scroll)

        for editor in (
            self.title_edit,
            self.requester_edit,
            self.notes_editor,
            self.add_sub_step_input,
            self.manual_duration_input,
        ):
            editor.installEventFilter(self)

        self.update_task(task, now=now, tokens=tokens)

    @property
    def task_id(self) -> str:
        """Return Task ID bound to this Thinking Space."""
        return self._task.id

    def has_editor_focus(self) -> bool:
        """Return True if any input widget inside this Thinking Space holds focus."""
        focus_widget = self.window().focusWidget()
        return focus_widget is not None and self.isAncestorOf(focus_widget)

    def open_manual_entry(self) -> None:
        """Reveal and focus the inline manual Work Session input."""
        self.manual_entry_row.setVisible(True)
        self.manual_duration_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.manual_duration_input.selectAll()

    def flush_pending_saves(self) -> None:
        """Immediately flush debounced notes and inline title/requester edits."""
        self._notes_timer.stop()
        self._flush_notes()
        self._commit_title()
        self._commit_requester()

    def update_task(self, task: Task, *, now: datetime, tokens: ColorTokens) -> None:
        """Synchronize all Thinking Space widgets to the latest Task snapshot."""
        self._loading = True
        try:
            self._task = task
            self._now = now
            self._tokens = tokens

            if not self.title_edit.hasFocus():
                self.title_edit.setText(task.title)
            if not self.requester_edit.hasFocus():
                self.requester_edit.setText(f"@{task.requester}" if task.requester else "")
            if not self.notes_editor.hasFocus() and self.notes_editor.toPlainText() != task.notes:
                self.notes_editor.setPlainText(task.notes)
                self._notes_dirty = False
                self.saved_label.setText("Saved")

            for status_val, btn in self._status_buttons.items():
                btn.setProperty("active", task.status == status_val)
                btn.style().unpolish(btn)
                btn.style().polish(btn)

            self._rebuild_sub_steps()
            self._rebuild_sessions()
            self.refresh_timer(now=now)
        finally:
            self._loading = False

    def refresh_timer(self, *, now: datetime) -> None:
        """Refresh running timer button and Work Sessions totals on 1s ticks."""
        self._now = now
        total_secs = self._task.total_logged_seconds(now=now)
        self.sessions_header_label.setText(f"Work Sessions · {format_hms(total_secs)}")

        if self._task.is_timer_running:
            self.timer_button.setText(f"Stop {format_hms(total_secs)}")
            self.timer_button.setIcon(create_stop_icon(QColor(self._tokens.status_doing), 12))
            self.timer_button.setProperty("running", True)
        else:
            self.timer_button.setText("Start Timer")
            self.timer_button.setIcon(create_play_icon(QColor(self._tokens.text_primary), 12))
            self.timer_button.setProperty("running", False)
        self.timer_button.style().unpolish(self.timer_button)
        self.timer_button.style().polish(self.timer_button)

        for idx in range(self.sessions_layout.count()):
            item = self.sessions_layout.itemAt(idx)
            if item is None:
                continue
            row_widget = item.widget()
            if row_widget is None:
                continue
            session_id = row_widget.property("session_id")
            label = row_widget.findChild(QLabel, "SessionRowLabel")
            if isinstance(session_id, str) and label is not None:
                session = next(
                    (s for s in self._task.work_sessions if s.id == session_id),
                    None,
                )
                if session is not None and session.is_running:
                    label.setText(self._format_session_line(session, now=now))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event = event
            assert isinstance(key_event, QKeyEvent)
            if key_event.key() == Qt.Key.Key_Escape:
                self.flush_pending_saves()
                self.collapse_requested.emit()
                return True
            if (
                key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and key_event.modifiers() & Qt.KeyboardModifier.ControlModifier
            ):
                self.flush_pending_saves()
                self.collapse_requested.emit()
                return True
        elif event.type() == QEvent.Type.FocusOut and watched is self.notes_editor:
            self._notes_timer.stop()
            self._flush_notes()
        return super().eventFilter(watched, event)

    def _make_divider(self) -> QFrame:
        line = QFrame(self)
        line.setObjectName("SectionDivider")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _commit_title(self) -> None:
        if self._loading:
            return
        cleaned = " ".join(self.title_edit.text().split())
        if not cleaned:
            self.title_edit.setText(self._task.title)
            return
        if cleaned != self._task.title:
            self.title_changed.emit(self._task.id, cleaned)

    def _commit_requester(self) -> None:
        if self._loading:
            return
        raw = self.requester_edit.text().strip().lstrip("@")
        new_req: str | None = raw or None
        if new_req != self._task.requester:
            self.requester_changed.emit(self._task.id, new_req)

    def _on_notes_text_changed(self) -> None:
        if self._loading:
            return
        self._notes_dirty = True
        self.saved_label.setText("Saving...")
        self._notes_timer.start()

    def _flush_notes(self) -> None:
        if self._loading or not self._notes_dirty:
            return
        self._notes_dirty = False
        text = self.notes_editor.toPlainText()
        self.saved_label.setText("Saved")
        if text != self._task.notes:
            self.notes_changed.emit(self._task.id, text)

    def _on_add_sub_step(self) -> None:
        text = " ".join(self.add_sub_step_input.text().split())
        if not text:
            return
        self.add_sub_step_input.clear()
        self.sub_step_added.emit(self._task.id, text)
        self.add_sub_step_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _submit_manual_entry(self) -> None:
        seconds = parse_manual_duration(self.manual_duration_input.text())
        if seconds is None:
            return
        self.manual_duration_input.clear()
        self.manual_entry_row.setVisible(False)
        self.manual_session_added.emit(self._task.id, seconds)

    def _rebuild_sub_steps(self) -> None:
        while self.sub_steps_layout.count():
            item = self.sub_steps_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                widget = item.widget()
                assert widget is not None
                widget.setParent(None)
                widget.deleteLater()

        done_count = self._task.completed_sub_steps_count
        total_count = len(self._task.sub_steps)
        self.sub_steps_header.setText(f"Sub-steps · {done_count}/{total_count}")

        for step in self._task.sub_steps:
            row = _SubStepRowWidget(step, tokens=self._tokens, parent=self.sub_steps_container)
            row.toggled.connect(self.sub_step_toggled)
            row.renamed.connect(self.sub_step_renamed)
            row.deleted.connect(self.sub_step_deleted)
            row.title_edit.installEventFilter(self)
            self.sub_steps_layout.addWidget(row)

    def _rebuild_sessions(self) -> None:
        while self.sessions_layout.count():
            item = self.sessions_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                widget = item.widget()
                assert widget is not None
                widget.setParent(None)
                widget.deleteLater()

        sessions = sorted(
            self._task.work_sessions,
            key=lambda s: (not s.is_running, s.started_at),
            reverse=False,
        )
        # Show newest / active first
        ordered = sorted(sessions, key=lambda s: s.started_at, reverse=True)
        ordered.sort(key=lambda s: not s.is_running)

        if not ordered:
            empty = QLabel("No Work Sessions logged yet.", self.sessions_container)
            empty.setObjectName("SessionRowLabel")
            self.sessions_layout.addWidget(empty)
            self.sessions_scroll.setFixedHeight(26)
            return

        for session in ordered:
            row = QWidget(self.sessions_container)
            row.setFixedHeight(22)
            row.setProperty("session_id", session.id)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            label = QLabel(self._format_session_line(session, now=self._now), row)
            label.setObjectName("SessionRowLabel")
            label.setProperty("running", session.is_running)
            label.setFont(make_mono_font(11))
            row_layout.addWidget(label, 1)

            delete_btn = QToolButton(row)
            delete_btn.setObjectName("RowDeleteButton")
            delete_btn.setFixedSize(18, 18)
            delete_btn.setIcon(create_close_icon(QColor(self._tokens.text_muted), 10))
            delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.clicked.connect(
                lambda _checked=False, sid=session.id: self.session_deleted.emit(sid)
            )
            row_layout.addWidget(delete_btn)
            self.sessions_layout.addWidget(row)

        visible_rows = min(4, len(ordered))
        self.sessions_scroll.setFixedHeight(visible_rows * 24 + 4)

    @staticmethod
    def _format_session_line(session: WorkSession, *, now: datetime) -> str:
        start_local = session.started_at.astimezone().strftime("%H:%M")
        dur_secs = session.duration_seconds(now=now)
        if session.is_running:
            return f"{start_local} - now ({format_hms(dur_secs)}) · Timer"
        assert session.ended_at is not None
        end_local = session.ended_at.astimezone().strftime("%H:%M")
        dur_label = _format_session_duration_short(dur_secs)
        kind = "Manual" if session.is_manual else "Timer"
        return f"{start_local} - {end_local} · {dur_label} · {kind}"
