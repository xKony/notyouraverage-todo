"""Activity Summary view with Day, Work Week, and Custom period navigation & daily strip."""

from datetime import date

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nyatodo.domain import (
    ActivitySummary,
    DayBreakdown,
    SummaryPeriod,
    SummaryPeriodKind,
    TaskStatus,
    TaskSummaryBreakdown,
    format_summary_period_label,
)
from nyatodo.ui.icons import create_calendar_icon, create_check_pixmap, create_chevron_icon
from nyatodo.ui.qt_helpers import clear_layout, set_qss_property
from nyatodo.ui.theme import (
    DARK_TOKENS,
    ColorTokens,
    format_hms,
    make_ui_font,
)


def _format_strip_duration(seconds: int, *, completed_count: int) -> str:
    if seconds <= 0:
        return "✓" if completed_count > 0 else "—"
    if seconds < 60:
        return "<1m"
    hours, rem = divmod(seconds, 3600)
    mins = rem // 60
    if hours == 0:
        return f"{mins}m"
    return f"{hours}h" if mins == 0 else f"{hours}h{mins:02d}"


class _DurationBar(QWidget):
    """Animated proportional pill bar scaled to max logged duration of the period."""

    def __init__(
        self,
        *,
        ratio: float,
        tokens: ColorTokens,
        animate: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._target = max(0.0, min(1.0, ratio))
        self._progress = 0.0 if animate else self._target
        self._tokens = tokens
        self.setFixedSize(78, 12)

        if animate and self._target > 0.0:
            anim = QVariantAnimation(self)
            anim.setStartValue(0.0)
            anim.setEndValue(self._target)
            anim.setDuration(380)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.valueChanged.connect(self._on_anim_val)
            anim.start()
            self._anim = anim

    def _on_anim_val(self, val: object) -> None:
        self._progress = float(val) if isinstance(val, (int, float)) else 0.0
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        y = (self.height() - 6.0) / 2.0
        painter.setBrush(QColor(self._tokens.bg_elevated))
        painter.drawRoundedRect(QRectF(0.0, y, float(self.width()), 6.0), 3.0, 3.0)

        if self._progress > 0.0:
            fill_w = max(6.0, float(self.width()) * self._progress)
            painter.setBrush(QColor(self._tokens.accent_primary))
            painter.drawRoundedRect(QRectF(0.0, y, fill_w, 6.0), 3.0, 3.0)
        painter.end()


class _VerticalStripBar(QWidget):
    """Vertical proportional activity bar for a single day in the Daily Strip."""

    def __init__(
        self,
        *,
        ratio: float,
        has_completion: bool,
        tokens: ColorTokens,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ratio = max(0.0, min(1.0, ratio))
        self._has_completion = has_completion
        self._tokens = tokens
        self.setFixedSize(10, 26)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        w = float(self.width())
        h = float(self.height())
        painter.setBrush(QColor(self._tokens.bg_elevated))
        painter.drawRoundedRect(QRectF(2.0, 0.0, w - 4.0, h), 3.0, 3.0)

        if self._ratio > 0.0:
            fill_h = max(4.0, h * self._ratio)
            painter.setBrush(QColor(self._tokens.accent_primary))
            painter.drawRoundedRect(QRectF(2.0, h - fill_h, w - 4.0, fill_h), 3.0, 3.0)
        elif self._has_completion:
            painter.setBrush(QColor(self._tokens.status_done))
            painter.drawEllipse(QRectF(3.0, h - 4.0, 4.0, 4.0))
        painter.end()


class _SummaryStatusDot(QWidget):
    """Semantic status dot or checkmark for Activity Summary breakdown rows."""

    def __init__(
        self,
        *,
        completed: bool,
        status: TaskStatus,
        tokens: ColorTokens,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._completed = completed
        self._status = status
        self._tokens = tokens
        self.setFixedSize(16, 16)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._completed or self._status == TaskStatus.DONE:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._tokens.status_done))
            painter.drawEllipse(QRectF(1.0, 1.0, 14.0, 14.0))
            check = create_check_pixmap(QColor("#FFFFFF"), 12)
            painter.drawPixmap(2, 2, check)
        else:
            color = (
                self._tokens.accent_primary
                if self._status == TaskStatus.DOING
                else self._tokens.text_muted
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(QRectF(4.0, 4.0, 8.0, 8.0))
        painter.end()


class ActivitySummaryView(QWidget):
    """Activity Summary supporting Day, Mon-Sun Work Week, Custom ranges, and daily drill-down."""

    period_changed = Signal(object)
    period_picker_requested = Signal()
    day_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tokens: ColorTokens = DARK_TOKENS
        self._summary: ActivitySummary | None = None
        self._today: date = date.today()
        self._last_period: SummaryPeriod | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addLayout(self._build_period_selector())
        root.addWidget(self._build_hero_panel())
        root.addWidget(self._build_daily_strip())
        self._build_breakdown_section(root)

        self.apply_theme(DARK_TOKENS)

    def _build_period_selector(self) -> QHBoxLayout:
        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(8)

        self.prev_period_button = QPushButton(self)
        self.prev_period_button.setObjectName("DayNavButton")
        self.prev_period_button.setFixedSize(28, 28)
        self.prev_period_button.setIconSize(QSize(14, 14))
        self.prev_period_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_period_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_period_button.clicked.connect(self.go_previous_period)
        self.prev_day_button = self.prev_period_button
        nav_row.addWidget(self.prev_period_button)

        self.period_button = QPushButton("Today", self)
        self.period_button.setObjectName("SummaryPeriodButton")
        self.period_button.setFixedHeight(28)
        self.period_button.setIconSize(QSize(14, 14))
        self.period_button.setFont(make_ui_font(12, QFont.Weight.DemiBold))
        self.period_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.period_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.period_button.setToolTip("Select Day, Work Week, or Custom range")
        self.period_button.clicked.connect(self.period_picker_requested.emit)
        nav_row.addWidget(self.period_button, 1)

        self.next_period_button = QPushButton(self)
        self.next_period_button.setObjectName("DayNavButton")
        self.next_period_button.setFixedSize(28, 28)
        self.next_period_button.setIconSize(QSize(14, 14))
        self.next_period_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_period_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_period_button.clicked.connect(self.go_next_period)
        self.next_day_button = self.next_period_button
        nav_row.addWidget(self.next_period_button)
        return nav_row

    def _make_metric_column(
        self,
        parent: QWidget,
        title: str,
        caption: str,
        *,
        secondary: bool = False,
    ) -> tuple[QVBoxLayout, QLabel]:
        col = QVBoxLayout()
        col.setSpacing(2)
        title_label = QLabel(title, parent)
        title_label.setObjectName("HeroMetricTitle")
        value_label = QLabel("00:00:00", parent)
        value_label.setObjectName("HeroMetricValue")
        if secondary:
            set_qss_property(value_label, "secondary", True)
            value_label.setFont(make_ui_font(22, QFont.Weight.ExtraLight, tracking_em=-0.01))
        else:
            value_label.setFont(make_ui_font(26, QFont.Weight.Bold, tracking_em=-0.03))
        caption_label = QLabel(caption, parent)
        caption_label.setObjectName("HeroMetricCaption")
        col.addWidget(title_label)
        col.addWidget(value_label)
        col.addWidget(caption_label)
        return col, value_label

    def _build_hero_panel(self) -> QFrame:
        self.hero_frame = QFrame(self)
        self.hero_frame.setObjectName("SummaryHero")
        hero_outer = QVBoxLayout(self.hero_frame)
        hero_outer.setContentsMargins(18, 14, 18, 14)
        hero_outer.setSpacing(10)

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(16)

        left_col, self.wall_clock_value = self._make_metric_column(
            self.hero_frame, "Active", "Wall-clock"
        )
        columns.addLayout(left_col, 1)

        v_divider = QFrame(self.hero_frame)
        v_divider.setObjectName("VerticalDivider")
        v_divider.setFrameShape(QFrame.Shape.VLine)
        columns.addWidget(v_divider)

        right_col, self.total_logged_value = self._make_metric_column(
            self.hero_frame, "Logged", "Sessions sum", secondary=True
        )
        columns.addLayout(right_col, 1)

        hero_outer.addLayout(columns)

        self.overlap_divider = QFrame(self.hero_frame)
        self.overlap_divider.setObjectName("SectionDivider")
        self.overlap_divider.setFrameShape(QFrame.Shape.HLine)
        hero_outer.addWidget(self.overlap_divider)

        self.overlap_caption = QLabel(self.hero_frame)
        self.overlap_caption.setObjectName("OverlapCaption")
        self.overlap_caption.setWordWrap(True)
        hero_outer.addWidget(self.overlap_caption)
        return self.hero_frame

    def _build_daily_strip(self) -> QFrame:
        self.daily_strip_frame = QFrame(self)
        self.daily_strip_frame.setObjectName("DailyStripFrame")
        self.daily_strip_frame.setVisible(False)
        self.daily_strip_layout = QHBoxLayout(self.daily_strip_frame)
        self.daily_strip_layout.setContentsMargins(8, 8, 8, 8)
        self.daily_strip_layout.setSpacing(4)
        return self.daily_strip_frame

    def _build_breakdown_section(self, root: QVBoxLayout) -> None:
        breakdown_header = QHBoxLayout()
        breakdown_header.setContentsMargins(4, 2, 4, 0)
        section_title = QLabel("Breakdown", self)
        section_title.setObjectName("SectionLabel")
        breakdown_header.addWidget(section_title)
        breakdown_header.addStretch(1)
        self.task_count_label = QLabel("0", self)
        self.task_count_label.setObjectName("SubStepCountLabel")
        self.task_count_label.setFont(make_ui_font(10, QFont.Weight.Medium))
        self.task_count_label.setFixedHeight(20)
        self.task_count_label.setMinimumWidth(24)
        self.task_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        breakdown_header.addWidget(self.task_count_label)
        root.addLayout(breakdown_header)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("SummaryScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_container.setObjectName("SummaryContainer")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 8)
        self.list_layout.setSpacing(6)
        self.scroll_area.setWidget(self.list_container)
        root.addWidget(self.scroll_area, 1)

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Refresh icon colors, daily strip, and breakdown rows for the active theme."""
        self._tokens = tokens
        nav_color = QColor(tokens.text_secondary)
        self.prev_period_button.setIcon(create_chevron_icon("left", nav_color, 14))
        self.next_period_button.setIcon(create_chevron_icon("right", nav_color, 14))
        self.period_button.setIcon(create_calendar_icon(nav_color, 14))
        if self._summary is not None:
            self.set_summary(self._summary, today=self._today)

    def current_period(self) -> SummaryPeriod:
        """Return currently displayed SummaryPeriod."""
        if self._summary is not None:
            return self._summary.period
        return SummaryPeriod.day(self._today)

    def current_day(self) -> date:
        """Return start date of currently displayed period."""
        return self.current_period().start_date

    def go_previous_period(self) -> None:
        """Navigate backward by one period."""
        target = self.current_period().step(-1, today=self._today)
        if target is not None:
            self.period_changed.emit(target)
            self.day_changed.emit(target.start_date)

    def go_next_period(self) -> None:
        """Navigate forward by one period if permitted by today."""
        target = self.current_period().step(1, today=self._today)
        if target is not None:
            self.period_changed.emit(target)
            self.day_changed.emit(target.start_date)

    go_previous_day = go_previous_period
    go_next_day = go_next_period

    def set_summary(self, summary: ActivitySummary, *, today: date) -> None:
        """Populate Activity Summary hero metrics, daily strip, and per-Task breakdown rows."""
        period_changed = self._last_period != summary.period
        self._last_period = summary.period
        self._summary = summary
        self._today = today

        self.period_button.setText(format_summary_period_label(summary.period, today=today))
        self.next_period_button.setEnabled(summary.period.can_step_next(today))

        self.wall_clock_value.setText(format_hms(summary.wall_clock_seconds))
        self.total_logged_value.setText(format_hms(summary.total_logged_seconds))

        has_overlap = summary.overlap_seconds > 0
        self.overlap_divider.setVisible(has_overlap)
        self.overlap_caption.setVisible(has_overlap)
        if has_overlap:
            overlap_str = format_hms(summary.overlap_seconds)
            self.overlap_caption.setText(f"+{overlap_str} concurrent")

        self._rebuild_daily_strip(summary.period, summary.daily_breakdown, today=today)
        count = len(summary.tasks)
        self.task_count_label.setText(f"{count}")
        self._rebuild_rows(summary.tasks, animate=period_changed)

    def _rebuild_daily_strip(
        self,
        period: SummaryPeriod,
        items: tuple[DayBreakdown, ...],
        *,
        today: date,
    ) -> None:
        clear_layout(self.daily_strip_layout)
        if not items:
            self.daily_strip_frame.setVisible(False)
            return

        self.daily_strip_frame.setVisible(True)
        max_secs = max(
            (max(d.wall_clock_seconds, d.total_logged_seconds) for d in items), default=0
        )
        compact_custom = period.kind == SummaryPeriodKind.CUSTOM and len(items) > 7

        for day_item in items:
            btn = QPushButton(self.daily_strip_frame)
            btn.setObjectName("DailyStripDay")
            btn.setProperty("day_iso", day_item.day.isoformat())
            set_qss_property(btn, "today", day_item.day == today)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(64)

            active_secs = day_item.wall_clock_seconds
            tooltip = (
                f"{day_item.day.strftime('%a, %b')} {day_item.day.day}, {day_item.day.year}"
                f" · Active {format_hms(active_secs)}"
            )
            if day_item.completed_count > 0:
                tooltip += f" · {day_item.completed_count} done"
            btn.setToolTip(tooltip)

            col = QVBoxLayout(btn)
            col.setContentsMargins(2, 4, 2, 4)
            col.setSpacing(3)
            col.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if period.kind == SummaryPeriodKind.WEEK:
                top_text = day_item.day.strftime("%a")
            elif compact_custom:
                top_text = f"{day_item.day.month}/{day_item.day.day}"
            else:
                top_text = f"{day_item.day.strftime('%b')} {day_item.day.day}"

            top_lbl = QLabel(top_text, btn)
            top_lbl.setObjectName("DailyStripDayLabel")
            top_lbl.setFont(make_ui_font(9 if compact_custom else 10, QFont.Weight.DemiBold))
            top_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            top_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            col.addWidget(top_lbl)

            ratio = (active_secs / max_secs) if max_secs > 0 and active_secs > 0 else 0.0
            bar = _VerticalStripBar(
                ratio=ratio,
                has_completion=day_item.completed_count > 0,
                tokens=self._tokens,
                parent=btn,
            )
            col.addWidget(bar, 0, Qt.AlignmentFlag.AlignHCenter)

            dur_text = _format_strip_duration(active_secs, completed_count=day_item.completed_count)
            dur_lbl = QLabel(dur_text, btn)
            dur_lbl.setObjectName("DailyStripDurationLabel")
            dur_lbl.setFont(make_ui_font(9 if compact_custom else 10, QFont.Weight.Medium))
            dur_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dur_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            col.addWidget(dur_lbl)

            target_day = day_item.day
            btn.clicked.connect(lambda _checked=False, d=target_day: self._drill_down_day(d))
            self.daily_strip_layout.addWidget(btn, 1)
            btn.show()

    def _drill_down_day(self, day: date) -> None:
        self.period_changed.emit(SummaryPeriod.day(day))
        self.day_changed.emit(day)

    def _rebuild_rows(self, items: tuple[TaskSummaryBreakdown, ...], *, animate: bool) -> None:
        clear_layout(self.list_layout)

        if not items:
            empty = QLabel("—", self.list_container)
            empty.setObjectName("EmptyStateHint")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setContentsMargins(0, 32, 0, 32)
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch(1)
            return

        max_logged = max((item.logged_seconds for item in items), default=1)
        max_logged = max(max_logged, 1)

        for item in items:
            row = QFrame(self.list_container)
            row.setObjectName("SummaryBreakdownRow")
            row.setFixedHeight(40)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 0, 12, 0)
            row_layout.setSpacing(10)

            dot = _SummaryStatusDot(
                completed=item.completed_in_period,
                status=item.status,
                tokens=self._tokens,
                parent=row,
            )
            row_layout.addWidget(dot)

            title_label = QLabel(row)
            title_label.setObjectName("TaskTitleLabel")
            title_font = make_ui_font(
                12, QFont.Weight.Medium if item.logged_seconds > 0 else QFont.Weight.Light
            )
            title_label.setFont(title_font)
            metrics = QFontMetrics(title_font)
            title_label.setText(metrics.elidedText(item.title, Qt.TextElideMode.ElideRight, 200))
            row_layout.addWidget(title_label, 1)

            if item.requester:
                pill = QLabel(f"@{item.requester}", row)
                pill.setObjectName("RequesterPill")
                pill.setFont(make_ui_font(10, QFont.Weight.Medium))
                pill.setFixedHeight(20)
                pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row_layout.addWidget(pill)

            bar = _DurationBar(
                ratio=item.logged_seconds / max_logged if item.logged_seconds > 0 else 0.0,
                tokens=self._tokens,
                animate=animate,
                parent=row,
            )
            row_layout.addWidget(bar)

            dur_text = format_hms(item.logged_seconds) if item.logged_seconds > 0 else "✓"
            dur_label = QLabel(dur_text, row)
            dur_label.setObjectName("SummaryDurationLabel")
            dur_label.setFont(make_ui_font(11, QFont.Weight.DemiBold))
            dur_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            dur_label.setMinimumWidth(58)
            row_layout.addWidget(dur_label)

            self.list_layout.addWidget(row)

        self.list_layout.addStretch(1)


DailySummaryView = ActivitySummaryView
