"""Top-level non-focus-stealing Requester autocompletion floating popup."""

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from nyatodo.ui.qt_helpers import clear_layout, set_qss_property
from nyatodo.ui.theme import DARK_TOKENS, ColorTokens, make_ui_font

_MAX_SUGGESTIONS = 6
_ROW_HEIGHT = 26


class RequesterAutocompletePopup(QFrame):
    """Non-focus-stealing floating popup displaying up to 6 @Requester suggestions."""

    requester_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setObjectName("RequesterAutocompletePopup")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVisible(False)

        self._tokens: ColorTokens = DARK_TOKENS
        self._suggestions: list[str] = []
        self._row_buttons: list[QPushButton] = []
        self._selected_index: int = 0
        self._explicit_navigation: bool = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)

        self.apply_theme(DARK_TOKENS)

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Apply theme ColorTokens directly to the top-level popup stylesheet."""
        self._tokens = tokens
        self.setStyleSheet(
            f"""
            #RequesterAutocompletePopup {{
                background-color: {tokens.bg_elevated};
                border: 1px solid {tokens.border_subtle};
                border-radius: 6px;
            }}
            QPushButton#RequesterAutocompleteRow {{
                text-align: left;
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: {tokens.text_primary};
                font-family: "Poppins", "Segoe UI", sans-serif;
                font-size: 12px;
                font-weight: 500;
                padding: 0px 8px;
            }}
            QPushButton#RequesterAutocompleteRow:hover {{
                background-color: {tokens.bg_hover};
            }}
            QPushButton#RequesterAutocompleteRow[selected="true"] {{
                background-color: {tokens.bg_selected};
                color: {tokens.accent_primary};
                font-weight: 600;
            }}
            """
        )

    def show_suggestions(
        self,
        suggestions: list[str],
        global_anchor: QPoint,
        *,
        clamp_bounds: QRect | None = None,
    ) -> None:
        """Populate up to 6 suggestion rows, position below global_anchor, and reveal."""
        items = suggestions[:_MAX_SUGGESTIONS]
        if not items:
            self.hide_popup()
            return

        clear_layout(self._layout)
        self._row_buttons.clear()
        self._suggestions = list(items)
        self._selected_index = 0
        self._explicit_navigation = False

        row_font = make_ui_font(12, QFont.Weight.Medium)
        metrics = QFontMetrics(row_font)
        widest = max(metrics.horizontalAdvance(f"@{name}") for name in items)
        popup_w = max(160, min(260, widest + 28))
        max_text_w = popup_w - 24

        for idx, name in enumerate(items):
            elided = metrics.elidedText(f"@{name}", Qt.TextElideMode.ElideRight, max_text_w)
            btn = QPushButton(elided, self)
            btn.setObjectName("RequesterAutocompleteRow")
            btn.setProperty("requester_name", name)
            btn.setToolTip(f"@{name}")
            btn.setFont(row_font)
            btn.setFixedHeight(_ROW_HEIGHT)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            set_qss_property(btn, "selected", idx == 0)
            btn.clicked.connect(lambda _checked=False, req=name: self._on_row_clicked(req))
            self._layout.addWidget(btn)
            btn.show()
            self._row_buttons.append(btn)

        self.setFixedWidth(popup_w)
        self._layout.activate()
        self.setFixedHeight(max(_ROW_HEIGHT + 10, self.sizeHint().height()))

        x = global_anchor.x()
        y = global_anchor.y()
        bounds = self._resolve_horizontal_bounds(global_anchor, clamp_bounds)
        if bounds.isValid() and bounds.width() > 0:
            max_x = bounds.right() - popup_w + 1
            x = max(bounds.left(), min(x, max_x)) if max_x >= bounds.left() else bounds.left()

        self.move(x, y)
        self.show()
        self.raise_()

    def hide_popup(self) -> None:
        """Hide the popup and clear suggestion selection state."""
        self.hide()
        self._explicit_navigation = False
        self._selected_index = 0
        self._suggestions = []
        self._row_buttons.clear()
        clear_layout(self._layout)

    def dismiss(self) -> None:
        """Alias for hide_popup."""
        self.hide_popup()

    def move_selection(self, step: int) -> None:
        """Move highlighted suggestion row by step (wrapping cleanly) and mark explicit."""
        if not self._row_buttons:
            return
        self._selected_index = (self._selected_index + step) % len(self._row_buttons)
        self._explicit_navigation = True
        self._refresh_row_selection()

    def current_suggestion(self) -> str | None:
        """Return currently highlighted Requester name, or None when empty."""
        if not self._suggestions or not (0 <= self._selected_index < len(self._suggestions)):
            return None
        return self._suggestions[self._selected_index]

    def has_explicit_navigation(self) -> bool:
        """Return True when the user navigated suggestions with Up/Down while open."""
        return self._explicit_navigation

    def suggestions(self) -> list[str]:
        """Return currently loaded Requester suggestion names."""
        return list(self._suggestions)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        event.accept()

    def _on_row_clicked(self, name: str) -> None:
        self.requester_selected.emit(name)

    def _refresh_row_selection(self) -> None:
        for idx, btn in enumerate(self._row_buttons):
            set_qss_property(btn, "selected", idx == self._selected_index)

    @staticmethod
    def _resolve_horizontal_bounds(global_anchor: QPoint, clamp_bounds: QRect | None) -> QRect:
        if clamp_bounds is not None and clamp_bounds.isValid() and clamp_bounds.width() > 0:
            return clamp_bounds
        screen = QGuiApplication.screenAt(global_anchor) or QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else QRect()
