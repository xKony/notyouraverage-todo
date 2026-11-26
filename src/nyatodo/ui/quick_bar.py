"""Morphing Quick Bar capture & '/' search widget with live @Requester pill preview."""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QFont, QKeyEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QWidget

from nyatodo.parser import (
    ActiveRequesterToken,
    apply_requester_completion,
    find_active_requester_token,
    is_search_input,
    parse_quick_input,
)
from nyatodo.ui.icons import create_plus_pixmap, create_search_pixmap
from nyatodo.ui.qt_helpers import set_qss_property, sync_importance_pill
from nyatodo.ui.requester_autocomplete_popup import RequesterAutocompletePopup
from nyatodo.ui.theme import DARK_TOKENS, ColorTokens, make_ui_font


class _QuickLineEdit(QLineEdit):
    """Single-line Quick Bar input handling autocomplete navigation, Tab/Down/Esc, and focus."""

    jump_to_list_requested = Signal()
    escape_pressed = Signal()
    focus_changed = Signal(bool)
    autocomplete_accept_requested = Signal()
    autocomplete_dismiss_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._autocomplete_popup: RequesterAutocompletePopup | None = None

    def set_autocomplete_popup(self, popup: RequesterAutocompletePopup) -> None:
        """Bind the Requester autocomplete popup for keyboard interception."""
        self._autocomplete_popup = popup

    def event(self, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() == Qt.Key.Key_Tab
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            self.keyPressEvent(event)
            if event.isAccepted():
                return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        mods = event.modifiers()
        has_non_keypad_mod = bool(
            mods
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.ShiftModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )
        if self._autocomplete_popup is not None and self._autocomplete_popup.isVisible():
            if key == Qt.Key.Key_Down and mods == Qt.KeyboardModifier.NoModifier:
                self._autocomplete_popup.move_selection(1)
                event.accept()
                return
            if key == Qt.Key.Key_Up and mods == Qt.KeyboardModifier.NoModifier:
                self._autocomplete_popup.move_selection(-1)
                event.accept()
                return
            if key == Qt.Key.Key_Tab and mods == Qt.KeyboardModifier.NoModifier:
                self.autocomplete_accept_requested.emit()
                event.accept()
                return
            if key == Qt.Key.Key_Escape:
                self.autocomplete_dismiss_requested.emit()
                event.accept()
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not has_non_keypad_mod:
                if self._autocomplete_popup.has_explicit_navigation():
                    self.autocomplete_accept_requested.emit()
                    event.accept()
                    return
                self.autocomplete_dismiss_requested.emit()

        if key in (Qt.Key.Key_Down, Qt.Key.Key_Tab) and mods == Qt.KeyboardModifier.NoModifier:
            self.jump_to_list_requested.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.focus_changed.emit(False)


class QuickBar(QFrame):
    """42px morphing borderless-to-pill Quick Bar for capture and '/' search."""

    query_changed = Signal(str)
    task_submitted = Signal(str)
    jump_to_list_requested = Signal()
    escape_pressed = Signal()
    focus_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("QuickBarFrame")
        self.setFixedHeight(42)
        self.setProperty("focused", False)
        self.setProperty("has_text", False)

        self._tokens: ColorTokens = DARK_TOKENS
        self._is_search_mode = False
        self._requester_suggester: Callable[[str], list[str]] | None = None
        self._suppress_autocomplete = False

        self.requester_popup = RequesterAutocompletePopup(self)
        self.requester_popup.requester_selected.connect(self._accept_requester_completion)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(8)

        self.mode_icon_label = QLabel(self)
        self.mode_icon_label.setFixedSize(16, 16)
        layout.addWidget(self.mode_icon_label)

        self.input_edit = _QuickLineEdit(self)
        self.input_edit.setObjectName("QuickBarInput")
        self.input_edit.setFont(make_ui_font(15, QFont.Weight.Light, tracking_em=-0.01))
        self.input_edit.setPlaceholderText("What's next?")
        self.input_edit.set_autocomplete_popup(self.requester_popup)
        layout.addWidget(self.input_edit, 1)

        self.importance_pill = QLabel(self)
        self.importance_pill.setObjectName("ImportancePill")
        self.importance_pill.setFont(make_ui_font(10, QFont.Weight.Bold))
        self.importance_pill.setFixedHeight(20)
        self.importance_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.importance_pill.setVisible(False)
        layout.addWidget(self.importance_pill)

        self.requester_pill = QLabel(self)
        self.requester_pill.setObjectName("RequesterPill")
        self.requester_pill.setFont(make_ui_font(11, QFont.Weight.Medium))
        self.requester_pill.setFixedHeight(22)
        self.requester_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.requester_pill.setVisible(False)
        layout.addWidget(self.requester_pill)

        self.enter_hint = QLabel("↵", self)
        self.enter_hint.setObjectName("EnterHintKeycap")
        self.enter_hint.setFont(make_ui_font(10, QFont.Weight.DemiBold))
        self.enter_hint.setFixedHeight(20)
        self.enter_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.enter_hint.setVisible(False)
        layout.addWidget(self.enter_hint)

        self.input_edit.textChanged.connect(self._on_text_changed)
        self.input_edit.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.input_edit.returnPressed.connect(self._on_return_pressed)
        self.input_edit.jump_to_list_requested.connect(self.jump_to_list_requested)
        self.input_edit.escape_pressed.connect(self.escape_pressed)
        self.input_edit.focus_changed.connect(self._on_focus_changed)
        self.input_edit.autocomplete_accept_requested.connect(self._accept_current_suggestion)
        self.input_edit.autocomplete_dismiss_requested.connect(self.dismiss_autocomplete)

        self.apply_theme(DARK_TOKENS)

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Update mode glyph colors and autocomplete popup to match active theme tokens."""
        self._tokens = tokens
        self._refresh_mode_icon()
        self.requester_popup.apply_theme(tokens)

    def set_requester_suggester(self, suggester: Callable[[str], list[str]] | None) -> None:
        """Configure callback providing Requester autocompletion suggestions."""
        self._requester_suggester = suggester
        if suggester is None:
            self.dismiss_autocomplete()

    def is_autocomplete_visible(self) -> bool:
        """Return True when the Requester autocomplete popup is currently visible."""
        return self.requester_popup.isVisible()

    def dismiss_autocomplete(self) -> None:
        """Hide the Requester autocomplete popup and reset navigation state."""
        self.requester_popup.hide_popup()

    def text(self) -> str:
        """Return current raw Quick Bar text."""
        return self.input_edit.text()

    def set_text(self, value: str) -> None:
        """Set Quick Bar text programmatically."""
        self.input_edit.setText(value)

    def clear(self) -> None:
        """Clear Quick Bar input text."""
        self.input_edit.clear()

    def is_search_mode(self) -> bool:
        """Return True when input begins with '/' search prefix."""
        return self._is_search_mode

    def has_input_focus(self) -> bool:
        """Return True when the Quick Bar QLineEdit currently holds keyboard focus."""
        return self.input_edit.hasFocus()

    def focus_input(self, *, select_all: bool = False) -> None:
        """Place keyboard focus in the Quick Bar input."""
        self.input_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        if select_all:
            self.input_edit.selectAll()
        else:
            self.input_edit.setCursorPosition(len(self.input_edit.text()))

    def start_search_mode(self) -> None:
        """Focus Quick Bar in '/' search mode."""
        if not is_search_input(self.input_edit.text()):
            self.input_edit.setText("/")
        self.focus_input(select_all=False)

    def _on_focus_changed(self, focused: bool) -> None:
        set_qss_property(self, "focused", focused)
        if not focused:
            self.dismiss_autocomplete()
        self.focus_changed.emit(focused)

    def _on_text_changed(self, raw: str) -> None:
        set_qss_property(self, "has_text", bool(raw))
        self.input_edit.setFont(
            make_ui_font(
                14 if raw else 15,
                QFont.Weight.Normal if raw else QFont.Weight.Light,
                tracking_em=-0.01 if not raw else 0.0,
            )
        )

        search_mode = is_search_input(raw)
        if search_mode != self._is_search_mode:
            self._is_search_mode = search_mode
            self._refresh_mode_icon()

        if search_mode:
            self.importance_pill.setVisible(False)
            self.requester_pill.setVisible(False)
            self.enter_hint.setVisible(False)
        else:
            parsed = parse_quick_input(raw)
            sync_importance_pill(self.importance_pill, parsed.importance)
            if parsed.requester:
                self.requester_pill.setText(f"@{parsed.requester}")
                self.requester_pill.setVisible(True)
            else:
                self.requester_pill.setVisible(False)
            self.enter_hint.setVisible(bool(parsed.title))

        self.query_changed.emit(raw)
        if not self._suppress_autocomplete:
            self._update_requester_autocomplete()

    def _on_cursor_position_changed(self, _old: int, _new: int) -> None:
        if not self._suppress_autocomplete:
            self._update_requester_autocomplete()

    def _update_requester_autocomplete(self) -> None:
        if self._requester_suggester is None or not self.input_edit.hasFocus():
            self.dismiss_autocomplete()
            return
        raw = self.input_edit.text()
        cursor_pos = self.input_edit.cursorPosition()
        token = find_active_requester_token(raw, cursor_pos)
        if token is None:
            self.dismiss_autocomplete()
            return
        suggestions = self._requester_suggester(token.query)
        if not suggestions:
            self.dismiss_autocomplete()
            return
        anchor = self._anchor_for_token(token)
        win = self.window()
        clamp_bounds = win.frameGeometry() if win is not None and win.isVisible() else None
        self.requester_popup.show_suggestions(suggestions, anchor, clamp_bounds=clamp_bounds)

    def _anchor_for_token(self, token: ActiveRequesterToken) -> QPoint:
        current_pos = self.input_edit.cursorPosition()
        prev_blocked = self.input_edit.blockSignals(True)
        try:
            self.input_edit.setCursorPosition(token.start)
            caret_rect = self.input_edit.cursorRect()
            self.input_edit.setCursorPosition(current_pos)
        finally:
            self.input_edit.blockSignals(prev_blocked)
        caret_global = self.input_edit.mapToGlobal(caret_rect.topLeft())
        bar_bottom_global = self.mapToGlobal(QPoint(0, self.height())).y()
        return QPoint(caret_global.x(), bar_bottom_global + 4)

    def _accept_current_suggestion(self) -> None:
        name = self.requester_popup.current_suggestion()
        if name is None:
            self.dismiss_autocomplete()
            return
        self._accept_requester_completion(name)

    def _accept_requester_completion(self, name: str) -> None:
        raw = self.input_edit.text()
        cursor_pos = self.input_edit.cursorPosition()
        token = find_active_requester_token(raw, cursor_pos)
        if token is None:
            self.dismiss_autocomplete()
            return
        updated, new_cursor = apply_requester_completion(raw, token, name, append_space=True)
        self._suppress_autocomplete = True
        try:
            self.input_edit.setText(updated)
            self.input_edit.setCursorPosition(new_cursor)
        finally:
            self._suppress_autocomplete = False
        self.dismiss_autocomplete()
        self.input_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_return_pressed(self) -> None:
        raw = self.input_edit.text()
        if is_search_input(raw):
            self.jump_to_list_requested.emit()
            return
        if raw.strip():
            self.task_submitted.emit(raw)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            self._refresh_mode_icon()

    def _refresh_mode_icon(self) -> None:
        dpr = self.devicePixelRatioF()
        if self._is_search_mode:
            pixmap = create_search_pixmap(QColor(self._tokens.accent_primary), 16, dpr=dpr)
        else:
            pixmap = create_plus_pixmap(QColor(self._tokens.text_muted), 16, dpr=dpr)
        self.mode_icon_label.setPixmap(pixmap)
