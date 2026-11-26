"""Contextual 20px whisper-quiet shortcut hints footer bar."""

from enum import StrEnum

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from nyatodo.ui.qt_helpers import clear_layout
from nyatodo.ui.theme import make_ui_font


class HintContext(StrEnum):
    """Focused surface context determining which shortcut hints appear."""

    COMPACT_SPOTLIGHT = "compact_spotlight"
    QUICK_BAR = "quick_bar"
    TASK_LIST = "task_list"
    THINKING_SPACE = "thinking_space"
    SUMMARY = "summary"


_HINTS_BY_CONTEXT: dict[HintContext, tuple[tuple[str, str], ...]] = {
    HintContext.COMPACT_SPOTLIGHT: (
        ("Enter", "Add"),
        ("/", "Search"),
        ("↓", "Expand"),
        ("Esc", "Hide"),
    ),
    HintContext.QUICK_BAR: (
        ("Enter", "Add"),
        ("/", "Search"),
        ("↓", "List"),
        ("Esc", "Hide"),
    ),
    HintContext.TASK_LIST: (
        ("↓↑", "Move"),
        ("t", "Timer"),
        ("n/s/r/e", "Edit"),
        ("w", "Wait"),
        ("d", "Done"),
        ("Esc", "Hide"),
    ),
    HintContext.THINKING_SPACE: (
        ("Esc", "Collapse"),
        ("Ctrl+Enter", "Done"),
    ),
    HintContext.SUMMARY: (
        ("←→", "Period"),
        ("1-3", "Tabs"),
        ("Esc", "Hide"),
    ),
}


class HintsFooter(QFrame):
    """20px contextual micro-tag hints bar that collapses completely when disabled."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HintsFooter")
        self.setFixedHeight(20)

        self._hints_enabled = True
        self._context = HintContext.QUICK_BAR

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 0, 12, 0)
        self._layout.setSpacing(8)

        self._rebuild()

    def set_hints_enabled(self, enabled: bool) -> None:
        """Show or completely collapse the footer based on Settings.show_shortcut_hints."""
        self._hints_enabled = enabled
        self.setVisible(enabled)
        self.setFixedHeight(20 if enabled else 0)

    def hints_enabled(self) -> bool:
        """Return True if shortcut hints are enabled."""
        return self._hints_enabled

    def set_context(self, context: HintContext) -> None:
        """Update displayed keycap hints for the active focus context."""
        if context == self._context:
            return
        self._context = context
        self._rebuild()

    def context(self) -> HintContext:
        """Return the current HintContext."""
        return self._context

    def _rebuild(self) -> None:
        clear_layout(self._layout)

        key_font = make_ui_font(10, QFont.Weight.DemiBold)
        verb_font = make_ui_font(10)

        for keycap_text, verb_text in _HINTS_BY_CONTEXT[self._context]:
            pair = QWidget(self)
            pair_layout = QHBoxLayout(pair)
            pair_layout.setContentsMargins(0, 0, 0, 0)
            pair_layout.setSpacing(3)

            keycap = QLabel(keycap_text, pair)
            keycap.setObjectName("KeycapLabel")
            keycap.setFont(key_font)
            pair_layout.addWidget(keycap)

            verb = QLabel(verb_text, pair)
            verb.setObjectName("HintVerbLabel")
            verb.setFont(verb_font)
            pair_layout.addWidget(verb)

            self._layout.addWidget(pair)
            pair.show()

        self._layout.addStretch(1)
        self._layout.activate()
