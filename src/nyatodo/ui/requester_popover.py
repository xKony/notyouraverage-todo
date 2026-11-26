"""Animated overflow Requester picker popover."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nyatodo.ui.qt_helpers import clear_layout, set_qss_property
from nyatodo.ui.shell_popover import AnimatedShellPopover
from nyatodo.ui.theme import make_ui_font


class RequesterPopover(AnimatedShellPopover):
    """Floating popover listing all Requesters when bar pills overflow."""

    requester_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, width=220)
        self.setObjectName("RequesterPopover")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 2, 0)
        title = QLabel("Requesters", self)
        title.setObjectName("FilterSectionLabel")
        title.setFont(make_ui_font(11, QFont.Weight.DemiBold))
        header.addWidget(title)
        header.addStretch(1)

        self.clear_button = QPushButton("Clear", self)
        self.clear_button.setObjectName("ModalResetButton")
        self.clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self._on_clear_clicked)
        header.addWidget(self.clear_button)
        root.addLayout(header)

        divider = QFrame(self)
        divider.setObjectName("SectionDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(divider)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("SessionListScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setMaximumHeight(210)

        self.list_host = QWidget(self.scroll_area)
        self.list_host.setObjectName("SessionListContainer")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(3)
        self.scroll_area.setWidget(self.list_host)
        root.addWidget(self.scroll_area)

    def open_near(
        self,
        anchor_widget: QWidget,
        *,
        requesters: list[str],
        active_requester: str | None,
    ) -> None:
        """Populate Requester rows, position below anchor_widget, and reveal."""
        clear_layout(self.list_layout)
        self.clear_button.setEnabled(active_requester is not None)

        item_font = make_ui_font(11, QFont.Weight.Medium)
        metrics = QFontMetrics(item_font)
        max_text_w = self.width() - 44

        for req in requesters:
            label = metrics.elidedText(f"@{req}", Qt.TextElideMode.ElideRight, max_text_w)
            btn = QPushButton(label, self.list_host)
            btn.setObjectName("RequesterPopoverItem")
            btn.setProperty("requester_name", req)
            btn.setToolTip(f"@{req}")
            btn.setFixedHeight(28)
            btn.setFont(item_font)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            set_qss_property(btn, "active", req == active_requester)
            btn.clicked.connect(lambda _checked=False, name=req: self._on_item_clicked(name))
            self.list_layout.addWidget(btn)

        self.list_host.adjustSize()
        content_h = self.list_host.sizeHint().height()
        self.scroll_area.setFixedHeight(min(210, max(28, content_h)))
        self._start_open_animation(anchor_widget, min_height=76)

    def _on_item_clicked(self, requester: str) -> None:
        self.close_popover()
        self.requester_selected.emit(requester)

    def _on_clear_clicked(self) -> None:
        self.close_popover()
        self.requester_selected.emit(None)
