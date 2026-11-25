"""Contextual 28px shortcut hints footer bar."""

from enum import StrEnum

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from nyatodo.ui.theme import make_mono_font, make_ui_font


class HintContext(StrEnum):
    """Focused surface context determining which shortcut hints appear."""

    QUICK_BAR = "quick_bar"
    TASK_LIST = "task_list"
    THINKING_SPACE = "thinking_space"
    SUMMARY = "summary"


_HINTS_BY_CONTEXT: dict[HintContext, tuple[tuple[str, str], ...]] = {
    HintContext.QUICK_BAR: (
        ("Enter", "Add"),
        ("/", "Search"),
        ("↓", "List"),
        ("Esc", "Hide"),
    ),
    HintContext.TASK_LIST: (
        ("↓↑", "Move"),
        ("t", "Timer"),
        ("Enter", "Expand"),
        ("w", "Waiting"),
        ("d", "Done"),
        ("Esc", "Hide"),
    ),
    HintContext.THINKING_SPACE: (
        ("Esc", "Collapse"),
        ("Ctrl+Enter", "Done"),
    ),
    HintContext.SUMMARY: (
        ("←→", "Day"),
        ("1-3", "Tabs"),
        ("Esc", "Hide"),
    ),
}


class HintsFooter(QFrame):
    """28px contextual keycap hints bar that collapses completely when disabled."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HintsFooter")
        self.setFixedHeight(28)

        self._hints_enabled = True
        self._context = HintContext.QUICK_BAR

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 0, 16, 0)
        self._layout.setSpacing(10)

        self._rebuild()

    def set_hints_enabled(self, enabled: bool) -> None:
        """Show or completely collapse the footer based on Settings.show_shortcut_hints."""
        self._hints_enabled = enabled
        self.setVisible(enabled)
        self.setFixedHeight(28 if enabled else 0)

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
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()

        key_font = make_mono_font(10)
        verb_font = make_ui_font(11)

        for keycap_text, verb_text in _HINTS_BY_CONTEXT[self._context]:
            pair = QWidget(self)
            pair_layout = QHBoxLayout(pair)
            pair_layout.setContentsMargins(0, 0, 0, 0)
            pair_layout.setSpacing(4)

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
