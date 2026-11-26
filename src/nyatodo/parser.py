"""Quick Bar and manual Work Session input parsing."""

import datetime as dt
import re
from dataclasses import dataclass

_REQUESTER_PATTERN = re.compile(
    r"(?:^|(?<=\s))@([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)[,;:.!?]?(?=$|\s)"
)
_ACTIVE_REQUESTER_BODY_RE = re.compile(r"([A-Za-z0-9_.-]*)(?=[,;:.!?]?(?:$|\s))")
_TIME_RANGE_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")
_COLON_DURATION_RE = re.compile(r"^\s*(\d+):(\d{1,2})\s*$")
_DURATION_PART_RE = re.compile(
    r"^\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?\s*$",
    re.I,
)


@dataclass(frozen=True)
class ParsedQuickInput:
    """Structured result of parsing raw Quick Bar task capture text."""

    title: str
    requester: str | None = None


@dataclass(frozen=True)
class ManualSessionSpec:
    """Structured result of parsing manual Work Session duration or time-range text."""

    duration_seconds: int | None = None
    started_at: dt.datetime | None = None
    ended_at: dt.datetime | None = None


@dataclass(frozen=True)
class ActiveRequesterToken:
    """Active @requester token around the cursor for Quick Bar autocompletion."""

    query: str
    start: int
    end: int


class QuickBarParser:
    """Stateless parser for Quick Bar task capture and search prefix detection."""

    @staticmethod
    def parse_quick_input(raw: str) -> ParsedQuickInput:
        """Extract clean task title and optional @requester from raw input."""
        match = _REQUESTER_PATTERN.search(raw)
        if match is None:
            title = " ".join(raw.split())
            return ParsedQuickInput(title=title, requester=None)

        requester = match.group(1)
        without_token = raw[: match.start()] + raw[match.end() :]
        title = " ".join(without_token.split())
        return ParsedQuickInput(title=title, requester=requester)

    @staticmethod
    def is_search_input(raw: str) -> bool:
        """Return True when the Quick Bar input starts with the '/' search prefix."""
        return raw.lstrip().startswith("/")

    @staticmethod
    def extract_search_query(raw: str) -> str:
        """Return the normalized search query after a leading '/', or empty string."""
        stripped = raw.lstrip()
        if not stripped.startswith("/"):
            return ""
        return " ".join(stripped[1:].split())

    @staticmethod
    def find_active_requester_token(raw: str, cursor_pos: int) -> ActiveRequesterToken | None:
        """Return the first @requester token if cursor_pos lies within it, else None."""
        stripped = raw.lstrip()
        slash_idx = len(raw) - len(stripped) if stripped.startswith("/") else None

        for idx, ch in enumerate(raw):
            if ch != "@":
                continue
            is_boundary = (
                idx == 0
                or raw[idx - 1].isspace()
                or (slash_idx is not None and idx == slash_idx + 1)
            )
            if not is_boundary:
                continue
            match = _ACTIVE_REQUESTER_BODY_RE.match(raw, idx + 1)
            if match is None:
                continue
            token = ActiveRequesterToken(
                query=match.group(1),
                start=idx,
                end=match.end(),
            )
            if token.start + 1 <= cursor_pos <= token.end:
                return token
            return None

        return None

    @staticmethod
    def apply_requester_completion(
        raw: str,
        token: ActiveRequesterToken,
        requester: str,
        *,
        append_space: bool = True,
    ) -> tuple[str, int]:
        """Replace token in raw with @requester and return (updated_text, new_cursor_pos)."""
        clean_requester = requester.strip().lstrip("@")
        replacement = f"@{clean_requester}"
        prefix = raw[: token.start]
        suffix = raw[token.end :]
        if not append_space:
            updated = f"{prefix}{replacement}{suffix}"
            return updated, token.start + len(replacement)

        if suffix and suffix[0].isspace():
            updated = f"{prefix}{replacement}{suffix}"
            return updated, token.start + len(replacement) + 1

        updated = f"{prefix}{replacement} {suffix}"
        return updated, token.start + len(replacement) + 1


def parse_quick_input(raw: str) -> ParsedQuickInput:
    """Parse raw Quick Bar input into a task title and optional requester."""
    return QuickBarParser.parse_quick_input(raw)


def is_search_input(raw: str) -> bool:
    """Return True when the Quick Bar input starts with the '/' search prefix."""
    return QuickBarParser.is_search_input(raw)


def extract_search_query(raw: str) -> str:
    """Return the normalized search query after a leading '/', or empty string."""
    return QuickBarParser.extract_search_query(raw)


def find_active_requester_token(raw: str, cursor_pos: int) -> ActiveRequesterToken | None:
    """Return the first @requester token if cursor_pos lies within it, else None."""
    return QuickBarParser.find_active_requester_token(raw, cursor_pos)


def apply_requester_completion(
    raw: str,
    token: ActiveRequesterToken,
    requester: str,
    *,
    append_space: bool = True,
) -> tuple[str, int]:
    """Replace token in raw with @requester and return (updated_text, new_cursor_pos)."""
    return QuickBarParser.apply_requester_completion(
        raw,
        token,
        requester,
        append_space=append_space,
    )


def parse_manual_session_input(
    raw: str,
    *,
    reference_day: dt.date,
    tzinfo: dt.tzinfo,
) -> ManualSessionSpec:
    """Parse manual Work Session duration ('25m', '+15m', '1:15') or range ('14:10-14:40')."""
    stripped = raw.strip()
    if not stripped:
        raise ValueError("Manual Work Session input cannot be empty.")

    range_match = _TIME_RANGE_RE.match(stripped)
    if range_match is not None:
        start_hour, start_min, end_hour, end_min = (int(g) for g in range_match.groups())
        if not (0 <= start_hour <= 23 and 0 <= start_min <= 59):
            raise ValueError(f"Invalid start time in manual range: {raw!r}")
        if not (0 <= end_hour <= 23 and 0 <= end_min <= 59):
            raise ValueError(f"Invalid end time in manual range: {raw!r}")
        started_at = dt.datetime.combine(
            reference_day,
            dt.time(start_hour, start_min),
            tzinfo=tzinfo,
        )
        ended_at = dt.datetime.combine(
            reference_day,
            dt.time(end_hour, end_min),
            tzinfo=tzinfo,
        )
        if ended_at <= started_at:
            raise ValueError(f"Manual Work Session end must be after start: {raw!r}")
        return ManualSessionSpec(duration_seconds=None, started_at=started_at, ended_at=ended_at)

    duration_text = stripped[1:].strip() if stripped.startswith("+") else stripped
    total_seconds = _parse_duration_seconds(duration_text)
    if total_seconds is None or total_seconds <= 0:
        raise ValueError(f"Invalid manual Work Session input: {raw!r}")
    return ManualSessionSpec(duration_seconds=total_seconds, started_at=None, ended_at=None)


def _parse_duration_seconds(text: str) -> int | None:
    if not text:
        return None
    if text.isdigit():
        return int(text) * 60

    colon_match = _COLON_DURATION_RE.match(text)
    if colon_match is not None:
        hours = int(colon_match.group(1))
        minutes = int(colon_match.group(2))
        if minutes >= 60:
            return None
        return hours * 3600 + minutes * 60

    part_match = _DURATION_PART_RE.match(text)
    if part_match is not None:
        h_str, m_str, s_str = part_match.groups()
        if any(part is not None for part in (h_str, m_str, s_str)):
            hours = int(h_str or 0)
            minutes = int(m_str or 0)
            seconds = int(s_str or 0)
            return hours * 3600 + minutes * 60 + seconds

    return None
