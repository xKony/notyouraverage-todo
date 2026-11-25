# Coding Standards

All code in `nyatodo` follows these standards to keep the codebase predictable, strictly typed, and cleanly layered.

---

## 1. Python & Static Analysis

- **Python Version**: Python `3.13+`. Use modern standard library features (`datetime.UTC`, `pathlib.Path`, `collections.abc`, `X | Y` union syntax, `StrEnum`).
- **Type Annotations**: Full type annotations across all modules and tests. Code must pass `uv run mypy --strict` with zero errors.
  - Avoid `Any` unless interfacing directly with untyped external boundaries (such as `ctypes` or Qt event overrides), and document why when used.
  - Prefer `Protocol` and `dataclass(frozen=True)` for clean interfaces and value objects.
- **Formatting & Linting**: Code must pass `uv run ruff check .` and `uv run ruff format --check .`.
  - Line length: `100` characters.
  - Enabled lint rule families: `E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`.

---

## 2. Architecture & Separation of Concerns

Dependencies must flow strictly inward toward `nyatodo.domain`. Lower layers never import higher layers or Qt.

- **`nyatodo.domain`**:
  - Pure dataclasses, enums, Quick Bar parsing (`QuickBarParser` / `parse_quick_input`), and time/interval-union math.
  - Zero I/O, zero SQL, zero Win32 calls, zero `PySide6` imports.
- **`nyatodo.storage`**:
  - SQLite persistence (`SQLiteRepository`), schema setup, and explicit SQL queries.
  - Accepts an injectable database path (`Path | str`) so tests run against temporary files or `:memory:`.
- **`nyatodo.service`**:
  - Application use cases (`TodoService`): **Task** lifecycle, concurrent **Task Timers**, **Thinking Space** operations, **Daily Summary** aggregation, and idle trim handling.
  - Accepts injectable repository, clock, and `PlatformBridge` dependencies.
- **`nyatodo.platform_win32`**:
  - Platform abstraction (`PlatformBridge` protocol) and Win32 `ctypes` implementation (`RegisterHotKey`, `GetLastInputInfo`, system theme query).
  - Isolates all `ctypes` structs and Win32 error handling behind clean typed Python methods.
- **`nyatodo.ui`**:
  - `PySide6` widgets, spotlight window, tray integration, dialogs, and QSS stylesheets.
  - **No raw SQL and no business/time-calculation logic inside Qt widgets.** Widgets call `TodoService` and render returned domain models.

---

## 3. Canonical Domain Vocabulary

Use the exact terms defined in [GLOSSARY.md](GLOSSARY.md) across symbols, modules, tests, comments, and UI copy:

- `Task` (avoid: ticket, issue, inbox item, card)
- `TaskList` / **Task List** (avoid: backlog, inbox, board)
- `Requester` (avoid: assignee, reporter, attribution, link)
- `TaskStatus` (`Todo`, `Doing`, `Waiting`, `Done`) (avoid: stage, column, priority)
- `ThinkingSpace` (avoid: description, wiki, sub-page)
- `SubStep` / **Sub-step** (avoid: sub-task, child ticket, checklist card)
- `TaskTimer` (avoid: focus lock, Pomodoro clock)
- `WorkSession` (avoid: timesheet, billable entry, Pomodoro)
- `DailySummary` (avoid: standup report, export, timesheet)

---

## 4. Functions, Error Handling & Testing

- **Small, Focused Functions**: Keep functions concise with shallow nesting and early returns. Extract shared helpers rather than duplicating logic.
- **No Silent Exception Swallowing**: Never write bare `except:` or silent `except Exception: pass`. Catch specific exceptions, log or surface actionable failures, and keep resource cleanup deterministic (`with` context managers).
- **Test-First Vertical Slices**:
  - Test against public seams (`parse_quick_input`, `SQLiteRepository`, `TodoService`, `PlatformBridge`), not private helpers or implementation internals.
  - Use deterministic clocks and fake `PlatformBridge` implementations instead of real wall-clock sleeps in tests.
  - All tests must pass via `uv run pytest`.
