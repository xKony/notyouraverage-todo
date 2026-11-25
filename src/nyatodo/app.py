"""Desktop application entrypoint wiring storage, Win32 platform bridge, tray, and UI."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QApplication

from nyatodo.platform_win32 import PlatformBridge, Win32PlatformBridge
from nyatodo.service import TodoService
from nyatodo.storage import SQLiteRepository
from nyatodo.ui.main_window import HotkeyEventFilter, MainWindow
from nyatodo.ui.theme import resolve_theme
from nyatodo.ui.tray import TrayController

DEFAULT_HOTKEY_ID = 1


def default_db_path() -> Path:
    """Resolve default local SQLite path (%LOCALAPPDATA%\\nyatodo\\nyatodo.db or fallback)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "nyatodo" / "nyatodo.db"
    return Path.home() / ".local" / "share" / "nyatodo" / "nyatodo.db"


@dataclass
class AppRuntime:
    """Live application handles returned by build_application for clean lifecycle management."""

    app: QApplication
    repository: SQLiteRepository
    service: TodoService
    window: MainWindow
    tray: TrayController
    hotkey_filter: HotkeyEventFilter


def build_application(
    *,
    db_path: Path | str | None = None,
    platform: PlatformBridge | None = None,
    argv: list[str] | None = None,
) -> AppRuntime:
    """Construct QApplication, repository, TodoService, MainWindow, TrayController, and hotkey."""
    existing_app = QApplication.instance()
    app = (
        existing_app
        if isinstance(existing_app, QApplication)
        else QApplication(argv if argv is not None else sys.argv)
    )
    app.setApplicationName("nyatodo")
    app.setQuitOnLastWindowClosed(False)

    resolved_path = db_path if db_path is not None else default_db_path()
    repo = SQLiteRepository(resolved_path)
    bridge: PlatformBridge = platform if platform is not None else Win32PlatformBridge()
    service = TodoService(repo, platform=bridge)

    window = MainWindow(service, hotkey_id=DEFAULT_HOTKEY_ID)
    tray = TrayController()

    def _sync_tray() -> None:
        running = service.get_running_tasks()
        settings = service.get_settings()
        tokens = resolve_theme(settings.theme, system_theme=service.get_system_theme())
        now = window.current_time()
        total_running_seconds = sum(task.active_session_seconds(now=now) for task in running)
        tray.update_state(
            running_count=len(running),
            running_seconds=total_running_seconds,
            shortcut=settings.global_shortcut,
            tokens=tokens,
        )

    def _open_settings_from_tray() -> None:
        window.show_and_focus()
        window.open_settings()

    window.state_changed.connect(_sync_tray)
    tray.toggle_window_requested.connect(window.toggle_visibility)
    tray.open_settings_requested.connect(_open_settings_from_tray)
    tray.quit_requested.connect(app.quit)

    hotkey_filter = HotkeyEventFilter(
        hotkey_id=DEFAULT_HOTKEY_ID,
        on_triggered=window.toggle_visibility,
    )
    app.installNativeEventFilter(hotkey_filter)
    bridge.register_hotkey(
        service.get_settings().global_shortcut,
        hotkey_id=DEFAULT_HOTKEY_ID,
        hwnd=window.hotkey_hwnd(),
    )

    def _on_about_to_quit() -> None:
        window.tick_timer.stop()
        window.flush_pending_saves()
        service.shutdown(hotkey_id=DEFAULT_HOTKEY_ID, hwnd=window.hotkey_hwnd())
        tray.hide()
        repo.close()

    app.aboutToQuit.connect(_on_about_to_quit)
    _sync_tray()
    return AppRuntime(
        app=app,
        repository=repo,
        service=service,
        window=window,
        tray=tray,
        hotkey_filter=hotkey_filter,
    )


def main() -> int:
    """Launch the nyatodo desktop application event loop."""
    runtime = build_application()
    runtime.tray.show()
    runtime.window.show_and_focus()
    return runtime.app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
