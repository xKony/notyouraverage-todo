# nyatodo

A personal, keyboard-first desktop workspace for low-friction **Task** capture, thought structuring in a **Thinking Space**, and concurrent time tracking via **Task Timers** and **Work Sessions**.

## Stack

- **Python 3.13+** managed with [`uv`](https://docs.astral.sh/uv/)
- **PySide6** (Qt 6) for the floating spotlight window and system tray icon
- **SQLite** for local persistence (`%LOCALAPPDATA%\nyatodo\nyatodo.db` by default)
- **Win32 `ctypes`** (`RegisterHotKey`, `GetLastInputInfo`) for global shortcut activation and idle detection

## Setup

```powershell
uv sync
```

## Development Checks

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

## Documentation

- [Domain Glossary](GLOSSARY.md)
- [Specification](docs/spec.md)
- [Coding Standards](CODING_STANDARDS.md)
- [ADRs](docs/adr/)
