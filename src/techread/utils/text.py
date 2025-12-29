from __future__ import annotations

import hashlib
import re

_WS_RE = re.compile(r"\s+")


def stable_hash(text: str) -> str:
    """Generate a stable SHA-256 hash of the given text.

    This function creates a consistent hash value for any input string,
    which can be used for caching, deduplication, or content addressing.

    Args:
        text: The input string to hash. Can be any UTF-8 compatible text.

    Returns:
        A hexadecimal string representing the SHA-256 hash of the input text.

    Examples:
        >>> stable_hash("hello world")
        'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
    """
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in the given text.

    This function replaces all sequences of whitespace characters (spaces, tabs,
    newlines) with single spaces and strips leading/trailing whitespace.

    Args:
        text: The input string to normalize. If None or empty, returns an empty string.

    Returns:
        A string with normalized whitespace: single spaces between words,
        no leading or trailing whitespace.

    Examples:
        >>> normalize_whitespace("  hello   world  \\n")
        'hello world'
        >>> normalize_whitespace("\\t\\tfoo\\tbar\\n")
        'foo bar'
    """
    return _WS_RE.sub(" ", (text or "").strip())


def contains_any(text: str, needles: list[str]) -> int:
    """Count how many search terms are contained in the text.

    This function performs a case-insensitive search for each needle in the haystack
    and returns the count of matches. Empty needles are ignored.

    Args:
        text: The input string to search within. If None or empty, returns 0.
        needles: A list of strings to search for in the text.

    Returns:
        The number of needles found in the text (case-insensitive).

    Examples:
        >>> contains_any("Hello World", ["hello", "foo"])
        1
        >>> contains_any("Python is great", ["python", "java", "C++"])
        1
    """
    t = (text or "").lower()
    return sum(1 for n in needles if n and n.lower() in t)
