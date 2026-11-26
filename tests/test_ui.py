"""PySide6 / pytest-qt UI integration tests for nyatodo."""

import ctypes
import sys
from ctypes import wintypes
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QMessageLogContext,
    QObject,
    QPoint,
    QPointF,
    Qt,
    QtMsgType,
    qInstallMessageHandler,
)
from PySide6.QtGui import QCursor, QEnterEvent, QGuiApplication, QImage, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QLabel,
    QPushButton,
    QToolButton,
    QWidget,
)
from pytestqt.qtbot import QtBot

from nyatodo.app import build_application
from nyatodo.domain import (
    AutoHideDelay,
    IdleThreshold,
    Settings,
    SummaryPeriod,
    TaskDateFilterMode,
    TaskImportance,
    TaskSortMode,
    TaskStatus,
    ThemeMode,
)
from nyatodo.platform_win32 import WM_HOTKEY
from nyatodo.service import TodoService
from nyatodo.storage import SQLiteRepository
from nyatodo.ui.hints_footer import HintContext
from nyatodo.ui.main_window import MainWindow, ViewTab
from nyatodo.ui.requester_autocomplete_popup import RequesterAutocompletePopup
from nyatodo.ui.task_row import TaskRowWidget
from nyatodo.ui.theme import DARK_TOKENS, LIGHT_TOKENS, load_bundled_fonts, make_ui_font
from nyatodo.ui.thinking_space import ThinkingSpaceWidget


class FakeClock:
    """Deterministic controllable clock for UI tests."""

    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs: int) -> datetime:
        self.current = self.current + timedelta(**kwargs)
        return self.current


class FakePlatform:
    """Deterministic fake PlatformBridge for UI tests."""

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


def make_window(
    qtbot: QtBot,
    tmp_path: Path,
    *,
    show: bool = True,
) -> tuple[MainWindow, TodoService, FakeClock, FakePlatform, SQLiteRepository]:
    """Construct a wired MainWindow + TodoService backed by a temp SQLite DB."""
    clock = FakeClock(datetime(2026, 11, 25, 14, 0, tzinfo=UTC))
    platform = FakePlatform()
    repo = SQLiteRepository(tmp_path / "ui_test.db")
    service = TodoService(repo, clock=clock, platform=platform, local_tz=UTC)
    window = MainWindow(service, clock=clock)
    qtbot.addWidget(window)
    if show:
        window.show_and_focus()
        QApplication.processEvents()
    return window, service, clock, platform, repo


def find_thinking_space(window: MainWindow) -> ThinkingSpaceWidget:
    """Locate the currently expanded ThinkingSpaceWidget via public objectName."""
    widget = window.findChild(ThinkingSpaceWidget, "ThinkingSpace")
    assert widget is not None
    return widget


def find_task_row(window: MainWindow, task_id: str) -> TaskRowWidget:
    """Locate a TaskRowWidget for task_id via public child lookup."""
    for row in window.findChildren(TaskRowWidget, "TaskRow"):
        if row.task_id == task_id:
            return row
    raise AssertionError(f"TaskRowWidget not found for {task_id}")


def send_hover_enter(widget: QAbstractButton | TaskRowWidget | object) -> None:
    """Dispatch a synthetic QEnterEvent to trigger hover-only UI reveals."""
    from PySide6.QtWidgets import QWidget

    assert isinstance(widget, QWidget)
    pos = QPointF(4.0, 4.0)
    QApplication.sendEvent(widget, QEnterEvent(pos, pos, pos))


def send_hover_leave(widget: object) -> None:
    """Dispatch a synthetic QEvent.Leave to trigger hover exit."""
    from PySide6.QtWidgets import QWidget

    assert isinstance(widget, QWidget)
    QApplication.sendEvent(widget, QEvent(QEvent.Type.Leave))


def test_quick_bar_add_requester_pill_and_search_mode(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
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

        # Add a Done task and verify '/' search finds it without creating on Enter
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
    window, service, clock, _platform, repo = make_window(qtbot, tmp_path)
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

        # Reorder Todo items with Alt+Down after moving selection onto t1 via Down
        t3 = service.add_task_from_input("Third task")
        assert t3 is not None
        window.refresh_views()
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Down)
        assert window.selected_task_id() == t1.id
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
        todo_ids = [t.id for t in service.list_tasks(TaskStatus.TODO)]
        assert todo_ids == [t3.id, t1.id]

        # 'w' marks Waiting and '2' switches to Waiting tab; Ctrl+2 / '/' do not hijack Task List
        QTest.keyClick(window.task_scroll, Qt.Key.Key_W)
        w_task = service.get_task(t1.id)
        assert w_task is not None and w_task.status == TaskStatus.WAITING

        QTest.keyClick(window.task_scroll, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
        assert window.current_tab() == ViewTab.ACTIVE
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Slash)
        assert not window.quick_bar.has_input_focus()

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


def test_running_timer_displays_active_session_separate_from_total_logged(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        task = service.add_task_from_input("API rate limit fix @Maya")
        assert task is not None
        # Add 30m closed session first
        service.add_manual_session(task.id, 30 * 60)
        window.refresh_views()

        # Select, expand, and start a fresh live TaskTimer
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Return)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_T)

        clock.advance(seconds=12)
        window.on_tick()

        row = find_task_row(window, task.id)
        ts = find_thinking_space(window)

        assert row.timer_label.text() == "00:00:12"
        assert window.running_pill_text.text() == "00:00:12"
        assert ts.timer_button.text() == "Stop 00:00:12"
        assert ts.sessions_header_label.text() == "Work Sessions · 00:30:12"
    finally:
        window.tick_timer.stop()
        repo.close()


def test_thinking_space_notes_sub_steps_and_manual_sessions(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        task = service.add_task_from_input("API rate limit fix @Maya")
        assert task is not None
        window.refresh_views()

        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Return)
        assert window.expanded_task_id() == task.id
        ts = find_thinking_space(window)

        # Edit Notes and flush immediately
        ts.notes_editor.setPlainText("Check retry-after header.")
        ts.flush_pending_saves()
        updated = service.get_task(task.id)
        assert updated is not None
        assert updated.notes == "Check retry-after header."

        # Add Sub-step via UI input and toggle it via checkbox click
        ts.add_sub_step_input.setFocus()
        QTest.keyClicks(ts.add_sub_step_input, "Reproduce 429 locally")
        QTest.keyClick(ts.add_sub_step_input, Qt.Key.Key_Return)
        updated = service.get_task(task.id)
        assert updated is not None and len(updated.sub_steps) == 1

        ts = find_thinking_space(window)
        checkbox = ts.findChild(QAbstractButton, "SubStepCheckBox")
        assert checkbox is not None
        checkbox.click()
        updated = service.get_task(task.id)
        assert updated is not None and updated.sub_steps[0].is_done

        # Quick +15m chip click
        ts = find_thinking_space(window)
        chip_15 = next(
            btn for btn in ts.findChildren(QPushButton, "SessionChip") if btn.text() == "+15m"
        )
        chip_15.click()

        # Manual duration entry '25m'
        ts = find_thinking_space(window)
        ts.manual_toggle_button.click()
        assert ts.manual_duration_input.placeholderText() == "25m or 14:10-14:40"
        QTest.keyClicks(ts.manual_duration_input, "25m")
        QTest.keyClick(ts.manual_duration_input, Qt.Key.Key_Return)

        # Invalid manual range surfaces inline error without collapsing input
        ts = find_thinking_space(window)
        ts.manual_toggle_button.click()
        QTest.keyClicks(ts.manual_duration_input, "14:40-14:10")
        QTest.keyClick(ts.manual_duration_input, Qt.Key.Key_Return)
        assert ts.manual_error_label.isVisible()
        assert ts.manual_entry_row.isVisible()

        # Valid manual range '14:10-14:40' adds a 30m WorkSession
        ts.manual_duration_input.clear()
        QTest.keyClicks(ts.manual_duration_input, "14:10-14:40")
        QTest.keyClick(ts.manual_duration_input, Qt.Key.Key_Return)

        updated = service.get_task(task.id)
        assert updated is not None
        assert updated.total_logged_seconds() == (900 + 1500 + 1800)
        assert any(
            s.started_at == datetime(2026, 11, 25, 14, 10, tzinfo=UTC)
            and s.ended_at == datetime(2026, 11, 25, 14, 40, tzinfo=UTC)
            for s in updated.work_sessions
        )
    finally:
        window.tick_timer.stop()
        repo.close()


def test_hover_only_delete_for_task_sub_step_and_work_session(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        t1 = service.add_task_from_input("Delete me later")
        t2 = service.add_task_from_input("Keep me")
        assert t1 is not None and t2 is not None
        service.add_sub_step(t1.id, "Temp step")
        service.add_manual_session(t1.id, 600)
        window.refresh_views()

        # Expand t1 to inspect SubStep & WorkSession hover-only delete buttons
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Return)
        ts = find_thinking_space(window)

        sub_row = ts.findChild(QLabel, "SubStepRow")
        assert sub_row is None  # SubStepRow is a QWidget, not QLabel
        from PySide6.QtWidgets import QWidget

        sub_step_row = ts.findChild(QWidget, "SubStepRow")
        session_row = ts.findChild(QWidget, "WorkSessionRow")
        assert sub_step_row is not None and session_row is not None

        sub_del = sub_step_row.findChild(QToolButton, "RowDeleteButton")
        ses_del = session_row.findChild(QToolButton, "RowDeleteButton")
        assert sub_del is not None and ses_del is not None
        assert not sub_del.isVisible()
        assert not ses_del.isVisible()

        send_hover_enter(sub_step_row)
        assert sub_del.isVisible()
        send_hover_leave(sub_step_row)
        assert not sub_del.isVisible()

        send_hover_enter(session_row)
        assert ses_del.isVisible()
        ses_del.click()
        reloaded = service.get_task(t1.id)
        assert reloaded is not None and len(reloaded.work_sessions) == 0

        ts = find_thinking_space(window)
        sub_step_row = ts.findChild(QWidget, "SubStepRow")
        assert sub_step_row is not None
        sub_del = sub_step_row.findChild(QToolButton, "RowDeleteButton")
        assert sub_del is not None
        send_hover_enter(sub_step_row)
        sub_del.click()
        reloaded = service.get_task(t1.id)
        assert reloaded is not None and len(reloaded.sub_steps) == 0

        # TaskRowWidget hover-only 'x' deletes entire Task
        row_t1 = find_task_row(window, t1.id)
        row_del = row_t1.findChild(QToolButton, "RowDeleteButton")
        assert row_del is not None
        assert not row_del.isVisible()

        send_hover_enter(row_t1)
        assert row_del.isVisible()
        send_hover_leave(row_t1)
        assert not row_del.isVisible()

        send_hover_enter(row_t1)
        row_del.click()
        assert service.get_task(t1.id) is None
        assert window.displayed_task_ids() == [t2.id]
    finally:
        window.tick_timer.stop()
        repo.close()


def test_daily_summary_view_overlap_and_day_navigation(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, clock, _platform, repo = make_window(qtbot, tmp_path)
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
    window, service, _clock, platform, repo = make_window(qtbot, tmp_path)
    try:
        assert window.hints_footer.isVisible()
        assert window.hints_footer.height() == 20
        assert window.shell.graphicsEffect() is None
        assert window.settings_overlay.graphicsEffect() is None

        task = service.add_task_from_input("Theme refresh task @Maya")
        assert task is not None
        window.refresh_views()
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Return)

        # Open Settings via Ctrl+,
        QTest.keyClick(window, Qt.Key.Key_Comma, Qt.KeyboardModifier.ControlModifier)
        assert window.settings_overlay.isVisible()
        assert window.settings_overlay.geometry() == window.shell.rect()

        # Toggle Show Shortcut Hints Off -> footer collapses completely
        window.settings_overlay.hints_switch.click()
        assert not window.hints_footer.isVisible()
        assert window.hints_footer.height() == 0
        assert not service.get_settings().show_shortcut_hints

        # Switch theme to Light via public objectName lookup and verify active widgets refresh
        light_btn = next(
            btn
            for btn in window.settings_overlay.findChildren(QPushButton, "SettingsSegmentOption")
            if btn.text() == "Light"
        )
        light_btn.click()
        assert service.get_settings().theme == ThemeMode.LIGHT
        assert LIGHT_TOKENS.bg_window in window.styleSheet()
        assert find_task_row(window, task.id)._tokens == LIGHT_TOKENS
        assert find_thinking_space(window)._tokens == LIGHT_TOKENS

        # System theme follows PlatformBridge.get_system_theme()
        platform.system_theme = ThemeMode.DARK
        system_btn = next(
            btn
            for btn in window.settings_overlay.findChildren(QPushButton, "SettingsSegmentOption")
            if btn.text() == "System"
        )
        system_btn.click()
        assert service.get_settings().theme == ThemeMode.SYSTEM
        assert DARK_TOKENS.bg_window in window.styleSheet()
        assert find_task_row(window, task.id)._tokens == DARK_TOKENS

        # Capture new Global Shortcut Ctrl+Shift+K (passes hwnd=0)
        window.settings_overlay.shortcut_button.click()
        assert window.settings_overlay.is_capturing_shortcut()
        QTest.keyClick(
            window.settings_overlay,
            Qt.Key.Key_K,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        assert not window.settings_overlay.is_capturing_shortcut()
        assert service.get_settings().global_shortcut == "Ctrl+Shift+K"
        assert platform.registered[-1] == ("Ctrl+Shift+K", 1, 0)

        # Change Idle Check Threshold to 30m
        idx_30 = window.settings_overlay.idle_combo.findData(IdleThreshold.THIRTY_MIN)
        window.settings_overlay.idle_combo.setCurrentIndex(idx_30)
        assert service.get_settings().idle_threshold == IdleThreshold.THIRTY_MIN

        # Change Auto-Hide on Focus Loss to 5s
        idx_5s = window.settings_overlay.auto_hide_combo.findData(AutoHideDelay.FIVE_SEC)
        window.settings_overlay.auto_hide_combo.setCurrentIndex(idx_5s)
        assert service.get_settings().auto_hide_delay == AutoHideDelay.FIVE_SEC

        window.settings_overlay.done_button.click()
        assert not window.settings_overlay.isVisible()
    finally:
        window.tick_timer.stop()
        repo.close()


def test_idle_banner_surfaces_on_resume_and_supports_keep_and_trim(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, clock, platform, repo = make_window(qtbot, tmp_path)
    try:
        task = service.add_task_from_input("Long debug session")
        assert task is not None
        service.toggle_timer(task.id)
        clock.advance(minutes=25)

        # Still idle (>=15m): poll records onset but does NOT surface banner until resume
        platform.idle_seconds = 1200.0  # 20m idle (onset 14:05)
        window.quick_bar.focus_input()
        window.check_idle_once()
        assert not window.idle_banner.isVisible()

        # Input resumes -> IdleBanner surfaces without stealing focus
        clock.advance(minutes=1)  # 14:26
        platform.idle_seconds = 0.0
        window.check_idle_once()

        assert window.idle_banner.isVisible()
        assert window.quick_bar.has_input_focus()
        assert "21m" in window.idle_banner.message_label.text()

        # Keep dismisses banner and preserves running timer
        window.idle_banner.keep_button.click()
        qtbot.waitUntil(lambda: not window.idle_banner.isVisible())
        kept = service.get_task(task.id)
        assert kept is not None and kept.is_timer_running

        # Another idle gap followed by resume -> Trim closes session back to idle onset
        clock.advance(minutes=19)  # 14:45
        platform.idle_seconds = 900.0  # 15m idle (onset 14:30)
        window.check_idle_once()
        assert not window.idle_banner.isVisible()

        clock.advance(minutes=1)  # 14:46
        platform.idle_seconds = 0.0
        window.check_idle_once()
        assert window.idle_banner.isVisible()

        window.idle_banner.trim_button.click()
        qtbot.waitUntil(lambda: not window.idle_banner.isVisible())
        trimmed = service.get_task(task.id)
        assert trimmed is not None and not trimmed.is_timer_running
        assert trimmed.total_logged_seconds() == 30 * 60  # 14:00 -> 14:30
    finally:
        window.tick_timer.stop()
        repo.close()


def test_layered_escape_closes_modal_thinking_quick_bar_then_hides(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
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
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Return)
        assert window.expanded_task_id() == task.id
        ts = find_thinking_space(window)
        ts.notes_editor.setFocus()
        QTest.keyClick(ts.notes_editor, Qt.Key.Key_Escape)
        assert window.expanded_task_id() is None
        assert window.isVisible()
        qtbot.waitUntil(lambda: window.findChild(ThinkingSpaceWidget, "ThinkingSpace") is None)

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


def test_show_and_focus_centers_on_active_screen_and_restores_dragged_position(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, _service, _clock, _platform, repo = make_window(qtbot, tmp_path, show=False)
    try:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        assert screen is not None
        avail = screen.availableGeometry()
        expected_x = avail.x() + (avail.width() - window.width()) // 2
        expected_y = avail.y() + (avail.height() - window.height()) // 2

        window.show_and_focus()
        QApplication.processEvents()
        assert abs(window.pos().x() - expected_x) <= 2
        assert abs(window.pos().y() - expected_y) <= 2

        # Simulate dragging the header bar by (+45, +35)
        start_local = window.shell.mapTo(window, window.header_bar.geometry().center())
        start_global = window.mapToGlobal(start_local)
        end_global = start_global + QPoint(45, 35)

        QApplication.sendEvent(
            window,
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(start_local),
                QPointF(start_global),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        QApplication.sendEvent(
            window,
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(start_local + QPoint(45, 35)),
                QPointF(end_global),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        QApplication.sendEvent(
            window,
            QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(start_local + QPoint(45, 35)),
                QPointF(end_global),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        dragged_pos = window.pos()
        assert dragged_pos == QPoint(expected_x + 45, expected_y + 35)

        # Hide and re-show -> restores dragged position instead of re-centering
        window.hide_to_tray()
        window.show_and_focus()
        QApplication.processEvents()
        assert window.pos() == dragged_pos
    finally:
        window.tick_timer.stop()
        repo.close()


def test_app_build_application_registers_hotkey_syncs_tray_and_shuts_down(
    qtbot: QtBot, tmp_path: Path
) -> None:
    platform = FakePlatform()
    runtime = build_application(db_path=tmp_path / "app.db", platform=platform)
    qtbot.addWidget(runtime.window)
    try:
        assert platform.registered == [("Ctrl+Alt+Space", 1, 0)]
        task = runtime.service.add_task_from_input("Tray test task")
        assert task is not None
        runtime.service.toggle_timer(task.id)
        runtime.window.refresh_views()

        assert runtime.tray.status_action.isVisible()
        assert "Running: 1 Task" in runtime.tray.status_action.text()

        # Changing shortcut via UI updates tray menu shortcut and re-registers with hwnd=0
        runtime.window.open_settings()
        runtime.window.settings_overlay.shortcut_button.click()
        QTest.keyClick(
            runtime.window.settings_overlay,
            Qt.Key.Key_K,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        assert platform.registered[-1] == ("Ctrl+Shift+K", 1, 0)
        assert "Ctrl+Shift+K" in runtime.tray.show_hide_action.text()

        # Clean shutdown closes running timer and unregisters thread hotkey (hwnd=0)
        runtime.service.shutdown(hotkey_id=1, hwnd=0)
        assert platform.unregistered[-1] == (1, 0)
        stopped = runtime.service.get_task(task.id)
        assert stopped is not None and not stopped.is_timer_running
    finally:
        runtime.window.tick_timer.stop()
        runtime.repository.close()


def test_compact_spotlight_mode_capture_and_auto_expand(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path, show=False)
    try:
        # 1. Global hotkey toggle_spotlight() opens Compact Spotlight Mode
        window.toggle_spotlight()
        QApplication.processEvents()
        assert window.isVisible()
        assert window.is_compact()
        assert 96 <= window.height() <= 112
        assert window.width() == 540
        assert not window.tabs_frame.isVisible()
        assert not window.stack.isVisible()
        assert not window.size_grip.isVisible()
        assert window.hints_footer.context() == HintContext.COMPACT_SPOTLIGHT

        # Repeated toggle_spotlight() hides and re-opens reliably in Compact Mode
        window.toggle_spotlight()
        assert not window.isVisible()
        window.toggle_spotlight()
        QApplication.processEvents()
        assert window.isVisible()
        assert window.is_compact()
        assert not (window.windowState() & Qt.WindowState.WindowMinimized)
        assert window.focusWidget() is window.quick_bar.input_edit

        # 2. Submitting a Task in Compact Mode creates Task, shows "Added" pill, stays compact
        QTest.keyClicks(window.quick_bar.input_edit, "Quick capture @Maya")
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Return)
        assert window.is_compact()
        assert window.quick_bar.text() == ""
        assert window.added_feedback_pill.isVisible()
        tasks = service.list_active_tasks()
        assert len(tasks) == 1
        assert tasks[0].title == "Quick capture"

        # 3. Pressing Down in Quick Bar auto-expands to Full Workspace Mode (540 x 640)
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QApplication.processEvents()
        assert not window.is_compact()
        assert window.size().width() == 540
        assert window.size().height() == 640
        assert window.tabs_frame.isVisible()
        assert window.stack.isVisible()
        assert window.focusWidget() is window.task_scroll

        # 4. Collapse back to Compact Mode via expand_button, then auto-expand on '/'
        window.expand_button.click()
        QApplication.processEvents()
        assert window.is_compact()
        QTest.keyClicks(window.quick_bar.input_edit, "/")
        QApplication.processEvents()
        assert not window.is_compact()
        assert window.quick_bar.is_search_mode()

        # 5. Collapse and verify Settings opens in Full Workspace Mode with aligned overlay
        window.quick_bar.clear()
        window.collapse_to_spotlight()
        assert window.is_compact()
        window.open_settings()
        QApplication.processEvents()
        assert not window.is_compact()
        assert window.settings_overlay.isVisible()
        assert window.settings_overlay.geometry() == window.shell.rect()
    finally:
        window.tick_timer.stop()
        repo.close()


def test_start_compact_constructor_and_tray_full_workspace(qtbot: QtBot, tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 11, 25, 14, 0, tzinfo=UTC))
    platform = FakePlatform()
    repo = SQLiteRepository(tmp_path / "compact.db")
    service = TodoService(repo, clock=clock, platform=platform, local_tz=UTC)
    window = MainWindow(service, clock=clock, start_compact=True)
    qtbot.addWidget(window)
    try:
        assert window.is_compact()
        window.toggle_visibility()
        QApplication.processEvents()
        assert window.isVisible()
        assert not window.is_compact()
        assert window.height() == 640
    finally:
        window.tick_timer.stop()
        repo.close()


def test_bundled_poppins_font_loads(qtbot: QtBot) -> None:
    loaded = load_bundled_fonts()
    assert loaded == "Poppins"
    font = make_ui_font(13)
    assert font.families()[0] == "Poppins"


def test_morph_pills_filter_strip_and_hover_action_orbs(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        t1 = service.add_task_from_input("Audit pill springs @Maya")
        t2 = service.add_task_from_input("Polish summary bars @Alex")
        assert t1 is not None and t2 is not None
        service.toggle_timer(t1.id)
        window.refresh_views()

        # Dynamic @Requester filter pills appear and filter tasks cleanly
        maya_pill = next(
            btn
            for btn in window.findChildren(QPushButton, "RequesterFilterPill")
            if btn.text() == "@Maya"
        )
        maya_pill.click()
        assert window.displayed_task_ids() == [t1.id]

        # Clicking active @Requester pill again clears filter
        maya_pill = next(
            btn
            for btn in window.findChildren(QPushButton, "RequesterFilterPill")
            if btn.text() == "@Maya"
        )
        maya_pill.click()
        assert set(window.displayed_task_ids()) == {t1.id, t2.id}

        # Doing pill filters only Doing tasks
        window.doing_filter_btn.click()
        assert window.displayed_task_ids() == [t1.id]
        window.active_tab_btn.click()
        assert set(window.displayed_task_ids()) == {t1.id, t2.id}

        # Hover action orbs reveal on enter and toggle timer / waiting
        row_t2 = find_task_row(window, t2.id)
        assert not row_t2.timer_orb.isVisible()
        assert not row_t2.wait_orb.isVisible()
        send_hover_enter(row_t2)
        assert row_t2.timer_orb.isVisible()
        assert row_t2.wait_orb.isVisible()

        row_t2.timer_orb.click()
        reloaded_t2 = service.get_task(t2.id)
        assert reloaded_t2 is not None and reloaded_t2.is_timer_running

        row_t2 = find_task_row(window, t2.id)
        send_hover_enter(row_t2)
        row_t2.wait_orb.click()
        waiting_t2 = service.get_task(t2.id)
        assert waiting_t2 is not None and waiting_t2.status == TaskStatus.WAITING
    finally:
        window.tick_timer.stop()
        repo.close()


class _UnexpectedWindowSpy(QObject):
    """Records unexpected top-level Show events or MainWindow deactivation during UI updates."""

    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self._main_window = main_window
        self.unexpected_shows: list[str] = []
        self.deactivated = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(watched, QWidget) and watched.isWindow():
            if event.type() == QEvent.Type.Show and watched is not self._main_window:
                self.unexpected_shows.append(type(watched).__name__)
            elif event.type() == QEvent.Type.WindowDeactivate and watched is self._main_window:
                self.deactivated = True
        return False


def test_switching_tabs_1_2_3_1_spawns_no_windows_and_keeps_focus(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    app = QApplication.instance()
    assert app is not None
    spy = _UnexpectedWindowSpy(window)
    app.installEventFilter(spy)
    try:
        service.add_task_from_input("Check tab switching @Maya")
        window.refresh_views()
        QApplication.processEvents()
        spy.unexpected_shows.clear()
        spy.deactivated = False

        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QApplication.processEvents()
        for key in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_1):
            focused = QApplication.focusWidget() or window
            QTest.keyClick(focused, key)
            QApplication.processEvents()

        assert spy.unexpected_shows == []
        assert not spy.deactivated
        assert window.current_tab() == ViewTab.ACTIVE
        assert window.task_scroll.hasFocus()
    finally:
        app.removeEventFilter(spy)
        window.tick_timer.stop()
        repo.close()


def test_hotkey_event_filter_handles_windows_generic_msg_and_toggles_spotlight(
    qtbot: QtBot, tmp_path: Path
) -> None:
    if sys.platform != "win32":
        pytest.skip("Win32 native WM_HOTKEY test only runs on Windows")

    platform = FakePlatform()
    runtime = build_application(db_path=tmp_path / "hotkey.db", platform=platform)
    qtbot.addWidget(runtime.window)
    try:
        runtime.window.hide_to_tray()
        assert not runtime.window.isVisible()

        msg = wintypes.MSG()
        msg.message = WM_HOTKEY
        msg.wParam = 1

        handled = runtime.hotkey_filter.nativeEventFilter(
            QByteArray(b"windows_generic_MSG"),
            ctypes.addressof(msg),
        )
        QApplication.processEvents()

        assert handled == (True, 0)
        assert runtime.window.isVisible()
        assert runtime.window.is_compact()
    finally:
        runtime.window.tick_timer.stop()
        runtime.tray.hide()
        runtime.repository.close()


def test_notes_editor_tab_and_ctrl_tab_navigate_out_of_notes(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        task = service.add_task_from_input("Focus navigation check")
        assert task is not None
        window.refresh_views()

        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Return)
        ts = find_thinking_space(window)

        ts.notes_editor.setFocus()
        QApplication.processEvents()
        assert ts.notes_editor.hasFocus()

        # Plain Tab moves focus out of NotesEditor instead of inserting '\t'
        QTest.keyClick(ts.notes_editor, Qt.Key.Key_Tab)
        QApplication.processEvents()
        assert not ts.notes_editor.hasFocus()
        assert ts.notes_editor.toPlainText() == ""

        # Shift+Tab moves back into NotesEditor, and Ctrl+Tab moves back out
        focused = QApplication.focusWidget()
        assert focused is not None
        QTest.keyClick(focused, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        QApplication.processEvents()
        assert ts.notes_editor.hasFocus()

        QTest.keyClick(ts.notes_editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()
        assert not ts.notes_editor.hasFocus()

        # Ctrl+Shift+Tab moves backward into NotesEditor, then out to requester_edit
        focused = QApplication.focusWidget()
        assert focused is not None
        QTest.keyClick(
            focused,
            Qt.Key.Key_Backtab,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        QApplication.processEvents()
        assert ts.notes_editor.hasFocus()

        QTest.keyClick(
            ts.notes_editor,
            Qt.Key.Key_Backtab,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        QApplication.processEvents()
        assert ts.requester_edit.hasFocus()
    finally:
        window.tick_timer.stop()
        window.focus_loss_timer.stop()
        repo.close()


def test_auto_hide_on_focus_loss_respects_delay_activation_and_off_setting(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        # Default delay is 3 seconds
        assert service.get_settings().auto_hide_delay == AutoHideDelay.THREE_SEC

        # Deactivate -> starts 3000ms focus-loss timer; re-activate cancels it
        QApplication.sendEvent(window, QEvent(QEvent.Type.WindowDeactivate))
        assert window.focus_loss_timer.isActive()
        assert window.focus_loss_timer.interval() == 3000

        QApplication.sendEvent(window, QEvent(QEvent.Type.WindowActivate))
        assert not window.focus_loss_timer.isActive()
        assert window.isVisible()

        # When set to OFF, losing focus does not start the timer
        off_settings = service.update_settings(
            Settings(auto_hide_delay=AutoHideDelay.OFF),
        )
        window.apply_settings(off_settings)
        QApplication.sendEvent(window, QEvent(QEvent.Type.WindowDeactivate))
        assert not window.focus_loss_timer.isActive()
        assert window.isVisible()

        # When set to IMMEDIATE (0s), losing focus hides window after event-loop tick
        imm_settings = service.update_settings(
            Settings(auto_hide_delay=AutoHideDelay.IMMEDIATE),
        )
        window.apply_settings(imm_settings)
        other_window = QWidget()
        qtbot.addWidget(other_window)
        other_window.show()
        other_window.activateWindow()
        QApplication.sendEvent(window, QEvent(QEvent.Type.WindowDeactivate))
        qtbot.waitUntil(lambda: not window.isVisible())
    finally:
        window.tick_timer.stop()
        window.focus_loss_timer.stop()
        repo.close()


def test_task_row_and_thinking_space_creation_dates(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        # Prior year task
        clock.current = datetime(2025, 11, 24, 14, 5, tzinfo=UTC)
        t_prior = service.add_task_from_input("Legacy migration")
        # Same year older task
        clock.current = datetime(2026, 11, 10, 9, 30, tzinfo=UTC)
        t_older = service.add_task_from_input("Earlier Nov task")
        # Yesterday
        clock.current = datetime(2026, 11, 25, 11, 15, tzinfo=UTC)
        t_yesterday = service.add_task_from_input("Yesterday task")
        # Today (2026-11-26)
        clock.current = datetime(2026, 11, 26, 18, 12, tzinfo=UTC)
        t_today = service.add_task_from_input("Today task @Maya")
        assert (
            t_prior is not None
            and t_older is not None
            and t_yesterday is not None
            and t_today is not None
        )

        window.refresh_views()

        row_today = find_task_row(window, t_today.id)
        row_yesterday = find_task_row(window, t_yesterday.id)
        row_older = find_task_row(window, t_older.id)
        row_prior = find_task_row(window, t_prior.id)

        assert row_today.date_pill.text() == "Today"
        assert row_today.date_pill.toolTip() == "Added Thu, Nov 26, 2026 · 18:12"
        assert row_yesterday.date_pill.text() == "Yesterday"
        assert row_older.date_pill.text() == "Nov 10"
        assert row_prior.date_pill.text() == "Nov 24 '25"

        # Expand Today task -> Thinking Space shows Added Thu, Nov 26 · 18:12
        window._expand_task(t_today.id)
        ts_today = find_thinking_space(window)
        assert ts_today.added_meta_label.text() == "Added Thu, Nov 26 · 18:12"

        # Expand prior year task -> includes year
        window._expand_task(t_prior.id)
        ts_prior = find_thinking_space(window)
        assert ts_prior.added_meta_label.text() == "Added Mon, Nov 24, 2025 · 14:05"
    finally:
        window.tick_timer.stop()
        repo.close()


def test_filter_and_sort_popover_sorting_filtering_and_manual_guard(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        # Last week: Wed Nov 18
        clock.current = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
        t_old_doing = service.add_task_from_input("Old doing task")
        t_wait_old = service.add_task_from_input("Waiting last week")
        # This week: Tue Nov 24
        clock.current = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
        t_week = service.add_task_from_input("Mid week task")
        # Today: Thu Nov 26
        clock.current = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
        t_today = service.add_task_from_input("Fresh today task")
        t_wait_today = service.add_task_from_input("Waiting today")
        assert (
            t_old_doing is not None
            and t_wait_old is not None
            and t_week is not None
            and t_today is not None
            and t_wait_today is not None
        )
        service.set_status(t_old_doing.id, TaskStatus.DOING)
        service.set_status(t_wait_old.id, TaskStatus.WAITING)
        service.set_status(t_wait_today.id, TaskStatus.WAITING)
        window.refresh_views()

        # Open Filter & Sort popover
        window.filter_sort_btn.click()
        assert window.filter_popover.isVisible()

        # Select Newest sort -> Doing pinned on top, Todo newest first
        newest_btn = next(
            b
            for b in window.filter_popover.findChildren(QPushButton, "SettingsSegmentOption")
            if b.text() == "Newest"
        )
        newest_btn.click()
        assert window.displayed_task_ids() == [t_old_doing.id, t_today.id, t_week.id]
        assert window.filter_sort_btn.property("active") is True

        # Alt+Down manual reorder is disabled while sort_mode != MANUAL
        window._focus_task_list()
        window._select_task(t_today.id)
        before_order = [t.id for t in service.list_tasks(TaskStatus.TODO)]
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
        assert [t.id for t in service.list_tasks(TaskStatus.TODO)] == before_order

        # Filter by Last Week -> applies across Active & Waiting
        last_week_chip = next(
            b
            for b in window.filter_popover.findChildren(QPushButton, "FilterChipButton")
            if b.text() == "Last Week"
        )
        last_week_chip.click()
        assert window.displayed_task_ids() == [t_old_doing.id]

        window.switch_tab(ViewTab.WAITING)
        assert window.displayed_task_ids() == [t_wait_old.id]

        # Re-open popover, select Custom range Nov 24..Nov 26
        window.filter_sort_btn.click()
        assert window.filter_popover.isVisible()
        custom_chip = next(
            b
            for b in window.filter_popover.findChildren(QPushButton, "FilterChipButton")
            if b.text() == "Custom"
        )
        custom_chip.click()
        assert window.filter_popover.custom_row.isVisible()

        from datetime import date as pydate

        from nyatodo.ui.filter_popover import _to_qdate

        window.filter_popover.from_date_edit.setDate(_to_qdate(pydate(2026, 11, 24)))
        window.filter_popover.to_date_edit.setDate(_to_qdate(pydate(2026, 11, 26)))
        assert window.displayed_task_ids() == [t_wait_today.id]

        # Esc closes popover without hiding MainWindow
        QTest.keyClick(window.filter_popover, Qt.Key.Key_Escape)
        qtbot.waitUntil(lambda: not window.filter_popover.isVisible())
        assert window.isVisible()

        # Reset restores Manual + Any
        window.filter_sort_btn.click()
        window.filter_popover.reset_button.click()
        assert window._sort_mode == TaskSortMode.MANUAL
        assert window._date_filter.mode == TaskDateFilterMode.ANY
        assert window.filter_sort_btn.property("active") is False
    finally:
        window.tick_timer.stop()
        repo.close()


def test_activity_summary_period_modal_work_week_custom_and_daily_strip(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        # Seed sessions across Mon Nov 23 and Thu Nov 26 (today)
        clock.current = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)
        t_mon = service.add_task_from_input("Monday planning @Maya")
        assert t_mon is not None
        service.toggle_timer(t_mon.id)
        clock.advance(minutes=45)
        service.toggle_timer(t_mon.id)

        clock.current = datetime(2026, 11, 26, 14, 0, tzinfo=UTC)
        t_thu = service.add_task_from_input("Thursday build")
        assert t_thu is not None
        service.toggle_timer(t_thu.id)
        clock.advance(minutes=30)  # 14:30, still running!

        window.switch_tab(ViewTab.SUMMARY)
        assert window.summary_view.period_button.text() == "Today · Thu, Nov 26"
        assert not window.summary_view.daily_strip_frame.isVisible()
        assert window.summary_view.wall_clock_value.text() == "00:30:00"

        # Open Summary Period Modal via period_button
        window.summary_view.period_button.click()
        assert window.summary_period_modal.isVisible()
        assert window.summary_period_modal.graphicsEffect() is None

        # Quick preset "This Week" -> closes modal, shows 7-day strip, aggregates Mon+Thu (75m)
        this_week_btn = window.summary_period_modal.preset_buttons["This Week"]
        this_week_btn.click()
        qtbot.waitUntil(lambda: not window.summary_period_modal.isVisible())
        assert window.summary_view.period_button.text() == "This Week · Nov 23\u201329"
        assert window.summary_view.daily_strip_frame.isVisible()
        strip_buttons = window.summary_view.daily_strip_frame.findChildren(
            QPushButton, "DailyStripDay"
        )
        assert len(strip_buttons) == 7
        assert window.summary_view.wall_clock_value.text() == "01:15:00"
        assert not window.summary_view.next_period_button.isEnabled()

        # Live 1s tick refreshes Work Week summary because today (Nov 26) is inside Nov 23..29
        clock.advance(seconds=15)
        window.on_tick()
        assert window.summary_view.wall_clock_value.text() == "01:15:15"

        # Step back to Last Week -> empty, live tick does not overwrite Last Week
        window.summary_view.prev_period_button.click()
        assert window.summary_view.period_button.text() == "Last Week · Nov 16\u201322"
        assert window.summary_view.wall_clock_value.text() == "00:00:00"
        clock.advance(seconds=10)
        window.on_tick()
        assert window.summary_view.period_button.text() == "Last Week · Nov 16\u201322"

        # Open modal and apply Custom 3-day range Nov 23..Nov 25 -> 3-day strip
        window.summary_view.period_button.click()
        assert window.summary_period_modal.isVisible()
        custom_mode_btn = next(
            b
            for b in window.summary_period_modal.findChildren(QPushButton, "SettingsSegmentOption")
            if b.text() == "Custom"
        )
        custom_mode_btn.click()
        from datetime import date as pydate

        from nyatodo.ui.summary_period_modal import _to_qdate as modal_qdate

        window.summary_period_modal.from_date_edit.setDate(modal_qdate(pydate(2026, 11, 23)))
        window.summary_period_modal.to_date_edit.setDate(modal_qdate(pydate(2026, 11, 25)))
        window.summary_period_modal.apply_button.click()
        qtbot.waitUntil(lambda: not window.summary_period_modal.isVisible())

        assert window.summary_view.period_button.text() == "Nov 23 \u2013 Nov 25"
        assert window.summary_view.wall_clock_value.text() == "00:45:00"
        strip_buttons = window.summary_view.daily_strip_frame.findChildren(
            QPushButton, "DailyStripDay"
        )
        assert len(strip_buttons) == 3

        # Click Monday Nov 23 in daily strip -> drills down into Day mode for Nov 23
        mon_btn = next(b for b in strip_buttons if b.property("day_iso") == "2026-11-23")
        mon_btn.click()
        assert window.summary_view.current_period() == SummaryPeriod.day(pydate(2026, 11, 23))
        assert not window.summary_view.daily_strip_frame.isVisible()
        assert window.summary_view.wall_clock_value.text() == "00:45:00"

        # Esc closes Summary Period Modal without hiding MainWindow
        window.summary_view.period_button.click()
        assert window.summary_period_modal.isVisible()
        QTest.keyClick(window.summary_period_modal, Qt.Key.Key_Escape)
        qtbot.waitUntil(lambda: not window.summary_period_modal.isVisible())
        assert window.isVisible()
    finally:
        window.tick_timer.stop()
        repo.close()


def test_task_list_direct_edit_shortcuts_n_s_r_e_and_compact_hints(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        task = service.add_task_from_input("Initial title @Maya")
        assert task is not None
        service.update_notes(task.id, "Start")
        window.refresh_views()

        # Focus Task List and verify compact TASK_LIST hints
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        assert window.task_scroll.hasFocus()
        assert window.hints_footer.context() == HintContext.TASK_LIST
        keycaps = [lbl.text() for lbl in window.hints_footer.findChildren(QLabel, "KeycapLabel")]
        verbs = [lbl.text() for lbl in window.hints_footer.findChildren(QLabel, "HintVerbLabel")]
        assert list(zip(keycaps, verbs, strict=True)) == [
            ("↓↑", "Move"),
            ("t", "Timer"),
            ("i", "!"),
            ("n/s/r/e", "Edit"),
            ("w", "Wait"),
            ("d", "Done"),
            ("Esc", "Hide"),
        ]

        # 1. 'n' focuses notes_editor at end; Enter adds newline, Esc saves & collapses
        QTest.keyClick(window.task_scroll, Qt.Key.Key_N)
        assert window.expanded_task_id() == task.id
        assert window.hints_footer.context() == HintContext.THINKING_SPACE
        ts = find_thinking_space(window)
        assert ts.notes_editor.hasFocus()
        assert ts.notes_editor.textCursor().position() == len("Start")

        QTest.keyClicks(ts.notes_editor, " more")
        QTest.keyClick(ts.notes_editor, Qt.Key.Key_Return)
        assert window.expanded_task_id() == task.id
        QTest.keyClicks(ts.notes_editor, "Next line")
        QTest.keyClick(ts.notes_editor, Qt.Key.Key_Escape)
        qtbot.waitUntil(lambda: window.findChild(ThinkingSpaceWidget, "ThinkingSpace") is None)
        assert window.expanded_task_id() is None
        assert window.task_scroll.hasFocus()
        assert window.hints_footer.context() == HintContext.TASK_LIST
        reloaded = service.get_task(task.id)
        assert reloaded is not None and reloaded.notes == "Start more\nNext line"

        # 2. 's' expands, focuses add_sub_step_input; Enter adds Sub-step and keeps focus for next
        QTest.keyClick(window.task_scroll, Qt.Key.Key_S)
        assert window.expanded_task_id() == task.id
        assert window.hints_footer.context() == HintContext.THINKING_SPACE
        ts = find_thinking_space(window)
        assert ts.add_sub_step_input.hasFocus()

        QTest.keyClicks(ts.add_sub_step_input, "First step")
        QTest.keyClick(ts.add_sub_step_input, Qt.Key.Key_Return)
        ts = find_thinking_space(window)
        assert ts.add_sub_step_input.hasFocus()
        QTest.keyClicks(ts.add_sub_step_input, "Second step")
        QTest.keyClick(ts.add_sub_step_input, Qt.Key.Key_Return)

        reloaded = service.get_task(task.id)
        assert reloaded is not None
        assert [step.title for step in reloaded.sub_steps] == ["First step", "Second step"]
        ts = find_thinking_space(window)
        assert ts.add_sub_step_input.hasFocus()
        QTest.keyClick(ts.add_sub_step_input, Qt.Key.Key_Escape)
        qtbot.waitUntil(lambda: window.findChild(ThinkingSpaceWidget, "ThinkingSpace") is None)
        assert window.task_scroll.hasFocus()

        # 3. 'r' expands, focuses requester_edit with text selected; Enter saves & collapses
        QTest.keyClick(window.task_scroll, Qt.Key.Key_R)
        assert window.expanded_task_id() == task.id
        assert window.hints_footer.context() == HintContext.THINKING_SPACE
        ts = find_thinking_space(window)
        assert ts.requester_edit.hasFocus()
        assert ts.requester_edit.selectedText() == "@Maya"

        QTest.keyClicks(ts.requester_edit, "Alex")
        QTest.keyClick(ts.requester_edit, Qt.Key.Key_Return)
        qtbot.waitUntil(lambda: window.findChild(ThinkingSpaceWidget, "ThinkingSpace") is None)
        assert window.expanded_task_id() is None
        assert window.task_scroll.hasFocus()
        assert window.hints_footer.context() == HintContext.TASK_LIST
        reloaded = service.get_task(task.id)
        assert reloaded is not None and reloaded.requester == "Alex"

        # 4. 'e' expands, focuses title_edit with text selected; Enter saves & collapses
        QTest.keyClick(window.task_scroll, Qt.Key.Key_E)
        assert window.expanded_task_id() == task.id
        assert window.hints_footer.context() == HintContext.THINKING_SPACE
        ts = find_thinking_space(window)
        assert ts.title_edit.hasFocus()
        assert ts.title_edit.selectedText() == "Initial title"

        QTest.keyClicks(ts.title_edit, "Updated title")
        QTest.keyClick(ts.title_edit, Qt.Key.Key_Return)
        qtbot.waitUntil(lambda: window.findChild(ThinkingSpaceWidget, "ThinkingSpace") is None)
        assert window.expanded_task_id() is None
        assert window.task_scroll.hasFocus()
        reloaded = service.get_task(task.id)
        assert reloaded is not None and reloaded.title == "Updated title"

        # 5. When Thinking Space is already expanded (focus in task_scroll), n/s/r/e jump directly
        QTest.keyClick(window.task_scroll, Qt.Key.Key_Return)
        assert window.expanded_task_id() == task.id
        assert window.task_scroll.hasFocus()

        QTest.keyClick(window.task_scroll, Qt.Key.Key_N)
        assert window.expanded_task_id() == task.id
        assert find_thinking_space(window).notes_editor.hasFocus()

        window.task_scroll.setFocus()
        QTest.keyClick(window.task_scroll, Qt.Key.Key_S)
        assert window.expanded_task_id() == task.id
        assert find_thinking_space(window).add_sub_step_input.hasFocus()

        window.task_scroll.setFocus()
        QTest.keyClick(window.task_scroll, Qt.Key.Key_R)
        assert window.expanded_task_id() == task.id
        ts = find_thinking_space(window)
        assert ts.requester_edit.hasFocus()
        assert ts.requester_edit.selectedText() == "@Alex"

        window.task_scroll.setFocus()
        QTest.keyClick(window.task_scroll, Qt.Key.Key_E)
        assert window.expanded_task_id() == task.id
        ts = find_thinking_space(window)
        assert ts.title_edit.hasFocus()
        assert ts.title_edit.selectedText() == "Updated title"
    finally:
        window.tick_timer.stop()
        repo.close()


def test_direct_edit_shortcut_scrolls_bottom_task_field_into_view(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        tasks = [service.add_task_from_input(f"Task #{i}") for i in range(14)]
        last_task = tasks[-1]
        assert last_task is not None
        window.refresh_views()

        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        for _ in range(len(tasks) - 1):
            QTest.keyClick(window.task_scroll, Qt.Key.Key_Down)
        assert window.selected_task_id() == last_task.id

        # Press 's' on bottom-most Task -> expand animates and scrolls add_sub_step_input into view
        QTest.keyClick(window.task_scroll, Qt.Key.Key_S)
        ts = find_thinking_space(window)
        assert ts.add_sub_step_input.hasFocus()
        qtbot.waitUntil(lambda: ts.maximumHeight() > 1000)
        QApplication.processEvents()

        viewport = window.task_scroll.viewport()
        top_left = ts.add_sub_step_input.mapTo(viewport, QPoint(0, 0))
        bottom_y = top_left.y() + ts.add_sub_step_input.height()
        assert top_left.y() >= 0
        assert bottom_y <= viewport.height()
    finally:
        window.tick_timer.stop()
        repo.close()


def test_filter_and_sort_mouse_click_reveals_non_zero_popover(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        t1 = service.add_task_from_input("Older task")
        t2 = service.add_task_from_input("Newer task")
        assert t1 is not None and t2 is not None
        window.refresh_views()

        QTest.mouseClick(
            window.filter_sort_btn,
            Qt.MouseButton.LeftButton,
            pos=window.filter_sort_btn.rect().center(),
        )
        qtbot.waitUntil(
            lambda: window.filter_popover.isVisible() and window.filter_popover.height() >= 120
        )

        newest_btn = next(
            b
            for b in window.filter_popover.findChildren(QPushButton, "SettingsSegmentOption")
            if b.text() == "Newest"
        )
        QTest.mouseClick(newest_btn, Qt.MouseButton.LeftButton, pos=newest_btn.rect().center())
        assert window._sort_mode == TaskSortMode.NEWEST
    finally:
        window.tick_timer.stop()
        repo.close()


def test_requester_pills_handle_more_than_three_people_and_long_names(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, _service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        # 1. Four short names fit inline without dropping the 4th person
        for idx, name in enumerate(("Al", "Bo", "Ed", "Jo")):
            QTest.keyClicks(window.quick_bar.input_edit, f"Short {idx} @{name}")
            QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Return)

        inline_names = [
            btn.property("requester_name") or btn.text().lstrip("@")
            for btn in window.findChildren(QPushButton, "RequesterFilterPill")
        ]
        overflow_btn = window.findChild(QPushButton, "RequesterOverflowButton")
        assert set(inline_names) == {"Al", "Bo", "Ed", "Jo"} or (
            overflow_btn is not None and overflow_btn.isVisible()
        )

        # 2. Add long-named people so >3 and overflow definitely occur
        for idx, name in enumerate(
            (
                "ChristopherAlexander",
                "JonathanMaximilian",
                "ElizabethMontgomery",
                "KatherineBell",
            )
        ):
            QTest.keyClicks(window.quick_bar.input_edit, f"Long {idx} @{name}")
            QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Return)

        QApplication.processEvents()
        # Filter & Sort and Summary buttons remain cleanly inside tabs_frame at both 540px and 460px
        for width in (540, 460):
            window.resize(width, 640)
            QApplication.processEvents()
            tabs_rect = window.tabs_frame.rect()
            assert tabs_rect.contains(window.filter_sort_btn.geometry())
            assert tabs_rect.contains(window.summary_tab_btn.geometry())
            assert window.requester_pills_host.geometry().right() < window.filter_sort_btn.x()

        # Overflow button is visible and lets the user select a 4th+ person (@KatherineBell)
        overflow_btn = window.findChild(QPushButton, "RequesterOverflowButton")
        assert overflow_btn is not None and overflow_btn.isVisible()
        QTest.mouseClick(
            overflow_btn,
            Qt.MouseButton.LeftButton,
            pos=overflow_btn.rect().center(),
        )
        popover = window.findChild(QWidget, "RequesterPopover")
        assert popover is not None
        qtbot.waitUntil(lambda: popover.isVisible() and popover.height() >= 60)

        katherine_item = next(
            b
            for b in popover.findChildren(QPushButton, "RequesterPopoverItem")
            if b.property("requester_name") == "KatherineBell"
        )
        QTest.mouseClick(
            katherine_item,
            Qt.MouseButton.LeftButton,
            pos=katherine_item.rect().center(),
        )
        QApplication.processEvents()
        assert len(window.displayed_task_ids()) == 1
        assert window.requester_filter() == "KatherineBell"

        # Active overflow requester is visible in the bar and clicking it clears the filter
        active_pill = next(
            b
            for b in window.findChildren(QPushButton, "RequesterFilterPill")
            if b.property("requester_name") == "KatherineBell"
        )
        assert active_pill.property("active") is True
        QTest.mouseClick(active_pill, Qt.MouseButton.LeftButton, pos=active_pill.rect().center())
        assert window.requester_filter() is None
        assert len(window.displayed_task_ids()) == 8
    finally:
        window.tick_timer.stop()
        repo.close()


def test_requester_pills_pack_inline_on_initial_cold_start_show(
    qtbot: QtBot, tmp_path: Path
) -> None:
    clock = FakeClock(datetime(2026, 11, 26, 19, 40, tzinfo=UTC))
    platform = FakePlatform()
    repo = SQLiteRepository(tmp_path / "cold_start.db")
    service = TodoService(repo, clock=clock, platform=platform, local_tz=UTC)
    for idx, name in enumerate(("adrian", "kamila", "kutasinski", "gowniak", "dkasodkasdp")):
        service.add_task_from_input(f"Task {idx} @{name}")

    window = MainWindow(service, clock=clock)
    qtbot.addWidget(window)
    try:
        window.show_and_focus()
        QApplication.processEvents()

        inline_names = [
            btn.property("requester_name")
            for btn in window.findChildren(QPushButton, "RequesterFilterPill")
        ]
        overflow_btn = window.findChild(QPushButton, "RequesterOverflowButton")
        assert inline_names[:2] == ["adrian", "kamila"]
        assert overflow_btn is not None and overflow_btn.text() == "+3"
    finally:
        window.tick_timer.stop()
        repo.close()


def test_quick_bar_requester_autocomplete_capture_navigation_and_compact_mode(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, clock, _platform, repo = make_window(qtbot, tmp_path, show=False)
    try:
        # Seed history including a Done task, a lowercase variant, and Bobby
        done_task = service.add_task_from_input("Archived work @DoneContact")
        assert done_task is not None
        service.toggle_done(done_task.id)
        clock.advance(minutes=1)
        service.add_task_from_input("Lowercase first @adrian")
        clock.advance(minutes=1)
        service.add_task_from_input("Proper case second @Adrian")
        clock.advance(minutes=1)
        service.add_task_from_input("Bobby task @Bobby")
        clock.advance(minutes=1)

        # Open in Compact Spotlight Mode
        window.toggle_spotlight()
        QApplication.processEvents()
        assert window.is_compact()
        popup: RequesterAutocompletePopup = window.quick_bar.requester_popup
        assert popup.isWindow()

        # 1. Bare '@' lists recent requesters including Done tasks, unclipped below compact bar
        QTest.keyClicks(window.quick_bar.input_edit, "Follow up @")
        QApplication.processEvents()
        assert popup.isVisible()
        assert popup.suggestions()[:3] == ["Bobby", "Adrian", "DoneContact"]
        assert popup.current_suggestion() == "Bobby"
        assert not popup.has_explicit_navigation()
        bar_bottom = window.quick_bar.mapToGlobal(QPoint(0, window.quick_bar.height())).y()
        assert popup.y() >= bar_bottom
        assert popup.height() >= 36
        assert window.is_compact()

        # 2. Typing 'ad' shows canonical '@Adrian' (even though lowercase 'adrian' also exists)
        window.quick_bar.clear()
        QTest.keyClicks(window.quick_bar.input_edit, "Ping @ad")
        QApplication.processEvents()
        assert popup.isVisible()
        assert popup.suggestions() == ["Adrian"]

        # Typing '@adrian' keeps popup open because case differs from canonical '@Adrian'
        QTest.keyClicks(window.quick_bar.input_edit, "rian")
        QApplication.processEvents()
        assert window.quick_bar.text() == "Ping @adrian"
        assert popup.isVisible()
        assert popup.suggestions() == ["Adrian"]

        # Exact case-sensitive sole match '@Adrian' hides popup silently
        window.quick_bar.clear()
        QTest.keyClicks(window.quick_bar.input_edit, "Ping @Adrian")
        QApplication.processEvents()
        assert not popup.isVisible()

        # 3. Second '@' token does not trigger popup
        QTest.keyClicks(window.quick_bar.input_edit, " and cc @bo")
        QApplication.processEvents()
        assert not popup.isVisible()

        # 4. Tab accepts highlighted suggestion with trailing space and keeps focus in Quick Bar
        window.quick_bar.clear()
        QTest.keyClicks(window.quick_bar.input_edit, "Review @ad")
        QApplication.processEvents()
        assert popup.isVisible()
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Tab)
        QApplication.processEvents()
        assert window.quick_bar.text() == "Review @Adrian "
        assert window.quick_bar.input_edit.cursorPosition() == len("Review @Adrian ")
        assert not popup.isVisible()
        assert window.quick_bar.has_input_focus()
        assert window.is_compact()

        # 5. Up/Down + Enter accepts suggestion without submitting Task
        window.quick_bar.clear()
        QTest.keyClicks(window.quick_bar.input_edit, "Call @")
        QApplication.processEvents()
        assert popup.suggestions()[:2] == ["Bobby", "Adrian"]
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        assert popup.has_explicit_navigation()
        assert popup.current_suggestion() == "Adrian"
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Up)
        assert popup.current_suggestion() == "Bobby"
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Down)
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Return)
        QApplication.processEvents()
        assert window.quick_bar.text() == "Call @Adrian "
        assert not popup.isVisible()
        assert window.quick_bar.has_input_focus()

        # 6. Esc closes popup without clearing text; next Esc clears Quick Bar
        window.quick_bar.clear()
        QTest.keyClicks(window.quick_bar.input_edit, "Sync @ad")
        QApplication.processEvents()
        assert popup.isVisible()
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Escape)
        QApplication.processEvents()
        assert not popup.isVisible()
        assert window.quick_bar.text() == "Sync @ad"
        assert window.isVisible()

        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Escape)
        QApplication.processEvents()
        assert window.quick_bar.text() == ""

        # 7. Unnavigated Enter submits '@Bob' directly even when '@Bobby' is highlighted
        QTest.keyClicks(window.quick_bar.input_edit, "Check @Bob")
        QApplication.processEvents()
        assert popup.isVisible()
        assert popup.current_suggestion() == "Bobby"
        assert not popup.has_explicit_navigation()
        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Return)
        QApplication.processEvents()
        assert not popup.isVisible()
        assert window.quick_bar.text() == ""
        bob_tasks = [t for t in service.list_active_tasks() if t.title == "Check"]
        assert len(bob_tasks) == 1
        assert bob_tasks[0].requester == "Bob"

        # 8. Clicking a popup row completes with trailing space and preserves input focus
        QTest.keyClicks(window.quick_bar.input_edit, "Meet @ad")
        QApplication.processEvents()
        assert popup.isVisible()
        row_btn = next(
            b
            for b in popup.findChildren(QPushButton, "RequesterAutocompleteRow")
            if b.property("requester_name") == "Adrian"
        )
        QTest.mouseClick(row_btn, Qt.MouseButton.LeftButton, pos=row_btn.rect().center())
        QApplication.processEvents()
        assert window.quick_bar.text() == "Meet @Adrian "
        assert not popup.isVisible()
        assert window.quick_bar.has_input_focus()
    finally:
        window.tick_timer.stop()
        repo.close()


def test_quick_bar_search_mode_requester_autocomplete(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        service.add_task_from_input("Prepare deck @Adrian")
        clock.advance(minutes=1)
        service.add_task_from_input("Fix CI @Maya")

        QTest.keyClicks(window.quick_bar.input_edit, "/@ad")
        QApplication.processEvents()
        popup = window.quick_bar.requester_popup
        assert window.quick_bar.is_search_mode()
        assert popup.isVisible()
        assert popup.suggestions() == ["Adrian"]

        QTest.keyClick(window.quick_bar.input_edit, Qt.Key.Key_Tab)
        QApplication.processEvents()
        assert window.quick_bar.text() == "/@Adrian "
        assert not popup.isVisible()
        assert window.quick_bar.has_input_focus()
        assert len(window.displayed_task_ids()) == 1
    finally:
        window.tick_timer.stop()
        repo.close()


def test_thinking_space_requester_autocomplete_workflow(qtbot: QtBot, tmp_path: Path) -> None:
    window, service, clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        service.add_task_from_input("Ref @Adrian")
        clock.advance(minutes=1)
        service.add_task_from_input("Ref @Adriana")
        clock.advance(minutes=1)
        service.add_task_from_input("Ref @Bobby")
        clock.advance(minutes=1)
        target = service.add_task_from_input("Target task @Maya")
        assert target is not None
        window.refresh_views()
        window._select_task(target.id)
        window.task_scroll.setFocus()
        QApplication.processEvents()

        # 1. 'r' expands and selects requester_edit without opening popup initially
        QTest.keyClick(window.task_scroll, Qt.Key.Key_R)
        QApplication.processEvents()
        ts = find_thinking_space(window)
        assert ts.requester_edit.hasFocus()
        assert ts.requester_edit.selectedText() == "@Maya"
        assert not ts.requester_popup.isVisible()

        # 2. Typing bare 'ad' opens popup; Tab fills '@Adriana' (most recent) and keeps focus
        QTest.keyClicks(ts.requester_edit, "ad")
        QApplication.processEvents()
        assert ts.requester_popup.isVisible()
        assert ts.requester_popup.suggestions() == ["Adriana", "Adrian"]
        QTest.keyClick(ts.requester_edit, Qt.Key.Key_Tab)
        QApplication.processEvents()
        assert ts.requester_edit.text() == "@Adriana"
        assert not ts.requester_popup.isVisible()
        assert ts.requester_edit.hasFocus()
        assert window.expanded_task_id() == target.id

        # 3. Typing '@ad', navigating with Down + Enter selects '@Adrian' without collapsing
        ts.requester_edit.selectAll()
        QTest.keyClicks(ts.requester_edit, "@ad")
        QApplication.processEvents()
        assert ts.requester_popup.isVisible()
        QTest.keyClick(ts.requester_edit, Qt.Key.Key_Down)
        assert ts.requester_popup.has_explicit_navigation()
        assert ts.requester_popup.current_suggestion() == "Adrian"
        QTest.keyClick(ts.requester_edit, Qt.Key.Key_Return)
        QApplication.processEvents()
        assert ts.requester_edit.text() == "@Adrian"
        assert not ts.requester_popup.isVisible()
        assert ts.requester_edit.hasFocus()
        assert window.expanded_task_id() == target.id

        # 4. Clicking a popup row fills requester and keeps focus in requester_edit
        ts.requester_edit.selectAll()
        QTest.keyClicks(ts.requester_edit, "ad")
        QApplication.processEvents()
        assert ts.requester_popup.isVisible()
        adriana_btn = next(
            b
            for b in ts.requester_popup.findChildren(QPushButton, "RequesterAutocompleteRow")
            if b.property("requester_name") == "Adriana"
        )
        QTest.mouseClick(adriana_btn, Qt.MouseButton.LeftButton, pos=adriana_btn.rect().center())
        QApplication.processEvents()
        assert ts.requester_edit.text() == "@Adriana"
        assert not ts.requester_popup.isVisible()
        assert ts.requester_edit.hasFocus()

        # 5. Esc closes open popup first without collapsing; next Esc saves & collapses
        ts.requester_edit.selectAll()
        QTest.keyClicks(ts.requester_edit, "@Bob")
        QApplication.processEvents()
        assert ts.requester_popup.isVisible()
        assert ts.requester_popup.suggestions() == ["Bobby"]
        QTest.keyClick(ts.requester_edit, Qt.Key.Key_Escape)
        QApplication.processEvents()
        assert not ts.requester_popup.isVisible()
        assert ts.requester_edit.hasFocus()
        assert window.expanded_task_id() == target.id

        QTest.keyClick(ts.requester_edit, Qt.Key.Key_Escape)
        qtbot.waitUntil(lambda: window.findChild(ThinkingSpaceWidget, "ThinkingSpace") is None)
        reloaded = service.get_task(target.id)
        assert reloaded is not None and reloaded.requester == "Bob"

        # 6. Unnavigated Enter in requester_edit saves typed text directly while popup is open
        window.task_scroll.setFocus()
        QTest.keyClick(window.task_scroll, Qt.Key.Key_R)
        QApplication.processEvents()
        ts = find_thinking_space(window)
        QTest.keyClicks(ts.requester_edit, "Bo")
        QApplication.processEvents()
        assert ts.requester_popup.isVisible()
        assert not ts.requester_popup.has_explicit_navigation()
        QTest.keyClick(ts.requester_edit, Qt.Key.Key_Return)
        qtbot.waitUntil(lambda: window.findChild(ThinkingSpaceWidget, "ThinkingSpace") is None)
        reloaded = service.get_task(target.id)
        assert reloaded is not None and reloaded.requester == "Bo"
    finally:
        window.tick_timer.stop()
        repo.close()


def test_main_window_startup_emits_no_qfont_point_size_warnings(
    qtbot: QtBot, tmp_path: Path
) -> None:
    captured: list[str] = []

    def _handler(_msg_type: QtMsgType, _ctx: QMessageLogContext, message: str) -> None:
        captured.append(message)

    previous = qInstallMessageHandler(_handler)
    try:
        window, _service, _clock, _platform, repo = make_window(qtbot, tmp_path)
        try:
            assert QGuiApplication.font().pointSize() > 0
            assert not any("QFont::setPointSize" in msg for msg in captured)
        finally:
            window.tick_timer.stop()
            repo.close()
    finally:
        qInstallMessageHandler(previous)


def test_importance_quick_bar_preview_sorting_shortcuts_and_thinking_space(
    qtbot: QtBot, tmp_path: Path
) -> None:
    window, service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        # 1. Quick Bar live Importance preview and creation
        window.quick_bar.input_edit.setText("Draft report")
        assert not window.quick_bar.importance_pill.isVisible()
        window.quick_bar.input_edit.setText("Urgent deploy !!! @Maya")
        assert window.quick_bar.importance_pill.isVisible()
        assert window.quick_bar.importance_pill.text() == "!!!"
        assert window.quick_bar.importance_pill.property("level") == "3"

        # Searching hides capture preview pills
        window.quick_bar.input_edit.setText("/ !!!")
        assert not window.quick_bar.importance_pill.isVisible()
        window.quick_bar.clear()

        t_none = service.add_task_from_input("Regular item")
        t_high = service.add_task_from_input("Urgent deploy !!! @Maya")
        t_low = service.add_task_from_input("Minor cleanup !")
        assert t_none is not None and t_high is not None and t_low is not None
        window.refresh_views()

        # Sorted by Importance descending: !!! -> ! -> None
        assert window.displayed_task_ids() == [t_high.id, t_low.id, t_none.id]
        row_high = window._row_widgets[t_high.id]
        row_low = window._row_widgets[t_low.id]
        row_none = window._row_widgets[t_none.id]
        assert row_high.importance_pill.isVisible()
        assert row_high.importance_pill.text() == "!!!"
        assert row_high.importance_pill.property("level") == "3"
        assert row_low.importance_pill.isVisible()
        assert row_low.importance_pill.text() == "!"
        assert row_low.importance_pill.property("level") == "1"
        assert not row_none.importance_pill.isVisible()

        # 2. Task List shortcuts 'i' and 'Shift+I' cycle Importance & re-sort
        window._select_task(t_none.id)
        window.task_scroll.setFocus()
        QTest.keyClick(window.task_scroll, Qt.Key.Key_I)
        reloaded = service.get_task(t_none.id)
        assert reloaded is not None and reloaded.importance == TaskImportance.LOW

        QTest.keyClick(window.task_scroll, Qt.Key.Key_I)
        reloaded = service.get_task(t_none.id)
        assert reloaded is not None and reloaded.importance == TaskImportance.MEDIUM
        assert window.displayed_task_ids() == [t_high.id, t_none.id, t_low.id]

        QTest.keyClick(window.task_scroll, Qt.Key.Key_I, Qt.KeyboardModifier.ShiftModifier)
        reloaded = service.get_task(t_none.id)
        assert reloaded is not None and reloaded.importance == TaskImportance.LOW

        # 3. Thinking Space segmented Importance selector updates task & re-sorts
        window._expand_task(t_low.id)
        ts = find_thinking_space(window)
        assert ts._importance_buttons[TaskImportance.LOW].property("active") is True
        btn_high = ts._importance_buttons[TaskImportance.HIGH]
        QTest.mouseClick(btn_high, Qt.MouseButton.LeftButton, pos=btn_high.rect().center())
        reloaded_low = service.get_task(t_low.id)
        assert reloaded_low is not None and reloaded_low.importance == TaskImportance.HIGH
        assert window.displayed_task_ids()[0] in (t_high.id, t_low.id)

        # 4. Done task in '/' search keeps muted Importance pill
        service.toggle_done(t_high.id)
        window.quick_bar.input_edit.setText("/ !!!")
        QApplication.processEvents()
        done_row = window._row_widgets[t_high.id]
        assert done_row.importance_pill.isVisible()
        assert done_row.importance_pill.property("done") is True
    finally:
        window.tick_timer.stop()
        repo.close()


def _rendered_glyph_padding(widget: QWidget) -> tuple[int, int, int, int]:
    """Return (left, right, top, bottom) pixel padding around a pill button's rendered glyph."""
    pixmap = widget.grab()
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    w, h = image.width(), image.height()
    dpr = pixmap.devicePixelRatio()
    bg = image.pixelColor(max(2, int(w * 0.2)), max(3, int(5 * dpr)))
    margin = max(2, int(2.5 * dpr))
    xs: list[int] = []
    ys: list[int] = []
    for y in range(margin, h - margin):
        for x in range(margin, w - margin):
            c = image.pixelColor(x, y)
            dist = abs(c.red() - bg.red()) + abs(c.green() - bg.green()) + abs(c.blue() - bg.blue())
            if dist > 18:
                xs.append(x)
                ys.append(y)
    assert xs and ys, "Expected visible icon pixels inside pill widget"
    return min(xs), (w - 1) - max(xs), min(ys), (h - 1) - max(ys)


def test_pill_icons_render_at_high_dpi_and_center_cleanly(qtbot: QtBot, tmp_path: Path) -> None:
    window, _service, _clock, _platform, repo = make_window(qtbot, tmp_path)
    try:
        for btn in (
            window.active_tab_btn,
            window.doing_filter_btn,
            window.waiting_tab_btn,
            window.summary_tab_btn,
            window.filter_sort_btn,
            window.expand_button,
            window.settings_button,
            window.summary_view.prev_period_button,
            window.summary_view.period_button,
            window.summary_view.next_period_button,
        ):
            icon_size = btn.iconSize()
            scaled = btn.icon().pixmap(icon_size, 2.0)
            assert scaled.devicePixelRatio() == pytest.approx(2.0)
            assert scaled.width() == icon_size.width() * 2
            assert scaled.height() == icon_size.height() * 2

        for symmetric_btn in (window.summary_tab_btn, window.filter_sort_btn):
            left, right, top, bottom = _rendered_glyph_padding(symmetric_btn)
            assert abs(left - right) <= 1
            assert abs(top - bottom) <= 1

        _left, _right, doing_top, doing_bottom = _rendered_glyph_padding(window.doing_filter_btn)
        assert abs(doing_top - doing_bottom) <= 1
    finally:
        window.tick_timer.stop()
        repo.close()
