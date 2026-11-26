# nyatodo

Windows desktop **Task** & time-tracking workspace (`PySide6`, `SQLite`, Win32 `ctypes`).

- **Domain terms**: read [GLOSSARY.md](GLOSSARY.md) before naming symbols or UI copy.
- **Behavior & UI**: [docs/spec.md](docs/spec.md), [docs/ui-spec.md](docs/ui-spec.md), [docs/adr/](docs/adr/).
- **Code layout** (dependencies flow strictly inward toward `domain`):
  - `src/nyatodo/domain.py`, `parser.py` — pure models, Quick Bar parsing, interval math (no I/O or Qt).
  - `src/nyatodo/storage.py` — `SQLiteRepository`.
  - `src/nyatodo/service.py` — `TodoService` lifecycle, timers, summaries.
  - `src/nyatodo/platform_win32.py` — `PlatformBridge` (`ctypes` isolated here).
  - `src/nyatodo/ui/` — `main_window.py` (shell, tabs, shortcuts), `thinking_space.py`, `task_row.py`, `quick_bar.py`, `hints_footer.py`, `summary_view.py`, `theme.py`.
  - `tests/` — `test_*.py` matching each module.
- **Review**: read [CODING_STANDARDS.md](CODING_STANDARDS.md) during code review.
- **Verify** (fast-first, PowerShell 5.1): `uv run ruff check src tests; if ($?) { uv run ruff format --check src tests }; if ($?) { uv run mypy src tests }; if ($?) { uv run pytest }`
