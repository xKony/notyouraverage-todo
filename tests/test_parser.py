"""Tests for QuickBarParser at the public nyatodo.parser seam."""

from nyatodo.parser import (
    ParsedQuickInput,
    QuickBarParser,
    extract_search_query,
    is_search_input,
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
