"""Application service layer orchestrating Tasks, Thinking Space, Timers, and Daily Summary."""

import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from enum import Enum, auto

from nyatodo.domain import (
    DailySummary,
    IdleGap,
    Settings,
    SubStep,
    Task,
    TaskDayBreakdown,
    TaskStatus,
    WorkSession,
    clip_session_interval,
    compute_wall_clock_seconds,
)
from nyatodo.parser import extract_search_query, is_search_input, parse_quick_input
from nyatodo.platform_win32 import PlatformBridge, parse_hotkey
from nyatodo.storage import SQLiteRepository


class _Unset(Enum):
    TOKEN = auto()


_UNSET = _Unset.TOKEN


def _default_clock() -> datetime:
    return datetime.now(UTC)


class TodoService:
    """Application use cases for nyatodo."""

    def __init__(
        self,
        repository: SQLiteRepository,
        *,
        clock: Callable[[], datetime] = _default_clock,
        platform: PlatformBridge | None = None,
    ) -> None:
        self._repo = repository
        self._clock = clock
        self._platform = platform

    def add_task_from_input(self, raw: str) -> Task | None:
        """Parse Quick Bar text and create a new Todo Task, or return None if empty."""
        parsed = parse_quick_input(raw)
        if not parsed.title:
            return None

        now = self._clock()
        existing = self._repo.list_tasks(TaskStatus.TODO)
        next_sort_order = max((t.sort_order for t in existing), default=-1) + 1
        task = Task(
            id=str(uuid.uuid4()),
            title=parsed.title,
            status=TaskStatus.TODO,
            requester=parsed.requester,
            notes="",
            sort_order=next_sort_order,
            created_at=now,
            updated_at=now,
        )
        return self._repo.save_task(task)

    def get_task(self, task_id: str) -> Task | None:
        """Return a hydrated Task by ID, or None if not found."""
        return self._repo.get_task(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List Tasks optionally filtered by TaskStatus."""
        return self._repo.list_tasks(status)

    def list_active_tasks(self) -> list[Task]:
        """Return Active Tasks with Doing pinned above Todo."""
        doing = self._repo.list_tasks(TaskStatus.DOING)
        todo = self._repo.list_tasks(TaskStatus.TODO)
        return doing + todo

    def list_waiting_tasks(self) -> list[Task]:
        """Return Waiting Tasks in deterministic sort order."""
        return self._repo.list_tasks(TaskStatus.WAITING)

    def search_tasks(self, query: str, *, include_done: bool = True) -> list[Task]:
        """Filter Tasks case-insensitively by title or requester (supports leading '/')."""
        clean = extract_search_query(query) if is_search_input(query) else " ".join(query.split())
        tasks = self._repo.list_tasks()
        if not include_done:
            tasks = [task for task in tasks if task.status != TaskStatus.DONE]
        if not clean:
            return tasks

        needle = clean.lower()
        return [
            task
            for task in tasks
            if needle in task.title.lower()
            or (task.requester is not None and needle in task.requester.lower())
        ]

    def update_task(
        self,
        task_id: str,
        *,
        title: str | _Unset = _UNSET,
        requester: str | _Unset | None = _UNSET,
    ) -> Task:
        """Update a Task's title and/or requester."""
        task = self._require_task(task_id)
        new_title = task.title if isinstance(title, _Unset) else " ".join(title.split())
        if not new_title:
            raise ValueError("Task title cannot be empty.")

        if isinstance(requester, _Unset):
            new_requester = task.requester
        elif requester is None:
            new_requester = None
        else:
            cleaned_req = requester.strip().lstrip("@")
            new_requester = cleaned_req or None

        updated = replace(
            task,
            title=new_title,
            requester=new_requester,
            updated_at=self._clock(),
        )
        return self._repo.save_task(updated)

    def update_notes(self, task_id: str, notes: str) -> Task:
        """Update freeform Thinking Space notes for a Task."""
        task = self._require_task(task_id)
        updated = replace(task, notes=notes, updated_at=self._clock())
        return self._repo.save_task(updated)

    def delete_task(self, task_id: str) -> None:
        """Delete a Task by ID."""
        self._repo.delete_task(task_id)

    def set_status(self, task_id: str, status: TaskStatus) -> Task:
        """Transition a Task to a new TaskStatus and update completion/timer state."""
        task = self._require_task(task_id)
        now = self._clock()

        if status in (TaskStatus.WAITING, TaskStatus.DONE):
            self._close_open_sessions_for_task(task, ended_at=now)
            task = self._require_task(task_id)

        if task.status == status:
            return task

        siblings = self._repo.list_tasks(status)
        next_sort_order = max((item.sort_order for item in siblings), default=-1) + 1
        completed_at = now if status == TaskStatus.DONE else None
        updated = replace(
            task,
            status=status,
            sort_order=next_sort_order,
            completed_at=completed_at,
            updated_at=now,
        )
        self._repo.save_task(updated)
        return self._require_task(task_id)

    def toggle_waiting(self, task_id: str) -> Task:
        """Toggle a Task between Waiting and Todo."""
        task = self._require_task(task_id)
        target = TaskStatus.TODO if task.status == TaskStatus.WAITING else TaskStatus.WAITING
        return self.set_status(task_id, target)

    def toggle_done(self, task_id: str) -> Task:
        """Toggle a Task between Done and Todo."""
        task = self._require_task(task_id)
        target = TaskStatus.TODO if task.status == TaskStatus.DONE else TaskStatus.DONE
        return self.set_status(task_id, target)

    def reorder_task(self, task_id: str, direction: int) -> list[Task]:
        """Move a Task up (direction < 0) or down (direction > 0) within its status group."""
        task = self._require_task(task_id)
        if direction == 0:
            return self._repo.list_tasks(task.status)

        group = self._repo.list_tasks(task.status)
        ids = [item.id for item in group]
        index = ids.index(task_id)
        step = -1 if direction < 0 else 1
        target_index = index + step
        if not (0 <= target_index < len(ids)):
            return group

        ids[index], ids[target_index] = ids[target_index], ids[index]
        self._repo.update_task_sort_orders(ids)
        return self._repo.list_tasks(task.status)

    def add_sub_step(self, task_id: str, title: str) -> SubStep:
        """Append a new Sub-step to a Task's Thinking Space."""
        task = self._require_task(task_id)
        cleaned = " ".join(title.split())
        if not cleaned:
            raise ValueError("Sub-step title cannot be empty.")
        next_order = max((step.sort_order for step in task.sub_steps), default=-1) + 1
        step = SubStep(
            id=str(uuid.uuid4()),
            task_id=task_id,
            title=cleaned,
            is_done=False,
            sort_order=next_order,
        )
        self._repo.save_sub_step(step)
        self._repo.save_task(replace(task, updated_at=self._clock()))
        return step

    def toggle_sub_step(self, sub_step_id: str) -> SubStep:
        """Toggle completion state of a Sub-step."""
        step = self._repo.get_sub_step(sub_step_id)
        if step is None:
            raise KeyError(f"Unknown Sub-step: {sub_step_id}")
        updated = replace(step, is_done=not step.is_done)
        self._repo.save_sub_step(updated)
        return updated

    def update_sub_step(self, sub_step_id: str, title: str) -> SubStep:
        """Rename a Sub-step."""
        step = self._repo.get_sub_step(sub_step_id)
        if step is None:
            raise KeyError(f"Unknown Sub-step: {sub_step_id}")
        cleaned = " ".join(title.split())
        if not cleaned:
            raise ValueError("Sub-step title cannot be empty.")
        updated = replace(step, title=cleaned)
        return self._repo.save_sub_step(updated)

    def delete_sub_step(self, sub_step_id: str) -> None:
        """Delete a Sub-step by ID."""
        self._repo.delete_sub_step(sub_step_id)

    def toggle_timer(self, task_id: str) -> Task:
        """Start or stop a Task Timer independently of other running Task Timers."""
        task = self._require_task(task_id)
        now = self._clock()

        if task.is_timer_running:
            self._close_open_sessions_for_task(task, ended_at=now)
            self._repo.save_task(replace(task, updated_at=now))
            return self._require_task(task_id)

        if task.status != TaskStatus.DOING:
            doing_tasks = self._repo.list_tasks(TaskStatus.DOING)
            next_sort_order = max((item.sort_order for item in doing_tasks), default=-1) + 1
            self._repo.save_task(
                replace(
                    task,
                    status=TaskStatus.DOING,
                    sort_order=next_sort_order,
                    completed_at=None,
                    updated_at=now,
                )
            )
        else:
            self._repo.save_task(replace(task, updated_at=now))

        session = WorkSession(
            id=str(uuid.uuid4()),
            task_id=task_id,
            started_at=now,
            ended_at=None,
            is_manual=False,
        )
        self._repo.save_work_session(session)
        return self._require_task(task_id)

    def get_running_tasks(self) -> list[Task]:
        """Return all Tasks that currently have a running Task Timer."""
        return [task for task in self._repo.list_tasks() if task.is_timer_running]

    def adjust_time(self, task_id: str, delta_seconds: int) -> Task:
        """Apply a positive or negative time adjustment without ever going below zero."""
        task = self._require_task(task_id)
        if delta_seconds == 0:
            return task

        now = self._clock()
        if delta_seconds > 0:
            self.add_manual_session(task_id, delta_seconds)
            return self._require_task(task_id)

        remaining_to_trim = -delta_seconds
        ordered = sorted(
            task.work_sessions,
            key=lambda s: (s.is_running, s.started_at),
            reverse=True,
        )
        # Trim closed sessions first (most recent first), then running sessions if needed
        closed_first = [s for s in ordered if not s.is_running] + [
            s for s in ordered if s.is_running
        ]
        for session in closed_first:
            if remaining_to_trim <= 0:
                break
            dur = session.duration_seconds(now=now)
            if not session.is_running:
                assert session.ended_at is not None
                if dur <= remaining_to_trim:
                    self._repo.delete_work_session(session.id)
                    remaining_to_trim -= dur
                else:
                    new_end = session.ended_at - timedelta(seconds=remaining_to_trim)
                    self._repo.save_work_session(replace(session, ended_at=new_end))
                    remaining_to_trim = 0
            else:
                trim = min(dur, remaining_to_trim)
                new_start = min(now, session.started_at + timedelta(seconds=trim))
                self._repo.save_work_session(replace(session, started_at=new_start))
                remaining_to_trim -= trim

        self._repo.save_task(replace(task, updated_at=now))
        return self._require_task(task_id)

    def add_manual_session(
        self,
        task_id: str,
        duration_seconds: int,
        *,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
    ) -> WorkSession:
        """Create an explicit manual Work Session for a Task."""
        task = self._require_task(task_id)
        now = self._clock()
        if started_at is not None and ended_at is not None:
            if ended_at <= started_at:
                raise ValueError("Manual Work Session end must be after start.")
            s_start, s_end = started_at, ended_at
        else:
            if duration_seconds <= 0:
                raise ValueError("Manual Work Session duration must be positive.")
            s_end = ended_at or now
            s_start = s_end - timedelta(seconds=duration_seconds)

        session = WorkSession(
            id=str(uuid.uuid4()),
            task_id=task_id,
            started_at=s_start,
            ended_at=s_end,
            is_manual=True,
        )
        self._repo.save_work_session(session)
        self._repo.save_task(replace(task, updated_at=now))
        return session

    def delete_work_session(self, session_id: str) -> None:
        """Delete a single Work Session by ID."""
        self._repo.delete_work_session(session_id)

    def get_daily_summary(self, day: date) -> DailySummary:
        """Compute per-Task breakdown, wall-clock active seconds, and overlap for a day."""
        now = self._clock()
        tz = now.tzinfo or UTC
        day_start = datetime.combine(day, time.min, tzinfo=tz)
        day_end = day_start + timedelta(days=1)

        tasks = self._repo.list_tasks()
        all_sessions: list[WorkSession] = []
        breakdowns: list[TaskDayBreakdown] = []

        for task in tasks:
            task_day_seconds = 0
            for session in task.work_sessions:
                all_sessions.append(session)
                clipped = clip_session_interval(session, now=now, start=day_start, end=day_end)
                if clipped is not None:
                    task_day_seconds += int((clipped[1] - clipped[0]).total_seconds())

            completed_on_day = (
                task.completed_at is not None and day_start <= task.completed_at < day_end
            )
            if task_day_seconds > 0 or completed_on_day:
                breakdowns.append(
                    TaskDayBreakdown(
                        task_id=task.id,
                        title=task.title,
                        requester=task.requester,
                        status=task.status,
                        logged_seconds=task_day_seconds,
                        completed_on_day=completed_on_day,
                    )
                )

        breakdowns.sort(
            key=lambda item: (-item.logged_seconds, not item.completed_on_day, item.title)
        )
        total_logged = sum(item.logged_seconds for item in breakdowns)
        wall_clock = compute_wall_clock_seconds(all_sessions, now=now, start=day_start, end=day_end)
        overlap = max(0, total_logged - wall_clock)
        completed_count = sum(1 for item in breakdowns if item.completed_on_day)

        return DailySummary(
            day=day,
            wall_clock_seconds=wall_clock,
            total_logged_seconds=total_logged,
            overlap_seconds=overlap,
            tasks=tuple(breakdowns),
            completed_count=completed_count,
        )

    def detect_idle_gap(self, idle_seconds: float | int) -> IdleGap | None:
        """Return an IdleGap if timers are active and idle_seconds meets threshold."""
        threshold_seconds = self._repo.get_settings().idle_threshold.seconds
        if threshold_seconds is None or idle_seconds < threshold_seconds:
            return None

        running = self.get_running_tasks()
        if not running:
            return None

        whole_idle = int(idle_seconds)
        idle_started_at = self._clock() - timedelta(seconds=whole_idle)
        return IdleGap(
            idle_seconds=whole_idle,
            idle_started_at=idle_started_at,
            affected_task_ids=tuple(task.id for task in running),
        )

    def resolve_idle_gap(self, *, keep: bool, idle_started_at: datetime) -> list[Task]:
        """Either keep running timers intact or trim them back to idle_started_at."""
        if keep:
            return self.get_running_tasks()

        now = self._clock()
        affected: list[Task] = []
        for task in self.get_running_tasks():
            self._close_open_sessions_for_task(task, ended_at=idle_started_at)
            self._repo.save_task(replace(task, updated_at=now))
            affected.append(self._require_task(task.id))
        return affected

    def get_settings(self) -> Settings:
        """Return persisted user Settings."""
        return self._repo.get_settings()

    def update_settings(self, settings: Settings, *, hotkey_id: int = 1, hwnd: int = 0) -> Settings:
        """Validate, persist, and apply updated user Settings."""
        parse_hotkey(settings.global_shortcut)
        previous = self._repo.get_settings()
        saved = self._repo.save_settings(settings)
        if self._platform is not None and (settings.global_shortcut != previous.global_shortcut):
            self._platform.register_hotkey(settings.global_shortcut, hotkey_id=hotkey_id, hwnd=hwnd)
        return saved

    def shutdown(self, *, hotkey_id: int = 1, hwnd: int = 0) -> None:
        """Persist all open Work Sessions up to now and unregister global hotkey."""
        now = self._clock()
        for task in self.get_running_tasks():
            self._close_open_sessions_for_task(task, ended_at=now)
            self._repo.save_task(replace(task, updated_at=now))
        if self._platform is not None:
            self._platform.unregister_hotkey(hotkey_id, hwnd=hwnd)

    def _close_open_sessions_for_task(self, task: Task, *, ended_at: datetime) -> None:
        for session in task.work_sessions:
            if session.is_running:
                clamped_end = max(session.started_at, ended_at)
                self._repo.save_work_session(replace(session, ended_at=clamped_end))

    def _require_task(self, task_id: str) -> Task:
        task = self._repo.get_task(task_id)
        if task is None:
            raise KeyError(f"Unknown Task: {task_id}")
        return task
