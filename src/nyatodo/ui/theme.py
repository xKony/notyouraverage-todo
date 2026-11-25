"""Color tokens, typography helpers, and flat QSS stylesheet builder for nyatodo."""

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont

from nyatodo.domain import ThemeMode


@dataclass(frozen=True)
class ColorTokens:
    """Complete semantic color palette for a single nyatodo theme."""

    is_dark: bool
    bg_window: str
    bg_surface: str
    bg_elevated: str
    bg_hover: str
    bg_selected: str
    border_subtle: str
    border_focus: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent_primary: str
    status_doing: str
    status_waiting: str
    status_done: str
    danger: str
    tint_accent: str
    tint_accent_border: str
    tint_waiting: str
    tint_waiting_border: str
    tint_danger: str
    scrim_modal: str
    modal_bg: str
    shadow_rgba: tuple[int, int, int, int]


DARK_TOKENS = ColorTokens(
    is_dark=True,
    bg_window="#111317",
    bg_surface="#171A20",
    bg_elevated="#1E222A",
    bg_hover="#1A1E26",
    bg_selected="#222733",
    border_subtle="#262B35",
    border_focus="#5E8BFF",
    text_primary="#ECEFF4",
    text_secondary="#9CA5B4",
    text_muted="#858FA1",
    accent_primary="#5E8BFF",
    status_doing="#5E8BFF",
    status_waiting="#E5A93B",
    status_done="#38C172",
    danger="#F06464",
    tint_accent="rgba(94, 139, 255, 0.14)",
    tint_accent_border="rgba(94, 139, 255, 0.35)",
    tint_waiting="rgba(229, 169, 59, 0.12)",
    tint_waiting_border="rgba(229, 169, 59, 0.38)",
    tint_danger="rgba(240, 100, 100, 0.12)",
    scrim_modal="rgba(0, 0, 0, 0.55)",
    modal_bg="#111317",
    shadow_rgba=(0, 0, 0, 122),
)

LIGHT_TOKENS = ColorTokens(
    is_dark=False,
    bg_window="#F8F9FB",
    bg_surface="#F1F3F7",
    bg_elevated="#FFFFFF",
    bg_hover="#EEF1F6",
    bg_selected="#E7ECF5",
    border_subtle="#DCE1EA",
    border_focus="#2054D6",
    text_primary="#111827",
    text_secondary="#4B5565",
    text_muted="#5F6B7E",
    accent_primary="#2054D6",
    status_doing="#2054D6",
    status_waiting="#9A5404",
    status_done="#137338",
    danger="#C62222",
    tint_accent="rgba(32, 84, 214, 0.10)",
    tint_accent_border="rgba(32, 84, 214, 0.28)",
    tint_waiting="rgba(154, 84, 4, 0.09)",
    tint_waiting_border="rgba(154, 84, 4, 0.30)",
    tint_danger="rgba(198, 34, 34, 0.08)",
    scrim_modal="rgba(15, 23, 42, 0.28)",
    modal_bg="#FFFFFF",
    shadow_rgba=(15, 23, 42, 36),
)


def resolve_theme_mode(mode: ThemeMode, system_theme: ThemeMode = ThemeMode.DARK) -> ThemeMode:
    """Resolve ThemeMode.SYSTEM into concrete DARK or LIGHT."""
    if mode != ThemeMode.SYSTEM:
        return mode
    if system_theme in (ThemeMode.DARK, ThemeMode.LIGHT):
        return system_theme
    return ThemeMode.DARK


def resolve_theme(mode: ThemeMode, system_theme: ThemeMode = ThemeMode.DARK) -> ColorTokens:
    """Return ColorTokens for the given ThemeMode."""
    resolved = resolve_theme_mode(mode, system_theme=system_theme)
    return LIGHT_TOKENS if resolved == ThemeMode.LIGHT else DARK_TOKENS


def make_ui_font(
    pixel_size: int = 13,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> QFont:
    """Create a proportional UI QFont with Segoe UI Variable Text / Segoe UI fallback."""
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Arial"])
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def make_mono_font(
    pixel_size: int = 12,
    weight: QFont.Weight = QFont.Weight.Medium,
) -> QFont:
    """Create a tabular monospace QFont for timers, durations, counts, and keycaps."""
    font = QFont()
    font.setFamilies(["Cascadia Mono", "Consolas", "Courier New"])
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def format_hms(seconds: int) -> str:
    """Format non-negative seconds as HH:MM:SS."""
    clamped = max(0, int(seconds))
    hours, remainder = divmod(clamped, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_compact_duration(seconds: int) -> str:
    """Format paused duration compactly as MM:SS under 1 hour or HH:MM:SS otherwise."""
    clamped = max(0, int(seconds))
    if clamped < 3600:
        minutes, secs = divmod(clamped, 60)
        return f"{minutes:02d}:{secs:02d}"
    return format_hms(clamped)


def shadow_qcolor(tokens: ColorTokens) -> QColor:
    """Return QColor for neutral spotlight window elevation."""
    r, g, b, a = tokens.shadow_rgba
    return QColor(r, g, b, a)


def build_stylesheet(tokens: ColorTokens) -> str:
    """Build flat, hairline-bordered QSS stylesheet from ColorTokens."""
    t = tokens
    return f"""
    QWidget {{
        font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
        color: {t.text_primary};
        outline: none;
    }}

    #SpotlightShell {{
        background-color: {t.bg_window};
        border: 1px solid {t.border_subtle};
        border-radius: 12px;
    }}

    #HeaderBar {{
        background-color: transparent;
    }}

    #BrandWordmark {{
        color: {t.text_primary};
        font-size: 13px;
        font-weight: 600;
    }}

    #RunningTimerPill {{
        background-color: {t.tint_accent};
        border: 1px solid {t.tint_accent_border};
        border-radius: 12px;
        padding: 0px 4px;
    }}
    #RunningTimerPill:hover {{
        border: 1px solid {t.accent_primary};
    }}
    #RunningTimerPillText {{
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 11px;
        font-weight: 500;
        color: {t.status_doing};
        background: transparent;
    }}

    #SettingsButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
    }}
    #SettingsButton:hover {{
        background-color: {t.bg_hover};
    }}

    #QuickBarFrame {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 8px;
    }}
    #QuickBarFrame[focused="true"] {{
        border: 1px solid {t.border_focus};
    }}
    #QuickBarInput {{
        background-color: transparent;
        border: none;
        color: {t.text_primary};
        font-size: 13px;
        selection-background-color: {t.accent_primary};
        selection-color: #FFFFFF;
    }}

    #RequesterPill {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 4px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 2px 6px;
    }}

    #EnterHintKeycap {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 4px;
        color: {t.text_muted};
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 10px;
        font-weight: 500;
        padding: 1px 6px;
    }}

    #IdleBanner {{
        background-color: {t.bg_surface};
        border: 1px solid {t.tint_waiting_border};
        border-radius: 8px;
    }}
    #IdleBannerText {{
        color: {t.text_primary};
        font-size: 12px;
        font-weight: 500;
        background: transparent;
    }}
    #IdleKeepButton {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_primary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 10px;
    }}
    #IdleKeepButton:hover {{
        background-color: {t.bg_hover};
    }}
    #IdleTrimButton {{
        background-color: {t.tint_danger};
        border: 1px solid {t.danger};
        border-radius: 6px;
        color: {t.danger};
        font-size: 11px;
        font-weight: 600;
        padding: 0px 10px;
    }}

    #SegmentedTabs {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
    }}
    QPushButton#SegmentTabButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 8px;
    }}
    QPushButton#SegmentTabButton:hover {{
        background-color: {t.bg_hover};
        color: {t.text_primary};
    }}
    QPushButton#SegmentTabButton[active="true"] {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
    }}

    #TaskListScroll, #SummaryScroll, #SessionListScroll {{
        background-color: transparent;
        border: none;
    }}
    #TaskListContainer, #SummaryContainer, #SessionListContainer {{
        background-color: transparent;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 0px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 2px 0px 2px 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.bg_elevated};
        border-radius: 3px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.border_subtle};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
        height: 0px;
    }}

    #TaskRow {{
        background-color: transparent;
        border-radius: 6px;
    }}
    #TaskRow:hover {{
        background-color: {t.bg_hover};
    }}
    #TaskRow[selected="true"] {{
        background-color: {t.bg_selected};
    }}
    #TaskRow[selected="true"]:hover {{
        background-color: {t.bg_selected};
    }}

    #TaskStatusButton {{
        background-color: transparent;
        border: none;
        padding: 0px;
    }}

    #TaskTimerLabel {{
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 12px;
        font-weight: 500;
        color: {t.status_doing};
        background: transparent;
    }}
    #TaskTimerLabel[paused="true"] {{
        font-size: 11px;
        color: {t.text_muted};
    }}

    #TaskTitleLabel {{
        font-size: 13px;
        font-weight: 500;
        color: {t.text_primary};
        background: transparent;
    }}
    #TaskTitleLabel[done="true"] {{
        color: {t.text_muted};
    }}

    #SubStepCountLabel {{
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 10px;
        font-weight: 500;
        color: {t.text_muted};
        background: transparent;
    }}

    #ThinkingSpace {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 8px;
    }}
    #ThinkingTitleEdit {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid transparent;
        color: {t.text_primary};
        font-size: 13px;
        font-weight: 600;
        padding: 2px 0px;
    }}
    #ThinkingTitleEdit:focus {{
        border-bottom: 1px solid {t.border_focus};
    }}
    #ThinkingRequesterEdit {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 4px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 2px 6px;
    }}
    #ThinkingRequesterEdit:focus {{
        border: 1px solid {t.border_focus};
        color: {t.text_primary};
    }}

    QPushButton#StatusChipButton {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 4px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 2px 8px;
    }}
    QPushButton#StatusChipButton:hover {{
        background-color: {t.bg_hover};
        color: {t.text_primary};
    }}
    QPushButton#StatusChipButton[active="true"] {{
        border: 1px solid {t.accent_primary};
        color: {t.text_primary};
    }}

    QPushButton#ThinkingTimerButton {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_primary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 10px;
    }}
    QPushButton#ThinkingTimerButton:hover {{
        background-color: {t.bg_hover};
    }}
    QPushButton#ThinkingTimerButton[running="true"] {{
        background-color: {t.tint_accent};
        border: 1px solid {t.tint_accent_border};
        color: {t.status_doing};
        font-family: "Cascadia Mono", "Consolas", monospace;
    }}

    #SectionDivider {{
        background-color: {t.border_subtle};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}
    #VerticalDivider {{
        background-color: {t.border_subtle};
        max-width: 1px;
        min-width: 1px;
        border: none;
    }}

    #SectionLabel {{
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 600;
        background: transparent;
    }}
    #SavedStatusLabel {{
        color: {t.text_muted};
        font-size: 10px;
        background: transparent;
    }}

    #NotesEditor {{
        background-color: {t.bg_window};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_primary};
        font-size: 13px;
        padding: 6px 8px;
    }}
    #NotesEditor:focus {{
        border: 1px solid {t.border_focus};
    }}

    #SubStepTitleEdit {{
        background-color: transparent;
        border: none;
        color: {t.text_primary};
        font-size: 12px;
        padding: 0px 2px;
    }}
    #SubStepTitleEdit[done="true"] {{
        color: {t.text_muted};
    }}
    #AddSubStepInput {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid transparent;
        color: {t.text_primary};
        font-size: 12px;
        padding: 2px 0px;
    }}
    #AddSubStepInput:focus {{
        border-bottom: 1px solid {t.border_focus};
    }}

    QPushButton#SessionChip {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_secondary};
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 10px;
        font-weight: 500;
        padding: 0px 8px;
    }}
    QPushButton#SessionChip:hover {{
        background-color: {t.bg_hover};
        color: {t.text_primary};
    }}

    #ManualDurationInput {{
        background-color: {t.bg_window};
        border: 1px solid {t.border_focus};
        border-radius: 6px;
        color: {t.text_primary};
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 11px;
        padding: 2px 8px;
    }}

    #SessionRowLabel {{
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 11px;
        color: {t.text_secondary};
        background: transparent;
    }}
    #SessionRowLabel[running="true"] {{
        color: {t.status_doing};
    }}

    QToolButton#RowDeleteButton {{
        background-color: transparent;
        border: none;
        border-radius: 4px;
        color: {t.text_muted};
        font-size: 12px;
    }}
    QToolButton#RowDeleteButton:hover {{
        background-color: {t.tint_danger};
        color: {t.danger};
    }}

    #DayNavButton {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_secondary};
    }}
    #DayNavButton:hover:enabled {{
        background-color: {t.bg_hover};
        color: {t.text_primary};
    }}
    #DayNavButton:disabled {{
        color: {t.text_muted};
    }}
    #DayTitleLabel {{
        color: {t.text_primary};
        font-size: 13px;
        font-weight: 600;
        background: transparent;
    }}

    #SummaryHero {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 8px;
    }}
    #HeroMetricTitle {{
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        background: transparent;
    }}
    #HeroMetricValue {{
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 22px;
        font-weight: 600;
        color: {t.text_primary};
        background: transparent;
    }}
    #HeroMetricCaption {{
        color: {t.text_muted};
        font-size: 11px;
        background: transparent;
    }}
    #OverlapCaption {{
        color: {t.text_secondary};
        font-size: 11px;
        background: transparent;
    }}
    #SummaryBreakdownRow {{
        background-color: transparent;
        border-bottom: 1px solid {t.border_subtle};
    }}
    #SummaryDurationLabel {{
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 12px;
        font-weight: 500;
        color: {t.text_primary};
        background: transparent;
    }}

    #EmptyStateTitle {{
        color: {t.text_secondary};
        font-size: 13px;
        font-weight: 500;
        background: transparent;
    }}
    #EmptyStateHint {{
        color: {t.text_muted};
        font-size: 12px;
        background: transparent;
    }}

    #ModalScrim {{
        background-color: {t.scrim_modal};
        border-radius: 12px;
    }}
    #SettingsModal {{
        background-color: {t.modal_bg};
        border: 1px solid {t.border_subtle};
        border-radius: 10px;
    }}
    #SettingsTitle {{
        color: {t.text_primary};
        font-size: 14px;
        font-weight: 600;
        background: transparent;
    }}
    #SettingsRowLabel {{
        color: {t.text_primary};
        font-size: 13px;
        font-weight: 500;
        background: transparent;
    }}
    #SettingsSegmentTrack {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
    }}
    QPushButton#SettingsSegmentOption {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 10px;
    }}
    QPushButton#SettingsSegmentOption[active="true"] {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
    }}
    QPushButton#ShortcutCaptureButton {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_primary};
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 11px;
        font-weight: 500;
        padding: 0px 10px;
    }}
    QPushButton#ShortcutCaptureButton[capturing="true"] {{
        border: 1px solid {t.border_focus};
        color: {t.accent_primary};
    }}
    #SettingsErrorLabel {{
        color: {t.danger};
        font-size: 11px;
        background: transparent;
    }}
    QComboBox#IdleThresholdCombo {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_primary};
        font-size: 12px;
        padding: 2px 10px;
    }}
    QComboBox#IdleThresholdCombo::drop-down {{
        border: none;
        width: 18px;
    }}
    QComboBox#IdleThresholdCombo QAbstractItemView {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
        selection-background-color: {t.bg_selected};
        selection-color: {t.text_primary};
    }}
    QPushButton#SettingsDoneButton {{
        background-color: {t.accent_primary};
        border: none;
        border-radius: 6px;
        color: #FFFFFF;
        font-size: 12px;
        font-weight: 600;
        padding: 0px 14px;
    }}

    #HintsFooter {{
        background-color: {t.bg_surface};
        border-top: 1px solid {t.border_subtle};
        border-bottom-left-radius: 12px;
        border-bottom-right-radius: 12px;
    }}
    #KeycapLabel {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 4px;
        color: {t.text_secondary};
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 10px;
        font-weight: 500;
        padding: 1px 5px;
    }}
    #HintVerbLabel {{
        color: {t.text_muted};
        font-size: 11px;
        background: transparent;
    }}
    """
