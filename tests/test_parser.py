"""Tests for QuickBarParser and manual session parsing at the nyatodo.parser seam."""

from datetime import date, datetime, timedelta, timezone

import pytest

from nyatodo.parser import (
    ManualSessionSpec,
    ParsedQuickInput,
    QuickBarParser,
    extract_search_query,
    is_search_input,
    parse_manual_session_input,
    parse_quick_input,
)


def test_parse_quick_input_extracts_trailing_requester() -> None:
    result = parse_quick_input("Fix login bug @alex")
    assert result == ParsedQuickInput(title="Fix login bug", requester="alex")
    assert QuickBarParser.parse_quick_input("Fix login bug @alex") == result


def test_parse_quick_input_positions_symbols_emails_and_whitespace() -> None:
    assert parse_quick_input("@Maya   review   PR #123") == ParsedQuickInput(
        title="review PR #123",
        requester="Maya",
    )
    assert parse_quick_input("Fix  @Maya  C++  /api  parser") == ParsedQuickInput(
        title="Fix C++ /api parser",
        requester="Maya",
    )
    assert parse_quick_input("Reply to user@domain.com about /api") == ParsedQuickInput(
        title="Reply to user@domain.com about /api",
        requester=None,
    )
    assert parse_quick_input("   \t\n  ") == ParsedQuickInput(title="", requester=None)
    assert parse_quick_input("@alice, check this") == ParsedQuickInput(
        title="check this",
        requester="alice",
    )


def test_search_mode_detection_and_query_extraction() -> None:
    assert is_search_input("/login") is True
    assert is_search_input("  / @alex") is True
    assert is_search_input("Fix /api endpoint") is False
    assert is_search_input("") is False

    assert extract_search_query("/login bug") == "login bug"
    assert extract_search_query("  /   @alex  ") == "@alex"
    assert extract_search_query("Fix /api") == ""


def test_parse_quick_input_multiple_mentions_urls_and_bare_at() -> None:
    assert parse_quick_input("Ask @alice about @bob") == ParsedQuickInput(
        title="Ask about @bob",
        requester="alice",
    )
    assert parse_quick_input("Check https://example.com/@user docs") == ParsedQuickInput(
        title="Check https://example.com/@user docs",
        requester=None,
    )
    assert parse_quick_input("Meet @ 3pm") == ParsedQuickInput(
        title="Meet @ 3pm",
        requester=None,
    )


@pytest.mark.parametrize(
    ("raw", "expected_seconds"),
    [
        ("25m", 25 * 60),
        ("1h", 3600),
        ("1h15m", 75 * 60),
        ("1h 15m", 75 * 60),
        ("1:15", 75 * 60),
        ("0:30", 30 * 60),
        ("90s", 90),
        ("1h2m3s", 3723),
        ("25", 25 * 60),
        ("+15m", 15 * 60),
        ("+25", 25 * 60),
    ],
)
def test_parse_manual_session_input_durations(raw: str, expected_seconds: int) -> None:
    tz = timezone(timedelta(hours=2))
    spec = parse_manual_session_input(raw, reference_day=date(2026, 11, 25), tzinfo=tz)
    assert spec == ManualSessionSpec(
        duration_seconds=expected_seconds,
        started_at=None,
        ended_at=None,
    )


@pytest.mark.parametrize(
    ("raw", "start_hm", "end_hm"),
    [
        ("14:10-14:40", (14, 10), (14, 40)),
        ("14:10 - 14:40", (14, 10), (14, 40)),
        ("9:05-10:00", (9, 5), (10, 0)),
    ],
)
def test_parse_manual_session_input_time_ranges(
    raw: str,
    start_hm: tuple[int, int],
    end_hm: tuple[int, int],
) -> None:
    tz = timezone(timedelta(hours=2))
    ref_day = date(2026, 11, 25)
    spec = parse_manual_session_input(raw, reference_day=ref_day, tzinfo=tz)
    assert spec == ManualSessionSpec(
        duration_seconds=None,
        started_at=datetime(2026, 11, 25, start_hm[0], start_hm[1], tzinfo=tz),
        ended_at=datetime(2026, 11, 25, end_hm[0], end_hm[1], tzinfo=tz),
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "0",
        "0m",
        "0s",
        "0:00",
        "-15m",
        "1:75",
        "14:10-14:10",
        "14:40-14:10",
        "24:00-25:00",
        "14:60-15:00",
        "14:10-",
        "-14:40",
        "not-a-duration",
    ],
)
def test_parse_manual_session_input_rejects_invalid_and_reversed_inputs(raw: str) -> None:
    tz = timezone(timedelta(hours=2))
    with pytest.raises(ValueError):
        parse_manual_session_input(raw, reference_day=date(2026, 11, 25), tzinfo=tz)
