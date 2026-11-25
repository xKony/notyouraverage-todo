"""PySide6 / pytest-qt UI integration tests for nyatodo."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from nyatodo.app import build_application
from nyatodo.domain import IdleThreshold, Settings, TaskStatus, ThemeMode
from nyatodo.service import TodoService
from nyatodo.storage import SQLiteRepository
from nyatodo.ui.main_window import MainWindow, ViewTab


class _FakeClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs: int) -> datetime:
        self.current = self.current + timedelta(**kwargs)
        return self.current


class _FakePlatform:
    def __init__(self) -> None:
        self.registered: list[tuple[str, int, int]] = []
        self.unregistered: list[tuple[int, int]] = []
        self.idle_seconds: float = 0.0
        self.system_theme: ThemeMode = ThemeMode.DARK

    def register_hotkey(self, shortcut: str, *, hotkey_id: int = 1, hwnd: int = 0) -> bool:
        self.registered.append((shortcut, hotkey_id, hwnd))
        return True

    def unregister_hotkey(self, hotkey_id: int, *, hwnd: int = 0) -> None:
        self.unregistered.append((hotkey_id, hwnd))

    def get_idle_seconds(self) -> float:
        return self.idle_seconds

    def get_system_theme(self) -> ThemeMode:
        return self.system_theme


def _make_window(
    qtbot: QtBot,
    tmp_path: Path,
) -> tuple[MainWindow, TodoService, _FakeClock, _FakePlatform, SQLiteRepository]:
    clock = _FakeClock(datetime(2026, 11, 25, 14, 0, tzinfo=UTC))
    platform = _FakePlatform()
    repo = SQLiteRepository(tmp_path / "ui_test.db")
    service = TodoService(repo, clock=clock, platform=platform)
    window = MainWindow(service, platform=platform, clock=clock)
    qtbot.addWidget(window)
    window.show_and_focus()
    QApplication.processEvents()
    return window, service, clock, platform, repo


def test_quick_bar_add_requester_pill_and_search_mode(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, _platform, repo = _make_window(qtbot, tmp_path)
    try:
        QTest.keyClicks(window.quick_bar.input_edit, "API rate limit fix @Maya")
        assert window.quick_bar.requester_pill.isVisible()
        assert window.quick_bar.requester_pill.text() == "@Maya"
        assert window.quick_bar.enter_hint.isVisible()

        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Return)
        assert window.quick_bar.text() == ""
        tasks = service.list_active_tasks()
        assert len(tasks) == 1
        assert tasks[0].title == "API rate limit fix"
        assert tasks[0].requester == "Maya"

        # Add a Done task and verify '/' search finds both without creating on Enter
        second = service.add_task_from_input("Review PR #418 @Sam")
        assert second is not None
        service.set_status(second.id, TaskStatus.DONE)
        window.refresh_views()

        QTest.keyClicks(window.quick_bar.input_edit, "/sam")
        assert window.quick_bar.is_search_mode()
        assert not window.quick_bar.requester_pill.isVisible()
        assert window.displayed_task_ids() == [second.id]

        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Return)
        assert len(service.list_tasks()) == 2
        assert window.task_scroll.hasFocus()
    finally:
        window.tick_timer.stop()
        repo.close()


def test_task_list_shortcuts_timer_promotion_status_and_reorder(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, clock, _platform, repo = _make_window(qtbot, tmp_path)
    try:
        t1 = service.add_task_from_input("First task @Alex")
        t2 = service.add_task_from_input("Second task @Maya")
        assert t1 is not None and t2 is not None
        window.refresh_views()

        # Jump from Quick Bar to Task List via Down
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        assert window.task_scroll.hasFocus()
        assert window.selected_task_id() == t1.id

        # Move down to second task and start timer -> promotes Todo to Doing and pins on top
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Down)
        assert window.selected_task_id() == t2.id
        QTest.keyClick(window.task_scroll, Qt.Key.Key_T)

        reloaded_t2 = service.get_task(t2.id)
        assert reloaded_t2 is not None
        assert reloaded_t2.status == TaskStatus.DOING
        assert reloaded_t2.is_timer_running
        assert window.displayed_task_ids() == [t2.id, t1.id]
        assert window.running_timer_pill.isVisible()

        clock.advance(seconds=12)
        window.on_tick()
        assert window.running_pill_text.text() == "00:00:12"

        # Stop timer with 't' (remains Doing)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_T)
        stopped_t2 = service.get_task(t2.id)
        assert stopped_t2 is not None
        assert not stopped_t2.is_timer_running
        assert stopped_t2.status == TaskStatus.DOING
        assert not window.running_timer_pill.isVisible()

        # Reorder Todo items with Alt+Down / Alt+Up
        t3 = service.add_task_from_input("Third task")
        assert t3 is not None
        window.refresh_views()
        window._select_task(t1.id)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
        todo_ids = [t.id for t in service.list_tasks(TaskStatus.TODO)]
        assert todo_ids == [t3.id, t1.id]

        # 'w' marks Waiting and moves it to Waiting tab
        QTest.keyClick(window.task_scroll, Qt.Key.Key_W)
        w_task = service.get_task(t1.id)
        assert w_task is not None and w_task.status == TaskStatus.WAITING
        QTest.keyClick(window.task_scroll, Qt.Key.Key_2)
        assert window.current_tab() == ViewTab.WAITING
        assert window.displayed_task_ids() == [t1.id]

        # 'd' marks Done and removes from Waiting
        QTest.keyClick(window.task_scroll, Qt.Key.Key_D)
        d_task = service.get_task(t1.id)
        assert d_task is not None and d_task.status == TaskStatus.DONE
        assert window.displayed_task_ids() == []
    finally:
        window.tick_timer.stop()
        repo.close()


def test_thinking_space_notes_sub_steps_and_work_sessions(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, _platform, repo = _make_window(qtbot, tmp_path)
    try:
        task = service.add_task_from_input("API rate limit fix @Maya")
        assert task is not None
        window.refresh_views()

        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Return)
        assert window.expanded_task_id() == task.id
        ts = window._thinking_widget
        assert ts is not None

        # Edit Notes and flush immediately
        ts.notes_editor.setPlainText("Check retry-after header.")
        ts.flush_pending_saves()
        updated = service.get_task(task.id)
        assert updated is not None
        assert updated.notes == "Check retry-after header."

        # Add and toggle Sub-step
        ts.add_sub_step_input.setFocus()
        QTest.keyClicks(ts.add_sub_step_input, "Reproduce 429 locally")
        QTest.keyClick(ts.add_sub_step_input, Qt.Key.Key_Return)
        updated = service.get_task(task.id)
        assert updated is not None and len(updated.sub_steps) == 1
        step_id = updated.sub_steps[0].id

        ts = window._thinking_widget
        assert ts is not None
        ts.sub_step_toggled.emit(step_id)
        updated = service.get_task(task.id)
        assert updated is not None and updated.sub_steps[0].is_done

        # Quick +15m chip & manual 25m session
        ts = window._thinking_widget
        assert ts is not None
        ts.time_adjusted.emit(task.id, 900)
        ts = window._thinking_widget
        assert ts is not None
        ts.open_manual_entry()
        QTest.keyClicks(ts.manual_duration_input, "25m")
        QTest.keyClick(ts.manual_duration_input, Qt.Key.Key_Return)

        updated = service.get_task(task.id)
        assert updated is not None
        assert updated.total_logged_seconds() == (900 + 1500)
    finally:
        window.tick_timer.stop()
        repo.close()


def test_daily_summary_view_overlap_and_day_navigation(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, clock, _platform, repo = _make_window(qtbot, tmp_path)
    try:
        t1 = service.add_task_from_input("Task A @Maya")
        t2 = service.add_task_from_input("Task B @Alex")
        assert t1 is not None and t2 is not None

        # Run overlapping timers: t1 [14:00..14:30], t2 [14:15..14:45] -> 45m wall-clock, 60m logged
        service.toggle_timer(t1.id)
        clock.advance(minutes=15)
        service.toggle_timer(t2.id)
        clock.advance(minutes=15)
        service.toggle_timer(t1.id)
        clock.advance(minutes=15)
        service.toggle_timer(t2.id)

        window.switch_tab(ViewTab.SUMMARY)
        assert window.current_tab() == ViewTab.SUMMARY
        assert window.summary_view.wall_clock_value.text() == "00:45:00"
        assert window.summary_view.total_logged_value.text() == "01:00:00"
        assert window.summary_view.overlap_caption.isVisible()
        assert "00:15:00" in window.summary_view.overlap_caption.text()
        assert not window.summary_view.next_day_button.isEnabled()

        # Navigate to previous day (empty) and back
        window.summary_view.prev_day_button.click()
        assert window.summary_view.next_day_button.isEnabled()
        assert window.summary_view.wall_clock_value.text() == "00:00:00"

        window.summary_view.next_day_button.click()
        assert window.summary_view.wall_clock_value.text() == "00:45:00"
    finally:
        window.tick_timer.stop()
        repo.close()


def test_settings_modal_theme_hints_and_hotkey_update(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, platform, repo = _make_window(qtbot, tmp_path)
    try:
        assert window.hints_footer.isVisible()
        assert window.hints_footer.height() == 28

        # Open Settings via Ctrl+,
        QTest.keyClick(window, Qt.Key.Key_Comma, Qt.KeyboardModifier.ControlModifier)
        assert window.settings_overlay.isVisible()

        # Toggle Show Shortcut Hints Off -> footer collapses completely
        window.settings_overlay.hints_switch.click()
        assert not window.hints_footer.isVisible()
        assert window.hints_footer.height() == 0
        assert not service.get_settings().show_shortcut_hints

        # Switch theme to Light
        window.settings_overlay._theme_buttons[ThemeMode.LIGHT].click()
        assert service.get_settings().theme == ThemeMode.LIGHT
        assert not window._tokens.is_dark

        # Capture new Global Shortcut Ctrl+Shift+K
        window.settings_overlay.shortcut_button.click()
        assert window.settings_overlay.is_capturing_shortcut()
        QTest.keyClick(
            window.settings_overlay,
            Qt.Key.Key_K,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        assert not window.settings_overlay.is_capturing_shortcut()
        assert service.get_settings().global_shortcut == "Ctrl+Shift+K"
        assert platform.registered[-1][0] == "Ctrl+Shift+K"

        # Change Idle Check Threshold to 30m
        idx_30 = window.settings_overlay.idle_combo.findData(IdleThreshold.THIRTY_MIN)
        window.settings_overlay.idle_combo.setCurrentIndex(idx_30)
        assert service.get_settings().idle_threshold == IdleThreshold.THIRTY_MIN

        window.settings_overlay.done_button.click()
        assert not window.settings_overlay.isVisible()
    finally:
        window.tick_timer.stop()
        repo.close()


def test_idle_banner_keep_and_trim_without_stealing_focus(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, clock, platform, repo = _make_window(qtbot, tmp_path)
    try:
        task = service.add_task_from_input("Long debug session")
        assert task is not None
        service.toggle_timer(task.id)
        clock.advance(minutes=25)
        platform.idle_seconds = 1200.0  # 20m >= 15m default threshold

        window.quick_bar.focus_input()
        window.check_idle_once()

        assert window.idle_banner.isVisible()
        assert window.quick_bar.has_input_focus()
        assert "20m" in window.idle_banner.message_label.text()

        # Keep dismisses banner and preserves running timer
        window.idle_banner.keep_button.click()
        assert not window.idle_banner.isVisible()
        kept = service.get_task(task.id)
        assert kept is not None and kept.is_timer_running

        # Reset idle below threshold then exceed again -> Trim trims back to idle onset
        platform.idle_seconds = 0.0
        window.check_idle_once()
        platform.idle_seconds = 900.0  # 15m
        window.check_idle_once()
        assert window.idle_banner.isVisible()

        window.idle_banner.trim_button.click()
        assert not window.idle_banner.isVisible()
        trimmed = service.get_task(task.id)
        assert trimmed is not None and not trimmed.is_timer_running
        assert trimmed.total_logged_seconds() == 600  # 25m - 15m = 10m
    finally:
        window.tick_timer.stop()
        repo.close()


def test_layered_escape_closes_modal_thinking_quick_bar_then_hides(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, _clock, _platform, repo = _make_window(qtbot, tmp_path)
    try:
        task = service.add_task_from_input("Write docs")
        assert task is not None
        window.refresh_views()

        # 1. Settings open -> Esc closes Settings only
        window.open_settings()
        assert window.settings_overlay.isVisible()
        QTest.keyClick(window.settings_overlay, Qt.Key.Key_Escape)
        assert not window.settings_overlay.isVisible()
        assert window.isVisible()

        # 2. Thinking Space expanded -> Esc collapses Thinking Space back to Task List
        window._select_task(task.id)
        window._toggle_expand_selected()
        assert window.expanded_task_id() == task.id
        assert window._thinking_widget is not None
        window._thinking_widget.notes_editor.setFocus()
        QTest.keyClick(window._thinking_widget.notes_editor, Qt.Key.Key_Escape)
        assert window.expanded_task_id() is None
        assert window.isVisible()

        # 3. Non-empty Quick Bar -> Esc clears Quick Bar without hiding
        window.quick_bar.focus_input()
        QTest.keyClicks(window.quick_bar.input_edit, "draft query")
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Escape)
        assert window.quick_bar.text() == ""
        assert window.isVisible()

        # 4. Empty Quick Bar / top level -> Esc hides window
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Escape)
        assert not window.isVisible()
    finally:
        window.tick_timer.stop()
        repo.close()


def test_app_build_application_registers_hotkey_syncs_tray_and_shuts_down(
    qtbot: QtBot, tmp_path: Path
) -> None:
    platform = _FakePlatform()
    runtime = build_application(db_path=tmp_path / "app.db", platform=platform)
    qtbot.addWidget(runtime.window)
    try:
        assert platform.registered == [("Ctrl+Alt+Space", 1, runtime.window.hotkey_hwnd())]
        task = runtime.service.add_task_from_input("Tray test task")
        assert task is not None
        runtime.service.toggle_timer(task.id)
        runtime.window.refresh_views()

        assert runtime.tray.status_action.isVisible()
        assert "Running: 1 Task" in runtime.tray.status_action.text()

        # Clean shutdown closes running timer and unregisters hotkey
        runtime.service.update_settings(Settings(theme=ThemeMode.LIGHT))
        runtime.service.shutdown(hotkey_id=1, hwnd=runtime.window.hotkey_hwnd())
        assert platform.unregistered == [(1, runtime.window.hotkey_hwnd())]
        stopped = runtime.service.get_task(task.id)
        assert stopped is not None and not stopped.is_timer_running
    finally:
        runtime.window.tick_timer.stop()
        runtime.repository.close()
