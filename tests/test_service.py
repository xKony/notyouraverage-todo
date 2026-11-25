"""Tests for domain interval math and TodoService use cases."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from nyatodo.domain import (
    IdleThreshold,
    Settings,
    Task,
    TaskStatus,
    ThemeMode,
    WorkSession,
    compute_wall_clock_seconds,
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
