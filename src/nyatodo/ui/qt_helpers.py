"""Shared Qt layout and QSS property helpers for nyatodo UI widgets."""

from PySide6.QtWidgets import QLayout, QWidget


def clear_layout(layout: QLayout) -> None:
    """Remove and schedule deletion of all child widgets and nested layouts."""
    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            # Hide before detaching so Qt never promotes a visible child into a top-level window.
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
            continue
        child_layout = item.layout()
        if child_layout is not None:
            clear_layout(child_layout)


def set_qss_property(widget: QWidget, name: str, value: object) -> None:
    """Set a dynamic QSS property on a widget and re-polish its style."""
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
