# Coding Standards

Review guidelines for judgement calls in `nyatodo`. Mechanical lint, formatting, strict typing, layer imports, and Qt DPI rules live in [pyproject.toml](pyproject.toml) and [tests/test_arch.py](tests/test_arch.py).

- **Static Typing Boundaries**: Avoid `Any`; reserve it strictly for untyped Win32 `ctypes` or Qt event overrides. Prefer `Protocol` and `dataclass(frozen=True)` for seams and value objects.
- **Domain & Layer Discipline**: Keep business logic, parsing, and time math out of Qt widgets ([AGENTS.md](AGENTS.md)). Use the exact domain terms from [GLOSSARY.md](GLOSSARY.md) in symbols, comments, and UI copy.
- **Cohesive Functions**: Keep functions focused with shallow nesting and early returns. Reuse shared helpers instead of duplicating non-trivial branches.
- **Explicit Error Handling**: Catch specific exceptions, surface or log actionable failures, and manage resources deterministically with context managers.
- **Tests at Real Seams**: Test public seams (`parse_quick_input`, `SQLiteRepository`, `TodoService`, `PlatformBridge`, rendered widget behavior) using deterministic clocks and fake `PlatformBridge` implementations instead of wall-clock sleeps.
