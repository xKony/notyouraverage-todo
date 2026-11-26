"""Expandable Thinking Space accordion for Title, Requester, Notes, Sub-steps, and Work Sessions."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, tzinfo
from enum import StrEnum

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QEnterEvent, QFont, QKeyEvent, QPainter, QPen, QTextCursor
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

from nyatodo.domain import SubStep, Task, TaskStatus, WorkSession, format_task_added_full
from nyatodo.ui.icons import create_close_icon, create_play_icon, create_stop_icon
from nyatodo.ui.qt_helpers import clear_layout, set_qss_property
from nyatodo.ui.requester_autocomplete_popup import RequesterAutocompletePopup
from nyatodo.ui.theme import (
    DARK_TOKENS,
    ColorTokens,
    format_hms,
    make_ui_font,
)


class ThinkingField(StrEnum):
    """Directly focusable fields inside a Thinking Space."""

    TITLE = "title"
    REQUESTER = "requester"
    NOTES = "notes"
    SUB_STEP = "sub_step"


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
        self.setObjectName("SubStepCheckBox")
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
            painter.drawRoundedRect(box, 7.0, 7.0)
            pen = QPen(QColor("#FFFFFF"), 1.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(4, 8, 7, 11)
            painter.drawLine(7, 11, 12, 5)
        else:
            painter.setPen(QPen(QColor(self._tokens.border_subtle), 1.3))
            painter.setBrush(QColor(self._tokens.bg_window))
            painter.drawRoundedRect(box, 7.0, 7.0)
        painter.end()


class _HoverDeleteRow(QWidget):
    """Row widget revealing its delete button only while hovered."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hover_delete_button: QToolButton | None = None

    def register_delete_button(self, button: QToolButton) -> None:
        """Bind the hover-revealed delete button and start hidden."""
        self._hover_delete_button = button
        button.setVisible(False)

    def enterEvent(self, event: QEnterEvent) -> None:
        if self._hover_delete_button is not None:
            self._hover_delete_button.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        if self._hover_delete_button is not None:
            self._hover_delete_button.setVisible(False)
        super().leaveEvent(event)


class _SubStepRowWidget(_HoverDeleteRow):
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
        self.setObjectName("SubStepRow")
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
        set_qss_property(self.title_edit, "done", step.is_done)
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
        self.register_delete_button(self.delete_button)

    def _commit_rename(self) -> None:
        text = " ".join(self.title_edit.text().split())
        if not text:
            self.title_edit.setText(self._step.title)
            return
        if text != self._step.title:
            self._step = replace(self._step, title=text)
            self.renamed.emit(self._step.id, text)


class _WorkSessionRowWidget(_HoverDeleteRow):
    """Single recorded Work Session row with hover-only delete button."""

    deleted = Signal(str)

    def __init__(
        self,
        session: WorkSession,
        *,
        line_text: str,
        tokens: ColorTokens,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WorkSessionRow")
        self.setFixedHeight(22)
        self.setProperty("session_id", session.id)

        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        self.line_label = QLabel(line_text, self)
        self.line_label.setObjectName("SessionRowLabel")
        self.line_label.setProperty("running", session.is_running)
        self.line_label.setFont(make_ui_font(11))
        row_layout.addWidget(self.line_label, 1)

        self.delete_button = QToolButton(self)
        self.delete_button.setObjectName("RowDeleteButton")
        self.delete_button.setFixedSize(20, 20)
        self.delete_button.setIcon(create_close_icon(QColor(tokens.text_muted), 10))
        self.delete_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.clicked.connect(lambda: self.deleted.emit(session.id))
        row_layout.addWidget(self.delete_button)
        self.register_delete_button(self.delete_button)


class _RequesterLineEdit(QLineEdit):
    """Inline Requester input keeping Tab inside the editor while autocomplete is visible."""

    def __init__(
        self,
        is_popup_visible: Callable[[], bool],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._is_popup_visible = is_popup_visible

    def event(self, event: QEvent) -> bool:
        if (
            self._is_popup_visible()
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() == Qt.Key.Key_Tab
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            self.keyPressEvent(event)
            if event.isAccepted():
                return True
        return super().event(event)


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
    manual_session_requested = Signal(str, str)
    session_deleted = Signal(str)
    collapse_requested = Signal()
    expand_finished = Signal()
    editor_focus_changed = Signal()

    def __init__(
        self,
        task: Task,
        *,
        now: datetime,
        tokens: ColorTokens = DARK_TOKENS,
        local_tz: tzinfo | None = None,
        requester_suggester: Callable[[str], list[str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ThinkingSpace")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._task = task
        self._now = now
        self._tokens = tokens
        self._local_tz = local_tz
        self._requester_suggester = requester_suggester
        self._loading = False
        self._notes_dirty = False
        self._collapsing = False
        self._collapse_callback: Callable[[], None] | None = None

        self.requester_popup = RequesterAutocompletePopup(self)
        self.requester_popup.apply_theme(tokens)
        self.requester_popup.requester_selected.connect(self._apply_requester_suggestion)

        self._notes_timer = QTimer(self)
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(400)
        self._notes_timer.timeout.connect(self._flush_notes)

        self._height_anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._height_anim.setDuration(160)
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._height_anim.finished.connect(self._on_height_anim_finished)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(12, 10, 12, 10)
        self._root_layout.setSpacing(8)

        self._build_header_section(self._root_layout)
        self._root_layout.addWidget(self._make_divider())
        self._build_notes_section(self._root_layout)
        self._root_layout.addWidget(self._make_divider())
        self._build_sub_steps_section(self._root_layout)
        self._root_layout.addWidget(self._make_divider())
        self._build_sessions_section(self._root_layout)
        self._install_editor_filters()

        self.update_task(task, now=now, tokens=tokens, local_tz=local_tz)

    def _build_header_section(self, root: QVBoxLayout) -> None:
        self.title_edit = QLineEdit(self)
        self.title_edit.setObjectName("ThinkingTitleEdit")
        self.title_edit.setFixedHeight(26)
        self.title_edit.setFont(make_ui_font(13, QFont.Weight.DemiBold))
        self.title_edit.setPlaceholderText("Task title")
        self.title_edit.editingFinished.connect(self._commit_title)
        root.addWidget(self.title_edit)

        self.added_meta_label = QLabel(self)
        self.added_meta_label.setObjectName("ThinkingAddedLabel")
        self.added_meta_label.setFont(make_ui_font(11))
        root.addWidget(self.added_meta_label)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(6)

        self.requester_edit = _RequesterLineEdit(self.is_requester_popup_visible, self)
        self.requester_edit.setObjectName("ThinkingRequesterEdit")
        self.requester_edit.setFont(make_ui_font(11))
        self.requester_edit.setPlaceholderText("+ @requester")
        self.requester_edit.setFixedSize(120, 22)
        self.requester_edit.textEdited.connect(self._on_requester_text_edited)
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

    def _build_notes_section(self, root: QVBoxLayout) -> None:
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
        self.notes_editor.setTabChangesFocus(True)
        self.notes_editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.notes_editor.textChanged.connect(self._on_notes_text_changed)
        root.addWidget(self.notes_editor)

    def _build_sub_steps_section(self, root: QVBoxLayout) -> None:
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

    def _build_sessions_section(self, root: QVBoxLayout) -> None:
        sessions_header = QHBoxLayout()
        sessions_header.setContentsMargins(0, 0, 0, 0)
        sessions_header.setSpacing(4)

        self.sessions_header_label = QLabel("Work Sessions · 00:00:00", self)
        self.sessions_header_label.setObjectName("SectionLabel")
        self.sessions_header_label.setFont(make_ui_font(11, QFont.Weight.DemiBold))
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
        self.manual_duration_input.setPlaceholderText("25m or 14:10-14:40")
        self.manual_duration_input.returnPressed.connect(self._submit_manual_entry)
        manual_layout.addWidget(self.manual_duration_input, 1)

        self.manual_add_button = QPushButton("Add", self.manual_entry_row)
        self.manual_add_button.setObjectName("SessionChip")
        self.manual_add_button.setFixedHeight(26)
        self.manual_add_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.manual_add_button.clicked.connect(self._submit_manual_entry)
        manual_layout.addWidget(self.manual_add_button)
        root.addWidget(self.manual_entry_row)

        self.manual_error_label = QLabel(self)
        self.manual_error_label.setObjectName("SettingsErrorLabel")
        self.manual_error_label.setVisible(False)
        root.addWidget(self.manual_error_label)

        self.sessions_scroll = QScrollArea(self)
        self.sessions_scroll.setObjectName("SessionListScroll")
        self.sessions_scroll.setWidgetResizable(True)
        self.sessions_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sessions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sessions_scroll.setMaximumHeight(96)
        self.sessions_container = QWidget()
        self.sessions_container.setObjectName("SessionListContainer")
        self.sessions_layout = QVBoxLayout(self.sessions_container)
        self.sessions_layout.setContentsMargins(0, 0, 0, 0)
        self.sessions_layout.setSpacing(2)
        self.sessions_scroll.setWidget(self.sessions_container)
        root.addWidget(self.sessions_scroll)

    def _install_editor_filters(self) -> None:
        for editor in (
            self.title_edit,
            self.requester_edit,
            self.notes_editor,
            self.add_sub_step_input,
            self.manual_duration_input,
        ):
            editor.installEventFilter(self)

    @property
    def task_id(self) -> str:
        """Return Task ID bound to this Thinking Space."""
        return self._task.id

    def has_editor_focus(self) -> bool:
        """Return True if any input widget inside this Thinking Space holds focus."""
        focus_widget = self.window().focusWidget()
        if focus_widget is not None and self.isAncestorOf(focus_widget):
            return True
        return any(
            editor.hasFocus()
            for editor in (
                self.title_edit,
                self.requester_edit,
                self.notes_editor,
                self.add_sub_step_input,
                self.manual_duration_input,
            )
        )

    def focus_field(self, field: ThinkingField) -> QWidget:
        """Focus a specific Thinking Space input with appropriate selection or cursor placement."""
        if field == ThinkingField.TITLE:
            self.title_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.title_edit.selectAll()
            return self.title_edit
        if field == ThinkingField.REQUESTER:
            self.requester_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.requester_edit.selectAll()
            return self.requester_edit
        if field == ThinkingField.NOTES:
            self.notes_editor.setFocus(Qt.FocusReason.ShortcutFocusReason)
            cursor = self.notes_editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.notes_editor.setTextCursor(cursor)
            return self.notes_editor
        self.add_sub_step_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        return self.add_sub_step_input

    def open_manual_entry(self) -> None:
        """Reveal and focus the inline manual Work Session input."""
        self.manual_error_label.setVisible(False)
        self.manual_entry_row.setVisible(True)
        self.manual_duration_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.manual_duration_input.selectAll()

    def clear_manual_entry(self) -> None:
        """Clear and collapse the manual Work Session entry row."""
        self.manual_duration_input.clear()
        self.manual_error_label.setVisible(False)
        self.manual_entry_row.setVisible(False)

    def show_manual_error(self, message: str) -> None:
        """Display an actionable validation error for manual Work Session entry."""
        self.manual_error_label.setText(message)
        self.manual_error_label.setVisible(True)

    def animate_expand(self) -> None:
        """Animate Thinking Space reveal over 160ms OutCubic."""
        self._height_anim.stop()
        self._collapsing = False
        self._collapse_callback = None
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        target_height = max(120, self.sizeHint().height())
        self.setMaximumHeight(0)
        self._height_anim.setStartValue(0)
        self._height_anim.setEndValue(target_height)
        self._height_anim.start()

    def set_requester_suggester(self, suggester: Callable[[str], list[str]] | None) -> None:
        """Configure callback providing Requester autocompletion suggestions."""
        self._requester_suggester = suggester
        if suggester is None:
            self.dismiss_requester_autocomplete()

    def is_requester_popup_visible(self) -> bool:
        """Return True when the Requester autocomplete popup is currently visible."""
        return self.requester_popup.isVisible()

    def dismiss_requester_autocomplete(self) -> None:
        """Hide the Requester autocomplete popup and reset navigation state."""
        self.requester_popup.hide_popup()

    def animate_collapse(self, on_finished: Callable[[], None]) -> None:
        """Animate Thinking Space collapse over 160ms OutCubic and invoke on_finished."""
        self.dismiss_requester_autocomplete()
        if self._collapsing:
            return
        self._height_anim.stop()
        self._collapsing = True
        self._collapse_callback = on_finished
        self.setMinimumHeight(0)
        start_height = max(self.height(), self.sizeHint().height())
        self._height_anim.setStartValue(start_height)
        self._height_anim.setEndValue(0)
        self._height_anim.start()

    def flush_pending_saves(self) -> None:
        """Immediately flush debounced notes and inline title/requester edits."""
        self._notes_timer.stop()
        self._flush_notes()
        self._commit_title()
        self._commit_requester()

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Refresh custom-painted checkboxes, icons, and autocomplete popup for updated theme."""
        self._tokens = tokens
        self.requester_popup.apply_theme(tokens)
        for checkbox in self.findChildren(_SubStepCheckBox):
            checkbox.apply_theme(tokens)
        for del_btn in self.findChildren(QToolButton, "RowDeleteButton"):
            del_btn.setIcon(create_close_icon(QColor(tokens.text_muted), 10))
        self.refresh_timer(now=self._now)

    def update_task(
        self,
        task: Task,
        *,
        now: datetime,
        tokens: ColorTokens,
        local_tz: tzinfo | None = None,
    ) -> None:
        """Synchronize all Thinking Space widgets to the latest Task snapshot."""
        self._loading = True
        try:
            self._task = task
            self._now = now
            self._tokens = tokens
            if local_tz is not None:
                self._local_tz = local_tz

            if not self.title_edit.hasFocus():
                self.title_edit.setText(task.title)
            self.added_meta_label.setText(
                format_task_added_full(task.created_at, now=now, tz=self._local_tz)
            )
            if not self.requester_edit.hasFocus():
                self.requester_edit.setText(f"@{task.requester}" if task.requester else "")
            if not self.notes_editor.hasFocus() and self.notes_editor.toPlainText() != task.notes:
                self.notes_editor.setPlainText(task.notes)
                self._notes_dirty = False
                self.saved_label.setText("Saved")

            for status_val, btn in self._status_buttons.items():
                set_qss_property(btn, "active", task.status == status_val)

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
            active_secs = self._task.active_session_seconds(now=now)
            self.timer_button.setText(f"Stop {format_hms(active_secs)}")
            self.timer_button.setIcon(create_stop_icon(QColor(self._tokens.status_doing), 12))
            set_qss_property(self.timer_button, "running", True)
        else:
            self.timer_button.setText("Start Timer")
            self.timer_button.setIcon(create_play_icon(QColor(self._tokens.text_primary), 12))
            set_qss_property(self.timer_button, "running", False)

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
                    label.setText(self._format_session_line(session, now=now, tz=self._local_tz))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event = event
            assert isinstance(key_event, QKeyEvent)
            if (
                watched is self.requester_edit
                and self.requester_popup.isVisible()
                and self._handle_requester_popup_key(key_event)
            ):
                return True
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
            if (
                watched in (self.title_edit, self.requester_edit)
                and key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not (
                    key_event.modifiers()
                    & (
                        Qt.KeyboardModifier.ControlModifier
                        | Qt.KeyboardModifier.AltModifier
                        | Qt.KeyboardModifier.ShiftModifier
                    )
                )
            ):
                self.flush_pending_saves()
                self.collapse_requested.emit()
                return True
            if key_event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and (
                key_event.modifiers() & Qt.KeyboardModifier.ControlModifier
            ):
                if isinstance(watched, QWidget):
                    backward = key_event.key() == Qt.Key.Key_Backtab or bool(
                        key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                    )
                    if backward:
                        watched.focusPreviousChild()
                    else:
                        watched.focusNextChild()
                return True
        elif event.type() == QEvent.Type.FocusIn:
            self.editor_focus_changed.emit()
        elif event.type() == QEvent.Type.FocusOut:
            if watched is self.notes_editor:
                self._notes_timer.stop()
                self._flush_notes()
            elif watched is self.requester_edit:
                self.dismiss_requester_autocomplete()
            self.editor_focus_changed.emit()
        return super().eventFilter(watched, event)

    def _handle_requester_popup_key(self, key_event: QKeyEvent) -> bool:
        key = key_event.key()
        mods = key_event.modifiers()
        has_non_keypad_mod = bool(
            mods
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.ShiftModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )
        if key == Qt.Key.Key_Down and mods == Qt.KeyboardModifier.NoModifier:
            self.requester_popup.move_selection(1)
            return True
        if key == Qt.Key.Key_Up and mods == Qt.KeyboardModifier.NoModifier:
            self.requester_popup.move_selection(-1)
            return True
        if key == Qt.Key.Key_Tab and mods == Qt.KeyboardModifier.NoModifier:
            self._accept_requester_suggestion()
            return True
        if key == Qt.Key.Key_Escape:
            self.dismiss_requester_autocomplete()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not has_non_keypad_mod:
            if self.requester_popup.has_explicit_navigation():
                self._accept_requester_suggestion()
                return True
            self.dismiss_requester_autocomplete()
        return False

    def _on_requester_text_edited(self, text: str) -> None:
        if self._loading or self._requester_suggester is None or not text.strip():
            self.dismiss_requester_autocomplete()
            return
        suggestions = self._requester_suggester(text)
        if not suggestions:
            self.dismiss_requester_autocomplete()
            return
        anchor = self.requester_edit.mapToGlobal(QPoint(0, self.requester_edit.height() + 4))
        win = self.window()
        clamp_bounds = win.frameGeometry() if win is not None and win.isVisible() else None
        self.requester_popup.show_suggestions(suggestions, anchor, clamp_bounds=clamp_bounds)

    def _accept_requester_suggestion(self) -> None:
        suggestion = self.requester_popup.current_suggestion()
        if suggestion is None:
            self.dismiss_requester_autocomplete()
            return
        self._apply_requester_suggestion(suggestion)

    def _apply_requester_suggestion(self, name: str) -> None:
        clean = name.strip().lstrip("@")
        if not clean:
            self.dismiss_requester_autocomplete()
            return
        self.requester_edit.setText(f"@{clean}")
        self.requester_edit.setCursorPosition(len(self.requester_edit.text()))
        self.dismiss_requester_autocomplete()
        self.requester_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_height_anim_finished(self) -> None:
        if self._collapsing:
            self._collapsing = False
            callback = self._collapse_callback
            self._collapse_callback = None
            if callback is not None:
                callback()
            return
        self.setMaximumHeight(16777215)
        self.expand_finished.emit()

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
            self._task = replace(self._task, title=cleaned)
            self.title_changed.emit(self._task.id, cleaned)

    def _commit_requester(self) -> None:
        if self._loading:
            return
        raw = self.requester_edit.text().strip().lstrip("@")
        new_req: str | None = raw or None
        if new_req != self._task.requester:
            self._task = replace(self._task, requester=new_req)
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
        raw = self.manual_duration_input.text().strip()
        if not raw:
            return
        self.manual_error_label.setVisible(False)
        self.manual_session_requested.emit(self._task.id, raw)

    def _rebuild_sub_steps(self) -> None:
        clear_layout(self.sub_steps_layout)

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
            row.show()

    def _rebuild_sessions(self) -> None:
        clear_layout(self.sessions_layout)

        ordered = sorted(self._task.work_sessions, key=lambda s: s.started_at, reverse=True)
        ordered.sort(key=lambda s: not s.is_running)

        if not ordered:
            empty = QLabel("No Work Sessions logged yet.", self.sessions_container)
            empty.setObjectName("SessionRowLabel")
            self.sessions_layout.addWidget(empty)
            self.sessions_scroll.setFixedHeight(26)
            return

        for session in ordered:
            row = _WorkSessionRowWidget(
                session,
                line_text=self._format_session_line(session, now=self._now, tz=self._local_tz),
                tokens=self._tokens,
                parent=self.sessions_container,
            )
            row.deleted.connect(self.session_deleted)
            self.sessions_layout.addWidget(row)
            row.show()

        visible_rows = min(4, len(ordered))
        self.sessions_scroll.setFixedHeight(visible_rows * 24 + 4)

    @staticmethod
    def _format_session_line(
        session: WorkSession,
        *,
        now: datetime,
        tz: tzinfo | None = None,
    ) -> str:
        start_local = (
            session.started_at.astimezone(tz) if tz is not None else session.started_at.astimezone()
        ).strftime("%H:%M")
        dur_secs = session.duration_seconds(now=now)
        if session.is_running:
            return f"{start_local} - now ({format_hms(dur_secs)}) · Timer"
        assert session.ended_at is not None
        end_local = (
            session.ended_at.astimezone(tz) if tz is not None else session.ended_at.astimezone()
        ).strftime("%H:%M")
        dur_label = _format_session_duration_short(dur_secs)
        kind = "Manual" if session.is_manual else "Timer"
        return f"{start_local} - {end_local} · {dur_label} · {kind}"
