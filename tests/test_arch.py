"""Mechanical architecture and Qt high-DPI guardrail tests."""

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "nyatodo"
UI_ROOT = SRC_ROOT / "ui"


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name)
                roots.add(alias.name.split(".", maxsplit=1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module)
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def _has_forbidden_import(imports: set[str], forbidden: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for target in forbidden:
        if any(imp == target or imp.startswith(f"{target}.") for imp in imports):
            hits.append(target)
    return hits


def test_layer_dependencies_flow_inward() -> None:
    rules: list[tuple[Path, tuple[str, ...]]] = [
        (
            SRC_ROOT / "domain.py",
            (
                "PySide6",
                "sqlite3",
                "ctypes",
                "nyatodo.storage",
                "nyatodo.service",
                "nyatodo.platform_win32",
                "nyatodo.ui",
                "nyatodo.app",
            ),
        ),
        (
            SRC_ROOT / "parser.py",
            (
                "PySide6",
                "sqlite3",
                "ctypes",
                "nyatodo.domain",
                "nyatodo.storage",
                "nyatodo.service",
                "nyatodo.platform_win32",
                "nyatodo.ui",
                "nyatodo.app",
            ),
        ),
        (
            SRC_ROOT / "storage.py",
            (
                "PySide6",
                "ctypes",
                "nyatodo.service",
                "nyatodo.platform_win32",
                "nyatodo.ui",
                "nyatodo.app",
            ),
        ),
        (
            SRC_ROOT / "platform_win32.py",
            (
                "PySide6",
                "sqlite3",
                "nyatodo.storage",
                "nyatodo.service",
                "nyatodo.ui",
                "nyatodo.app",
            ),
        ),
        (
            SRC_ROOT / "service.py",
            ("PySide6", "sqlite3", "ctypes", "nyatodo.ui", "nyatodo.app"),
        ),
    ]

    for path, forbidden in rules:
        hits = _has_forbidden_import(_imported_roots(path), forbidden)
        assert not hits, f"{path.name} has forbidden inward-layer violation(s): {hits}"

    for ui_file in sorted(UI_ROOT.glob("*.py")):
        hits = _has_forbidden_import(_imported_roots(ui_file), ("sqlite3", "ctypes"))
        assert not hits, f"{ui_file.name} must not import low-level I/O/Win32 modules: {hits}"


def test_ui_icons_use_vector_and_dpr_helpers() -> None:
    for ui_file in sorted(UI_ROOT.glob("*.py")):
        source = ui_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(ui_file))

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "center"
                and isinstance(node.func.value, ast.Call)
                and isinstance(node.func.value.func, ast.Attribute)
                and node.func.value.func.attr == "rect"
            ):
                raise AssertionError(
                    f"{ui_file.name}:{node.lineno} calls .rect().center(); "
                    "use floating-point center or QRectF(...).center() for QPainter glyphs"
                )

            if ui_file.name != "icons.py" and isinstance(node, ast.Call):
                func_name = node.func.id if isinstance(node.func, ast.Name) else None
                if func_name in {"QPixmap", "QIcon"}:
                    raise AssertionError(
                        f"{ui_file.name}:{node.lineno} instantiates {func_name} directly; "
                        "route icon/pixmap creation through nyatodo.ui.icons"
                    )
