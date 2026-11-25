"""Daily Summary view showing Wall-Clock Active vs Total Logged and per-Task breakdown."""

from datetime import date, timedelta

from PySide6.QtCore import QRectF, QSize, Qt, Signal
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

from nyatodo.domain import DailySummary, TaskDayBreakdown, TaskStatus
from nyatodo.ui.icons import create_check_pixmap, create_chevron_icon
from nyatodo.ui.qt_helpers import clear_layout
from nyatodo.ui.theme import (
    DARK_TOKENS,
    ColorTokens,
    format_hms,
    make_ui_font,
)


class _DurationBar(QWidget):
    """Compact 4px horizontal proportional bar scaled to max logged duration of the day."""

    def __init__(
        self,
        *,
        ratio: float,
        tokens: ColorTokens,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ratio = max(0.0, min(1.0, ratio))
        self._tokens = tokens
        self.setFixedSize(64, 12)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        y = (self.height() - 4.0) / 2.0
        painter.setBrush(QColor(self._tokens.bg_surface))
        painter.drawRoundedRect(QRectF(0.0, y, float(self.width()), 4.0), 2.0, 2.0)

        if self._ratio > 0.0:
            fill_w = max(4.0, float(self.width()) * self._ratio)
            painter.setBrush(QColor(self._tokens.accent_primary))
            painter.drawRoundedRect(QRectF(0.0, y, fill_w, 4.0), 2.0, 2.0)
        painter.end()


class _SummaryStatusDot(QWidget):
    """Semantic status dot or checkmark for Daily Summary breakdown rows."""

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


class DailySummaryView(QWidget):
    """Surface 4: Chronological Daily Summary with merged Wall-Clock Active math."""

    day_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tokens: ColorTokens = DARK_TOKENS
        self._summary: DailySummary | None = None
        self._today: date = date.today()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addLayout(self._build_day_selector())
        root.addWidget(self._build_hero_panel())
        self._build_breakdown_section(root)

        self.apply_theme(DARK_TOKENS)

    def _build_day_selector(self) -> QHBoxLayout:
        day_row = QHBoxLayout()
        day_row.setContentsMargins(0, 0, 0, 0)
        day_row.setSpacing(8)

        self.prev_day_button = QPushButton(self)
        self.prev_day_button.setObjectName("DayNavButton")
        self.prev_day_button.setFixedSize(28, 28)
        self.prev_day_button.setIconSize(QSize(14, 14))
        self.prev_day_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_day_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_day_button.clicked.connect(self.go_previous_day)
        day_row.addWidget(self.prev_day_button)

        self.day_title_label = QLabel("Today", self)
        self.day_title_label.setObjectName("DayTitleLabel")
        self.day_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.day_title_label.setFont(make_ui_font(13, QFont.Weight.DemiBold))
        day_row.addWidget(self.day_title_label, 1)

        self.next_day_button = QPushButton(self)
        self.next_day_button.setObjectName("DayNavButton")
        self.next_day_button.setFixedSize(28, 28)
        self.next_day_button.setIconSize(QSize(14, 14))
        self.next_day_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_day_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_day_button.clicked.connect(self.go_next_day)
        day_row.addWidget(self.next_day_button)
        return day_row

    def _make_metric_column(
        self,
        parent: QWidget,
        title: str,
        caption: str,
    ) -> tuple[QVBoxLayout, QLabel]:
        col = QVBoxLayout()
        col.setSpacing(2)
        title_label = QLabel(title, parent)
        title_label.setObjectName("HeroMetricTitle")
        value_label = QLabel("00:00:00", parent)
        value_label.setObjectName("HeroMetricValue")
        value_label.setFont(make_ui_font(22, QFont.Weight.DemiBold))
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
        hero_outer.setContentsMargins(16, 12, 16, 12)
        hero_outer.setSpacing(10)

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(16)

        left_col, self.wall_clock_value = self._make_metric_column(
            self.hero_frame, "Wall-Clock Active", "Time with >=1 timer running"
        )
        columns.addLayout(left_col, 1)

        v_divider = QFrame(self.hero_frame)
        v_divider.setObjectName("VerticalDivider")
        v_divider.setFrameShape(QFrame.Shape.VLine)
        columns.addWidget(v_divider)

        right_col, self.total_logged_value = self._make_metric_column(
            self.hero_frame, "Total Logged", "Sum of Work Sessions"
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

    def _build_breakdown_section(self, root: QVBoxLayout) -> None:
        breakdown_header = QHBoxLayout()
        breakdown_header.setContentsMargins(0, 4, 0, 0)
        section_title = QLabel("Tasks Worked & Completed", self)
        section_title.setObjectName("SectionLabel")
        breakdown_header.addWidget(section_title)
        breakdown_header.addStretch(1)
        self.task_count_label = QLabel("0 tasks", self)
        self.task_count_label.setObjectName("SubStepCountLabel")
        self.task_count_label.setFont(make_ui_font(11, QFont.Weight.Medium))
        breakdown_header.addWidget(self.task_count_label)
        root.addLayout(breakdown_header)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("SummaryScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_container.setObjectName("SummaryContainer")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.scroll_area.setWidget(self.list_container)
        root.addWidget(self.scroll_area, 1)

    def apply_theme(self, tokens: ColorTokens) -> None:
        """Refresh icon colors and breakdown rows for the active theme."""
        self._tokens = tokens
        nav_color = QColor(tokens.text_secondary)
        self.prev_day_button.setIcon(create_chevron_icon("left", nav_color, 14))
        self.next_day_button.setIcon(create_chevron_icon("right", nav_color, 14))
        if self._summary is not None:
            self.set_summary(self._summary, today=self._today)

    def current_day(self) -> date:
        """Return currently displayed summary date."""
        return self._summary.day if self._summary is not None else self._today

    def go_previous_day(self) -> None:
        """Navigate to the previous calendar day."""
        self.day_changed.emit(self.current_day() - timedelta(days=1))

    def go_next_day(self) -> None:
        """Navigate to the next calendar day if not already on today."""
        current = self.current_day()
        if current < self._today:
            self.day_changed.emit(current + timedelta(days=1))

    def set_summary(self, summary: DailySummary, *, today: date) -> None:
        """Populate Daily Summary hero metrics and per-Task breakdown rows."""
        self._summary = summary
        self._today = today

        self.day_title_label.setText(self._format_day_title(summary.day, today))
        self.next_day_button.setEnabled(summary.day < today)

        self.wall_clock_value.setText(format_hms(summary.wall_clock_seconds))
        self.total_logged_value.setText(format_hms(summary.total_logged_seconds))

        has_overlap = summary.overlap_seconds > 0
        self.overlap_divider.setVisible(has_overlap)
        self.overlap_caption.setVisible(has_overlap)
        if has_overlap:
            overlap_str = format_hms(summary.overlap_seconds)
            self.overlap_caption.setText(
                f"Includes {overlap_str} of concurrent Task Timers across overlapping sessions."
            )

        count = len(summary.tasks)
        self.task_count_label.setText(f"{count} task" if count == 1 else f"{count} tasks")
        self._rebuild_rows(summary.tasks)

    def _rebuild_rows(self, items: tuple[TaskDayBreakdown, ...]) -> None:
        clear_layout(self.list_layout)

        if not items:
            empty = QLabel("No Work Sessions or completed Tasks for this day.", self.list_container)
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
            row.setFixedHeight(36)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 0, 8, 0)
            row_layout.setSpacing(8)

            dot = _SummaryStatusDot(
                completed=item.completed_on_day,
                status=item.status,
                tokens=self._tokens,
                parent=row,
            )
            row_layout.addWidget(dot)

            title_label = QLabel(row)
            title_label.setObjectName("TaskTitleLabel")
            title_font = make_ui_font(12, QFont.Weight.Medium)
            title_label.setFont(title_font)
            metrics = QFontMetrics(title_font)
            title_label.setText(metrics.elidedText(item.title, Qt.TextElideMode.ElideRight, 220))
            row_layout.addWidget(title_label, 1)

            if item.requester:
                pill = QLabel(f"@{item.requester}", row)
                pill.setObjectName("RequesterPill")
                pill.setFont(make_ui_font(11, QFont.Weight.Medium))
                pill.setFixedHeight(20)
                pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row_layout.addWidget(pill)

            bar = _DurationBar(
                ratio=item.logged_seconds / max_logged if item.logged_seconds > 0 else 0.0,
                tokens=self._tokens,
                parent=row,
            )
            row_layout.addWidget(bar)

            dur_text = format_hms(item.logged_seconds) if item.logged_seconds > 0 else "Done"
            dur_label = QLabel(dur_text, row)
            dur_label.setObjectName("SummaryDurationLabel")
            dur_label.setFont(make_ui_font(12, QFont.Weight.DemiBold))
            dur_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            dur_label.setMinimumWidth(68)
            row_layout.addWidget(dur_label)

            self.list_layout.addWidget(row)

        self.list_layout.addStretch(1)

    @staticmethod
    def _format_day_title(day: date, today: date) -> str:
        formatted = day.strftime("%a, %b %d").replace(" 0", " ")
        if day == today:
            return f"Today · {formatted}"
        if day == today - timedelta(days=1):
            return f"Yesterday · {formatted}"
        return day.strftime("%a, %b %d, %Y").replace(" 0", " ")
