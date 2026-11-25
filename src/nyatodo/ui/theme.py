"""Color tokens, typography helpers, and flat QSS stylesheet builder for nyatodo."""

from dataclasses import dataclass

from PySide6.QtGui import QFont

from nyatodo.domain import ThemeMode


@dataclass(frozen=True)
class ColorTokens:
    """Complete semantic color palette for a single nyatodo theme."""

    is_dark: bool
    bg_window: str
    bg_surface: str
    bg_elevated: str
    bg_thinking: str
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
    tint_done: str
    tint_done_border: str
    tint_danger: str
    scrim_modal: str
    modal_bg: str


DARK_TOKENS = ColorTokens(
    is_dark=True,
    bg_window="#16171B",
    bg_surface="#1D1F25",
    bg_elevated="#252831",
    bg_thinking="#1D1F25",
    bg_hover="#222631",
    bg_selected="#2A3040",
    border_subtle="#2D313B",
    border_focus="#4C8DFF",
    text_primary="#F4F4F5",
    text_secondary="#A1A1AA",
    text_muted="#8E8E98",
    accent_primary="#4C8DFF",
    status_doing="#4C8DFF",
    status_waiting="#F59E0B",
    status_done="#34D399",
    danger="#F87171",
    tint_accent="rgba(76, 141, 255, 0.14)",
    tint_accent_border="rgba(76, 141, 255, 0.35)",
    tint_waiting="rgba(245, 158, 11, 0.12)",
    tint_waiting_border="rgba(245, 158, 11, 0.38)",
    tint_done="rgba(52, 211, 153, 0.12)",
    tint_done_border="rgba(52, 211, 153, 0.32)",
    tint_danger="rgba(248, 113, 113, 0.12)",
    scrim_modal="rgba(0, 0, 0, 0.56)",
    modal_bg="#16171B",
)

LIGHT_TOKENS = ColorTokens(
    is_dark=False,
    bg_window="#FFFFFF",
    bg_surface="#FAF8F4",
    bg_elevated="#FFFFFF",
    bg_thinking="#FEFCE8",
    bg_hover="#F4F1EA",
    bg_selected="#EFF4FF",
    border_subtle="#E6E2D8",
    border_focus="#0066FF",
    text_primary="#18181B",
    text_secondary="#52525B",
    text_muted="#71717A",
    accent_primary="#0066FF",
    status_doing="#0066FF",
    status_waiting="#D97706",
    status_done="#15803D",
    danger="#DC2626",
    tint_accent="rgba(0, 102, 255, 0.10)",
    tint_accent_border="rgba(0, 102, 255, 0.28)",
    tint_waiting="rgba(217, 119, 6, 0.10)",
    tint_waiting_border="rgba(217, 119, 6, 0.30)",
    tint_done="rgba(21, 128, 61, 0.10)",
    tint_done_border="rgba(21, 128, 61, 0.28)",
    tint_danger="rgba(220, 38, 38, 0.08)",
    scrim_modal="rgba(24, 24, 27, 0.28)",
    modal_bg="#FFFFFF",
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
    """Create a unified Segoe UI QFont for all nyatodo text and numeric readouts."""
    font = QFont("Segoe UI")
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


def build_stylesheet(tokens: ColorTokens) -> str:
    """Build flat, warm, hairline-bordered QSS stylesheet from ColorTokens."""
    t = tokens
    return f"""
    QWidget {{
        font-family: "Segoe UI";
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

    #AddedFeedbackPill {{
        background-color: {t.tint_done};
        border: 1px solid {t.tint_done_border};
        border-radius: 10px;
        color: {t.status_done};
        font-size: 11px;
        font-weight: 600;
        padding: 0px 8px;
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
        font-family: "Segoe UI";
        font-size: 11px;
        font-weight: 600;
        color: {t.status_doing};
        background: transparent;
    }}

    #SettingsButton, #ExpandToggleButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
    }}
    #SettingsButton:hover, #ExpandToggleButton:hover {{
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
        border-radius: 10px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 1px 8px;
    }}

    #EnterHintKeycap {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 4px;
        color: {t.text_muted};
        font-family: "Segoe UI";
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
        border-radius: 12px;
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
        border-radius: 12px;
        color: {t.danger};
        font-size: 11px;
        font-weight: 600;
        padding: 0px 10px;
    }}

    #SegmentedTabs {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 8px;
    }}
    QPushButton#SegmentTabButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
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
        font-weight: 600;
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
        background: {t.border_subtle};
        border-radius: 3px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.text_muted};
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
        font-family: "Segoe UI";
        font-size: 12px;
        font-weight: 600;
        color: {t.status_doing};
        background: transparent;
    }}
    #TaskTimerLabel[paused="true"] {{
        font-size: 11px;
        font-weight: 500;
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
        font-family: "Segoe UI";
        font-size: 10.5px;
        font-weight: 500;
        color: {t.text_muted};
        background: transparent;
    }}

    #ThinkingSpace {{
        background-color: {t.bg_thinking};
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
        border-radius: 10px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 2px 8px;
    }}
    #ThinkingRequesterEdit:focus {{
        border: 1px solid {t.border_focus};
        color: {t.text_primary};
    }}

    QPushButton#StatusChipButton {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 12px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 2px 10px;
    }}
    QPushButton#StatusChipButton:hover {{
        background-color: {t.bg_hover};
        color: {t.text_primary};
    }}
    QPushButton#StatusChipButton[active="true"] {{
        background-color: {t.tint_accent};
        border: 1px solid {t.accent_primary};
        color: {t.accent_primary};
        font-weight: 600;
    }}

    QPushButton#ThinkingTimerButton {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 13px;
        color: {t.text_primary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 12px;
    }}
    QPushButton#ThinkingTimerButton:hover {{
        background-color: {t.bg_hover};
    }}
    QPushButton#ThinkingTimerButton[running="true"] {{
        background-color: {t.tint_accent};
        border: 1px solid {t.tint_accent_border};
        color: {t.status_doing};
        font-family: "Segoe UI";
        font-weight: 600;
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
        border-radius: 11px;
        color: {t.text_secondary};
        font-family: "Segoe UI";
        font-size: 10.5px;
        font-weight: 500;
        padding: 0px 9px;
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
        font-family: "Segoe UI";
        font-size: 11px;
        padding: 2px 8px;
    }}

    #SessionRowLabel {{
        font-family: "Segoe UI";
        font-size: 11px;
        color: {t.text_secondary};
        background: transparent;
    }}
    #SessionRowLabel[running="true"] {{
        color: {t.status_doing};
        font-weight: 600;
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
        font-family: "Segoe UI";
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
        font-family: "Segoe UI";
        font-size: 12px;
        font-weight: 600;
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
        border-radius: 8px;
    }}
    QPushButton#SettingsSegmentOption {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 10px;
    }}
    QPushButton#SettingsSegmentOption:hover {{
        color: {t.text_primary};
    }}
    QPushButton#SettingsSegmentOption[active="true"] {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
        font-weight: 600;
    }}
    QPushButton#ShortcutCaptureButton {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_primary};
        font-family: "Segoe UI";
        font-size: 11px;
        font-weight: 600;
        padding: 0px 10px;
    }}
    QPushButton#ShortcutCaptureButton:hover {{
        background-color: {t.bg_hover};
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
        font-family: "Segoe UI";
        font-size: 12px;
        font-weight: 500;
        padding: 2px 24px 2px 10px;
    }}
    QComboBox#IdleThresholdCombo:hover {{
        background-color: {t.bg_hover};
        border: 1px solid {t.border_focus};
    }}
    QComboBox#IdleThresholdCombo::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border: none;
        background: transparent;
    }}
    QComboBox#IdleThresholdCombo::down-arrow {{
        image: none;
        width: 0px;
        height: 0px;
    }}
    QComboBox#IdleThresholdCombo QAbstractItemView {{
        background-color: {t.modal_bg};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_primary};
        selection-background-color: {t.bg_selected};
        selection-color: {t.text_primary};
        padding: 2px;
        outline: none;
    }}
    QPushButton#SettingsDoneButton {{
        background-color: {t.accent_primary};
        border: none;
        border-radius: 14px;
        color: #FFFFFF;
        font-size: 12px;
        font-weight: 600;
        padding: 0px 16px;
    }}

    #HintsFooter {{
        background-color: {t.bg_surface};
        border-top: 1px solid {t.border_subtle};
        border-bottom-left-radius: 12px;
        border-bottom-right-radius: 12px;
    }}
    #KeycapLabel {{
        background-color: {t.bg_elevated};
        border: none;
        border-radius: 3px;
        color: {t.text_secondary};
        font-family: "Segoe UI";
        font-size: 9.5px;
        font-weight: 600;
        padding: 0px 4px;
    }}
    #HintVerbLabel {{
        color: {t.text_muted};
        font-family: "Segoe UI";
        font-size: 10px;
        background: transparent;
    }}
    """
