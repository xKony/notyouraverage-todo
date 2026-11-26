"""SQLite persistence layer for nyatodo."""

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from nyatodo.domain import (
    AutoHideDelay,
    IdleThreshold,
    Settings,
    SubStep,
    Task,
    TaskImportance,
    TaskStatus,
    ThemeMode,
    WorkSession,
)

_SCHEMA_VERSION = 3


def _serialize_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return aware.isoformat()


def _deserialize_dt(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    parsed = datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


class SQLiteRepository:
    """SQLite-backed repository for Tasks, Sub-steps, Work Sessions, and Settings."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL;")
        self.create_tables()

    def __enter__(self) -> "SQLiteRepository":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def schema_version(self) -> int:
        """Return the current SQLite PRAGMA user_version."""
        row = self._conn.execute("PRAGMA user_version;").fetchone()
        return int(row[0]) if row is not None else 0

    def journal_mode(self) -> str:
        """Return the active SQLite PRAGMA journal_mode."""
        row = self._conn.execute("PRAGMA journal_mode;").fetchone()
        return str(row[0]) if row is not None else ""

    def create_tables(self) -> None:
        """Idempotently create database tables and indices."""
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    importance INTEGER NOT NULL DEFAULT 0,
                    requester TEXT,
                    notes TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS sub_steps (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    is_done INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_sub_steps_task_sort
                    ON sub_steps (task_id, sort_order, id);

                CREATE TABLE IF NOT EXISTS work_sessions (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    is_manual INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_work_sessions_task_started
                    ON work_sessions (task_id, started_at, id);

                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    theme TEXT NOT NULL,
                    global_shortcut TEXT NOT NULL,
                    show_shortcut_hints INTEGER NOT NULL,
                    idle_threshold_minutes INTEGER,
                    auto_hide_seconds INTEGER DEFAULT 3
                );
                """
            )
            task_columns = {
                str(col["name"])
                for col in self._conn.execute("PRAGMA table_info(tasks);").fetchall()
            }
            if "importance" not in task_columns:
                self._conn.execute(
                    "ALTER TABLE tasks ADD COLUMN importance INTEGER NOT NULL DEFAULT 0;"
                )
            if self.schema_version() < 3:
                self._conn.execute("DROP INDEX IF EXISTS idx_tasks_status_sort;")
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_status_sort
                    ON tasks (status, importance DESC, sort_order, created_at, id);
                """
            )
            columns = {
                str(col["name"])
                for col in self._conn.execute("PRAGMA table_info(settings);").fetchall()
            }
            if "auto_hide_seconds" not in columns:
                self._conn.execute(
                    "ALTER TABLE settings ADD COLUMN auto_hide_seconds INTEGER DEFAULT 3;"
                )
            if self.schema_version() < _SCHEMA_VERSION:
                self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION};")

    def save_task(self, task: Task) -> Task:
        """Insert or update a Task row (does not overwrite child rows unless saved directly)."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO tasks (
                    id, title, status, importance, requester, notes, sort_order,
                    created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    status = excluded.status,
                    importance = excluded.importance,
                    requester = excluded.requester,
                    notes = excluded.notes,
                    sort_order = excluded.sort_order,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    completed_at = excluded.completed_at;
                """,
                (
                    task.id,
                    task.title,
                    task.status.value,
                    int(task.importance),
                    task.requester,
                    task.notes,
                    task.sort_order,
                    _serialize_dt(task.created_at),
                    _serialize_dt(task.updated_at),
                    _serialize_dt(task.completed_at),
                ),
            )
        return task

    def get_task(self, task_id: str) -> Task | None:
        """Fetch a single Task by ID with its Sub-steps and Work Sessions."""
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,)).fetchone()
        if row is None:
            return None
        sub_steps = self._fetch_sub_steps_for_tasks([task_id]).get(task_id, ())
        sessions = self._fetch_sessions_for_tasks([task_id]).get(task_id, ())
        return self._row_to_task(row, sub_steps, sessions)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List Tasks sorted deterministically by importance DESC, sort_order, created_at, id."""
        if status is None:
            rows = self._conn.execute(
                """
                SELECT * FROM tasks
                ORDER BY importance DESC, sort_order ASC, created_at ASC, id ASC;
                """
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = ?
                ORDER BY importance DESC, sort_order ASC, created_at ASC, id ASC;
                """,
                (status.value,),
            ).fetchall()

        task_ids = [str(row["id"]) for row in rows]
        if not task_ids:
            return []
        steps_by_task = self._fetch_sub_steps_for_tasks(task_ids)
        sessions_by_task = self._fetch_sessions_for_tasks(task_ids)
        return [
            self._row_to_task(
                row,
                steps_by_task.get(str(row["id"]), ()),
                sessions_by_task.get(str(row["id"]), ()),
            )
            for row in rows
        ]

    def delete_task(self, task_id: str) -> None:
        """Delete a Task and cascade-delete its Sub-steps and Work Sessions."""
        with self._conn:
            self._conn.execute("DELETE FROM tasks WHERE id = ?;", (task_id,))

    def update_task_sort_orders(self, ordered_task_ids: Sequence[str]) -> None:
        """Persist deterministic sort_order values for a sequence of Task IDs."""
        with self._conn:
            self._conn.executemany(
                "UPDATE tasks SET sort_order = ? WHERE id = ?;",
                [(index, task_id) for index, task_id in enumerate(ordered_task_ids)],
            )

    def save_sub_step(self, sub_step: SubStep) -> SubStep:
        """Insert or update a Sub-step row."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sub_steps (id, task_id, title, is_done, sort_order)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id = excluded.task_id,
                    title = excluded.title,
                    is_done = excluded.is_done,
                    sort_order = excluded.sort_order;
                """,
                (
                    sub_step.id,
                    sub_step.task_id,
                    sub_step.title,
                    int(sub_step.is_done),
                    sub_step.sort_order,
                ),
            )
        return sub_step

    def get_sub_step(self, sub_step_id: str) -> SubStep | None:
        """Fetch a single Sub-step by ID."""
        row = self._conn.execute("SELECT * FROM sub_steps WHERE id = ?;", (sub_step_id,)).fetchone()
        return None if row is None else self._row_to_sub_step(row)

    def delete_sub_step(self, sub_step_id: str) -> None:
        """Delete a Sub-step by ID."""
        with self._conn:
            self._conn.execute("DELETE FROM sub_steps WHERE id = ?;", (sub_step_id,))

    def save_work_session(self, session: WorkSession) -> WorkSession:
        """Insert or update a Work Session row."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO work_sessions (id, task_id, started_at, ended_at, is_manual)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id = excluded.task_id,
                    started_at = excluded.started_at,
                    ended_at = excluded.ended_at,
                    is_manual = excluded.is_manual;
                """,
                (
                    session.id,
                    session.task_id,
                    _serialize_dt(session.started_at),
                    _serialize_dt(session.ended_at),
                    int(session.is_manual),
                ),
            )
        return session

    def get_work_session(self, session_id: str) -> WorkSession | None:
        """Fetch a single Work Session by ID."""
        row = self._conn.execute(
            "SELECT * FROM work_sessions WHERE id = ?;", (session_id,)
        ).fetchone()
        return None if row is None else self._row_to_session(row)

    def delete_work_session(self, session_id: str) -> None:
        """Delete a Work Session by ID."""
        with self._conn:
            self._conn.execute("DELETE FROM work_sessions WHERE id = ?;", (session_id,))

    def list_running_sessions(self) -> list[WorkSession]:
        """Return all open Work Sessions (ended_at IS NULL)."""
        rows = self._conn.execute(
            "SELECT * FROM work_sessions WHERE ended_at IS NULL ORDER BY started_at ASC, id ASC;"
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def get_settings(self) -> Settings:
        """Return persisted Settings or defaults if not yet saved."""
        row = self._conn.execute("SELECT * FROM settings WHERE id = 1;").fetchone()
        if row is None:
            return Settings()
        return Settings(
            theme=ThemeMode(str(row["theme"])),
            global_shortcut=str(row["global_shortcut"]),
            show_shortcut_hints=bool(row["show_shortcut_hints"]),
            idle_threshold=IdleThreshold.from_minutes(row["idle_threshold_minutes"]),
            auto_hide_delay=AutoHideDelay.from_seconds(row["auto_hide_seconds"]),
        )

    def save_settings(self, settings: Settings) -> Settings:
        """Persist Settings to the singleton row."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO settings (
                    id, theme, global_shortcut, show_shortcut_hints,
                    idle_threshold_minutes, auto_hide_seconds
                ) VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    theme = excluded.theme,
                    global_shortcut = excluded.global_shortcut,
                    show_shortcut_hints = excluded.show_shortcut_hints,
                    idle_threshold_minutes = excluded.idle_threshold_minutes,
                    auto_hide_seconds = excluded.auto_hide_seconds;
                """,
                (
                    settings.theme.value,
                    settings.global_shortcut,
                    int(settings.show_shortcut_hints),
                    settings.idle_threshold.minutes,
                    settings.auto_hide_delay.seconds,
                ),
            )
        return settings

    def _fetch_sub_steps_for_tasks(self, task_ids: Sequence[str]) -> dict[str, tuple[SubStep, ...]]:
        placeholders = ",".join("?" for _ in task_ids)
        rows = self._conn.execute(
            f"""
            SELECT * FROM sub_steps
            WHERE task_id IN ({placeholders})
            ORDER BY sort_order ASC, id ASC;
            """,
            tuple(task_ids),
        ).fetchall()
        grouped: dict[str, list[SubStep]] = {}
        for row in rows:
            step = self._row_to_sub_step(row)
            grouped.setdefault(step.task_id, []).append(step)
        return {key: tuple(items) for key, items in grouped.items()}

    def _fetch_sessions_for_tasks(
        self, task_ids: Sequence[str]
    ) -> dict[str, tuple[WorkSession, ...]]:
        placeholders = ",".join("?" for _ in task_ids)
        rows = self._conn.execute(
            f"""
            SELECT * FROM work_sessions
            WHERE task_id IN ({placeholders})
            ORDER BY started_at ASC, id ASC;
            """,
            tuple(task_ids),
        ).fetchall()
        grouped: dict[str, list[WorkSession]] = {}
        for row in rows:
            session = self._row_to_session(row)
            grouped.setdefault(session.task_id, []).append(session)
        return {key: tuple(items) for key, items in grouped.items()}

    @staticmethod
    def _row_to_sub_step(row: sqlite3.Row) -> SubStep:
        return SubStep(
            id=str(row["id"]),
            task_id=str(row["task_id"]),
            title=str(row["title"]),
            is_done=bool(row["is_done"]),
            sort_order=int(row["sort_order"]),
        )

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> WorkSession:
        started_at = _deserialize_dt(str(row["started_at"]))
        assert started_at is not None
        ended_raw = row["ended_at"]
        ended_at = _deserialize_dt(str(ended_raw)) if ended_raw is not None else None
        return WorkSession(
            id=str(row["id"]),
            task_id=str(row["task_id"]),
            started_at=started_at,
            ended_at=ended_at,
            is_manual=bool(row["is_manual"]),
        )

    @staticmethod
    def _row_to_task(
        row: sqlite3.Row,
        sub_steps: tuple[SubStep, ...],
        sessions: tuple[WorkSession, ...],
    ) -> Task:
        created_at = _deserialize_dt(str(row["created_at"]))
        updated_at = _deserialize_dt(str(row["updated_at"]))
        assert created_at is not None and updated_at is not None
        completed_raw = row["completed_at"]
        completed_at = _deserialize_dt(str(completed_raw)) if completed_raw is not None else None
        requester_raw = row["requester"]
        return Task(
            id=str(row["id"]),
            title=str(row["title"]),
            status=TaskStatus(str(row["status"])),
            importance=TaskImportance.from_int(int(row["importance"])),
            requester=str(requester_raw) if requester_raw is not None else None,
            notes=str(row["notes"]),
            sort_order=int(row["sort_order"]),
            created_at=created_at,
            updated_at=updated_at,
            completed_at=completed_at,
            sub_steps=sub_steps,
            work_sessions=sessions,
        )
