"""Centered Settings modal overlay for Theme, Shortcut, Hints, and Idle threshold."""

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nyatodo.domain import IdleThreshold, Settings, ThemeMode
from nyatodo.platform_win32 import parse_hotkey
from nyatodo.ui.icons import create_close_icon
from nyatodo.ui.theme import DARK_TOKENS, ColorTokens, make_mono_font, make_ui_font

_IDLE_OPTIONS: tuple[tuple[str, IdleThreshold], ...] = (
    ("Off", IdleThreshold.OFF),
    ("5m", IdleThreshold.FIVE_MIN),
    ("10m", IdleThreshold.TEN_MIN),
    ("15m", IdleThreshold.FIFTEEN_MIN),
    ("30m", IdleThreshold.THIRTY_MIN),
)

_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_AltGr,
    Qt.Key.Key_Meta,
    Qt.Key.Key_Super_L,
    Qt.Key.Key_Super_R,
}

_SPECIAL_KEY_NAMES: dict[int, str] = {
    Qt.Key.Key_Space: "Space",
    Qt.Key.Key_Return: "Enter",
    Qt.Key.Key_Enter: "Enter",
    Qt.Key.Key_Tab: "Tab",
    Qt.Key.Key_Backspace: "Backspace",
    Qt.Key.Key_Delete: "Delete",
    Qt.Key.Key_Insert: "Insert",
    Qt.Key.Key_Home: "Home",
    Qt.Key.Key_End: "End",
    Qt.Key.Key_PageUp: "PageUp",
    Qt.Key.Key_PageDown: "PageDown",
    Qt.Key.Key_Up: "Up",
    Qt.Key.Key_Down: "Down",
    Qt.Key.Key_Left: "Left",
    Qt.Key.Key_Right: "Right",
    Qt.Key.Key_Comma: ",",
    Qt.Key.Key_Period: ".",
    Qt.Key.Key_Slash: "/",
    Qt.Key.Key_Semicolon: ";",
    Qt.Key.Key_Minus: "-",
    Qt.Key.Key_Equal: "=",
    Qt.Key.Key_BracketLeft: "[",
    Qt.Key.Key_BracketRight: "]",
    Qt.Key.Key_Backslash: "\\",
    Qt.Key.Key_QuoteLeft: "`",
}


def format_qt_key_event(event: QKeyEvent) -> str | None:
    """Convert a QKeyEvent into a canonical hotkey string like 'Ctrl+Alt+Space', or None."""
    key = event.key()
    if key in _MODIFIER_KEYS or key == Qt.Key.Key_unknown:
        return None

    mods = event.modifiers()
    parts: list[str] = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        parts.append("Ctrl")
    if mods & Qt.KeyboardModifier.AltModifier:
        parts.append("Alt")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        parts.append("Shift")
    if mods & Qt.KeyboardModifier.MetaModifier:
        parts.append("Win")

    if not parts:
        return None

    key_name: str | None = _SPECIAL_KEY_NAMES.get(key)
    if key_name is None:
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
            key_name = f"F{key - Qt.Key.Key_F1 + 1}"
        elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            key_name = chr(key)
        else:
            text = event.text().strip()
            if len(text) == 1:
                key_name = text.upper()

    if key_name is None:
        return None
    parts.append(key_name)
    return "+".join(parts)


class ToggleSwitch(QAbstractButton):
    """Compact 34x18 pill toggle switch."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(34, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tokens: ColorTokens = DARK_TOKENS

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Update switch colors."""
        self._tokens = tokens
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(34, 18)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.5, 0.5, float(self.width()) - 1.0, float(self.height()) - 1.0)
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._tokens.accent_primary))
            painter.drawRoundedRect(rect, 9.0, 9.0)
            thumb_x = float(self.width()) - 15.0
            thumb_color = QColor("#FFFFFF")
        else:
            painter.setPen(QPen(QColor(self._tokens.border_subtle), 1.0))
            painter.setBrush(QColor(self._tokens.bg_surface))
            painter.drawRoundedRect(rect, 9.0, 9.0)
            thumb_x = 3.0
            thumb_color = QColor(self._tokens.text_secondary)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(thumb_color)
        painter.drawEllipse(QRectF(thumb_x, 3.0, 12.0, 12.0))
        painter.end()


class SettingsOverlay(QWidget):
    """Centered Settings modal over a semi-transparent scrim inside the spotlight shell."""

    settings_changed = Signal(object)
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModalScrim")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setVisible(False)

        self._tokens: ColorTokens = DARK_TOKENS
        self._settings = Settings()
        self._loading = False
        self._capturing_shortcut = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.modal_card = QFrame(self)
        self.modal_card.setObjectName("SettingsModal")
        self.modal_card.setFixedWidth(360)
        card_layout = QVBoxLayout(self.modal_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(0)

        # Header
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 12)
        title_label = QLabel("Settings", self.modal_card)
        title_label.setObjectName("SettingsTitle")
        header_font = make_ui_font(14)
        header_font.setWeight(header_font.Weight.DemiBold)
        title_label.setFont(header_font)
        header_row.addWidget(title_label)
        header_row.addStretch(1)

        self.close_button = QPushButton(self.modal_card)
        self.close_button.setObjectName("SettingsButton")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setIconSize(QSize(12, 12))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_modal)
        header_row.addWidget(self.close_button)
        card_layout.addLayout(header_row)

        # Row 1: Theme
        theme_track = QFrame(self.modal_card)
        theme_track.setObjectName("SettingsSegmentTrack")
        theme_track.setFixedHeight(28)
        track_layout = QHBoxLayout(theme_track)
        track_layout.setContentsMargins(3, 3, 3, 3)
        track_layout.setSpacing(2)

        self._theme_buttons: dict[ThemeMode, QPushButton] = {}
        for mode in (ThemeMode.DARK, ThemeMode.LIGHT, ThemeMode.SYSTEM):
            btn = QPushButton(mode.value, theme_track)
            btn.setObjectName("SettingsSegmentOption")
            btn.setFixedHeight(22)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, m=mode: self._select_theme(m))
            self._theme_buttons[mode] = btn
            track_layout.addWidget(btn)

        card_layout.addWidget(self._make_divider())
        card_layout.addLayout(self._make_setting_row("Theme", theme_track))

        # Row 2: Global Shortcut
        self.shortcut_button = QPushButton(self._settings.global_shortcut, self.modal_card)
        self.shortcut_button.setObjectName("ShortcutCaptureButton")
        self.shortcut_button.setFixedHeight(26)
        self.shortcut_button.setMinimumWidth(138)
        self.shortcut_button.setFont(make_mono_font(11))
        self.shortcut_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.shortcut_button.clicked.connect(self._begin_shortcut_capture)

        card_layout.addWidget(self._make_divider())
        card_layout.addLayout(self._make_setting_row("Global Shortcut", self.shortcut_button))

        self.shortcut_error_label = QLabel(self.modal_card)
        self.shortcut_error_label.setObjectName("SettingsErrorLabel")
        self.shortcut_error_label.setVisible(False)
        card_layout.addWidget(self.shortcut_error_label)

        # Row 3: Show Shortcut Hints
        self.hints_switch = ToggleSwitch(self.modal_card)
        self.hints_switch.toggled.connect(self._on_hints_toggled)
        card_layout.addWidget(self._make_divider())
        card_layout.addLayout(self._make_setting_row("Show Shortcut Hints", self.hints_switch))

        # Row 4: Idle Check Threshold
        self.idle_combo = QComboBox(self.modal_card)
        self.idle_combo.setObjectName("IdleThresholdCombo")
        self.idle_combo.setFixedHeight(28)
        self.idle_combo.setMinimumWidth(92)
        for label, threshold in _IDLE_OPTIONS:
            self.idle_combo.addItem(label, threshold)
        self.idle_combo.currentIndexChanged.connect(self._on_idle_changed)
        card_layout.addWidget(self._make_divider())
        card_layout.addLayout(self._make_setting_row("Idle Check Threshold", self.idle_combo))

        card_layout.addWidget(self._make_divider())

        # Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 14, 0, 0)
        footer.addStretch(1)
        self.done_button = QPushButton("Done", self.modal_card)
        self.done_button.setObjectName("SettingsDoneButton")
        self.done_button.setFixedHeight(28)
        self.done_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_button.clicked.connect(self.close_modal)
        footer.addWidget(self.done_button)
        card_layout.addLayout(footer)

        outer.addWidget(self.modal_card)
        self.apply_theme(DARK_TOKENS)

    def is_capturing_shortcut(self) -> bool:
        """Return True while waiting for user to press a new Global Shortcut."""
        return self._capturing_shortcut

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Refresh icon & switch colors for the active theme."""
        self._tokens = tokens
        self.close_button.setIcon(create_close_icon(QColor(tokens.text_secondary), 12))
        self.hints_switch.apply_theme(tokens)

    def open_with_settings(self, settings: Settings) -> None:
        """Populate modal controls from Settings and display the overlay."""
        self._loading = True
        try:
            self._settings = settings
            self._capturing_shortcut = False
            self.shortcut_error_label.setVisible(False)
            self._update_theme_buttons()
            self._update_shortcut_button()
            self.hints_switch.setChecked(settings.show_shortcut_hints)

            idx = self.idle_combo.findData(settings.idle_threshold)
            if idx >= 0:
                self.idle_combo.setCurrentIndex(idx)
        finally:
            self._loading = False

        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.setVisible(True)
        self.raise_()
        self.done_button.setFocus(Qt.FocusReason.PopupFocusReason)

    def close_modal(self) -> None:
        """Cancel any active capture and hide the Settings modal."""
        self._capturing_shortcut = False
        self._update_shortcut_button()
        self.shortcut_error_label.setVisible(False)
        self.setVisible(False)
        self.closed.emit()

    def cancel_capture_or_close(self) -> None:
        """Layered Esc inside Settings: cancel shortcut capture first, else close modal."""
        if self._capturing_shortcut:
            self._capturing_shortcut = False
            self.shortcut_error_label.setVisible(False)
            self._update_shortcut_button()
            return
        self.close_modal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._capturing_shortcut:
            if (
                event.key() == Qt.Key.Key_Escape
                and event.modifiers() == Qt.KeyboardModifier.NoModifier
            ):
                self.cancel_capture_or_close()
                event.accept()
                return

            combo = format_qt_key_event(event)
            if combo is None:
                if event.key() not in _MODIFIER_KEYS:
                    self.shortcut_error_label.setText(
                        "Require at least one modifier + key (e.g. Ctrl+Alt+Space)."
                    )
                    self.shortcut_error_label.setVisible(True)
                event.accept()
                return

            try:
                parse_hotkey(combo)
            except ValueError as exc:
                self.shortcut_error_label.setText(str(exc))
                self.shortcut_error_label.setVisible(True)
                event.accept()
                return

            self._capturing_shortcut = False
            self.shortcut_error_label.setVisible(False)
            self._emit_updated(
                Settings(
                    theme=self._settings.theme,
                    global_shortcut=combo,
                    show_shortcut_hints=self._settings.show_shortcut_hints,
                    idle_threshold=self._settings.idle_threshold,
                )
            )
            self._update_shortcut_button()
            event.accept()
            return

        if event.key() == Qt.Key.Key_Escape:
            self.close_modal()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.modal_card.geometry().contains(event.pos()):
            self.close_modal()
            event.accept()
            return
        super().mousePressEvent(event)

    def _make_divider(self) -> QFrame:
        line = QFrame(self.modal_card)
        line.setObjectName("SectionDivider")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _make_setting_row(self, label_text: str, control: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(12)
        label = QLabel(label_text, self.modal_card)
        label.setObjectName("SettingsRowLabel")
        label.setFont(make_ui_font(13))
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(control)
        return row

    def _select_theme(self, mode: ThemeMode) -> None:
        if mode == self._settings.theme:
            return
        self._emit_updated(
            Settings(
                theme=mode,
                global_shortcut=self._settings.global_shortcut,
                show_shortcut_hints=self._settings.show_shortcut_hints,
                idle_threshold=self._settings.idle_threshold,
            )
        )
        self._update_theme_buttons()

    def _begin_shortcut_capture(self) -> None:
        self._capturing_shortcut = True
        self.shortcut_error_label.setVisible(False)
        self._update_shortcut_button()
        self.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _on_hints_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        self._emit_updated(
            Settings(
                theme=self._settings.theme,
                global_shortcut=self._settings.global_shortcut,
                show_shortcut_hints=checked,
                idle_threshold=self._settings.idle_threshold,
            )
        )

    def _on_idle_changed(self, index: int) -> None:
        if self._loading or index < 0:
            return
        threshold = self.idle_combo.itemData(index)
        if not isinstance(threshold, IdleThreshold):
            return
        self._emit_updated(
            Settings(
                theme=self._settings.theme,
                global_shortcut=self._settings.global_shortcut,
                show_shortcut_hints=self._settings.show_shortcut_hints,
                idle_threshold=threshold,
            )
        )

    def _emit_updated(self, new_settings: Settings) -> None:
        self._settings = new_settings
        self.settings_changed.emit(new_settings)

    def _update_theme_buttons(self) -> None:
        for mode, btn in self._theme_buttons.items():
            btn.setProperty("active", mode == self._settings.theme)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _update_shortcut_button(self) -> None:
        self.shortcut_button.setProperty("capturing", self._capturing_shortcut)
        self.shortcut_button.setText(
            "Press shortcut..." if self._capturing_shortcut else self._settings.global_shortcut
        )
        self.shortcut_button.style().unpolish(self.shortcut_button)
        self.shortcut_button.style().polish(self.shortcut_button)
