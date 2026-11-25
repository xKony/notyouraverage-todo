"""Core domain models, enums, and pure interval math for nyatodo."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum, StrEnum

from nyatodo.parser import (
    ParsedQuickInput,
    QuickBarParser,
    extract_search_query,
    is_search_input,
    parse_quick_input,
)

__all__ = [
    "DailySummary",
    "IdleGap",
    "IdleThreshold",
    "ParsedQuickInput",
    "QuickBarParser",
    "Settings",
    "SubStep",
    "Task",
    "TaskDayBreakdown",
    "TaskStatus",
    "ThemeMode",
    "WorkSession",
    "compute_wall_clock_seconds",
    "extract_search_query",
    "is_search_input",
    "parse_quick_input",
]


class TaskStatus(StrEnum):
    """Lifecycle status of a Task."""

    TODO = "Todo"
    DOING = "Doing"
    WAITING = "Waiting"
    DONE = "Done"


class ThemeMode(StrEnum):
    """Visual theme preference."""

    DARK = "Dark"
    LIGHT = "Light"
    SYSTEM = "System"


class IdleThreshold(Enum):
    """Idle detection threshold in minutes, or OFF when disabled."""

    OFF = None
    FIVE_MIN = 5
    TEN_MIN = 10
    FIFTEEN_MIN = 15
    THIRTY_MIN = 30

    @property
    def minutes(self) -> int | None:
        """Return threshold in minutes, or None when disabled."""
        return None if self.value is None else int(self.value)

    @property
    def seconds(self) -> int | None:
        """Return threshold in seconds, or None when disabled."""
        return None if self.value is None else self.value * 60

    @classmethod
    def from_minutes(cls, minutes: int | None) -> "IdleThreshold":
        """Resolve an IdleThreshold from an integer minute value or None."""
        for member in cls:
            if member.value == minutes:
                return member
        raise ValueError(f"Unsupported idle threshold minutes: {minutes!r}")


@dataclass(frozen=True)
class SubStep:
    """Checkable action item nested inside a Task's Thinking Space."""

    id: str
    task_id: str
    title: str
    is_done: bool = False
    sort_order: int = 0


@dataclass(frozen=True)
class WorkSession:
    """Recorded work interval for a Task (live Task Timer or manual entry)."""

    id: str
    task_id: str
    started_at: datetime
    ended_at: datetime | None = None
    is_manual: bool = False

    @property
    def is_running(self) -> bool:
        """Return True if this Work Session is currently open."""
        return self.ended_at is None

    def duration_seconds(self, now: datetime | None = None) -> int:
        """Compute non-negative duration in whole seconds."""
        end = self.ended_at if self.ended_at is not None else (now or datetime.now(UTC))
        delta = int((end - self.started_at).total_seconds())
        return max(0, delta)


@dataclass(frozen=True)
class Task:
    """Primary unit of work tracked in the Task List."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    status: TaskStatus = TaskStatus.TODO
    requester: str | None = None
    notes: str = ""
    sort_order: int = 0
    completed_at: datetime | None = None
    sub_steps: tuple[SubStep, ...] = ()
    work_sessions: tuple[WorkSession, ...] = ()

    @property
    def is_timer_running(self) -> bool:
        """Return True when at least one Work Session on this Task is open."""
        return any(session.is_running for session in self.work_sessions)

    @property
    def active_session(self) -> WorkSession | None:
        """Return the currently running Work Session, if any."""
        for session in self.work_sessions:
            if session.is_running:
                return session
        return None

    def active_session_seconds(self, now: datetime | None = None) -> int:
        """Return elapsed seconds of the currently running Work Session, or 0 if stopped."""
        session = self.active_session
        return 0 if session is None else session.duration_seconds(now=now)

    def total_logged_seconds(self, now: datetime | None = None) -> int:
        """Return summed seconds across all Work Sessions on this Task."""
        return sum(session.duration_seconds(now=now) for session in self.work_sessions)

    @property
    def completed_sub_steps_count(self) -> int:
        """Return number of completed Sub-steps."""
        return sum(1 for step in self.sub_steps if step.is_done)


@dataclass(frozen=True)
class TaskDayBreakdown:
    """Per-Task summary row within a Daily Summary."""

    task_id: str
    title: str
    requester: str | None
    status: TaskStatus
    logged_seconds: int
    completed_on_day: bool


@dataclass(frozen=True)
class DailySummary:
    """Chronological summary of Work Sessions and completed Tasks for a calendar day."""

    day: date
    wall_clock_seconds: int
    total_logged_seconds: int
    overlap_seconds: int
    tasks: tuple[TaskDayBreakdown, ...]
    completed_count: int


@dataclass(frozen=True)
class Settings:
    """Persisted user preferences."""

    theme: ThemeMode = ThemeMode.DARK
    global_shortcut: str = "Ctrl+Alt+Space"
    show_shortcut_hints: bool = True
    idle_threshold: IdleThreshold = IdleThreshold.FIFTEEN_MIN


@dataclass(frozen=True)
class IdleGap:
    """Detected OS idle period exceeding configured threshold while timers ran."""

    idle_seconds: int
    idle_started_at: datetime
    affected_task_ids: tuple[str, ...]
    detected_at: datetime | None = None


def clip_session_interval(
    session: WorkSession,
    *,
    now: datetime,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[datetime, datetime] | None:
    """Return clipped [s_start, s_end] interval or None if outside window or empty."""
    s_start = session.started_at
    s_end = session.ended_at if session.ended_at is not None else now
    if start is not None and s_start < start:
        s_start = start
    if end is not None and s_end > end:
        s_end = end
    if s_end <= s_start:
        return None
    return (s_start, s_end)


def compute_wall_clock_seconds(
    sessions: Iterable[WorkSession],
    *,
    now: datetime | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    """Merge overlapping Work Session intervals and return total wall-clock seconds."""
    effective_now = now or datetime.now(UTC)
    intervals: list[tuple[datetime, datetime]] = []
    for session in sessions:
        clipped = clip_session_interval(session, now=effective_now, start=start, end=end)
        if clipped is not None:
            intervals.append(clipped)

    if not intervals:
        return 0

    intervals.sort(key=lambda pair: (pair[0], pair[1]))
    merged_start, merged_end = intervals[0]
    total_seconds = 0

    for iv_start, iv_end in intervals[1:]:
        if iv_start <= merged_end:
            if iv_end > merged_end:
                merged_end = iv_end
        else:
            total_seconds += int((merged_end - merged_start).total_seconds())
            merged_start, merged_end = iv_start, iv_end

    total_seconds += int((merged_end - merged_start).total_seconds())
    return total_seconds
