"""Main frameless spotlight window, Segmented Tabs, Smart Dual Focus, and Win32 hotkey filter."""

import sys
from collections.abc import Callable
from datetime import UTC, date, datetime
from enum import StrEnum

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nyatodo.domain import Settings, Task, TaskStatus
from nyatodo.parser import is_search_input
from nyatodo.platform_win32 import WM_HOTKEY, PlatformBridge
from nyatodo.service import TodoService
from nyatodo.ui.hints_footer import HintContext, HintsFooter
from nyatodo.ui.icons import (
    create_cat_monogram_pixmap,
    create_check_pixmap,
    create_gear_icon,
)
from nyatodo.ui.idle_banner import IdleBanner
from nyatodo.ui.quick_bar import QuickBar
from nyatodo.ui.settings_dialog import SettingsOverlay
from nyatodo.ui.summary_view import DailySummaryView
from nyatodo.ui.task_row import TaskRowWidget
from nyatodo.ui.theme import (
    DARK_TOKENS,
    ColorTokens,
    build_stylesheet,
    format_hms,
    make_mono_font,
    make_ui_font,
    resolve_theme,
    shadow_qcolor,
)
from nyatodo.ui.thinking_space import ThinkingSpaceWidget


class ViewTab(StrEnum):
    """Top-level segmented tabs."""

    ACTIVE = "active"
    WAITING = "waiting"
    SUMMARY = "summary"


class HotkeyEventFilter(QAbstractNativeEventFilter):
    """Qt native event filter listening for Win32 WM_HOTKEY messages."""

    def __init__(self, *, hotkey_id: int, on_triggered: Callable[[], None]) -> None:
        super().__init__()
        self._hotkey_id = hotkey_id
        self._on_triggered = on_triggered

    def nativeEventFilter(
        self,
        eventType: QByteArray | bytes | bytearray | memoryview,
        message: int,
    ) -> object:
        if sys.platform != "win32":
            return False, 0
        raw_type = eventType.data() if isinstance(eventType, QByteArray) else bytes(eventType)
        if raw_type != b"windows_generic_msg":
            return False, 0
        try:
            from ctypes.wintypes import MSG

            msg = MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and int(msg.wParam) == self._hotkey_id:
                self._on_triggered()
                return True, 0
        except (ValueError, TypeError, OSError):
            return False, 0
        return False, 0


class _RunningTimerPill(QFrame):
    """Clickable header pill displaying active Task Timer count and readout."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("RunningTimerPill")
        self.setFixedHeight(24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class _TaskListFocusSurface(QScrollArea):
    """Scrollable Task List surface handling keyboard navigation and task shortcuts."""

    key_command = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TaskListScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self.key_command.emit(event)
        if event.isAccepted():
            return
        super().keyPressEvent(event)


class MainWindow(QWidget):
    """Compact always-on-top frameless spotlight window for nyatodo."""

    state_changed = Signal()
    settings_updated = Signal(object)

    def __init__(
        self,
        service: TodoService,
        *,
        platform: PlatformBridge | None = None,
        clock: Callable[[], datetime] | None = None,
        hotkey_id: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._platform = platform
        self._clock = clock or (lambda: datetime.now(UTC))
        self._hotkey_id = hotkey_id

        self._tokens: ColorTokens = DARK_TOKENS
        self._current_tab = ViewTab.ACTIVE
        self._selected_task_id: str | None = None
        self._expanded_task_id: str | None = None
        self._summary_day: date = self._clock().astimezone().date()
        self._row_widgets: dict[str, TaskRowWidget] = {}
        self._thinking_widget: ThinkingSpaceWidget | None = None
        self._idle_dismissed_for_gap = False
        self._drag_offset: QPoint | None = None

        self.setWindowTitle("nyatodo")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(540, 660)
        self.setMinimumSize(460, 520)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)

        self.shell = QFrame(self)
        self.shell.setObjectName("SpotlightShell")
        self._shadow_effect = QGraphicsDropShadowEffect(self.shell)
        self._shadow_effect.setBlurRadius(28.0)
        self._shadow_effect.setOffset(0.0, 8.0)
        self.shell.setGraphicsEffect(self._shadow_effect)
        outer_layout.addWidget(self.shell)

        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        content_host = QWidget(self.shell)
        content_layout = QVBoxLayout(content_host)
        content_layout.setContentsMargins(16, 8, 16, 8)
        content_layout.setSpacing(8)

        # Surface 1: Header (44px)
        self.header_bar = QFrame(content_host)
        self.header_bar.setObjectName("HeaderBar")
        self.header_bar.setFixedHeight(36)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.brand_icon_label = QLabel(self.header_bar)
        self.brand_icon_label.setFixedSize(18, 18)
        header_layout.addWidget(self.brand_icon_label)

        self.brand_wordmark = QLabel("nyatodo", self.header_bar)
        self.brand_wordmark.setObjectName("BrandWordmark")
        brand_font = make_ui_font(13)
        brand_font.setWeight(brand_font.Weight.DemiBold)
        self.brand_wordmark.setFont(brand_font)
        header_layout.addWidget(self.brand_wordmark)

        header_layout.addStretch(1)

        self.running_timer_pill = _RunningTimerPill(self.header_bar)
        self.running_timer_pill.setVisible(False)
        pill_layout = QHBoxLayout(self.running_timer_pill)
        pill_layout.setContentsMargins(10, 0, 10, 0)
        pill_layout.setSpacing(6)
        self.running_pill_dot = QFrame(self.running_timer_pill)
        self.running_pill_dot.setFixedSize(6, 6)
        pill_layout.addWidget(self.running_pill_dot)
        self.running_pill_text = QLabel("00:00:00", self.running_timer_pill)
        self.running_pill_text.setObjectName("RunningTimerPillText")
        self.running_pill_text.setFont(make_mono_font(11))
        pill_layout.addWidget(self.running_pill_text)
        self.running_timer_pill.clicked.connect(self._jump_to_running_task)
        header_layout.addWidget(self.running_timer_pill)

        self.settings_button = QPushButton(self.header_bar)
        self.settings_button.setObjectName("SettingsButton")
        self.settings_button.setFixedSize(28, 28)
        self.settings_button.setIconSize(QSize(16, 16))
        self.settings_button.setToolTip("Settings (Ctrl+,)")
        self.settings_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.clicked.connect(self.open_settings)
        header_layout.addWidget(self.settings_button)

        content_layout.addWidget(self.header_bar)

        # Quick Bar
        self.quick_bar = QuickBar(content_host)
        self.quick_bar.query_changed.connect(self._on_quick_query_changed)
        self.quick_bar.task_submitted.connect(self._on_quick_task_submitted)
        self.quick_bar.jump_to_list_requested.connect(self._focus_task_list)
        self.quick_bar.escape_pressed.connect(self._handle_escape)
        self.quick_bar.focus_changed.connect(self._on_quick_bar_focus_changed)
        content_layout.addWidget(self.quick_bar)

        # Idle Check Banner (non-modal)
        self.idle_banner = IdleBanner(content_host)
        self.idle_banner.keep_requested.connect(self._on_idle_keep)
        self.idle_banner.trim_requested.connect(self._on_idle_trim)
        content_layout.addWidget(self.idle_banner)

        # Surface 2: Segmented Tabs (32px)
        self.tabs_frame = QFrame(content_host)
        self.tabs_frame.setObjectName("SegmentedTabs")
        self.tabs_frame.setFixedHeight(32)
        tabs_layout = QHBoxLayout(self.tabs_frame)
        tabs_layout.setContentsMargins(3, 3, 3, 3)
        tabs_layout.setSpacing(2)

        self.active_tab_btn = QPushButton("1 Active  0", self.tabs_frame)
        self.waiting_tab_btn = QPushButton("2 Waiting  0", self.tabs_frame)
        self.summary_tab_btn = QPushButton("3 Summary", self.tabs_frame)
        self._tab_buttons: dict[ViewTab, QPushButton] = {
            ViewTab.ACTIVE: self.active_tab_btn,
            ViewTab.WAITING: self.waiting_tab_btn,
            ViewTab.SUMMARY: self.summary_tab_btn,
        }
        for tab_val, btn in self._tab_buttons.items():
            btn.setObjectName("SegmentTabButton")
            btn.setFixedHeight(26)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, t=tab_val: self.switch_tab(t))
            tabs_layout.addWidget(btn, 1)

        content_layout.addWidget(self.tabs_frame)

        # Main Stack (Task List vs Daily Summary)
        self.stack = QStackedWidget(content_host)

        self.task_scroll = _TaskListFocusSurface(self.stack)
        self.task_scroll.key_command.connect(self._on_task_list_key)
        self.task_list_container = QWidget()
        self.task_list_container.setObjectName("TaskListContainer")
        self.task_list_container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.task_list_layout = QVBoxLayout(self.task_list_container)
        self.task_list_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.task_list_layout.setContentsMargins(0, 0, 0, 0)
        self.task_list_layout.setSpacing(2)
        self.task_scroll.setWidget(self.task_list_container)
        self.stack.addWidget(self.task_scroll)

        self.summary_view = DailySummaryView(self.stack)
        self.summary_view.day_changed.connect(self._on_summary_day_changed)
        self.stack.addWidget(self.summary_view)

        content_layout.addWidget(self.stack, 1)

        # Size grip row (subtle bottom-right resize handle inside shell)
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch(1)
        self.size_grip = QSizeGrip(content_host)
        self.size_grip.setFixedSize(12, 12)
        grip_row.addWidget(self.size_grip)
        content_layout.addLayout(grip_row)

        shell_layout.addWidget(content_host, 1)

        # Surface 5: Contextual Hints Footer
        self.hints_footer = HintsFooter(self.shell)
        shell_layout.addWidget(self.hints_footer)

        # Settings Modal Overlay
        self.settings_overlay = SettingsOverlay(self.shell)
        self.settings_overlay.settings_changed.connect(self._on_settings_changed)
        self.settings_overlay.closed.connect(self._on_settings_closed)

        # 1-second timer tick for live timers & periodic idle check
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self.on_tick)
        self.tick_timer.start()

        self.apply_settings(self._service.get_settings())
        self.refresh_views()
        self.quick_bar.focus_input()

    def hotkey_hwnd(self) -> int:
        """Return native window handle used for Win32 hotkey registration."""
        return int(self.winId())

    def current_tab(self) -> ViewTab:
        """Return currently selected ViewTab."""
        return self._current_tab

    def selected_task_id(self) -> str | None:
        """Return currently selected Task ID in the Task List."""
        return self._selected_task_id

    def expanded_task_id(self) -> str | None:
        """Return Task ID whose Thinking Space is currently expanded."""
        return self._expanded_task_id

    def displayed_task_ids(self) -> list[str]:
        """Return ordered Task IDs currently visible in the Task List."""
        return list(self._row_widgets.keys())

    def apply_settings(self, settings: Settings) -> None:
        """Apply theme, shortcut hints visibility, and refresh theme-dependent widgets."""
        tokens = resolve_theme(settings.theme, platform=self._platform)
        self._tokens = tokens
        self.setStyleSheet(build_stylesheet(tokens))
        self._shadow_effect.setColor(shadow_qcolor(tokens))

        self.brand_icon_label.setPixmap(create_cat_monogram_pixmap(18, QColor(tokens.text_primary)))
        self.running_pill_dot.setStyleSheet(
            f"background-color: {tokens.status_doing}; border-radius: 3px;"
        )
        self.settings_button.setIcon(create_gear_icon(QColor(tokens.text_secondary), 16))

        self.quick_bar.apply_theme(tokens)
        self.idle_banner.apply_theme(tokens)
        self.summary_view.apply_theme(tokens)
        self.settings_overlay.apply_theme(tokens)
        self.hints_footer.set_hints_enabled(settings.show_shortcut_hints)
        self._update_hints_context()

    def show_and_focus(self) -> None:
        """Show spotlight window, raise to front, and focus Quick Bar."""
        self.refresh_views()
        self.show()
        self.raise_()
        self.activateWindow()
        self.quick_bar.focus_input(select_all=True)
        self._update_hints_context()

    def hide_to_tray(self) -> None:
        """Flush any open Thinking Space edits and hide window."""
        if self._thinking_widget is not None:
            self._thinking_widget.flush_pending_saves()
        self.hide()

    def toggle_visibility(self) -> None:
        """Toggle spotlight window visibility from tray or global hotkey."""
        if self.isVisible():
            self.hide_to_tray()
        else:
            self.show_and_focus()

    def switch_tab(self, tab: ViewTab) -> None:
        """Switch between Active, Waiting, and Daily Summary tabs."""
        if self._thinking_widget is not None:
            self._thinking_widget.flush_pending_saves()
        self._current_tab = tab
        if tab == ViewTab.SUMMARY:
            self._summary_day = self._clock().astimezone().date()
            self.stack.setCurrentWidget(self.summary_view)
        else:
            self.stack.setCurrentWidget(self.task_scroll)
        self.refresh_views()
        self._update_hints_context()

    def open_settings(self) -> None:
        """Open the centered Settings modal overlay."""
        if self._thinking_widget is not None:
            self._thinking_widget.flush_pending_saves()
        self.settings_overlay.open_with_settings(self._service.get_settings())

    def check_idle_once(self) -> None:
        """Poll PlatformBridge idle duration and surface IdleBanner if threshold exceeded."""
        if self._platform is None:
            return
        running = self._service.get_running_tasks()
        if not running:
            self._idle_dismissed_for_gap = False
            if self.idle_banner.isVisible():
                self.idle_banner.dismiss()
            return

        idle_seconds = self._platform.get_idle_seconds()
        threshold = self._service.get_settings().idle_threshold.seconds
        if threshold is None or idle_seconds < threshold:
            self._idle_dismissed_for_gap = False
            return

        if self._idle_dismissed_for_gap or self.idle_banner.isVisible():
            return

        gap = self._service.detect_idle_gap(idle_seconds)
        if gap is not None:
            titles = [task.title for task in running]
            self.idle_banner.show_idle_gap(gap, titles)

    def on_tick(self) -> None:
        """1-second heartbeat refreshing running timers and polling idle status."""
        now = self._clock()
        self._refresh_header_timer_pill(now=now)
        for row in self._row_widgets.values():
            row.refresh_timer(now=now)
        if self._thinking_widget is not None:
            self._thinking_widget.refresh_timer(now=now)
        if self._current_tab == ViewTab.SUMMARY and self._summary_day == now.astimezone().date():
            self.summary_view.set_summary(
                self._service.get_daily_summary(self._summary_day),
                today=self._summary_day,
            )
        self.check_idle_once()
        self.state_changed.emit()

    def refresh_views(self) -> None:
        """Re-query TodoService and synchronize header pill, tab counts, list, or summary."""
        now = self._clock()
        active_tasks = self._service.list_active_tasks()
        waiting_tasks = self._service.list_waiting_tasks()

        self.active_tab_btn.setText(f"1 Active  {len(active_tasks)}")
        self.waiting_tab_btn.setText(f"2 Waiting  {len(waiting_tasks)}")
        for tab_val, btn in self._tab_buttons.items():
            btn.setProperty("active", tab_val == self._current_tab)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._refresh_header_timer_pill(now=now)

        if self._current_tab == ViewTab.SUMMARY:
            today = now.astimezone().date()
            summary = self._service.get_daily_summary(self._summary_day)
            self.summary_view.set_summary(summary, today=today)
            self.state_changed.emit()
            return

        tasks = self._compute_visible_tasks(active_tasks, waiting_tasks)
        self._rebuild_task_list(tasks, now=now)
        self.state_changed.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.settings_overlay.isVisible():
            self.settings_overlay.keyPressEvent(event)
            return

        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self._handle_escape()
            event.accept()
            return

        if mods & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_Comma:
                self.open_settings()
                event.accept()
                return
            if key == Qt.Key.Key_L:
                self.quick_bar.focus_input(select_all=True)
                event.accept()
                return
            if key == Qt.Key.Key_1:
                self.switch_tab(ViewTab.ACTIVE)
                event.accept()
                return
            if key == Qt.Key.Key_2:
                self.switch_tab(ViewTab.WAITING)
                event.accept()
                return
            if key == Qt.Key.Key_3:
                self.switch_tab(ViewTab.SUMMARY)
                event.accept()
                return

        if self._current_tab == ViewTab.SUMMARY and not self.quick_bar.has_input_focus():
            if key == Qt.Key.Key_Left:
                self.summary_view.go_previous_day()
                event.accept()
                return
            if key == Qt.Key.Key_Right:
                self.summary_view.go_next_day()
                event.accept()
                return
            if key in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3):
                self._switch_tab_by_number(key)
                event.accept()
                return
            if key == Qt.Key.Key_Slash:
                self.quick_bar.start_search_mode()
                event.accept()
                return

        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            header_rect = self.header_bar.geometry()
            shell_pos = self.shell.mapFrom(self, event.pos())
            if header_rect.contains(shell_pos):
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.settings_overlay.isVisible():
            self.settings_overlay.setGeometry(self.shell.rect())

    def _compute_visible_tasks(
        self,
        active_tasks: list[Task],
        waiting_tasks: list[Task],
    ) -> list[Task]:
        raw = self.quick_bar.text()
        if is_search_input(raw):
            return self._service.search_tasks(raw, include_done=True)
        if raw.strip():
            # Live match preview across active/waiting tasks while typing in capture mode
            return self._service.search_tasks(raw, include_done=False)
        if self._current_tab == ViewTab.WAITING:
            return waiting_tasks
        return active_tasks

    def _rebuild_task_list(self, tasks: list[Task], *, now: datetime) -> None:
        # Preserve focused sub-widget identity (e.g., Add Sub-step input) across in-list mutations
        focused_name: str | None = None
        if self._thinking_widget is not None:
            fw = self.focusWidget()
            if fw is not None and self._thinking_widget.isAncestorOf(fw):
                focused_name = fw.objectName()

        self._row_widgets.clear()
        self._thinking_widget = None

        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                widget = item.widget()
                assert widget is not None
                widget.setParent(None)
                widget.deleteLater()

        valid_ids = {t.id for t in tasks}
        if self._selected_task_id not in valid_ids:
            self._selected_task_id = tasks[0].id if tasks else None
        if self._expanded_task_id not in valid_ids:
            self._expanded_task_id = None

        if not tasks:
            self.task_list_layout.addWidget(self._build_empty_state())
            self.task_list_layout.addStretch(1)
            return

        for task in tasks:
            is_selected = task.id == self._selected_task_id
            row = TaskRowWidget(
                task,
                now=now,
                tokens=self._tokens,
                selected=is_selected,
                parent=self.task_list_container,
            )
            row.clicked.connect(self._on_row_clicked)
            row.double_clicked.connect(self._on_row_double_clicked)
            row.status_clicked.connect(self._on_row_status_clicked)
            self._row_widgets[task.id] = row
            self.task_list_layout.addWidget(row)

            if task.id == self._expanded_task_id:
                thinking = ThinkingSpaceWidget(
                    task,
                    now=now,
                    tokens=self._tokens,
                    parent=self.task_list_container,
                )
                self._connect_thinking_space(thinking)
                self._thinking_widget = thinking
                self.task_list_layout.addWidget(thinking)

        self.task_list_layout.addStretch(1)

        if self._thinking_widget is not None and focused_name:
            target = self._thinking_widget.findChild(QWidget, focused_name)
            if target is not None:
                target.setFocus(Qt.FocusReason.OtherFocusReason)

    def _build_empty_state(self) -> QWidget:
        box = QWidget(self.task_list_container)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(20, 64, 20, 64)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        glyph = QLabel(box)
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setPixmap(create_check_pixmap(QColor(self._tokens.text_muted), 20))
        layout.addWidget(glyph)

        if self.quick_bar.text().strip():
            title_text = "No matching tasks"
            hint_text = "Press Enter to create a new Task or Esc to clear."
        elif self._current_tab == ViewTab.WAITING:
            title_text = "No waiting tasks"
            hint_text = "Press w on a selected Task to mark it Waiting."
        else:
            title_text = "No active tasks"
            hint_text = "Press Ctrl+L or click above to add a task."

        title = QLabel(title_text, box)
        title.setObjectName("EmptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel(hint_text, box)
        hint.setObjectName("EmptyStateHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        return box

    def _connect_thinking_space(self, widget: ThinkingSpaceWidget) -> None:
        widget.title_changed.connect(self._on_thinking_title_changed)
        widget.requester_changed.connect(self._on_thinking_requester_changed)
        widget.status_changed.connect(self._on_thinking_status_changed)
        widget.timer_toggled.connect(self._on_thinking_timer_toggled)
        widget.notes_changed.connect(self._on_thinking_notes_changed)
        widget.sub_step_added.connect(self._on_thinking_sub_step_added)
        widget.sub_step_toggled.connect(self._on_thinking_sub_step_toggled)
        widget.sub_step_renamed.connect(self._on_thinking_sub_step_renamed)
        widget.sub_step_deleted.connect(self._on_thinking_sub_step_deleted)
        widget.time_adjusted.connect(self._on_thinking_time_adjusted)
        widget.manual_session_added.connect(self._on_thinking_manual_session_added)
        widget.session_deleted.connect(self._on_thinking_session_deleted)
        widget.collapse_requested.connect(self._collapse_thinking_space)

    def _refresh_header_timer_pill(self, *, now: datetime) -> None:
        running = self._service.get_running_tasks()
        if not running:
            self.running_timer_pill.setVisible(False)
            return
        if len(running) == 1:
            secs = running[0].total_logged_seconds(now=now)
            self.running_pill_text.setText(format_hms(secs))
        else:
            total_secs = sum(t.total_logged_seconds(now=now) for t in running)
            self.running_pill_text.setText(f"{len(running)} · {format_hms(total_secs)}")
        self.running_timer_pill.setVisible(True)

    def _jump_to_running_task(self) -> None:
        running = self._service.get_running_tasks()
        if not running:
            return
        target = running[0]
        self._current_tab = ViewTab.ACTIVE
        self._selected_task_id = target.id
        self._expanded_task_id = target.id
        self.stack.setCurrentWidget(self.task_scroll)
        self.refresh_views()
        self._focus_task_list()

    def _focus_task_list(self) -> None:
        if self._current_tab == ViewTab.SUMMARY:
            self.switch_tab(ViewTab.ACTIVE)
        ids = self.displayed_task_ids()
        if ids and self._selected_task_id not in ids:
            self._select_task(ids[0])
        self.task_scroll.setFocus(Qt.FocusReason.TabFocusReason)
        self._update_hints_context()

    def _select_task(self, task_id: str | None) -> None:
        self._selected_task_id = task_id
        for tid, row in self._row_widgets.items():
            row.set_selected(tid == task_id)
        if task_id is not None and task_id in self._row_widgets:
            self.task_scroll.ensureWidgetVisible(self._row_widgets[task_id], 0, 20)

    def _move_selection(self, step: int) -> None:
        ids = self.displayed_task_ids()
        if not ids:
            return
        if self._selected_task_id not in ids:
            self._select_task(ids[0])
            return
        idx = ids.index(self._selected_task_id)
        new_idx = max(0, min(len(ids) - 1, idx + step))
        self._select_task(ids[new_idx])

    def _toggle_expand_selected(self) -> None:
        if self._selected_task_id is None:
            return
        if self._expanded_task_id == self._selected_task_id:
            self._collapse_thinking_space()
        else:
            if self._thinking_widget is not None:
                self._thinking_widget.flush_pending_saves()
            self._expanded_task_id = self._selected_task_id
            self.refresh_views()
            self._update_hints_context()

    def _collapse_thinking_space(self) -> None:
        if self._thinking_widget is not None:
            self._thinking_widget.flush_pending_saves()
        self._expanded_task_id = None
        self.refresh_views()
        self.task_scroll.setFocus(Qt.FocusReason.OtherFocusReason)
        self._update_hints_context()

    def _handle_escape(self) -> None:
        if self.settings_overlay.isVisible():
            self.settings_overlay.cancel_capture_or_close()
            return
        if self._thinking_widget is not None and (
            self._thinking_widget.has_editor_focus() or self._expanded_task_id is not None
        ):
            self._collapse_thinking_space()
            return
        if self.quick_bar.text():
            self.quick_bar.clear()
            self.refresh_views()
            return
        self.hide_to_tray()

    def _on_quick_bar_focus_changed(self, _focused: bool) -> None:
        self._update_hints_context()

    def _on_quick_query_changed(self, _raw: str) -> None:
        if self._current_tab == ViewTab.SUMMARY and is_search_input(self.quick_bar.text()):
            self.switch_tab(ViewTab.ACTIVE)
            return
        self.refresh_views()

    def _on_quick_task_submitted(self, raw: str) -> None:
        created = self._service.add_task_from_input(raw)
        self.quick_bar.clear()
        if created is not None:
            self._current_tab = ViewTab.ACTIVE
            self._selected_task_id = created.id
            self.stack.setCurrentWidget(self.task_scroll)
        self.refresh_views()
        self.quick_bar.focus_input()

    def _on_task_list_key(self, event: QKeyEvent) -> None:
        if not self.task_scroll.hasFocus():
            return
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self._handle_escape()
            event.accept()
            return

        if mods & Qt.KeyboardModifier.AltModifier and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            if self._selected_task_id is not None:
                direction = -1 if key == Qt.Key.Key_Up else 1
                self._service.reorder_task(self._selected_task_id, direction)
                self.refresh_views()
            event.accept()
            return

        if mods != Qt.KeyboardModifier.NoModifier and not (
            key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal) and mods == Qt.KeyboardModifier.ShiftModifier
        ):
            return

        if key in (Qt.Key.Key_Up, Qt.Key.Key_K):
            self._move_selection(-1)
            event.accept()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_J):
            self._move_selection(1)
            event.accept()
        elif key == Qt.Key.Key_T and self._selected_task_id is not None:
            self._service.toggle_timer(self._selected_task_id)
            self.refresh_views()
            event.accept()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._toggle_expand_selected()
            event.accept()
        elif key == Qt.Key.Key_W and self._selected_task_id is not None:
            self._service.toggle_waiting(self._selected_task_id)
            self.refresh_views()
            event.accept()
        elif key == Qt.Key.Key_D and self._selected_task_id is not None:
            self._service.toggle_done(self._selected_task_id)
            self.refresh_views()
            event.accept()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal) and self._selected_task_id is not None:
            self._expanded_task_id = self._selected_task_id
            self.refresh_views()
            if self._thinking_widget is not None:
                self._thinking_widget.open_manual_entry()
                self._update_hints_context()
            event.accept()
        elif key in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3):
            self._switch_tab_by_number(key)
            event.accept()
        elif key == Qt.Key.Key_Slash:
            self.quick_bar.start_search_mode()
            event.accept()

    def _switch_tab_by_number(self, key: int) -> None:
        if key == Qt.Key.Key_1:
            self.switch_tab(ViewTab.ACTIVE)
        elif key == Qt.Key.Key_2:
            self.switch_tab(ViewTab.WAITING)
        elif key == Qt.Key.Key_3:
            self.switch_tab(ViewTab.SUMMARY)

    def _on_row_clicked(self, task_id: str) -> None:
        if self._selected_task_id == task_id:
            self._toggle_expand_selected()
        else:
            self._select_task(task_id)
        self.task_scroll.setFocus(Qt.FocusReason.MouseFocusReason)
        self._update_hints_context()

    def _on_row_double_clicked(self, task_id: str) -> None:
        self._select_task(task_id)
        if self._expanded_task_id != task_id:
            self._expanded_task_id = task_id
            self.refresh_views()
            self._update_hints_context()

    def _on_row_status_clicked(self, task_id: str) -> None:
        self._service.toggle_done(task_id)
        self.refresh_views()

    def _on_thinking_title_changed(self, task_id: str, title: str) -> None:
        self._service.update_task(task_id, title=title)
        self.refresh_views()

    def _on_thinking_requester_changed(self, task_id: str, requester: object) -> None:
        req = requester if isinstance(requester, str) else None
        self._service.update_task(task_id, requester=req)
        self.refresh_views()

    def _on_thinking_status_changed(self, task_id: str, status: object) -> None:
        if isinstance(status, TaskStatus):
            self._service.set_status(task_id, status)
            self.refresh_views()

    def _on_thinking_timer_toggled(self, task_id: str) -> None:
        self._service.toggle_timer(task_id)
        self.refresh_views()

    def _on_thinking_notes_changed(self, task_id: str, notes: str) -> None:
        self._service.update_notes(task_id, notes)
        self.state_changed.emit()

    def _on_thinking_sub_step_added(self, task_id: str, title: str) -> None:
        self._service.add_sub_step(task_id, title)
        self.refresh_views()

    def _on_thinking_sub_step_toggled(self, sub_step_id: str) -> None:
        self._service.toggle_sub_step(sub_step_id)
        self.refresh_views()

    def _on_thinking_sub_step_renamed(self, sub_step_id: str, title: str) -> None:
        self._service.update_sub_step(sub_step_id, title)
        self.refresh_views()

    def _on_thinking_sub_step_deleted(self, sub_step_id: str) -> None:
        self._service.delete_sub_step(sub_step_id)
        self.refresh_views()

    def _on_thinking_time_adjusted(self, task_id: str, delta_seconds: int) -> None:
        self._service.adjust_time(task_id, delta_seconds)
        self.refresh_views()

    def _on_thinking_manual_session_added(self, task_id: str, duration_seconds: int) -> None:
        self._service.add_manual_session(task_id, duration_seconds)
        self.refresh_views()

    def _on_thinking_session_deleted(self, session_id: str) -> None:
        self._service.delete_work_session(session_id)
        self.refresh_views()

    def _on_summary_day_changed(self, day: object) -> None:
        if isinstance(day, date):
            self._summary_day = day
            self.refresh_views()

    def _on_idle_keep(self) -> None:
        self._idle_dismissed_for_gap = True
        self._service.resolve_idle_gap(keep=True, idle_started_at=self._clock())
        self.refresh_views()

    def _on_idle_trim(self, idle_started_at: object) -> None:
        self._idle_dismissed_for_gap = True
        if isinstance(idle_started_at, datetime):
            self._service.resolve_idle_gap(keep=False, idle_started_at=idle_started_at)
            self.refresh_views()

    def _on_settings_changed(self, settings: object) -> None:
        if not isinstance(settings, Settings):
            return
        saved = self._service.update_settings(
            settings,
            hotkey_id=self._hotkey_id,
            hwnd=self.hotkey_hwnd(),
        )
        self.apply_settings(saved)
        self.settings_updated.emit(saved)
        self.state_changed.emit()

    def _on_settings_closed(self) -> None:
        self.quick_bar.focus_input()
        self._update_hints_context()

    def _update_hints_context(self) -> None:
        if self._current_tab == ViewTab.SUMMARY:
            self.hints_footer.set_context(HintContext.SUMMARY)
        elif self._expanded_task_id is not None and (
            self._thinking_widget is not None and self._thinking_widget.has_editor_focus()
        ):
            self.hints_footer.set_context(HintContext.THINKING_SPACE)
        elif self.quick_bar.has_input_focus():
            self.hints_footer.set_context(HintContext.QUICK_BAR)
        else:
            self.hints_footer.set_context(HintContext.TASK_LIST)
