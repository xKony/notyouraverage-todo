"""Tests for QuickBarParser and manual session parsing at the nyatodo.parser seam."""

from datetime import date, datetime, timedelta, timezone

import pytest

from nyatodo.parser import (
    ActiveRequesterToken,
    ManualSessionSpec,
    ParsedQuickInput,
    QuickBarParser,
    apply_requester_completion,
    extract_search_query,
    find_active_requester_token,
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


def test_find_active_requester_token_capture_and_search_modes() -> None:
    assert find_active_requester_token("@ad", 3) == ActiveRequesterToken(query="ad", start=0, end=3)
    assert QuickBarParser.find_active_requester_token("@ad", 2) == ActiveRequesterToken(
        query="ad", start=0, end=3
    )
    assert find_active_requester_token("Fix @ad", 7) == ActiveRequesterToken(
        query="ad", start=4, end=7
    )
    assert find_active_requester_token("Fix @ad bug", 5) == ActiveRequesterToken(
        query="ad", start=4, end=7
    )
    assert find_active_requester_token("Fix @ad bug", 7) == ActiveRequesterToken(
        query="ad", start=4, end=7
    )
    # Cursor before '@' or outside token returns None
    assert find_active_requester_token("Fix @ad bug", 4) is None
    assert find_active_requester_token("Fix @ad bug", 8) is None
    assert find_active_requester_token("Fix @ad", 0) is None
    assert find_active_requester_token("Fix @ad", 10) is None

    # Search mode: '/@', '  /@ad', '/ @ad', '/fix @ad'
    assert find_active_requester_token("/@", 2) == ActiveRequesterToken(query="", start=1, end=2)
    assert find_active_requester_token("/@ad", 4) == ActiveRequesterToken(
        query="ad", start=1, end=4
    )
    assert find_active_requester_token("  /@ad", 6) == ActiveRequesterToken(
        query="ad", start=3, end=6
    )
    assert find_active_requester_token("/ @ad", 5) == ActiveRequesterToken(
        query="ad", start=2, end=5
    )
    assert find_active_requester_token("/fix @ad", 8) == ActiveRequesterToken(
        query="ad", start=5, end=8
    )


def test_find_active_requester_token_bare_at_first_at_rule_and_punctuation() -> None:
    assert find_active_requester_token("@", 1) == ActiveRequesterToken(query="", start=0, end=1)
    assert find_active_requester_token("Fix @", 5) == ActiveRequesterToken(query="", start=4, end=5)
    assert find_active_requester_token("Fix @ bug", 5) == ActiveRequesterToken(
        query="", start=4, end=5
    )

    # First-@ rule: first boundary '@' works, second boundary '@' is ignored
    text_two = "Ask @alice about @bob"
    assert find_active_requester_token(text_two, 7) == ActiveRequesterToken(
        query="alice", start=4, end=10
    )
    assert find_active_requester_token(text_two, len(text_two)) is None

    # Non-boundary '@' (emails and mid-sentence URLs) are skipped
    assert find_active_requester_token("Email user@domain.com", 21) is None
    assert find_active_requester_token("Check https://example.com/@user", 31) is None
    assert find_active_requester_token("Email user@domain.com @ad", 25) == ActiveRequesterToken(
        query="ad", start=22, end=25
    )

    # Dots and trailing punctuation
    assert find_active_requester_token("Ping @john.", 11) == ActiveRequesterToken(
        query="john.", start=5, end=11
    )
    assert find_active_requester_token("Ping @john.doe", 14) == ActiveRequesterToken(
        query="john.doe", start=5, end=14
    )
    assert find_active_requester_token("Ping @alice, check", 11) == ActiveRequesterToken(
        query="alice", start=5, end=11
    )
    assert find_active_requester_token("Ping @alice, check", 12) is None


def test_apply_requester_completion_end_mid_sentence_search_and_no_space() -> None:
    end_token = ActiveRequesterToken(query="ad", start=4, end=7)
    assert apply_requester_completion("Fix @ad", end_token, "Adrian") == ("Fix @Adrian ", 12)
    assert QuickBarParser.apply_requester_completion("Fix @ad", end_token, "Adrian") == (
        "Fix @Adrian ",
        12,
    )

    # Mid-sentence before existing space reuses the space and advances cursor past it
    mid_token = ActiveRequesterToken(query="ad", start=4, end=7)
    assert apply_requester_completion("Fix @ad bug", mid_token, "Adrian") == (
        "Fix @Adrian bug",
        12,
    )

    # Search mode bare '@'
    search_token = ActiveRequesterToken(query="", start=1, end=2)
    assert apply_requester_completion("/@", search_token, "Adrian") == ("/@Adrian ", 9)

    # append_space=False leaves text without adding trailing space
    assert apply_requester_completion("Fix @ad", end_token, "Adrian", append_space=False) == (
        "Fix @Adrian",
        11,
    )
    assert apply_requester_completion("Fix @ad bug", mid_token, "Adrian", append_space=False) == (
        "Fix @Adrian bug",
        11,
    )
