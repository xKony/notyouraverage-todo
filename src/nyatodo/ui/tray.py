"""System tray icon and context menu integration for nyatodo."""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from nyatodo.ui.icons import create_cat_tray_icon
from nyatodo.ui.theme import DARK_TOKENS, ColorTokens, format_hms


class TrayController(QObject):
    """Persistent system tray icon with active Task Timer badge and context menu."""

    toggle_window_requested = Signal()
    open_settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tokens: ColorTokens = DARK_TOKENS
        self._last_active_state: tuple[bool, bool] | None = None

        self.menu = QMenu()

        self.show_hide_action = QAction("Show / Hide nyatodo", self.menu)
        bold_font = self.show_hide_action.font()
        bold_font.setBold(True)
        self.show_hide_action.setFont(bold_font)
        self.show_hide_action.triggered.connect(self.toggle_window_requested)
        self.menu.addAction(self.show_hide_action)

        self.status_action = QAction("", self.menu)
        self.status_action.setEnabled(False)
        self.status_action.setVisible(False)
        self.menu.addAction(self.status_action)

        self.menu.addSeparator()

        self.settings_action = QAction("Settings…", self.menu)
        self.settings_action.triggered.connect(self.open_settings_requested)
        self.menu.addAction(self.settings_action)

        self.quit_action = QAction("Quit", self.menu)
        self.quit_action.triggered.connect(self.quit_requested)
        self.menu.addAction(self.quit_action)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.setToolTip("nyatodo")
        self.tray_icon.activated.connect(self._on_activated)

        self.update_state(
            running_count=0,
            running_seconds=0,
            shortcut="Ctrl+Alt+Space",
            tokens=DARK_TOKENS,
        )

    def show(self) -> None:
        """Display the tray icon when a system tray is available."""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()

    def hide(self) -> None:
        """Hide the tray icon."""
        self.tray_icon.hide()

    def update_state(
        self,
        *,
        running_count: int,
        running_seconds: int,
        shortcut: str,
        tokens: ColorTokens,
    ) -> None:
        """Refresh tray badge dot, tooltip, shortcut label, and running timer status row."""
        self._tokens = tokens
        has_active = running_count > 0
        self.show_hide_action.setText(f"Show / Hide nyatodo  ({shortcut})")

        if has_active:
            noun = "Task" if running_count == 1 else "Tasks"
            formatted = format_hms(running_seconds)
            self.status_action.setText(f"Running: {running_count} {noun} ({formatted})")
            self.status_action.setVisible(True)
            self.tray_icon.setToolTip(f"nyatodo — {running_count} {noun} running ({formatted})")
        else:
            self.status_action.setVisible(False)
            self.tray_icon.setToolTip("nyatodo")

        icon_state = (has_active, tokens.is_dark)
        if icon_state != self._last_active_state:
            self._last_active_state = icon_state
            fg = QColor(tokens.text_primary)
            badge = QColor(tokens.accent_primary)
            self.tray_icon.setIcon(
                create_cat_tray_icon(foreground=fg, active_timer=has_active, badge_color=badge)
            )

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_window_requested.emit()
