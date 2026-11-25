"""Tests for SQLiteRepository at the nyatodo.storage seam."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from nyatodo.domain import (
    IdleThreshold,
    Settings,
    SubStep,
    Task,
    TaskStatus,
    ThemeMode,
    WorkSession,
)
from nyatodo.storage import SQLiteRepository


def test_repository_persists_task_substep_and_open_work_session_across_restarts(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nyatodo.db"
    t0 = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)

    repo = SQLiteRepository(db_path)
    repo.create_tables()  # Idempotent re-run
    assert repo.schema_version() >= 1
    assert repo.journal_mode().lower() == "wal"

    task = Task(
        id="task-1",
        title="Investigate memory spike",
        status=TaskStatus.DOING,
        requester="Alex",
        notes="Check SQLite connection lifecycle.",
        sort_order=0,
        created_at=t0,
        updated_at=t0,
    )
    repo.save_task(task)
    repo.save_sub_step(
        SubStep(id="step-1", task_id="task-1", title="Profile queries", is_done=True, sort_order=0)
    )
    repo.save_work_session(
        WorkSession(
            id="ws-1",
            task_id="task-1",
            started_at=t0 + timedelta(minutes=5),
            ended_at=None,
        )
    )
    repo.close()

    reopened = SQLiteRepository(db_path)
    loaded = reopened.get_task("task-1")
    reopened.close()

    assert loaded is not None
    assert loaded.title == "Investigate memory spike"
    assert loaded.status == TaskStatus.DOING
    assert loaded.requester == "Alex"
    assert loaded.notes == "Check SQLite connection lifecycle."
    assert len(loaded.sub_steps) == 1
    assert loaded.sub_steps[0].is_done is True
    assert len(loaded.work_sessions) == 1
    assert loaded.work_sessions[0].is_running is True
    assert loaded.work_sessions[0].started_at == t0 + timedelta(minutes=5)


def test_repository_sorting_cascade_delete_and_settings_roundtrip() -> None:
    t0 = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)
    with SQLiteRepository(":memory:") as repo:
        assert repo.get_settings() == Settings()

        custom_settings = Settings(
            theme=ThemeMode.LIGHT,
            global_shortcut="Ctrl+Shift+Space",
            show_shortcut_hints=False,
            idle_threshold=IdleThreshold.OFF,
        )
        repo.save_settings(custom_settings)
        assert repo.get_settings() == custom_settings

        t_a = Task(id="a", title="Alpha", sort_order=0, created_at=t0, updated_at=t0)
        t_b = Task(id="b", title="Beta", sort_order=1, created_at=t0, updated_at=t0)
        repo.save_task(t_a)
        repo.save_task(t_b)
        repo.update_task_sort_orders(["b", "a"])

        listed = repo.list_tasks(TaskStatus.TODO)
        assert [t.id for t in listed] == ["b", "a"]

        repo.save_sub_step(SubStep(id="s1", task_id="b", title="Step 1"))
        repo.save_work_session(WorkSession(id="w1", task_id="b", started_at=t0))
        assert [s.id for s in repo.list_running_sessions()] == ["w1"]

        repo.delete_task("b")
        assert repo.get_sub_step("s1") is None
        assert repo.get_work_session("w1") is None
        assert repo.list_running_sessions() == []
