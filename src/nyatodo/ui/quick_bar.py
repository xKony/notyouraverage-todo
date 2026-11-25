"""Quick Bar capture & '/' search widget with live @Requester pill preview."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QFont, QKeyEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QWidget

from nyatodo.parser import is_search_input, parse_quick_input
from nyatodo.ui.icons import create_plus_pixmap, create_search_pixmap
from nyatodo.ui.qt_helpers import set_qss_property
from nyatodo.ui.theme import DARK_TOKENS, ColorTokens, make_ui_font


class _QuickLineEdit(QLineEdit):
    """Single-line Quick Bar input forwarding Down/Tab/Escape and focus state."""

    jump_to_list_requested = Signal()
    escape_pressed = Signal()
    focus_changed = Signal(bool)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if (
            key in (Qt.Key.Key_Down, Qt.Key.Key_Tab)
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
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
    """38px spotlight Quick Bar supporting Task capture, @Requester preview, and '/' search."""

    query_changed = Signal(str)
    task_submitted = Signal(str)
    jump_to_list_requested = Signal()
    escape_pressed = Signal()
    focus_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("QuickBarFrame")
        self.setFixedHeight(38)
        self.setProperty("focused", False)

        self._tokens: ColorTokens = DARK_TOKENS
        self._is_search_mode = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        self.mode_icon_label = QLabel(self)
        self.mode_icon_label.setFixedSize(16, 16)
        layout.addWidget(self.mode_icon_label)

        self.input_edit = _QuickLineEdit(self)
        self.input_edit.setObjectName("QuickBarInput")
        self.input_edit.setFont(make_ui_font(13))
        self.input_edit.setPlaceholderText("Add task... (@who)  or  / to search")
        layout.addWidget(self.input_edit, 1)

        self.requester_pill = QLabel(self)
        self.requester_pill.setObjectName("RequesterPill")
        self.requester_pill.setFont(make_ui_font(11, QFont.Weight.Medium))
        self.requester_pill.setFixedHeight(20)
        self.requester_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.requester_pill.setVisible(False)
        layout.addWidget(self.requester_pill)

        self.enter_hint = QLabel("Enter", self)
        self.enter_hint.setObjectName("EnterHintKeycap")
        self.enter_hint.setFont(make_ui_font(10, QFont.Weight.Medium))
        self.enter_hint.setFixedHeight(20)
        self.enter_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.enter_hint.setVisible(False)
        layout.addWidget(self.enter_hint)

        self.input_edit.textChanged.connect(self._on_text_changed)
        self.input_edit.returnPressed.connect(self._on_return_pressed)
        self.input_edit.jump_to_list_requested.connect(self.jump_to_list_requested)
        self.input_edit.escape_pressed.connect(self.escape_pressed)
        self.input_edit.focus_changed.connect(self._on_focus_changed)

        self.apply_theme(DARK_TOKENS)

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Update mode glyph colors to match active theme tokens."""
        self._tokens = tokens
        self._refresh_mode_icon()

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
        self.focus_changed.emit(focused)

    def _on_text_changed(self, raw: str) -> None:
        search_mode = is_search_input(raw)
        if search_mode != self._is_search_mode:
            self._is_search_mode = search_mode
            self._refresh_mode_icon()

        if search_mode:
            self.requester_pill.setVisible(False)
            self.enter_hint.setVisible(False)
        else:
            parsed = parse_quick_input(raw)
            if parsed.requester:
                self.requester_pill.setText(f"@{parsed.requester}")
                self.requester_pill.setVisible(True)
            else:
                self.requester_pill.setVisible(False)
            self.enter_hint.setVisible(bool(parsed.title))

        self.query_changed.emit(raw)

    def _on_return_pressed(self) -> None:
        raw = self.input_edit.text()
        if is_search_input(raw):
            self.jump_to_list_requested.emit()
            return
        if raw.strip():
            self.task_submitted.emit(raw)

    def _refresh_mode_icon(self) -> None:
        if self._is_search_mode:
            pixmap = create_search_pixmap(QColor(self._tokens.accent_primary), 16)
        else:
            pixmap = create_plus_pixmap(QColor(self._tokens.text_muted), 16)
        self.mode_icon_label.setPixmap(pixmap)
