"""Cozy Morph-Pills color tokens, bundled Poppins typography, and QSS stylesheet builder."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication

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
    tint_danger_border: str
    scrim_modal: str
    modal_bg: str


DARK_TOKENS = ColorTokens(
    is_dark=True,
    bg_window="#141417",
    bg_surface="#1D1E24",
    bg_elevated="#262730",
    bg_thinking="#232220",
    bg_hover="#21232B",
    bg_selected="#232A3D",
    border_subtle="#2B2D37",
    border_focus="#6B9EFF",
    text_primary="#F4F2ED",
    text_secondary="#A7A39B",
    text_muted="#73706A",
    accent_primary="#6B9EFF",
    status_doing="#6B9EFF",
    status_waiting="#FBBF24",
    status_done="#4ADE80",
    danger="#F87171",
    tint_accent="rgba(107, 158, 255, 0.15)",
    tint_accent_border="rgba(107, 158, 255, 0.36)",
    tint_waiting="rgba(251, 191, 36, 0.14)",
    tint_waiting_border="rgba(251, 191, 36, 0.36)",
    tint_done="rgba(74, 222, 128, 0.14)",
    tint_done_border="rgba(74, 222, 128, 0.32)",
    tint_danger="rgba(248, 113, 113, 0.14)",
    tint_danger_border="rgba(248, 113, 113, 0.36)",
    scrim_modal="rgba(0, 0, 0, 0.56)",
    modal_bg="#1B1C22",
)

LIGHT_TOKENS = ColorTokens(
    is_dark=False,
    bg_window="#FFFFFF",
    bg_surface="#FFFFFF",
    bg_elevated="#F2F4F7",
    bg_thinking="#F9FAFB",
    bg_hover="#F7F8FA",
    bg_selected="#EEF4FF",
    border_subtle="#E5E7EB",
    border_focus="#2F6BFF",
    text_primary="#18181B",
    text_secondary="#52525B",
    text_muted="#8A8F98",
    accent_primary="#2F6BFF",
    status_doing="#2F6BFF",
    status_waiting="#D97706",
    status_done="#16A34A",
    danger="#DC2626",
    tint_accent="rgba(47, 107, 255, 0.10)",
    tint_accent_border="rgba(47, 107, 255, 0.30)",
    tint_waiting="rgba(217, 119, 6, 0.11)",
    tint_waiting_border="rgba(217, 119, 6, 0.30)",
    tint_done="rgba(22, 163, 74, 0.11)",
    tint_done_border="rgba(22, 163, 74, 0.28)",
    tint_danger="rgba(220, 38, 38, 0.08)",
    tint_danger_border="rgba(220, 38, 38, 0.28)",
    scrim_modal="rgba(24, 24, 27, 0.24)",
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


_BUNDLED_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_LOADED_FONT_FAMILY: str | None = None


def load_bundled_fonts() -> str:
    """Register bundled Poppins TTF weights with Qt once and return active UI font family."""
    global _LOADED_FONT_FAMILY
    if _LOADED_FONT_FAMILY is not None and _LOADED_FONT_FAMILY in QFontDatabase.families():
        return _LOADED_FONT_FAMILY

    family_name = "Segoe UI"
    if QGuiApplication.instance() is not None and _BUNDLED_FONT_DIR.is_dir():
        for font_path in sorted(_BUNDLED_FONT_DIR.glob("*.ttf")):
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                for fam in families:
                    if fam.lower() == "poppins":
                        family_name = fam
                        break
                else:
                    if families and family_name == "Segoe UI":
                        family_name = families[0]

    _LOADED_FONT_FAMILY = family_name
    app = QGuiApplication.instance()
    if app is not None:
        app_font = make_ui_font(13)
        # Qt internal widgets (such as QDateEdit's calendar popup) read
        # QGuiApplication.font().pointSize() and warn on -1 when pixelSize is used.
        screen = QGuiApplication.primaryScreen()
        screen_dpi = screen.logicalDotsPerInch() if screen is not None else 0.0
        dpi = screen_dpi if screen_dpi > 0 else 96.0
        app_font.setPointSizeF(round((13.0 * 72.0) / dpi, 2))
        QGuiApplication.setFont(app_font)
    return family_name


def make_ui_font(
    pixel_size: int = 13,
    weight: QFont.Weight = QFont.Weight.Normal,
    *,
    tracking_em: float = 0.0,
) -> QFont:
    """Create a Poppins QFont (with Segoe UI fallback) and optional optical tracking."""
    font = QFont()
    primary = _LOADED_FONT_FAMILY or "Poppins"
    if primary == "Segoe UI":
        font.setFamilies(["Segoe UI"])
    else:
        font.setFamilies([primary, "Segoe UI"])
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    if tracking_em != 0.0:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, pixel_size * tracking_em)
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
    """Build cozy Morph-Pills QSS stylesheet from ColorTokens."""
    t = tokens
    segment_track_bg = t.bg_window if t.is_dark else t.bg_elevated
    segment_active_bg = t.bg_elevated if t.is_dark else t.bg_surface
    return f"""
    QWidget {{
        font-family: "Poppins", "Segoe UI", sans-serif;
        color: {t.text_primary};
        outline: none;
    }}

    #SpotlightShell {{
        background-color: {t.bg_window};
        border: 1px solid {t.border_subtle};
        border-radius: 24px;
    }}

    #HeaderBar {{
        background-color: transparent;
    }}

    #BrandWordmark {{
        color: {t.text_secondary};
        font-size: 12px;
        font-weight: 500;
    }}

    #AddedFeedbackPill {{
        background-color: {t.tint_done};
        border: 1px solid {t.tint_done_border};
        border-radius: 10px;
        color: {t.status_done};
        font-size: 11px;
        font-weight: 600;
        padding: 0px 9px;
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
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 11px;
        font-weight: 600;
        color: {t.status_doing};
        background: transparent;
    }}

    #SettingsButton, #ExpandToggleButton {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 13px;
    }}
    #SettingsButton:hover, #ExpandToggleButton:hover {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
    }}

    #QuickBarFrame {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 21px;
    }}
    #QuickBarFrame[focused="true"], #QuickBarFrame[has_text="true"] {{
        background-color: {t.bg_surface};
        border: 1px solid {t.tint_accent_border};
    }}
    #QuickBarInput {{
        background-color: transparent;
        border: none;
        color: {t.text_primary};
        font-size: 15px;
        font-weight: 300;
        selection-background-color: {t.accent_primary};
        selection-color: #FFFFFF;
    }}

    #RequesterPill {{
        background-color: {t.bg_elevated};
        border: none;
        border-radius: 10px;
        color: {t.text_secondary};
        font-size: 10.5px;
        font-weight: 500;
        padding: 1px 9px;
    }}

    #EnterHintKeycap {{
        background-color: {t.bg_elevated};
        border: none;
        border-radius: 10px;
        color: {t.text_muted};
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 10px;
        font-weight: 500;
        padding: 1px 8px;
    }}

    #IdleBanner {{
        background-color: {t.bg_surface};
        border: 1px solid {t.tint_waiting_border};
        border-radius: 16px;
    }}
    #IdleBannerText {{
        color: {t.text_primary};
        font-size: 12px;
        font-weight: 500;
        background: transparent;
    }}
    #IdleKeepButton {{
        background-color: {t.bg_elevated};
        border: none;
        border-radius: 12px;
        color: {t.text_primary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 11px;
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
        padding: 0px 11px;
    }}

    #SegmentedTabs {{
        background-color: transparent;
        border: none;
    }}
    QPushButton#SegmentTabButton {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 13px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 11px;
    }}
    QPushButton#SegmentTabButton:hover {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
    }}
    QPushButton#SegmentTabButton[active="true"] {{
        background-color: {t.accent_primary};
        border: 1px solid {t.accent_primary};
        color: #FFFFFF;
        font-weight: 600;
    }}
    QPushButton#SegmentTabButton[kind="waiting"][active="true"] {{
        background-color: {t.tint_waiting};
        border: 1px solid {t.tint_waiting_border};
        color: {t.status_waiting};
        font-weight: 600;
    }}

    QPushButton#FilterSortButton {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 13px;
        color: {t.text_secondary};
    }}
    QPushButton#FilterSortButton:hover {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
    }}
    QPushButton#FilterSortButton[active="true"] {{
        background-color: {t.tint_accent};
        border: 1px solid {t.tint_accent_border};
        color: {t.accent_primary};
    }}

    #FilterPopover {{
        background-color: {t.modal_bg};
        border: 1px solid {t.border_subtle};
        border-radius: 16px;
    }}
    #FilterSectionLabel {{
        color: {t.text_secondary};
        font-size: 10.5px;
        font-weight: 600;
        background: transparent;
    }}
    #FilterFieldLabel {{
        color: {t.text_muted};
        font-size: 11px;
        font-weight: 500;
        background: transparent;
    }}
    QPushButton#FilterChipButton {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 11px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 10px;
    }}
    QPushButton#FilterChipButton:hover {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
    }}
    QPushButton#FilterChipButton[active="true"] {{
        background-color: {t.accent_primary};
        border: 1px solid {t.accent_primary};
        color: #FFFFFF;
        font-weight: 600;
    }}
    QPushButton#ModalResetButton {{
        background-color: transparent;
        border: none;
        color: {t.accent_primary};
        font-size: 10.5px;
        font-weight: 600;
        padding: 0px 4px;
    }}
    QPushButton#ModalResetButton:disabled {{
        color: {t.text_muted};
    }}

    QDateEdit#DatePickerEdit {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 10px;
        color: {t.text_primary};
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 11px;
        font-weight: 500;
        padding: 2px 8px;
    }}
    QDateEdit#DatePickerEdit:focus {{
        border: 1px solid {t.border_focus};
    }}
    QDateEdit#DatePickerEdit::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 18px;
        border: none;
        background: transparent;
    }}
    QCalendarWidget QWidget {{
        background-color: {t.modal_bg};
        color: {t.text_primary};
        alternate-background-color: {t.bg_surface};
    }}
    QCalendarWidget QToolButton {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: none;
        border-radius: 6px;
        padding: 3px 6px;
        font-size: 11px;
        font-weight: 600;
    }}
    QCalendarWidget QToolButton:hover {{
        background-color: {t.bg_hover};
    }}
    QCalendarWidget QMenu {{
        background-color: {t.modal_bg};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
    }}
    QCalendarWidget QSpinBox {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        color: {t.text_primary};
        padding: 1px 4px;
    }}
    QCalendarWidget QAbstractItemView:enabled {{
        background-color: {t.modal_bg};
        color: {t.text_primary};
        selection-background-color: {t.accent_primary};
        selection-color: #FFFFFF;
        outline: none;
    }}
    QCalendarWidget QAbstractItemView:disabled {{
        color: {t.text_muted};
    }}

    QPushButton#RequesterFilterPill,
    QPushButton#RequesterOverflowButton {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 13px;
        color: {t.text_secondary};
        font-size: 10.5px;
        font-weight: 500;
        padding: 0px 10px;
    }}
    QPushButton#RequesterFilterPill:hover,
    QPushButton#RequesterOverflowButton:hover {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
    }}
    QPushButton#RequesterFilterPill[active="true"],
    QPushButton#RequesterOverflowButton[active="true"] {{
        background-color: {t.accent_primary};
        border: 1px solid {t.accent_primary};
        color: #FFFFFF;
        font-weight: 600;
    }}

    #RequesterPopover {{
        background-color: {t.modal_bg};
        border: 1px solid {t.border_subtle};
        border-radius: 16px;
    }}
    QPushButton#RequesterPopoverItem {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        color: {t.text_primary};
        font-size: 11px;
        font-weight: 500;
        text-align: left;
        padding: 0px 10px;
    }}
    QPushButton#RequesterPopoverItem:hover {{
        background-color: {t.bg_hover};
    }}
    QPushButton#RequesterPopoverItem[active="true"] {{
        background-color: {t.tint_accent};
        border: 1px solid {t.tint_accent_border};
        color: {t.accent_primary};
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
        width: 5px;
        margin: 2px 0px 2px 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border_subtle};
        border-radius: 2px;
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
        border: 1px solid transparent;
        border-radius: 18px;
    }}
    #TaskRow:hover {{
        background-color: {t.bg_hover};
        border: 1px solid {t.border_subtle};
    }}
    #TaskRow[doing="true"] {{
        background-color: {t.bg_surface};
        border: 1px solid {t.tint_accent_border};
    }}
    #TaskRow[selected="true"] {{
        background-color: {t.bg_selected};
        border: 1px solid {t.tint_accent_border};
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
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 11px;
        font-weight: 700;
        color: {t.status_doing};
        background-color: {t.tint_accent};
        border-radius: 11px;
        padding: 2px 9px;
    }}
    #TaskTimerLabel[paused="true"] {{
        font-size: 10.5px;
        font-weight: 500;
        color: {t.text_muted};
        background-color: {t.bg_elevated};
        border-radius: 10px;
        padding: 1px 8px;
    }}

    #TaskTitleLabel {{
        font-size: 13px;
        font-weight: 400;
        color: {t.text_primary};
        background: transparent;
    }}
    #TaskTitleLabel[done="true"] {{
        color: {t.text_muted};
    }}

    #ImportancePill {{
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 10.5px;
        font-weight: 700;
        border-radius: 9px;
        padding: 0px 6px;
        color: {t.text_secondary};
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
    }}
    #ImportancePill[level="1"] {{
        color: {t.text_secondary};
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
    }}
    #ImportancePill[level="2"] {{
        color: {t.status_waiting};
        background-color: {t.tint_waiting};
        border: 1px solid {t.tint_waiting_border};
    }}
    #ImportancePill[level="3"] {{
        color: {t.danger};
        background-color: {t.tint_danger};
        border: 1px solid {t.tint_danger_border};
    }}
    #ImportancePill[done="true"] {{
        color: {t.text_muted};
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
    }}

    #TaskDatePill {{
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 10px;
        font-weight: 500;
        color: {t.text_muted};
        background-color: {t.bg_elevated};
        border-radius: 10px;
        padding: 2px 7px;
    }}

    #SubStepCountLabel {{
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 10px;
        font-weight: 500;
        color: {t.text_muted};
        background-color: {t.bg_elevated};
        border-radius: 10px;
        padding: 2px 8px;
    }}

    #ThinkingSpace {{
        background-color: {t.bg_thinking};
        border: 1px solid {t.border_subtle};
        border-radius: 20px;
    }}
    #ThinkingAddedLabel {{
        color: {t.text_muted};
        font-size: 10.5px;
        font-weight: 400;
        background: transparent;
    }}
    #ThinkingTitleEdit {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid transparent;
        color: {t.text_primary};
        font-size: 14px;
        font-weight: 600;
        padding: 2px 0px;
    }}
    #ThinkingTitleEdit:focus {{
        border-bottom: 1px solid {t.border_focus};
    }}
    #ThinkingRequesterEdit {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 11px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 2px 10px;
    }}
    #ThinkingRequesterEdit:focus {{
        border: 1px solid {t.border_focus};
        color: {t.text_primary};
    }}

    QPushButton#StatusChipButton {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 12px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 2px 10px;
    }}
    QPushButton#StatusChipButton:hover {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
    }}
    QPushButton#StatusChipButton[active="true"] {{
        background-color: {t.tint_accent};
        border: 1px solid {t.tint_accent_border};
        color: {t.accent_primary};
        font-weight: 600;
    }}

    #ImportanceSegmentTrack {{
        background-color: {segment_track_bg};
        border: none;
        border-radius: 11px;
    }}
    QPushButton#ImportanceSegmentOption {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 9px;
        color: {t.text_muted};
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 10.5px;
        font-weight: 600;
        padding: 0px 7px;
    }}
    QPushButton#ImportanceSegmentOption:hover {{
        color: {t.text_primary};
    }}
    QPushButton#ImportanceSegmentOption[active="true"] {{
        background-color: {segment_active_bg};
        border: 1px solid {t.border_subtle};
        color: {t.text_primary};
    }}
    QPushButton#ImportanceSegmentOption[active="true"][level="2"] {{
        background-color: {t.tint_waiting};
        border: 1px solid {t.tint_waiting_border};
        color: {t.status_waiting};
    }}
    QPushButton#ImportanceSegmentOption[active="true"][level="3"] {{
        background-color: {t.tint_danger};
        border: 1px solid {t.tint_danger_border};
        color: {t.danger};
    }}

    QPushButton#ThinkingTimerButton {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 13px;
        color: {t.text_primary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 12px;
    }}
    QPushButton#ThinkingTimerButton:hover {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
    }}
    QPushButton#ThinkingTimerButton[running="true"] {{
        background-color: {t.tint_accent};
        border: 1px solid {t.tint_accent_border};
        color: {t.status_doing};
        font-family: "Poppins", "Segoe UI", sans-serif;
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
        font-weight: 300;
        background: transparent;
    }}

    #NotesEditor {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 14px;
        color: {t.text_primary};
        font-size: 12.5px;
        font-weight: 300;
        padding: 8px 10px;
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
        background-color: {t.bg_elevated};
        border: none;
        border-radius: 12px;
        color: {t.text_primary};
        font-size: 12px;
        font-weight: 300;
        padding: 4px 10px;
    }}
    #AddSubStepInput:focus {{
        background-color: {t.bg_surface};
    }}

    QPushButton#SessionChip {{
        background-color: {t.bg_elevated};
        border: none;
        border-radius: 11px;
        color: {t.text_secondary};
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 10.5px;
        font-weight: 500;
        padding: 0px 10px;
    }}
    QPushButton#SessionChip:hover {{
        background-color: {t.tint_accent};
        color: {t.accent_primary};
    }}

    #ManualDurationInput {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_focus};
        border-radius: 12px;
        color: {t.text_primary};
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 11px;
        padding: 2px 10px;
    }}

    #SessionRowLabel {{
        font-family: "Poppins", "Segoe UI", sans-serif;
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
        border-radius: 10px;
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
        border-radius: 14px;
        color: {t.text_secondary};
    }}
    #DayNavButton:hover:enabled {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
    }}
    #DayNavButton:disabled {{
        color: {t.text_muted};
    }}
    QPushButton#SummaryPeriodButton {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 14px;
        color: {t.text_primary};
        font-size: 12px;
        font-weight: 600;
        padding: 0px 12px;
    }}
    QPushButton#SummaryPeriodButton:hover {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_focus};
    }}
    #DailyStripFrame {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 16px;
    }}
    QPushButton#DailyStripDay {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 11px;
        padding: 2px;
    }}
    QPushButton#DailyStripDay:hover {{
        background-color: {t.bg_hover};
        border: 1px solid {t.border_subtle};
    }}
    QPushButton#DailyStripDay[today="true"] {{
        border: 1px solid {t.tint_accent_border};
        background-color: {t.tint_accent};
    }}
    #DailyStripDayLabel {{
        color: {t.text_secondary};
        background: transparent;
    }}
    #DailyStripDurationLabel {{
        color: {t.text_muted};
        background: transparent;
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
        border-radius: 22px;
    }}
    #HeroMetricTitle {{
        color: {t.text_muted};
        font-size: 10.5px;
        font-weight: 500;
        background: transparent;
    }}
    #HeroMetricValue {{
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 24px;
        font-weight: 700;
        color: {t.text_primary};
        background: transparent;
    }}
    #HeroMetricValue[secondary="true"] {{
        font-weight: 200;
        color: {t.text_secondary};
    }}
    #HeroMetricCaption {{
        color: {t.text_muted};
        font-size: 10.5px;
        font-weight: 300;
        background: transparent;
    }}
    #OverlapCaption {{
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 300;
        background: transparent;
    }}
    #SummaryBreakdownRow {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 18px;
    }}
    #SummaryDurationLabel {{
        font-family: "Poppins", "Segoe UI", sans-serif;
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
        font-weight: 300;
        background: transparent;
    }}

    #ModalScrim {{
        background-color: {t.scrim_modal};
        border-radius: 24px;
    }}
    #SettingsModal, #SummaryPeriodModal {{
        background-color: {t.modal_bg};
        border: 1px solid {t.border_subtle};
        border-radius: 22px;
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
        background-color: {segment_track_bg};
        border: none;
        border-radius: 14px;
    }}
    QPushButton#SettingsSegmentOption {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 11px;
        color: {t.text_secondary};
        font-size: 11px;
        font-weight: 500;
        padding: 0px 10px;
    }}
    QPushButton#SettingsSegmentOption:hover {{
        color: {t.text_primary};
    }}
    QPushButton#SettingsSegmentOption[active="true"] {{
        background-color: {segment_active_bg};
        border: 1px solid {t.border_subtle};
        border-radius: 11px;
        color: {t.text_primary};
        font-weight: 600;
    }}
    QPushButton#ShortcutCaptureButton {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 13px;
        color: {t.text_primary};
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 11px;
        font-weight: 600;
        padding: 0px 12px;
    }}
    QPushButton#ShortcutCaptureButton:hover {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
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
    QComboBox#IdleThresholdCombo, QComboBox#AutoHideDelayCombo {{
        background-color: {t.bg_elevated};
        border: 1px solid transparent;
        border-radius: 14px;
        color: {t.text_primary};
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 12px;
        font-weight: 500;
        padding: 2px 24px 2px 12px;
    }}
    QComboBox#IdleThresholdCombo:hover, QComboBox#AutoHideDelayCombo:hover {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_focus};
    }}
    QComboBox#IdleThresholdCombo::drop-down, QComboBox#AutoHideDelayCombo::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border: none;
        background: transparent;
    }}
    QComboBox#IdleThresholdCombo::down-arrow, QComboBox#AutoHideDelayCombo::down-arrow {{
        image: none;
        width: 0px;
        height: 0px;
    }}
    QComboBox#IdleThresholdCombo QAbstractItemView,
    QComboBox#AutoHideDelayCombo QAbstractItemView {{
        background-color: {t.modal_bg};
        border: 1px solid {t.border_subtle};
        border-radius: 12px;
        color: {t.text_primary};
        selection-background-color: {t.bg_selected};
        selection-color: {t.text_primary};
        padding: 4px;
        outline: none;
    }}
    QPushButton#SettingsDoneButton {{
        background-color: {t.accent_primary};
        border: none;
        border-radius: 14px;
        color: #FFFFFF;
        font-size: 12px;
        font-weight: 600;
        padding: 0px 18px;
    }}
    QPushButton#ModalSecondaryButton {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 14px;
        color: {t.text_primary};
        font-size: 12px;
        font-weight: 500;
        padding: 0px 14px;
    }}
    QPushButton#ModalSecondaryButton:hover {{
        background-color: {t.bg_surface};
    }}

    #HintsFooter {{
        background-color: transparent;
        border-top: 1px solid {t.border_subtle};
        border-bottom-left-radius: 24px;
        border-bottom-right-radius: 24px;
    }}
    #KeycapLabel {{
        background-color: {t.bg_elevated};
        border: none;
        border-radius: 6px;
        color: {t.text_secondary};
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 9.5px;
        font-weight: 600;
        padding: 0px 5px;
    }}
    #HintVerbLabel {{
        color: {t.text_muted};
        font-family: "Poppins", "Segoe UI", sans-serif;
        font-size: 10px;
        font-weight: 300;
        background: transparent;
    }}
    """
