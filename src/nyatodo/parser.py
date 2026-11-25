"""Quick Bar input parsing for task capture and search mode detection."""

import re
from dataclasses import dataclass

_REQUESTER_PATTERN = re.compile(
    r"(?:^|(?<=\s))@([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)[,;:.!?]?(?=$|\s)"
)


@dataclass(frozen=True)
class ParsedQuickInput:
    """Structured result of parsing raw Quick Bar task capture text."""

    title: str
    requester: str | None = None


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


def parse_quick_input(raw: str) -> ParsedQuickInput:
    """Parse raw Quick Bar input into a task title and optional requester."""
    return QuickBarParser.parse_quick_input(raw)


def is_search_input(raw: str) -> bool:
    """Return True when the Quick Bar input starts with the '/' search prefix."""
    return QuickBarParser.is_search_input(raw)


def extract_search_query(raw: str) -> str:
    """Return the normalized search query after a leading '/', or empty string."""
    return QuickBarParser.extract_search_query(raw)
