"""Animated Task List Sort & Creation-Date Filter popover."""

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nyatodo.domain import TaskDateFilter, TaskDateFilterMode, TaskSortMode
from nyatodo.ui.qt_helpers import set_qss_property
from nyatodo.ui.shell_popover import AnimatedShellPopover
from nyatodo.ui.theme import make_ui_font


def _to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _from_qdate(qd: QDate) -> date:
    return date(qd.year(), qd.month(), qd.day())


class TaskFilterPopover(AnimatedShellPopover):
    """Smoothly animated popover for Task List sorting and creation-date filtering."""

    filter_changed = Signal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, width=292)
        self.setObjectName("FilterPopover")

        self._sort_mode: TaskSortMode = TaskSortMode.MANUAL
        self._date_filter: TaskDateFilter = TaskDateFilter(TaskDateFilterMode.ANY)
        self._today: date = date.today()
        self._loading = False

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        sort_header = QHBoxLayout()
        sort_header.setContentsMargins(0, 0, 0, 0)
        sort_label = QLabel("Sort", self)
        sort_label.setObjectName("FilterSectionLabel")
        sort_label.setFont(make_ui_font(11, QFont.Weight.DemiBold))
        sort_header.addWidget(sort_label)
        sort_header.addStretch(1)

        self.reset_button = QPushButton("Reset", self)
        self.reset_button.setObjectName("ModalResetButton")
        self.reset_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        sort_header.addWidget(self.reset_button)
        root.addLayout(sort_header)

        sort_track = QFrame(self)
        sort_track.setObjectName("SettingsSegmentTrack")
        sort_track.setFixedHeight(28)
        sort_layout = QHBoxLayout(sort_track)
        sort_layout.setContentsMargins(3, 3, 3, 3)
        sort_layout.setSpacing(2)

        self._sort_buttons: dict[TaskSortMode, QPushButton] = {}
        for mode in (TaskSortMode.MANUAL, TaskSortMode.NEWEST, TaskSortMode.OLDEST):
            btn = QPushButton(mode.value, sort_track)
            btn.setObjectName("SettingsSegmentOption")
            btn.setFixedHeight(22)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, m=mode: self._select_sort(m))
            self._sort_buttons[mode] = btn
            sort_layout.addWidget(btn)
        root.addWidget(sort_track)

        divider = QFrame(self)
        divider.setObjectName("SectionDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(divider)

        added_label = QLabel("Added", self)
        added_label.setObjectName("FilterSectionLabel")
        added_label.setFont(make_ui_font(11, QFont.Weight.DemiBold))
        root.addWidget(added_label)

        self._date_buttons: dict[TaskDateFilterMode, QPushButton] = {}
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(6)
        for dmode in (
            TaskDateFilterMode.ANY,
            TaskDateFilterMode.TODAY,
            TaskDateFilterMode.THIS_WEEK,
        ):
            btn = self._make_chip_button(dmode)
            row1.addWidget(btn)
        row1.addStretch(1)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)
        for dmode in (TaskDateFilterMode.LAST_WEEK, TaskDateFilterMode.CUSTOM):
            btn = self._make_chip_button(dmode)
            row2.addWidget(btn)
        row2.addStretch(1)
        root.addLayout(row2)

        self.custom_row = QWidget(self)
        custom_layout = QHBoxLayout(self.custom_row)
        custom_layout.setContentsMargins(0, 2, 0, 0)
        custom_layout.setSpacing(6)

        from_lbl = QLabel("From", self.custom_row)
        from_lbl.setObjectName("FilterFieldLabel")
        custom_layout.addWidget(from_lbl)

        self.from_date_edit = QDateEdit(self.custom_row)
        self.from_date_edit.setObjectName("DatePickerEdit")
        self.from_date_edit.setCalendarPopup(True)
        self.from_date_edit.setDisplayFormat("MMM d, yyyy")
        self.from_date_edit.setFixedHeight(26)
        self.from_date_edit.dateChanged.connect(self._on_from_date_changed)
        custom_layout.addWidget(self.from_date_edit, 1)

        to_lbl = QLabel("To", self.custom_row)
        to_lbl.setObjectName("FilterFieldLabel")
        custom_layout.addWidget(to_lbl)

        self.to_date_edit = QDateEdit(self.custom_row)
        self.to_date_edit.setObjectName("DatePickerEdit")
        self.to_date_edit.setCalendarPopup(True)
        self.to_date_edit.setDisplayFormat("MMM d, yyyy")
        self.to_date_edit.setFixedHeight(26)
        self.to_date_edit.dateChanged.connect(self._on_to_date_changed)
        custom_layout.addWidget(self.to_date_edit, 1)

        self.custom_row.setVisible(False)
        root.addWidget(self.custom_row)

    def _make_chip_button(self, mode: TaskDateFilterMode) -> QPushButton:
        btn = QPushButton(mode.value, self)
        btn.setObjectName("FilterChipButton")
        btn.setFixedHeight(24)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _checked=False, m=mode: self._select_date_mode(m))
        self._date_buttons[mode] = btn
        return btn

    def open_near(
        self,
        anchor_widget: QWidget,
        *,
        sort_mode: TaskSortMode,
        date_filter: TaskDateFilter,
        today: date,
    ) -> None:
        """Sync controls, position below anchor_widget, and smoothly reveal."""
        self._loading = True
        try:
            self._sort_mode = sort_mode
            self._date_filter = date_filter
            self._today = today

            start_d = date_filter.start_date or today
            end_d = date_filter.end_date or today
            if start_d > end_d:
                end_d = start_d
            self.from_date_edit.setDate(_to_qdate(start_d))
            self.to_date_edit.setDate(_to_qdate(end_d))
            self._sync_control_states()
        finally:
            self._loading = False

        self.custom_row.setVisible(self._date_filter.mode == TaskDateFilterMode.CUSTOM)
        self._start_open_animation(anchor_widget, min_height=120)

    def _sync_control_states(self) -> None:
        for mode, btn in self._sort_buttons.items():
            set_qss_property(btn, "active", mode == self._sort_mode)
        for dmode, btn in self._date_buttons.items():
            set_qss_property(btn, "active", dmode == self._date_filter.mode)
        self.custom_row.setVisible(self._date_filter.mode == TaskDateFilterMode.CUSTOM)
        has_active = self._sort_mode != TaskSortMode.MANUAL or self._date_filter.is_active
        self.reset_button.setEnabled(has_active)
        self._fit_open_height()

    def _select_sort(self, mode: TaskSortMode) -> None:
        if self._loading or mode == self._sort_mode:
            return
        self._sort_mode = mode
        self._sync_control_states()
        self.filter_changed.emit(self._sort_mode, self._date_filter)

    def _select_date_mode(self, mode: TaskDateFilterMode) -> None:
        if self._loading:
            return
        if mode == TaskDateFilterMode.CUSTOM:
            start_d = _from_qdate(self.from_date_edit.date())
            end_d = _from_qdate(self.to_date_edit.date())
            if start_d > end_d:
                end_d = start_d
                self.to_date_edit.blockSignals(True)
                self.to_date_edit.setDate(_to_qdate(end_d))
                self.to_date_edit.blockSignals(False)
            self._date_filter = TaskDateFilter(
                TaskDateFilterMode.CUSTOM,
                start_date=start_d,
                end_date=end_d,
            )
        else:
            self._date_filter = TaskDateFilter(mode)
        self._sync_control_states()
        self.filter_changed.emit(self._sort_mode, self._date_filter)

    def _on_from_date_changed(self, qd: QDate) -> None:
        if self._loading:
            return
        start_d = _from_qdate(qd)
        end_d = _from_qdate(self.to_date_edit.date())
        if start_d > end_d:
            end_d = start_d
            self.to_date_edit.blockSignals(True)
            self.to_date_edit.setDate(_to_qdate(end_d))
            self.to_date_edit.blockSignals(False)
        if self._date_filter.mode == TaskDateFilterMode.CUSTOM:
            self._date_filter = TaskDateFilter(
                TaskDateFilterMode.CUSTOM,
                start_date=start_d,
                end_date=end_d,
            )
            self.filter_changed.emit(self._sort_mode, self._date_filter)

    def _on_to_date_changed(self, qd: QDate) -> None:
        if self._loading:
            return
        start_d = _from_qdate(self.from_date_edit.date())
        end_d = _from_qdate(qd)
        if end_d < start_d:
            start_d = end_d
            self.from_date_edit.blockSignals(True)
            self.from_date_edit.setDate(_to_qdate(start_d))
            self.from_date_edit.blockSignals(False)
        if self._date_filter.mode == TaskDateFilterMode.CUSTOM:
            self._date_filter = TaskDateFilter(
                TaskDateFilterMode.CUSTOM,
                start_date=start_d,
                end_date=end_d,
            )
            self.filter_changed.emit(self._sort_mode, self._date_filter)

    def _on_reset_clicked(self) -> None:
        self._sort_mode = TaskSortMode.MANUAL
        self._date_filter = TaskDateFilter(TaskDateFilterMode.ANY)
        self._sync_control_states()
        self.filter_changed.emit(self._sort_mode, self._date_filter)
