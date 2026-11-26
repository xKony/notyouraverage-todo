"""Centered Settings modal overlay for Theme, Shortcut, Hints, and Idle threshold."""

from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPen
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

from nyatodo.domain import AutoHideDelay, IdleThreshold, Settings, ThemeMode
from nyatodo.platform_win32 import parse_hotkey
from nyatodo.ui.icons import create_close_icon
from nyatodo.ui.qt_helpers import set_qss_property
from nyatodo.ui.theme import DARK_TOKENS, ColorTokens, make_ui_font

_IDLE_OPTIONS: tuple[tuple[str, IdleThreshold], ...] = (
    ("Off", IdleThreshold.OFF),
    ("5m", IdleThreshold.FIVE_MIN),
    ("10m", IdleThreshold.TEN_MIN),
    ("15m", IdleThreshold.FIFTEEN_MIN),
    ("30m", IdleThreshold.THIRTY_MIN),
)

_AUTO_HIDE_OPTIONS: tuple[tuple[str, AutoHideDelay], ...] = (
    ("Off", AutoHideDelay.OFF),
    ("Immediate", AutoHideDelay.IMMEDIATE),
    ("1s", AutoHideDelay.ONE_SEC),
    ("3s", AutoHideDelay.THREE_SEC),
    ("5s", AutoHideDelay.FIVE_SEC),
    ("10s", AutoHideDelay.TEN_SEC),
    ("30s", AutoHideDelay.THIRTY_SEC),
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


class _ThemedComboBox(QComboBox):
    """QComboBox with custom-painted crisp chevron matching active theme tokens."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tokens: ColorTokens = DARK_TOKENS

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Update chevron stroke color for active theme."""
        self._tokens = tokens
        self.update()

    def paintEvent(self, event: object) -> None:
        super().paintEvent(event)  # type: ignore[arg-type]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(self._tokens.text_secondary), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        cx = float(self.width()) - 13.0
        cy = float(self.height()) / 2.0
        painter.drawLine(QPointF(cx - 3.5, cy - 1.5), QPointF(cx, cy + 2.0))
        painter.drawLine(QPointF(cx, cy + 2.0), QPointF(cx + 3.5, cy - 1.5))
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

        self.modal_card = self._build_modal_card()
        outer.addWidget(self.modal_card)
        self.apply_theme(DARK_TOKENS)

    def _build_modal_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("SettingsModal")
        card.setFixedWidth(360)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(0)

        card_layout.addLayout(self._build_header(card))

        theme_track = self._build_theme_control(card)
        card_layout.addWidget(self._make_divider(card))
        card_layout.addLayout(self._make_setting_row(card, "Theme", theme_track))

        self.shortcut_button = self._build_shortcut_control(card)
        card_layout.addWidget(self._make_divider(card))
        card_layout.addLayout(self._make_setting_row(card, "Global Shortcut", self.shortcut_button))

        self.shortcut_error_label = QLabel(card)
        self.shortcut_error_label.setObjectName("SettingsErrorLabel")
        self.shortcut_error_label.setVisible(False)
        card_layout.addWidget(self.shortcut_error_label)

        self.hints_switch = ToggleSwitch(card)
        self.hints_switch.toggled.connect(self._on_hints_toggled)
        card_layout.addWidget(self._make_divider(card))
        card_layout.addLayout(
            self._make_setting_row(card, "Show Shortcut Hints", self.hints_switch)
        )

        self.idle_combo = self._build_idle_control(card)
        card_layout.addWidget(self._make_divider(card))
        card_layout.addLayout(self._make_setting_row(card, "Idle Check Threshold", self.idle_combo))

        self.auto_hide_combo = self._build_auto_hide_control(card)
        card_layout.addWidget(self._make_divider(card))
        card_layout.addLayout(
            self._make_setting_row(card, "Auto-Hide on Focus Loss", self.auto_hide_combo)
        )

        card_layout.addWidget(self._make_divider(card))
        card_layout.addLayout(self._build_footer(card))
        return card

    def _build_header(self, card: QFrame) -> QHBoxLayout:
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 12)
        title_label = QLabel("Settings", card)
        title_label.setObjectName("SettingsTitle")
        title_label.setFont(make_ui_font(14, QFont.Weight.DemiBold))
        header_row.addWidget(title_label)
        header_row.addStretch(1)

        self.close_button = QPushButton(card)
        self.close_button.setObjectName("SettingsButton")
        self.close_button.setFixedSize(26, 26)
        self.close_button.setIconSize(QSize(12, 12))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_modal)
        header_row.addWidget(self.close_button)
        return header_row

    def _build_theme_control(self, card: QFrame) -> QFrame:
        theme_track = QFrame(card)
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
        return theme_track

    def _build_shortcut_control(self, card: QFrame) -> QPushButton:
        btn = QPushButton(self._settings.global_shortcut, card)
        btn.setObjectName("ShortcutCaptureButton")
        btn.setFixedHeight(26)
        btn.setMinimumWidth(138)
        btn.setFont(make_ui_font(11, QFont.Weight.DemiBold))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._begin_shortcut_capture)
        return btn

    def _build_idle_control(self, card: QFrame) -> _ThemedComboBox:
        combo = _ThemedComboBox(card)
        combo.setObjectName("IdleThresholdCombo")
        combo.setFont(make_ui_font(12, QFont.Weight.Medium))
        combo.setFixedHeight(28)
        combo.setMinimumWidth(92)
        for label, threshold in _IDLE_OPTIONS:
            combo.addItem(label, threshold)
        combo.currentIndexChanged.connect(self._on_idle_changed)
        return combo

    def _build_auto_hide_control(self, card: QFrame) -> _ThemedComboBox:
        combo = _ThemedComboBox(card)
        combo.setObjectName("AutoHideDelayCombo")
        combo.setFont(make_ui_font(12, QFont.Weight.Medium))
        combo.setFixedHeight(28)
        combo.setMinimumWidth(92)
        for label, delay in _AUTO_HIDE_OPTIONS:
            combo.addItem(label, delay)
        combo.currentIndexChanged.connect(self._on_auto_hide_changed)
        return combo

    def _build_footer(self, card: QFrame) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 14, 0, 0)
        footer.addStretch(1)
        self.done_button = QPushButton("Done", card)
        self.done_button.setObjectName("SettingsDoneButton")
        self.done_button.setFixedHeight(28)
        self.done_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_button.clicked.connect(self.close_modal)
        footer.addWidget(self.done_button)
        return footer

    def is_capturing_shortcut(self) -> bool:
        """Return True while waiting for user to press a new Global Shortcut."""
        return self._capturing_shortcut

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Refresh icon, combo chevron, and switch colors for the active theme."""
        self._tokens = tokens
        self.close_button.setIcon(create_close_icon(QColor(tokens.text_secondary), 12))
        self.hints_switch.apply_theme(tokens)
        self.idle_combo.apply_theme(tokens)
        self.auto_hide_combo.apply_theme(tokens)

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

            auto_hide_idx = self.auto_hide_combo.findData(settings.auto_hide_delay)
            if auto_hide_idx >= 0:
                self.auto_hide_combo.setCurrentIndex(auto_hide_idx)
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
            self._emit_updated(replace(self._settings, global_shortcut=combo))
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

    def _make_divider(self, card: QFrame) -> QFrame:
        line = QFrame(card)
        line.setObjectName("SectionDivider")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _make_setting_row(self, card: QFrame, label_text: str, control: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(12)
        label = QLabel(label_text, card)
        label.setObjectName("SettingsRowLabel")
        label.setFont(make_ui_font(13))
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(control)
        return row

    def _select_theme(self, mode: ThemeMode) -> None:
        if mode == self._settings.theme:
            return
        self._emit_updated(replace(self._settings, theme=mode))
        self._update_theme_buttons()

    def _begin_shortcut_capture(self) -> None:
        self._capturing_shortcut = True
        self.shortcut_error_label.setVisible(False)
        self._update_shortcut_button()
        self.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _on_hints_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        self._emit_updated(replace(self._settings, show_shortcut_hints=checked))

    def _on_idle_changed(self, index: int) -> None:
        if self._loading or index < 0:
            return
        threshold = self.idle_combo.itemData(index)
        if not isinstance(threshold, IdleThreshold):
            return
        self._emit_updated(replace(self._settings, idle_threshold=threshold))

    def _on_auto_hide_changed(self, index: int) -> None:
        if self._loading or index < 0:
            return
        delay = self.auto_hide_combo.itemData(index)
        if not isinstance(delay, AutoHideDelay):
            return
        self._emit_updated(replace(self._settings, auto_hide_delay=delay))

    def _emit_updated(self, new_settings: Settings) -> None:
        self._settings = new_settings
        self.settings_changed.emit(new_settings)

    def _update_theme_buttons(self) -> None:
        for mode, btn in self._theme_buttons.items():
            set_qss_property(btn, "active", mode == self._settings.theme)

    def _update_shortcut_button(self) -> None:
        set_qss_property(self.shortcut_button, "capturing", self._capturing_shortcut)
        self.shortcut_button.setText(
            "Press shortcut..." if self._capturing_shortcut else self._settings.global_shortcut
        )
