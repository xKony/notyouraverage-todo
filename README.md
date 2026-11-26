# nyatodo

A personal, keyboard-first desktop workspace for low-friction **Task** capture, thought structuring in a **Thinking Space**, and concurrent time tracking via **Task Timers** and **Work Sessions**.

## Stack

- **Python 3.13+** managed with [`uv`](https://docs.astral.sh/uv/)
- **PySide6** (Qt 6) for the floating spotlight window and system tray icon
- **SQLite** for local persistence (`%LOCALAPPDATA%\nyatodo\nyatodo.db` by default)
- **Win32 `ctypes`** (`RegisterHotKey`, `GetLastInputInfo`) for global shortcut activation and idle detection

## Setup & Run

```powershell
uv sync
uv run nyatodo
# Or without .exe script wrappers:
uv run python -m nyatodo
```

## Development Checks

```powershell
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src tests
uv run pytest
```

## Documentation

- [Domain Glossary](GLOSSARY.md)
- [Specification](docs/spec.md)
- [Coding Standards](CODING_STANDARDS.md)
- [ADRs](docs/adr/)

## License

Built by [xKony](https://github.com/xKony). Released under the [MIT License](LICENSE).
