"""PySide6 / pytest-qt UI integration tests for nyatodo."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QCursor, QEnterEvent, QGuiApplication, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QPushButton, QToolButton
from pytestqt.qtbot import QtBot

from nyatodo.app import build_application
from nyatodo.domain import IdleThreshold, TaskStatus, ThemeMode
from nyatodo.service import TodoService
from nyatodo.storage import SQLiteRepository
from nyatodo.ui.hints_footer import HintContext
from nyatodo.ui.main_window import MainWindow, ViewTab
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


def test_bundled_inter_font_loads(qtbot: QtBot) -> None:
    loaded = load_bundled_fonts()
    assert loaded == "Inter"
    font = make_ui_font(13)
    assert font.families()[0] == "Inter"
