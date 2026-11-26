"""Animated centered Activity Summary Period Picker modal."""

from datetime import date, timedelta

from PySide6.QtCore import QDate, QEasingCurve, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nyatodo.domain import SummaryPeriod, SummaryPeriodKind, format_week_range_short
from nyatodo.ui.icons import create_close_icon
from nyatodo.ui.qt_helpers import set_qss_property
from nyatodo.ui.theme import DARK_TOKENS, ColorTokens, make_ui_font


def _to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _from_qdate(qd: QDate) -> date:
    return date(qd.year(), qd.month(), qd.day())


class SummaryPeriodModal(QWidget):
    """Animated centered overlay modal for picking Day, Work Week, or Custom period."""

    period_selected = Signal(object)
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModalScrim")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setVisible(False)

        self._tokens: ColorTokens = DARK_TOKENS
        self._today: date = date.today()
        self._mode: SummaryPeriodKind = SummaryPeriodKind.DAY
        self._loading = False
        self._closing = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.modal_card = self._build_modal_card()
        outer.addWidget(self.modal_card)

        self._card_anim = QPropertyAnimation(self.modal_card, b"maximumHeight", self)
        self._card_anim.setDuration(160)
        self._card_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._card_anim.finished.connect(self._on_anim_finished)

        self.apply_theme(DARK_TOKENS)

    def _build_modal_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("SummaryPeriodModal")
        card.setFixedWidth(360)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addLayout(self._build_header(card))
        layout.addWidget(self._make_divider(card))
        layout.addLayout(self._build_presets_section(card))
        layout.addWidget(self._make_divider(card))
        layout.addLayout(self._build_mode_section(card))
        layout.addWidget(self._build_date_controls(card))
        layout.addWidget(self._make_divider(card))
        layout.addLayout(self._build_footer(card))
        return card

    def _build_header(self, card: QFrame) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 2)
        title = QLabel("Activity Period", card)
        title.setObjectName("SettingsTitle")
        title.setFont(make_ui_font(14, QFont.Weight.DemiBold))
        header.addWidget(title)
        header.addStretch(1)

        self.close_button = QPushButton(card)
        self.close_button.setObjectName("SettingsButton")
        self.close_button.setFixedSize(26, 26)
        self.close_button.setIconSize(QSize(12, 12))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_modal)
        header.addWidget(self.close_button)
        return header

    def _build_presets_section(self, card: QFrame) -> QVBoxLayout:
        section = QVBoxLayout()
        section.setContentsMargins(0, 0, 0, 0)
        section.setSpacing(6)

        label = QLabel("Quick Select", card)
        label.setObjectName("FilterSectionLabel")
        label.setFont(make_ui_font(11, QFont.Weight.DemiBold))
        section.addWidget(label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.preset_buttons: dict[str, QPushButton] = {}
        for text in ("Today", "Yesterday", "This Week", "Last Week"):
            btn = QPushButton(text, card)
            btn.setObjectName("FilterChipButton")
            btn.setFixedHeight(25)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, name=text: self._apply_preset(name))
            self.preset_buttons[text] = btn
            row.addWidget(btn)
        row.addStretch(1)
        section.addLayout(row)
        return section

    def _build_mode_section(self, card: QFrame) -> QVBoxLayout:
        section = QVBoxLayout()
        section.setContentsMargins(0, 0, 0, 0)
        section.setSpacing(6)

        label = QLabel("Period Mode", card)
        label.setObjectName("FilterSectionLabel")
        label.setFont(make_ui_font(11, QFont.Weight.DemiBold))
        section.addWidget(label)

        track = QFrame(card)
        track.setObjectName("SettingsSegmentTrack")
        track.setFixedHeight(28)
        track_layout = QHBoxLayout(track)
        track_layout.setContentsMargins(3, 3, 3, 3)
        track_layout.setSpacing(2)

        self._mode_buttons: dict[SummaryPeriodKind, QPushButton] = {}
        for kind, title in (
            (SummaryPeriodKind.DAY, "Day"),
            (SummaryPeriodKind.WEEK, "Work Week"),
            (SummaryPeriodKind.CUSTOM, "Custom"),
        ):
            btn = QPushButton(title, track)
            btn.setObjectName("SettingsSegmentOption")
            btn.setFixedHeight(22)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, k=kind: self._select_mode(k))
            self._mode_buttons[kind] = btn
            track_layout.addWidget(btn)
        section.addWidget(track)
        return section

    def _build_date_controls(self, card: QFrame) -> QWidget:
        host = QWidget(card)
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(6)

        self.single_date_row = QWidget(host)
        single_layout = QHBoxLayout(self.single_date_row)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.setSpacing(8)

        self.single_date_label = QLabel("Date", self.single_date_row)
        self.single_date_label.setObjectName("FilterFieldLabel")
        single_layout.addWidget(self.single_date_label)

        self.single_date_edit = QDateEdit(self.single_date_row)
        self.single_date_edit.setObjectName("DatePickerEdit")
        self.single_date_edit.setCalendarPopup(True)
        self.single_date_edit.setDisplayFormat("MMM d, yyyy")
        self.single_date_edit.setFixedHeight(28)
        self.single_date_edit.dateChanged.connect(self._update_week_preview)
        single_layout.addWidget(self.single_date_edit, 1)

        self.week_preview_label = QLabel("", host)
        self.week_preview_label.setObjectName("FilterFieldLabel")
        self.week_preview_label.setVisible(False)

        self.custom_range_row = QWidget(host)
        custom_layout = QHBoxLayout(self.custom_range_row)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(6)

        from_lbl = QLabel("From", self.custom_range_row)
        from_lbl.setObjectName("FilterFieldLabel")
        custom_layout.addWidget(from_lbl)

        self.from_date_edit = QDateEdit(self.custom_range_row)
        self.from_date_edit.setObjectName("DatePickerEdit")
        self.from_date_edit.setCalendarPopup(True)
        self.from_date_edit.setDisplayFormat("MMM d, yyyy")
        self.from_date_edit.setFixedHeight(28)
        self.from_date_edit.dateChanged.connect(self._on_from_date_changed)
        custom_layout.addWidget(self.from_date_edit, 1)

        to_lbl = QLabel("To", self.custom_range_row)
        to_lbl.setObjectName("FilterFieldLabel")
        custom_layout.addWidget(to_lbl)

        self.to_date_edit = QDateEdit(self.custom_range_row)
        self.to_date_edit.setObjectName("DatePickerEdit")
        self.to_date_edit.setCalendarPopup(True)
        self.to_date_edit.setDisplayFormat("MMM d, yyyy")
        self.to_date_edit.setFixedHeight(28)
        self.to_date_edit.dateChanged.connect(self._on_to_date_changed)
        custom_layout.addWidget(self.to_date_edit, 1)

        host_layout.addWidget(self.single_date_row)
        host_layout.addWidget(self.week_preview_label)
        host_layout.addWidget(self.custom_range_row)
        return host

    def _build_footer(self, card: QFrame) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        footer.setSpacing(8)
        footer.addStretch(1)

        self.cancel_button = QPushButton("Cancel", card)
        self.cancel_button.setObjectName("ModalSecondaryButton")
        self.cancel_button.setFixedHeight(28)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.close_modal)
        footer.addWidget(self.cancel_button)

        self.apply_button = QPushButton("Apply", card)
        self.apply_button.setObjectName("SettingsDoneButton")
        self.apply_button.setFixedHeight(28)
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        footer.addWidget(self.apply_button)
        return footer

    def _make_divider(self, card: QFrame) -> QFrame:
        line = QFrame(card)
        line.setObjectName("SectionDivider")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Refresh icon colors for active theme."""
        self._tokens = tokens
        self.close_button.setIcon(create_close_icon(QColor(tokens.text_secondary), 12))

    def open_with_period(self, period: SummaryPeriod, *, today: date) -> None:
        """Populate modal controls from period and animate card reveal."""
        self._loading = True
        try:
            self._today = today
            self._mode = period.kind
            max_qdate = _to_qdate(today)
            self.single_date_edit.setMaximumDate(max_qdate)
            self.from_date_edit.setMaximumDate(max_qdate)
            self.to_date_edit.setMaximumDate(max_qdate)

            ref_date = min(period.start_date, today)
            self.single_date_edit.setDate(_to_qdate(ref_date))
            self.from_date_edit.setDate(_to_qdate(min(period.start_date, today)))
            self.to_date_edit.setDate(_to_qdate(min(period.end_date, today)))
            self._sync_mode_ui()
            self._update_preset_highlights(period)
        finally:
            self._loading = False

        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

        self._card_anim.stop()
        self._closing = False
        self.modal_card.setMaximumHeight(16777215)
        if (card_layout := self.modal_card.layout()) is not None:
            card_layout.activate()
        target_height = max(200, self.modal_card.sizeHint().height())
        self.modal_card.setMaximumHeight(0)
        self.setVisible(True)
        self.raise_()
        self.apply_button.setFocus(Qt.FocusReason.PopupFocusReason)

        self._card_anim.setStartValue(0)
        self._card_anim.setEndValue(target_height)
        self._card_anim.start()

    def close_modal(self) -> None:
        """Animate modal card closed and hide scrim."""
        if not self.isVisible():
            self._card_anim.stop()
            self._closing = False
            self.modal_card.setMaximumHeight(16777215)
            return
        if self._closing:
            return
        self._card_anim.stop()
        self._closing = True
        start_height = max(self.modal_card.height(), 1)
        self._card_anim.setStartValue(start_height)
        self._card_anim.setEndValue(0)
        self._card_anim.start()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_modal()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if QApplication.activePopupWidget() is not None:
            super().mousePressEvent(event)
            return
        if not self.modal_card.geometry().contains(event.pos()):
            self.close_modal()
            event.accept()
            return
        super().mousePressEvent(event)

    def _on_anim_finished(self) -> None:
        if self._closing:
            self._closing = False
            self.setVisible(False)
            self.modal_card.setMaximumHeight(16777215)
            self.closed.emit()
            return
        self.modal_card.setMaximumHeight(16777215)

    def _select_mode(self, mode: SummaryPeriodKind) -> None:
        self._mode = mode
        self._sync_mode_ui()

    def _sync_mode_ui(self) -> None:
        for kind, btn in self._mode_buttons.items():
            set_qss_property(btn, "active", kind == self._mode)
        is_custom = self._mode == SummaryPeriodKind.CUSTOM
        self.single_date_row.setVisible(not is_custom)
        self.custom_range_row.setVisible(is_custom)
        self.single_date_label.setText(
            "Week of" if self._mode == SummaryPeriodKind.WEEK else "Date"
        )
        self.week_preview_label.setVisible(self._mode == SummaryPeriodKind.WEEK)
        self._update_week_preview()
        if self.isVisible() and not self._closing:
            self.modal_card.setMaximumHeight(16777215)
            self.modal_card.adjustSize()

    def _update_week_preview(self) -> None:
        if self._mode != SummaryPeriodKind.WEEK:
            return
        ref = _from_qdate(self.single_date_edit.date())
        week = SummaryPeriod.work_week(ref)
        span = format_week_range_short(week.start_date, week.end_date, today_year=self._today.year)
        self.week_preview_label.setText(f"Mon\u2013Sun: {span}")

    def _update_preset_highlights(self, period: SummaryPeriod) -> None:
        presets = {
            "Today": SummaryPeriod.day(self._today),
            "Yesterday": SummaryPeriod.day(self._today - timedelta(days=1)),
            "This Week": SummaryPeriod.work_week(self._today),
            "Last Week": SummaryPeriod.work_week(self._today - timedelta(days=7)),
        }
        for name, btn in self.preset_buttons.items():
            set_qss_property(btn, "active", period == presets[name])

    def _on_from_date_changed(self, qd: QDate) -> None:
        if self._loading:
            return
        start_d = _from_qdate(qd)
        end_d = _from_qdate(self.to_date_edit.date())
        if start_d > end_d:
            self.to_date_edit.blockSignals(True)
            self.to_date_edit.setDate(_to_qdate(start_d))
            self.to_date_edit.blockSignals(False)

    def _on_to_date_changed(self, qd: QDate) -> None:
        if self._loading:
            return
        start_d = _from_qdate(self.from_date_edit.date())
        end_d = _from_qdate(qd)
        if end_d < start_d:
            self.from_date_edit.blockSignals(True)
            self.from_date_edit.setDate(_to_qdate(end_d))
            self.from_date_edit.blockSignals(False)

    def _apply_preset(self, preset_name: str) -> None:
        if preset_name == "Today":
            period = SummaryPeriod.day(self._today)
        elif preset_name == "Yesterday":
            period = SummaryPeriod.day(self._today - timedelta(days=1))
        elif preset_name == "This Week":
            period = SummaryPeriod.work_week(self._today)
        else:
            period = SummaryPeriod.work_week(self._today - timedelta(days=7))
        self.period_selected.emit(period)
        self.close_modal()

    def _on_apply_clicked(self) -> None:
        if self._mode == SummaryPeriodKind.DAY:
            period = SummaryPeriod.day(_from_qdate(self.single_date_edit.date()))
        elif self._mode == SummaryPeriodKind.WEEK:
            period = SummaryPeriod.work_week(_from_qdate(self.single_date_edit.date()))
        else:
            start_d = _from_qdate(self.from_date_edit.date())
            end_d = _from_qdate(self.to_date_edit.date())
            if start_d > end_d:
                end_d = start_d
            period = SummaryPeriod.custom(start_d, end_d)
        self.period_selected.emit(period)
        self.close_modal()
