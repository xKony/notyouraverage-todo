"""Tests for domain interval math and TodoService use cases."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from nyatodo.domain import (
    ActivitySummary,
    DayBreakdown,
    IdleThreshold,
    Settings,
    SummaryPeriod,
    SummaryPeriodKind,
    Task,
    TaskDateFilter,
    TaskDateFilterMode,
    TaskImportance,
    TaskSortMode,
    TaskStatus,
    ThemeMode,
    WorkSession,
    compute_wall_clock_seconds,
    format_summary_period_label,
    format_task_added_full,
    format_task_date_pill,
)
from nyatodo.service import TodoService
from nyatodo.storage import SQLiteRepository


class _FakeClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs: int) -> datetime:
        self.current = self.current + timedelta(**kwargs)
        return self.current


def test_compute_wall_clock_seconds_merges_overlapping_work_sessions() -> None:
    t0 = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
    sessions = [
        WorkSession(
            id="s1",
            task_id="t1",
            started_at=t0,
            ended_at=t0 + timedelta(minutes=30),
        ),
        WorkSession(
            id="s2",
            task_id="t2",
            started_at=t0 + timedelta(minutes=15),
            ended_at=t0 + timedelta(minutes=45),
        ),
        WorkSession(
            id="s3",
            task_id="t1",
            started_at=t0 + timedelta(minutes=60),
            ended_at=None,
        ),
    ]
    now = t0 + timedelta(minutes=70)

    # [10:00, 10:45] -> 45m (2700s), [11:00, 11:10] -> 10m (600s) => 3300s total
    assert compute_wall_clock_seconds(sessions, now=now) == 3300
    assert TaskStatus.TODO.value == "Todo"
    assert ThemeMode.DARK.value == "Dark"
    assert IdleThreshold.OFF.minutes is None
    assert IdleThreshold.FIFTEEN_MIN.minutes == 15


def test_task_active_session_seconds_distinguishes_running_vs_total() -> None:
    t0 = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
    stopped_task = Task(
        id="t1",
        title="Stopped task",
        created_at=t0,
        updated_at=t0,
        work_sessions=(
            WorkSession(id="s1", task_id="t1", started_at=t0, ended_at=t0 + timedelta(minutes=20)),
        ),
    )
    assert stopped_task.active_session_seconds(t0 + timedelta(minutes=30)) == 0
    assert stopped_task.total_logged_seconds(t0 + timedelta(minutes=30)) == 20 * 60

    running_task = Task(
        id="t2",
        title="Running task",
        created_at=t0,
        updated_at=t0,
        work_sessions=(
            WorkSession(id="s1", task_id="t2", started_at=t0, ended_at=t0 + timedelta(minutes=20)),
            WorkSession(
                id="s2", task_id="t2", started_at=t0 + timedelta(minutes=30), ended_at=None
            ),
        ),
    )
    now = t0 + timedelta(minutes=42)
    assert running_task.active_session_seconds(now) == 12 * 60
    assert running_task.total_logged_seconds(now) == 32 * 60


def test_service_add_search_edit_and_sub_steps() -> None:
    clock = _FakeClock(datetime(2026, 11, 25, 9, 0, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock)

        assert service.add_task_from_input("   ") is None
        t1 = service.add_task_from_input("Fix login bug @alex")
        t2 = service.add_task_from_input("Draft Q4 notes @Maya")
        assert t1 is not None and t2 is not None
        assert t1.title == "Fix login bug"
        assert t1.requester == "alex"
        assert t1.status == TaskStatus.TODO

        assert [t.id for t in service.search_tasks("/maya")] == [t2.id]
        assert [t.id for t in service.search_tasks("login")] == [t1.id]
        assert [t.id for t in service.search_tasks("/@maya")] == [t2.id]
        assert [t.id for t in service.search_tasks("@maya")] == [t2.id]
        assert [t.id for t in service.search_tasks("/@ma")] == [t2.id]
        assert [t.id for t in service.search_tasks("Q4 notes @Maya")] == [t2.id]
        assert [t.id for t in service.search_tasks("/Q4 @maya")] == [t2.id]
        assert service.search_tasks("login @Maya") == []

        t3 = service.add_task_from_input("Email user@domain.com about API")
        assert t3 is not None
        assert [t.id for t in service.search_tasks("user@domain.com")] == [t3.id]
        assert {t.id for t in service.search_tasks("/@")} == {t1.id, t2.id}

        clock.advance(minutes=5)
        updated = service.update_task(t1.id, title="Fix SSO login bug", requester="Sam")
        assert updated.title == "Fix SSO login bug"
        assert updated.requester == "Sam"

        updated = service.update_notes(t1.id, "Check token expiry.")
        assert updated.notes == "Check token expiry."

        step1 = service.add_sub_step(t1.id, "Reproduce locally")
        step2 = service.add_sub_step(t1.id, "Add regression test")
        toggled = service.toggle_sub_step(step1.id)
        assert toggled.is_done is True

        refreshed = service.get_task(t1.id)
        assert refreshed is not None
        assert refreshed.completed_sub_steps_count == 1
        assert [s.id for s in refreshed.sub_steps] == [step1.id, step2.id]

        service.delete_sub_step(step2.id)
        after_delete = service.get_task(t1.id)
        assert after_delete is not None
        assert [s.id for s in after_delete.sub_steps] == [step1.id]


def test_service_status_transitions_and_within_group_reordering() -> None:
    clock = _FakeClock(datetime(2026, 11, 25, 9, 0, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock)
        t1 = service.add_task_from_input("Task A")
        t2 = service.add_task_from_input("Task B")
        t3 = service.add_task_from_input("Task C")
        assert t1 is not None and t2 is not None and t3 is not None

        assert [t.id for t in service.list_active_tasks()] == [t1.id, t2.id, t3.id]

        # Move Task C up twice -> C, A, B
        service.reorder_task(t3.id, -1)
        service.reorder_task(t3.id, -1)
        assert [t.id for t in service.list_active_tasks()] == [t3.id, t1.id, t2.id]
        # Boundary clamp: moving top task up is a no-op
        service.reorder_task(t3.id, -1)
        assert [t.id for t in service.list_active_tasks()] == [t3.id, t1.id, t2.id]

        # Move Task A to Doing -> Active shows Doing pinned above Todo
        service.set_status(t1.id, TaskStatus.DOING)
        assert [t.id for t in service.list_active_tasks()] == [t1.id, t3.id, t2.id]

        # Waiting toggle
        service.toggle_waiting(t2.id)
        assert [t.id for t in service.list_waiting_tasks()] == [t2.id]
        assert [t.id for t in service.list_active_tasks()] == [t1.id, t3.id]
        service.toggle_waiting(t2.id)
        assert service.get_task(t2.id).status == TaskStatus.TODO  # type: ignore[union-attr]

        # Done & reopen
        clock.advance(minutes=10)
        done = service.toggle_done(t3.id)
        assert done.status == TaskStatus.DONE
        assert done.completed_at == clock.current
        assert [t.id for t in service.list_active_tasks()] == [t1.id, t2.id]

        reopened = service.toggle_done(t3.id)
        assert reopened.status == TaskStatus.TODO
        assert reopened.completed_at is None


def test_service_concurrent_timers_and_todo_to_doing_promotion() -> None:
    clock = _FakeClock(datetime(2026, 11, 25, 10, 0, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock)
        t1 = service.add_task_from_input("Write tests")
        t2 = service.add_task_from_input("Review PR")
        assert t1 is not None and t2 is not None

        # Starting timer on Todo promotes to Doing
        started1 = service.toggle_timer(t1.id)
        assert started1.status == TaskStatus.DOING
        assert started1.is_timer_running is True

        # Starting second timer concurrently keeps first running
        clock.advance(minutes=10)
        started2 = service.toggle_timer(t2.id)
        assert started2.status == TaskStatus.DOING
        assert started2.is_timer_running is True
        assert {t.id for t in service.get_running_tasks()} == {t1.id, t2.id}

        # Stopping first timer leaves it Doing and leaves second running
        clock.advance(minutes=15)
        paused1 = service.toggle_timer(t1.id)
        assert paused1.status == TaskStatus.DOING
        assert paused1.is_timer_running is False
        assert paused1.total_logged_seconds(clock.current) == 25 * 60
        assert [t.id for t in service.get_running_tasks()] == [t2.id]


def test_service_manual_time_adjustments_and_session_deletion() -> None:
    clock = _FakeClock(datetime(2026, 11, 25, 11, 0, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock)
        task = service.add_task_from_input("Refactor parser")
        assert task is not None

        # +15m
        task = service.adjust_time(task.id, 15 * 60)
        assert task.total_logged_seconds(clock.current) == 900
        assert len(task.work_sessions) == 1
        assert task.work_sessions[0].is_manual is True

        # -10m -> 5m remaining
        task = service.adjust_time(task.id, -10 * 60)
        assert task.total_logged_seconds(clock.current) == 300

        # -30m -> clamped safely to 0s, never negative
        task = service.adjust_time(task.id, -30 * 60)
        assert task.total_logged_seconds(clock.current) == 0
        assert len(task.work_sessions) == 0

        # Explicit manual session + deletion
        manual = service.add_manual_session(task.id, 25 * 60)
        assert manual.duration_seconds() == 25 * 60
        service.delete_work_session(manual.id)
        reloaded = service.get_task(task.id)
        assert reloaded is not None
        assert reloaded.total_logged_seconds(clock.current) == 0


def test_service_add_manual_session_from_input_supports_durations_and_ranges() -> None:
    local_tz = timezone(timedelta(hours=2))
    # 2026-11-25 15:00+02:00 (13:00 UTC)
    clock = _FakeClock(datetime(2026, 11, 25, 13, 0, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock, local_tz=local_tz)
        task = service.add_task_from_input("Write design doc")
        assert task is not None

        dur_session = service.add_manual_session_from_input(task.id, "+15m")
        assert dur_session.is_manual is True
        assert dur_session.duration_seconds() == 15 * 60

        range_session = service.add_manual_session_from_input(task.id, "14:10 - 14:40")
        assert range_session.is_manual is True
        assert range_session.started_at == datetime(2026, 11, 25, 14, 10, tzinfo=local_tz)
        assert range_session.ended_at == datetime(2026, 11, 25, 14, 40, tzinfo=local_tz)
        assert range_session.duration_seconds() == 30 * 60

        reloaded = service.get_task(task.id)
        assert reloaded is not None
        assert reloaded.total_logged_seconds(clock.current) == 45 * 60

        with pytest.raises(ValueError):
            service.add_manual_session_from_input(task.id, "14:40-14:10")


def test_service_daily_summary_slices_midnight_overlap_and_completed_tasks() -> None:
    # Start on Nov 24 at 23:30
    clock = _FakeClock(datetime(2026, 11, 24, 23, 30, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock, local_tz=UTC)
        t_cross = service.add_task_from_input("Midnight deploy @Ops")
        t_overlap = service.add_task_from_input("Write runbook")
        t_quick_done = service.add_task_from_input("Ping team")
        assert t_cross is not None and t_overlap is not None and t_quick_done is not None

        # Start t_cross at 23:30 Nov 24, stop at 00:30 Nov 25 (30m each day)
        service.toggle_timer(t_cross.id)
        clock.advance(minutes=60)  # 2026-11-25 00:30
        service.toggle_timer(t_cross.id)

        # Complete t_quick_done on Nov 25 with 0 logged time
        service.toggle_done(t_quick_done.id)

        # Concurrent sessions on Nov 25:
        # t_cross runs 10:00 -> 10:30 (30m)
        # t_overlap runs 10:15 -> 10:45 (30m), then keeps running 11:00 -> 11:10 (10m)
        clock.current = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
        service.toggle_timer(t_cross.id)
        clock.advance(minutes=15)  # 10:15
        service.toggle_timer(t_overlap.id)
        clock.advance(minutes=15)  # 10:30
        service.toggle_timer(t_cross.id)
        clock.advance(minutes=15)  # 10:45
        service.toggle_timer(t_overlap.id)
        clock.advance(minutes=15)  # 11:00
        service.toggle_timer(t_overlap.id)
        clock.advance(minutes=10)  # 11:10 (still running!)

        summary_nov24 = service.get_daily_summary(date(2026, 11, 24))
        assert summary_nov24.total_logged_seconds == 30 * 60
        assert summary_nov24.wall_clock_seconds == 30 * 60
        assert summary_nov24.overlap_seconds == 0
        assert summary_nov24.completed_count == 0
        assert [b.task_id for b in summary_nov24.tasks] == [t_cross.id]

        summary_nov25 = service.get_daily_summary(date(2026, 11, 25))
        # Logged on Nov 25: t_cross=60m, t_overlap=40m -> total 100m (6000s)
        # Wall-clock: [00:00,00:30] (30m) + [10:00,10:45] (45m) + [11:00,11:10] (10m) = 85m
        # Overlap delta: 100m - 85m = 15m (900s)
        assert summary_nov25.total_logged_seconds == 100 * 60
        assert summary_nov25.wall_clock_seconds == 85 * 60
        assert summary_nov25.overlap_seconds == 15 * 60
        assert summary_nov25.completed_count == 1
        by_id = {b.task_id: b for b in summary_nov25.tasks}
        assert set(by_id) == {t_cross.id, t_overlap.id, t_quick_done.id}
        assert by_id[t_cross.id].logged_seconds == 60 * 60
        assert by_id[t_overlap.id].logged_seconds == 40 * 60
        assert by_id[t_quick_done.id].completed_on_day is True
        assert by_id[t_quick_done.id].logged_seconds == 0


def test_service_daily_summary_slices_against_local_timezone() -> None:
    local_tz = timezone(timedelta(hours=2))
    # 21:30 UTC == 23:30 +02:00 on Nov 24
    clock = _FakeClock(datetime(2026, 11, 24, 21, 30, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock, local_tz=local_tz)
        task = service.add_task_from_input("Late evening deploy")
        assert task is not None

        service.toggle_timer(task.id)
        clock.advance(minutes=60)  # 22:30 UTC == 00:30 +02:00 on Nov 25
        service.toggle_timer(task.id)
        service.toggle_done(task.id)

        nov24 = service.get_daily_summary(date(2026, 11, 24))
        assert nov24.wall_clock_seconds == 30 * 60
        assert nov24.total_logged_seconds == 30 * 60
        assert nov24.completed_count == 0

        nov25 = service.get_daily_summary(date(2026, 11, 25))
        assert nov25.wall_clock_seconds == 30 * 60
        assert nov25.total_logged_seconds == 30 * 60
        assert nov25.completed_count == 1


class _FakePlatform:
    def __init__(
        self,
        idle_seconds: float = 0.0,
        *,
        system_theme: ThemeMode = ThemeMode.DARK,
    ) -> None:
        self.idle_seconds = idle_seconds
        self.system_theme = system_theme
        self.registered: list[str] = []
        self.unregistered_count = 0

    def register_hotkey(self, shortcut: str, *, hotkey_id: int = 1, hwnd: int = 0) -> bool:
        self.registered.append(shortcut)
        return True

    def unregister_hotkey(self, hotkey_id: int, *, hwnd: int = 0) -> None:
        self.unregistered_count += 1

    def get_idle_seconds(self) -> float:
        return self.idle_seconds

    def get_system_theme(self) -> ThemeMode:
        return self.system_theme


def test_service_idle_gap_detection_resolution_settings_and_shutdown() -> None:
    clock = _FakeClock(datetime(2026, 11, 25, 14, 0, tzinfo=UTC))
    platform = _FakePlatform()
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock, platform=platform)
        t1 = service.add_task_from_input("Debug cache")
        t2 = service.add_task_from_input("Write docs")
        assert t1 is not None and t2 is not None

        # No running timers -> no idle gap
        assert service.detect_idle_gap(20 * 60) is None

        # Start timer on t1 at 14:00, advance 25m -> 14:25, idle for 18m (started at 14:07)
        service.toggle_timer(t1.id)
        clock.advance(minutes=25)
        gap = service.detect_idle_gap(18 * 60)
        assert gap is not None
        assert gap.idle_started_at == datetime(2026, 11, 25, 14, 7, tzinfo=UTC)
        assert gap.affected_task_ids == (t1.id,)

        # Keep full time leaves timer running
        service.resolve_idle_gap(keep=True, idle_started_at=gap.idle_started_at)
        assert service.get_task(t1.id).is_timer_running is True  # type: ignore[union-attr]

        # Trim idle time closes running session back to idle_started_at (14:07 -> 7m)
        service.resolve_idle_gap(keep=False, idle_started_at=gap.idle_started_at)
        trimmed = service.get_task(t1.id)
        assert trimmed is not None
        assert trimmed.is_timer_running is False
        assert trimmed.total_logged_seconds(clock.current) == 7 * 60

        # Update settings: IdleThreshold.OFF suppresses idle detection & updates hotkey
        new_settings = Settings(
            theme=ThemeMode.LIGHT,
            global_shortcut="Ctrl+Shift+Space",
            show_shortcut_hints=False,
            idle_threshold=IdleThreshold.OFF,
        )
        service.update_settings(new_settings)
        assert service.get_settings() == new_settings
        assert platform.registered[-1] == "Ctrl+Shift+Space"

        # Start t2 timer at 14:25, verify IdleThreshold.OFF ignores idle, then shutdown stops it
        service.toggle_timer(t2.id)
        clock.advance(minutes=40)
        assert service.detect_idle_gap(40 * 60) is None

        service.shutdown()
        assert platform.unregistered_count >= 1
        stopped_t2 = service.get_task(t2.id)
        assert stopped_t2 is not None
        assert stopped_t2.is_timer_running is False
        assert stopped_t2.total_logged_seconds(clock.current) == 40 * 60


def test_service_poll_idle_gap_triggers_on_resume_and_delegates_system_theme() -> None:
    clock = _FakeClock(datetime(2026, 11, 25, 14, 0, tzinfo=UTC))
    platform = _FakePlatform(system_theme=ThemeMode.LIGHT)
    with SQLiteRepository(":memory:") as repo:
        service_no_platform = TodoService(repo, clock=clock)
        assert service_no_platform.get_system_theme() == ThemeMode.DARK
        assert service_no_platform.poll_idle_gap() is None

        service = TodoService(repo, clock=clock, platform=platform)
        assert service.get_system_theme() == ThemeMode.LIGHT

        task = service.add_task_from_input("Deep work")
        assert task is not None

        # No running timers -> resets and returns None even if OS idle is high
        platform.idle_seconds = 20 * 60
        assert service.poll_idle_gap() is None

        # Start timer at 14:00, advance 25m -> 14:25, idle for 18m (onset 14:07)
        platform.idle_seconds = 0.0
        service.toggle_timer(task.id)
        assert service.poll_idle_gap() is None

        clock.advance(minutes=25)
        platform.idle_seconds = 18 * 60
        # Still idle -> records pending onset, does NOT trigger yet
        assert service.poll_idle_gap() is None

        # Still idle 5m later -> preserves original onset (14:07)
        clock.advance(minutes=5)
        platform.idle_seconds = 23 * 60
        assert service.poll_idle_gap() is None

        # User input resumes at 14:31 -> triggers IdleGap once!
        clock.advance(minutes=1)
        platform.idle_seconds = 0.0
        gap = service.poll_idle_gap()
        assert gap is not None
        assert gap.idle_started_at == datetime(2026, 11, 25, 14, 7, tzinfo=UTC)
        assert gap.detected_at == datetime(2026, 11, 25, 14, 31, tzinfo=UTC)
        assert gap.idle_seconds == 24 * 60
        assert gap.affected_task_ids == (task.id,)

        # Subsequent poll while active returns None
        assert service.poll_idle_gap() is None

        # Trim idle time back to 14:07 -> 7m logged
        service.resolve_idle_gap(keep=False, idle_started_at=gap.idle_started_at)
        trimmed = service.get_task(task.id)
        assert trimmed is not None
        assert trimmed.is_timer_running is False
        assert trimmed.total_logged_seconds(clock.current) == 7 * 60

        # IdleThreshold.OFF suppresses and resets pending state
        service.toggle_timer(task.id)
        clock.advance(minutes=20)
        platform.idle_seconds = 20 * 60
        assert service.poll_idle_gap() is None
        service.update_settings(Settings(idle_threshold=IdleThreshold.OFF))
        platform.idle_seconds = 0.0
        assert service.poll_idle_gap() is None


def test_task_date_filter_and_sort_modes_respect_local_tz_and_doing_pinning() -> None:
    local_tz = timezone(timedelta(hours=2))
    # Anchor "now" at Thu 2026-11-26 12:00+02:00 (10:00 UTC)
    # Local This Week = Mon 2026-11-23 .. Sun 2026-11-29
    # Local Last Week = Mon 2026-11-16 .. Sun 2026-11-22
    clock = _FakeClock(datetime(2026, 11, 16, 10, 0, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock, local_tz=local_tz)

        # Last week Monday (Nov 16 12:00+02:00)
        t_last_week = service.add_task_from_input("Last week task")
        # UTC Nov 22 22:30 == Local Nov 23 00:30+02:00 -> THIS_WEEK (Monday), NOT Last Week!
        clock.current = datetime(2026, 11, 22, 22, 30, tzinfo=UTC)
        t_tz_boundary = service.add_task_from_input("Midnight boundary task")
        # Nov 24 local (Tuesday this week)
        clock.current = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
        t_this_week = service.add_task_from_input("This week task")
        # Nov 26 local (Today) - two tasks with identical created_at to verify ID tie-breaker
        clock.current = datetime(2026, 11, 26, 8, 0, tzinfo=UTC)
        t_today_a = service.add_task_from_input("Today A")
        t_today_b = service.add_task_from_input("Today B")
        # Waiting task created today
        t_waiting_new = service.add_task_from_input("Waiting new")
        # Waiting task created last week
        clock.current = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
        t_waiting_old = service.add_task_from_input("Waiting old")

        assert (
            t_last_week is not None
            and t_tz_boundary is not None
            and t_this_week is not None
            and t_today_a is not None
            and t_today_b is not None
            and t_waiting_new is not None
            and t_waiting_old is not None
        )

        # Set Doing on oldest task (t_last_week) and Waiting on waiting tasks
        clock.current = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)  # 12:00+02:00
        service.set_status(t_last_week.id, TaskStatus.DOING)
        service.set_status(t_waiting_new.id, TaskStatus.WAITING)
        service.set_status(t_waiting_old.id, TaskStatus.WAITING)

        # Reorder Todo tasks manually: move t_today_a up once
        service.reorder_task(t_today_a.id, -1)
        manual_ids = [t.id for t in service.list_active_tasks(sort_mode=TaskSortMode.MANUAL)]
        assert manual_ids == [
            t_last_week.id,  # Doing pinned on top
            t_tz_boundary.id,
            t_today_a.id,
            t_this_week.id,
            t_today_b.id,
        ]

        # NEWEST: Doing stays pinned on top, Todo sorted newest first with id tie-breaker
        newest_ids = [t.id for t in service.list_active_tasks(sort_mode=TaskSortMode.NEWEST)]
        same_ts_pair = sorted([t_today_a.id, t_today_b.id])
        assert newest_ids == [
            t_last_week.id,
            *same_ts_pair,
            t_this_week.id,
            t_tz_boundary.id,
        ]

        # OLDEST: Doing stays pinned on top, Todo sorted oldest first with id tie-breaker
        oldest_ids = [t.id for t in service.list_active_tasks(sort_mode=TaskSortMode.OLDEST)]
        assert oldest_ids == [
            t_last_week.id,
            t_tz_boundary.id,
            t_this_week.id,
            *same_ts_pair,
        ]

        # Waiting tab sorting
        assert [t.id for t in service.list_waiting_tasks(sort_mode=TaskSortMode.NEWEST)] == [
            t_waiting_new.id,
            t_waiting_old.id,
        ]
        assert [t.id for t in service.list_waiting_tasks(sort_mode=TaskSortMode.OLDEST)] == [
            t_waiting_old.id,
            t_waiting_new.id,
        ]

        # Date filters
        assert {
            t.id
            for t in service.list_active_tasks(date_filter=TaskDateFilter(TaskDateFilterMode.TODAY))
        } == {t_today_a.id, t_today_b.id}

        assert {
            t.id
            for t in service.list_active_tasks(
                date_filter=TaskDateFilter(TaskDateFilterMode.THIS_WEEK)
            )
        } == {t_tz_boundary.id, t_this_week.id, t_today_a.id, t_today_b.id}

        assert [
            t.id
            for t in service.list_active_tasks(
                date_filter=TaskDateFilter(TaskDateFilterMode.LAST_WEEK)
            )
        ] == [t_last_week.id]

        assert [
            t.id
            for t in service.list_waiting_tasks(
                date_filter=TaskDateFilter(TaskDateFilterMode.LAST_WEEK)
            )
        ] == [t_waiting_old.id]

        custom = TaskDateFilter(
            TaskDateFilterMode.CUSTOM,
            start_date=date(2026, 11, 23),
            end_date=date(2026, 11, 24),
        )
        assert {t.id for t in service.list_active_tasks(date_filter=custom)} == {
            t_tz_boundary.id,
            t_this_week.id,
        }

        with pytest.raises(ValueError):
            TaskDateFilter(
                TaskDateFilterMode.CUSTOM,
                start_date=date(2026, 11, 25),
                end_date=date(2026, 11, 20),
            )


def test_summary_period_work_week_stepping_and_bounds() -> None:
    # Wed 2025-12-31 belongs to Mon 2025-12-29 .. Sun 2026-01-04
    nye_week = SummaryPeriod.work_week(date(2025, 12, 31))
    assert nye_week.kind == SummaryPeriodKind.WEEK
    assert nye_week.start_date == date(2025, 12, 29)
    assert nye_week.end_date == date(2026, 1, 4)
    assert nye_week.day_count == 7
    assert nye_week.contains_date(date(2026, 1, 1))
    assert not nye_week.contains_date(date(2026, 1, 5))

    # Sunday maps to the same Mon-Sun Work Week
    assert SummaryPeriod.work_week(date(2026, 1, 4)) == nye_week

    today = date(2026, 11, 26)  # Thursday; this work week is Nov 23..Nov 29
    this_week = SummaryPeriod.work_week(today)
    assert this_week.start_date == date(2026, 11, 23)
    assert this_week.end_date == date(2026, 11, 29)
    assert not this_week.can_step_next(today)
    assert this_week.step(1, today=today) is None

    last_week = this_week.step(-1, today=today)
    assert last_week == SummaryPeriod.work_week(date(2026, 11, 16))
    assert last_week is not None
    assert last_week.can_step_next(today)
    assert last_week.step(1, today=today) == this_week

    # Day mode stepping
    day_today = SummaryPeriod.day(today)
    assert not day_today.can_step_next(today)
    assert day_today.step(1, today=today) is None
    yesterday = day_today.step(-1, today=today)
    assert yesterday == SummaryPeriod.day(date(2026, 11, 25))
    assert yesterday is not None and yesterday.step(1, today=today) == day_today

    # Custom range validation & stepping
    with pytest.raises(ValueError):
        SummaryPeriod.custom(date(2026, 11, 25), date(2026, 11, 20))

    custom = SummaryPeriod.custom(date(2026, 11, 10), date(2026, 11, 12))
    assert custom.day_count == 3
    assert custom.can_step_next(today)
    assert custom.step(1, today=today) == SummaryPeriod.custom(
        date(2026, 11, 13), date(2026, 11, 15)
    )
    assert custom.step(-1, today=today) == SummaryPeriod.custom(
        date(2026, 11, 7), date(2026, 11, 9)
    )

    at_today = SummaryPeriod.custom(date(2026, 11, 24), today)
    assert not at_today.can_step_next(today)
    assert at_today.step(1, today=today) is None


def test_service_activity_summary_week_and_custom_daily_breakdown() -> None:
    local_tz = timezone(timedelta(hours=2))
    # Mon Nov 23 .. Sun Nov 29, 2026
    clock = _FakeClock(datetime(2026, 11, 22, 21, 0, tzinfo=UTC))  # Sun Nov 22 23:00+02:00
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock, local_tz=local_tz)
        t1 = service.add_task_from_input("Cross-week deploy @Ops")
        t2 = service.add_task_from_input("Write tests")
        t3 = service.add_task_from_input("Quick close")
        assert t1 is not None and t2 is not None and t3 is not None

        # Session on t1 crossing Sunday Nov 22 23:30+02 -> Monday Nov 23 00:30+02
        clock.current = datetime(2026, 11, 22, 21, 30, tzinfo=UTC)
        service.toggle_timer(t1.id)
        clock.advance(minutes=60)
        service.toggle_timer(t1.id)

        # Concurrent sessions on Wednesday Nov 25: t1 [10:00..10:30], t2 [10:15..10:45]
        clock.current = datetime(2026, 11, 25, 8, 0, tzinfo=UTC)  # 10:00+02
        service.toggle_timer(t1.id)
        clock.advance(minutes=15)
        service.toggle_timer(t2.id)
        clock.advance(minutes=15)
        service.toggle_timer(t1.id)
        clock.advance(minutes=15)
        service.toggle_timer(t2.id)

        # Quick completion on Thursday Nov 26 with 0 logged seconds
        clock.current = datetime(2026, 11, 26, 9, 0, tzinfo=UTC)
        service.toggle_done(t3.id)

        week_period = SummaryPeriod.work_week(date(2026, 11, 26))
        summary = service.get_activity_summary(week_period)
        assert isinstance(summary, ActivitySummary)
        assert summary.period == week_period
        # Mon: 30m (1800s), Wed: t1 30m + t2 30m logged (60m), wall-clock 45m -> total 90m, wall 75m
        assert summary.total_logged_seconds == 90 * 60
        assert summary.wall_clock_seconds == 75 * 60
        assert summary.overlap_seconds == 15 * 60
        assert summary.completed_count == 1
        assert {b.task_id for b in summary.tasks} == {t1.id, t2.id, t3.id}

        assert len(summary.daily_breakdown) == 7
        assert [d.day for d in summary.daily_breakdown] == [
            date(2026, 11, 23) + timedelta(days=i) for i in range(7)
        ]
        by_day = {d.day: d for d in summary.daily_breakdown}
        assert by_day[date(2026, 11, 23)] == DayBreakdown(
            day=date(2026, 11, 23),
            wall_clock_seconds=30 * 60,
            total_logged_seconds=30 * 60,
            completed_count=0,
        )
        assert by_day[date(2026, 11, 25)] == DayBreakdown(
            day=date(2026, 11, 25),
            wall_clock_seconds=45 * 60,
            total_logged_seconds=60 * 60,
            completed_count=0,
        )
        assert by_day[date(2026, 11, 26)] == DayBreakdown(
            day=date(2026, 11, 26),
            wall_clock_seconds=0,
            total_logged_seconds=0,
            completed_count=1,
        )

        # Day mode -> daily_breakdown is empty
        day_summary = service.get_activity_summary(SummaryPeriod.day(date(2026, 11, 25)))
        assert day_summary.daily_breakdown == ()
        assert day_summary.wall_clock_seconds == 45 * 60

        # Custom 1-day -> empty daily_breakdown
        custom_1 = service.get_activity_summary(
            SummaryPeriod.custom(date(2026, 11, 25), date(2026, 11, 25))
        )
        assert custom_1.daily_breakdown == ()

        # Custom 4-day -> 4 DayBreakdown items
        custom_4 = service.get_activity_summary(
            SummaryPeriod.custom(date(2026, 11, 23), date(2026, 11, 26))
        )
        assert len(custom_4.daily_breakdown) == 4
        assert custom_4.wall_clock_seconds == 75 * 60

        # Custom 15-day -> empty daily_breakdown (>14 days)
        custom_15 = service.get_activity_summary(
            SummaryPeriod.custom(date(2026, 11, 12), date(2026, 11, 26))
        )
        assert custom_15.daily_breakdown == ()


def test_domain_date_formatting_helpers() -> None:
    now = datetime(2026, 11, 26, 18, 12, tzinfo=UTC)
    today = date(2026, 11, 26)

    assert format_task_date_pill(now, now=now, tz=UTC) == "Today"
    assert format_task_date_pill(now - timedelta(days=1), now=now, tz=UTC) == "Yesterday"
    assert (
        format_task_date_pill(datetime(2026, 11, 5, 9, 0, tzinfo=UTC), now=now, tz=UTC) == "Nov 5"
    )
    assert (
        format_task_date_pill(datetime(2025, 11, 24, 9, 0, tzinfo=UTC), now=now, tz=UTC)
        == "Nov 24 '25"
    )

    assert format_task_added_full(now, now=now, tz=UTC) == "Added Thu, Nov 26 · 18:12"
    assert (
        format_task_added_full(datetime(2025, 11, 24, 9, 5, tzinfo=UTC), now=now, tz=UTC)
        == "Added Mon, Nov 24, 2025 · 09:05"
    )

    assert (
        format_summary_period_label(SummaryPeriod.day(today), today=today) == "Today · Thu, Nov 26"
    )
    assert (
        format_summary_period_label(SummaryPeriod.day(date(2026, 11, 25)), today=today)
        == "Yesterday · Wed, Nov 25"
    )
    assert (
        format_summary_period_label(SummaryPeriod.work_week(today), today=today)
        == "This Week · Nov 23\u201329"
    )
    assert (
        format_summary_period_label(SummaryPeriod.work_week(date(2026, 11, 16)), today=today)
        == "Last Week · Nov 16\u201322"
    )
    assert (
        format_summary_period_label(
            SummaryPeriod.custom(date(2026, 11, 10), date(2026, 11, 26)), today=today
        )
        == "Nov 10 \u2013 Nov 26"
    )


def test_service_suggest_requesters_ranking_dedup_done_and_exact_single() -> None:
    clock = _FakeClock(datetime(2026, 11, 26, 9, 0, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock)

        # Older Done task with "Adrian" should still be included & win capitalization
        done_adrian = service.add_task_from_input("Old deploy @Adrian")
        assert done_adrian is not None
        service.toggle_done(done_adrian.id)

        # Even if a lowercase "adrian" row exists directly in storage later & more frequently,
        # canonicalization prefers highest uppercase count ("Adrian")
        clock.advance(minutes=10)
        repo.save_task(
            Task(
                id="raw-lower-1",
                title="Lowercase one",
                requester="adrian",
                created_at=clock.current,
                updated_at=clock.current,
            )
        )
        clock.advance(minutes=1)
        repo.save_task(
            Task(
                id="raw-lower-2",
                title="Lowercase two",
                requester="adrian",
                created_at=clock.current,
                updated_at=clock.current,
            )
        )

        # Frequency tie-breaker at the same updated_at timestamp:
        # "Bob" (count=2) vs "Ben" (count=1) at t=same
        clock.advance(minutes=10)
        service.add_task_from_input("Task for Ben @Ben")
        service.add_task_from_input("Task 1 for Bob @Bob")
        service.add_task_from_input("Task 2 for Bob @Bob")

        # Substring vs prefix: "Hannah" is newer, "Andreas" is older, query "an" puts prefix first
        clock.advance(minutes=10)
        service.add_task_from_input("Older prefix @Andreas")
        clock.advance(minutes=10)
        service.add_task_from_input("Newer substring @Hannah")

        # Most recent requester overall: "Adrianna"
        clock.advance(minutes=10)
        service.add_task_from_input("Latest task @Adrianna")

        # Bare "@" lists all canonicalized requesters ordered by recency, then count
        assert service.suggest_requesters("@") == [
            "Adrianna",
            "Hannah",
            "Andreas",
            "Bob",
            "Ben",
            "Adrian",
        ]
        assert service.suggest_requesters("", limit=3) == ["Adrianna", "Hannah", "Andreas"]

        # Prefix tier 0 ("Andreas") before substring tier 1 ("Adrianna", "Hannah", "Adrian")
        assert service.suggest_requesters("an") == ["Andreas", "Adrianna", "Hannah", "Adrian"]

        # Multiple matches keep suggestions visible even when one matches exact prefix
        assert service.suggest_requesters("@Adr") == ["Adrianna", "Adrian"]
        assert service.suggest_requesters("@Adrian") == ["Adrianna", "Adrian"]

        # Sole exact case-sensitive match is hidden when hide_if_exact_single=True
        assert service.suggest_requesters("@Hannah") == []
        assert service.suggest_requesters("Hannah") == []
        assert service.suggest_requesters("@Hannah", hide_if_exact_single=False) == ["Hannah"]

        # Sole case-mismatched query suggests canonical casing
        assert service.suggest_requesters("@hannah") == ["Hannah"]


def test_service_requester_canonicalization_on_add_and_update() -> None:
    clock = _FakeClock(datetime(2026, 11, 26, 10, 0, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock)

        t1 = service.add_task_from_input("Fix cache @Adrian")
        clock.advance(minutes=5)
        t2 = service.add_task_from_input("Review docs @adrian")
        assert t1 is not None and t2 is not None
        assert t1.requester == "Adrian"
        assert t2.requester == "Adrian"

        # Higher-uppercase input wins and canonicalizes subsequent lowercase entries
        clock.advance(minutes=5)
        t3 = service.add_task_from_input("Audit auth @apiTeam")
        assert t3 is not None and t3.requester == "apiTeam"
        clock.advance(minutes=5)
        t4 = service.add_task_from_input("Check metrics @APITeam")
        assert t4 is not None and t4.requester == "APITeam"
        clock.advance(minutes=5)
        t5 = service.add_task_from_input("Scale workers @apiteam")
        assert t5 is not None and t5.requester == "APITeam"

        # update_task canonicalizes against existing tasks
        clock.advance(minutes=5)
        updated_t3 = service.update_task(t3.id, requester="@apiteam")
        assert updated_t3.requester == "APITeam"

        # Fixing capitalization on the sole task holding "@ALLCAPS" excludes itself
        t_sole = service.add_task_from_input("Fix typo @ALLCAPS")
        assert t_sole is not None and t_sole.requester == "ALLCAPS"
        fixed_sole = service.update_task(t_sole.id, requester="AllCaps")
        assert fixed_sole.requester == "AllCaps"

        # Clearing requester via None or whitespace/bare '@' stores None
        assert service.update_task(t_sole.id, requester=None).requester is None
        assert service.update_task(t5.id, requester="  @  ").requester is None


def test_service_importance_parsing_sorting_tier_reordering_and_search() -> None:
    clock = _FakeClock(datetime(2026, 11, 26, 9, 0, tzinfo=UTC))
    with SQLiteRepository(":memory:") as repo:
        service = TodoService(repo, clock=clock)

        # Importance-only Quick Bar input does not create an empty Task
        assert service.add_task_from_input("!!!") is None
        assert service.add_task_from_input("@Maya !!") is None

        t_none = service.add_task_from_input("Normal task")
        clock.advance(minutes=5)
        t_low_a = service.add_task_from_input("Low A !")
        clock.advance(minutes=5)
        t_low_b = service.add_task_from_input("Low B !")
        clock.advance(minutes=5)
        t_high = service.add_task_from_input("Critical outage !!! @Maya")
        clock.advance(minutes=5)
        t_med = service.add_task_from_input("Medium review !! @Alex")
        assert (
            t_none is not None
            and t_low_a is not None
            and t_low_b is not None
            and t_high is not None
            and t_med is not None
        )
        assert t_high.title == "Critical outage"
        assert t_high.importance == TaskImportance.HIGH
        assert t_high.requester == "Maya"

        # Importance descending first across Manual, Newest, and Oldest
        assert [t.id for t in service.list_active_tasks(TaskSortMode.MANUAL)] == [
            t_high.id,
            t_med.id,
            t_low_a.id,
            t_low_b.id,
            t_none.id,
        ]
        assert [t.id for t in service.list_active_tasks(TaskSortMode.NEWEST)] == [
            t_high.id,
            t_med.id,
            t_low_b.id,
            t_low_a.id,
            t_none.id,
        ]
        assert [t.id for t in service.list_active_tasks(TaskSortMode.OLDEST)] == [
            t_high.id,
            t_med.id,
            t_low_a.id,
            t_low_b.id,
            t_none.id,
        ]

        # Reordering stays strictly within the (status, importance) tier
        service.reorder_task(t_low_b.id, -1)
        assert [t.id for t in service.list_active_tasks(TaskSortMode.MANUAL)] == [
            t_high.id,
            t_med.id,
            t_low_b.id,
            t_low_a.id,
            t_none.id,
        ]
        # Boundary clamp: cannot push Low B above Medium
        service.reorder_task(t_low_b.id, -1)
        assert [t.id for t in service.list_active_tasks(TaskSortMode.MANUAL)] == [
            t_high.id,
            t_med.id,
            t_low_b.id,
            t_low_a.id,
            t_none.id,
        ]

        # Doing stays pinned above Todo even if Doing task has lower Importance
        service.toggle_timer(t_none.id)
        active_ids = [t.id for t in service.list_active_tasks(TaskSortMode.MANUAL)]
        assert active_ids[0] == t_none.id
        assert active_ids[1] == t_high.id

        # Waiting also sorts by Importance descending
        service.set_status(t_low_a.id, TaskStatus.WAITING)
        service.set_status(t_med.id, TaskStatus.WAITING)
        assert [t.id for t in service.list_waiting_tasks(TaskSortMode.MANUAL)] == [
            t_med.id,
            t_low_a.id,
        ]

        # Importance is preserved across Done and reopen, and cycle_importance wraps
        done_high = service.toggle_done(t_high.id)
        assert done_high.status == TaskStatus.DONE
        assert done_high.importance == TaskImportance.HIGH
        reopened = service.toggle_done(t_high.id)
        assert reopened.status == TaskStatus.TODO
        assert reopened.importance == TaskImportance.HIGH

        assert service.cycle_importance(t_low_b.id).importance == TaskImportance.MEDIUM
        assert service.cycle_importance(t_low_b.id, reverse=True).importance == TaskImportance.LOW
        assert service.cycle_importance(t_low_b.id, reverse=True).importance == TaskImportance.NONE
        assert service.cycle_importance(t_low_b.id, reverse=True).importance == TaskImportance.HIGH

        # Search supports ! / !! / !!! filters and orders by status + Importance
        assert [t.id for t in service.search_tasks("/ !!!")] == [t_low_b.id, t_high.id]
        service.toggle_timer(t_high.id)
        assert [t.id for t in service.search_tasks("/ !!!")] == [t_high.id, t_low_b.id]
        assert [t.id for t in service.search_tasks("/ @Maya !!!")] == [t_high.id]
        assert [t.id for t in service.search_tasks("/ !!")] == [t_med.id]
