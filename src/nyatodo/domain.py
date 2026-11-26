"""Core domain models, enums, and pure interval math for nyatodo."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo
from enum import Enum, StrEnum

from nyatodo.parser import (
    ParsedQuickInput,
    QuickBarParser,
    extract_search_query,
    is_search_input,
    parse_quick_input,
)

__all__ = [
    "ActivitySummary",
    "AutoHideDelay",
    "DailySummary",
    "DayBreakdown",
    "IdleGap",
    "IdleThreshold",
    "ParsedQuickInput",
    "QuickBarParser",
    "Settings",
    "SubStep",
    "SummaryPeriod",
    "SummaryPeriodKind",
    "Task",
    "TaskDateFilter",
    "TaskDateFilterMode",
    "TaskDayBreakdown",
    "TaskSortMode",
    "TaskStatus",
    "TaskSummaryBreakdown",
    "ThemeMode",
    "WorkSession",
    "compute_wall_clock_seconds",
    "extract_search_query",
    "format_summary_period_label",
    "format_task_added_full",
    "format_task_added_tooltip",
    "format_task_date_pill",
    "format_week_range_short",
    "is_search_input",
    "parse_quick_input",
]


class TaskStatus(StrEnum):
    """Lifecycle status of a Task."""

    TODO = "Todo"
    DOING = "Doing"
    WAITING = "Waiting"
    DONE = "Done"


class TaskSortMode(StrEnum):
    """Ordering mode for Task List groups."""

    MANUAL = "Manual"
    NEWEST = "Newest"
    OLDEST = "Oldest"


class TaskDateFilterMode(StrEnum):
    """Creation-date filter presets for the Task List."""

    ANY = "Any"
    TODAY = "Today"
    THIS_WEEK = "This Week"
    LAST_WEEK = "Last Week"
    CUSTOM = "Custom"


@dataclass(frozen=True)
class TaskDateFilter:
    """Creation-date filter specification evaluated against local task creation dates."""

    mode: TaskDateFilterMode = TaskDateFilterMode.ANY
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("TaskDateFilter start_date must be on or before end_date.")

    @property
    def is_active(self) -> bool:
        """Return True when a non-default creation-date filter is active."""
        return self.mode != TaskDateFilterMode.ANY

    def resolve_range(self, today: date) -> tuple[date | None, date | None]:
        """Resolve inclusive local [start_date, end_date] bounds relative to local today."""
        if self.mode == TaskDateFilterMode.ANY:
            return (None, None)
        if self.mode == TaskDateFilterMode.TODAY:
            return (today, today)
        if self.mode == TaskDateFilterMode.THIS_WEEK:
            monday = today - timedelta(days=today.weekday())
            return (monday, monday + timedelta(days=6))
        if self.mode == TaskDateFilterMode.LAST_WEEK:
            this_monday = today - timedelta(days=today.weekday())
            last_monday = this_monday - timedelta(days=7)
            return (last_monday, last_monday + timedelta(days=6))
        return (self.start_date, self.end_date)

    def matches_date(self, target_date: date, *, today: date) -> bool:
        """Return True if target_date falls within the resolved inclusive range."""
        start, end = self.resolve_range(today)
        if start is not None and target_date < start:
            return False
        return not (end is not None and target_date > end)


class SummaryPeriodKind(StrEnum):
    """Granularity of an Activity Summary period."""

    DAY = "Day"
    WEEK = "Week"
    CUSTOM = "Custom"


@dataclass(frozen=True)
class SummaryPeriod:
    """Inclusive local calendar date window for Activity Summary aggregation."""

    kind: SummaryPeriodKind
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("SummaryPeriod start_date must be on or before end_date.")

    @classmethod
    def day(cls, day: date) -> "SummaryPeriod":
        """Create a single-day SummaryPeriod."""
        return cls(kind=SummaryPeriodKind.DAY, start_date=day, end_date=day)

    @classmethod
    def work_week(cls, reference_day: date) -> "SummaryPeriod":
        """Create a Monday-through-Sunday Work Week SummaryPeriod containing reference_day."""
        monday = reference_day - timedelta(days=reference_day.weekday())
        sunday = monday + timedelta(days=6)
        return cls(kind=SummaryPeriodKind.WEEK, start_date=monday, end_date=sunday)

    @classmethod
    def custom(cls, start_date: date, end_date: date) -> "SummaryPeriod":
        """Create a custom inclusive [start_date, end_date] SummaryPeriod."""
        return cls(kind=SummaryPeriodKind.CUSTOM, start_date=start_date, end_date=end_date)

    @property
    def day_count(self) -> int:
        """Return inclusive number of calendar days covered by this period."""
        return (self.end_date - self.start_date).days + 1

    def contains_date(self, day: date) -> bool:
        """Return True if day lies inside [start_date, end_date] inclusive."""
        return self.start_date <= day <= self.end_date

    def can_step_next(self, today: date) -> bool:
        """Return True if stepping forward by one period stays on or before today's period."""
        if self.kind == SummaryPeriodKind.DAY:
            return self.start_date < today
        if self.kind == SummaryPeriodKind.WEEK:
            return self.start_date < SummaryPeriod.work_week(today).start_date
        return self.end_date < today

    def step(self, delta: int, *, today: date) -> "SummaryPeriod | None":
        """Step backward or forward by delta periods, returning None if blocked by today."""
        if delta == 0:
            return self
        if delta > 0 and not self.can_step_next(today):
            return None

        if self.kind == SummaryPeriodKind.DAY:
            target = self.start_date + timedelta(days=delta)
            if delta > 0 and target > today:
                target = today
            return SummaryPeriod.day(target)

        if self.kind == SummaryPeriodKind.WEEK:
            candidate = SummaryPeriod.work_week(self.start_date + timedelta(days=7 * delta))
            max_week = SummaryPeriod.work_week(today)
            if delta > 0 and candidate.start_date > max_week.start_date:
                return max_week
            return candidate

        shift = delta * self.day_count
        new_start = self.start_date + timedelta(days=shift)
        new_end = self.end_date + timedelta(days=shift)
        if delta > 0 and new_end > today:
            new_end = today
            new_start = today - timedelta(days=self.day_count - 1)
        return SummaryPeriod.custom(new_start, new_end)


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


class AutoHideDelay(Enum):
    """Auto-hide delay in seconds after losing window focus, or OFF when disabled."""

    OFF = None
    IMMEDIATE = 0
    ONE_SEC = 1
    THREE_SEC = 3
    FIVE_SEC = 5
    TEN_SEC = 10
    THIRTY_SEC = 30

    @property
    def seconds(self) -> int | None:
        """Return delay in seconds, or None when disabled."""
        return None if self.value is None else int(self.value)

    @classmethod
    def from_seconds(cls, seconds: int | None) -> "AutoHideDelay":
        """Resolve an AutoHideDelay from an integer second value or None."""
        for member in cls:
            if member.value == seconds:
                return member
        raise ValueError(f"Unsupported auto-hide delay seconds: {seconds!r}")


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
class DayBreakdown:
    """Single-day metrics within an Activity Summary daily strip."""

    day: date
    wall_clock_seconds: int
    total_logged_seconds: int
    completed_count: int


@dataclass(frozen=True)
class TaskSummaryBreakdown:
    """Per-Task summary row within an Activity Summary."""

    task_id: str
    title: str
    requester: str | None
    status: TaskStatus
    logged_seconds: int
    completed_in_period: bool

    @property
    def completed_on_day(self) -> bool:
        """Backward-compatible alias for single-day breakdown callers."""
        return self.completed_in_period


TaskDayBreakdown = TaskSummaryBreakdown


@dataclass(frozen=True)
class ActivitySummary:
    """Chronological summary of Work Sessions and completed Tasks over a SummaryPeriod."""

    period: SummaryPeriod
    wall_clock_seconds: int
    total_logged_seconds: int
    overlap_seconds: int
    tasks: tuple[TaskSummaryBreakdown, ...]
    daily_breakdown: tuple[DayBreakdown, ...]
    completed_count: int

    @property
    def day(self) -> date:
        """Return start_date for single-day compatibility."""
        return self.period.start_date


DailySummary = ActivitySummary


def _to_local_datetime(dt: datetime, tz: tzinfo | None = None) -> datetime:
    aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return aware.astimezone(tz) if tz is not None else aware.astimezone()


def _format_month_day(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}"


def format_task_date_pill(
    created_at: datetime,
    *,
    now: datetime,
    tz: tzinfo | None = None,
) -> str:
    """Format Task creation date as Today, Yesterday, 'Nov 24', or \"Nov 24 '25\"."""
    created_local = _to_local_datetime(created_at, tz)
    now_local = _to_local_datetime(now, tz)
    created_day = created_local.date()
    today = now_local.date()

    if created_day == today:
        return "Today"
    if created_day == today - timedelta(days=1):
        return "Yesterday"
    base = _format_month_day(created_day)
    if created_day.year == today.year:
        return base
    return f"{base} '{created_day.year % 100:02d}"


def format_task_added_full(
    created_at: datetime,
    *,
    now: datetime,
    tz: tzinfo | None = None,
) -> str:
    """Format Thinking Space header creation metadata, e.g. 'Added Thu, Nov 26 · 18:12'."""
    created_local = _to_local_datetime(created_at, tz)
    now_local = _to_local_datetime(now, tz)
    created_day = created_local.date()
    weekday = created_day.strftime("%a")
    month_day = _format_month_day(created_day)
    time_str = created_local.strftime("%H:%M")
    if created_day.year != now_local.date().year:
        return f"Added {weekday}, {month_day}, {created_day.year} · {time_str}"
    return f"Added {weekday}, {month_day} · {time_str}"


def format_task_added_tooltip(created_at: datetime, *, tz: tzinfo | None = None) -> str:
    """Format full local creation timestamp tooltip for Task Row date pills."""
    created_local = _to_local_datetime(created_at, tz)
    created_day = created_local.date()
    return (
        f"Added {created_day.strftime('%a')}, {_format_month_day(created_day)}, "
        f"{created_day.year} · {created_local.strftime('%H:%M')}"
    )


def format_week_range_short(start: date, end: date, *, today_year: int) -> str:
    """Format a Monday-Sunday Work Week range concisely (e.g. 'Nov 23-29')."""
    if start.year == end.year:
        if start.month == end.month:
            span = f"{start.strftime('%b')} {start.day}\u2013{end.day}"
        else:
            span = f"{_format_month_day(start)}\u2013{_format_month_day(end)}"
        return span if start.year == today_year else f"{span}, {start.year}"
    return f"{_format_month_day(start)}, {start.year} \u2013 {_format_month_day(end)}, {end.year}"


def format_summary_period_label(period: SummaryPeriod, *, today: date) -> str:
    """Format clickable Activity Summary period pill label relative to local today."""
    if period.kind == SummaryPeriodKind.DAY:
        d = period.start_date
        base = f"{d.strftime('%a')}, {_format_month_day(d)}"
        if d == today:
            return f"Today · {base}"
        if d == today - timedelta(days=1):
            return f"Yesterday · {base}"
        if d.year == today.year:
            return base
        return f"{base}, {d.year}"

    if period.kind == SummaryPeriodKind.WEEK:
        this_week = SummaryPeriod.work_week(today)
        last_week = SummaryPeriod.work_week(today - timedelta(days=7))
        span = format_week_range_short(period.start_date, period.end_date, today_year=today.year)
        if period == this_week:
            return f"This Week · {span}"
        if period == last_week:
            return f"Last Week · {span}"
        return f"Week · {span}"

    start, end = period.start_date, period.end_date
    if start == end:
        base = _format_month_day(start)
        return base if start.year == today.year else f"{base}, {start.year}"
    if start.year == end.year == today.year:
        return f"{_format_month_day(start)} \u2013 {_format_month_day(end)}"
    return f"{_format_month_day(start)}, {start.year} \u2013 {_format_month_day(end)}, {end.year}"


@dataclass(frozen=True)
class Settings:
    """Persisted user preferences."""

    theme: ThemeMode = ThemeMode.DARK
    global_shortcut: str = "Ctrl+Alt+Space"
    show_shortcut_hints: bool = True
    idle_threshold: IdleThreshold = IdleThreshold.FIFTEEN_MIN
    auto_hide_delay: AutoHideDelay = AutoHideDelay.THREE_SEC


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
