from __future__ import annotations

from dataclasses import dataclass

import feedparser


@dataclass(frozen=True)
class FeedEntry:
    title: str
    url: str
    author: str
    published: str


def parse_feed(url: str) -> list[FeedEntry]:
    """Parse an RSS/Atom feed from the given URL and return a list of FeedEntry objects.

    This function parses a feed using feedparser, extracts relevant fields from each entry,
    and returns them as FeedEntry dataclass instances. The function handles various feed
    formats and ensures consistent field extraction with fallback values.

    Args:
        url: The URL of the RSS or Atom feed to parse.

    Returns:
        A list of FeedEntry objects containing parsed feed entries. The list is
        deduplicated by URL while preserving the original order of entries.

    Raises:
        Exception: If feedparser encounters an error parsing the URL (e.g., network
                   issues, invalid URL, or unsupported feed format).

    Notes:
        - For each entry, the function extracts: title (with link as fallback),
          url (link), author, and published date (with updated as fallback).
        - All string fields are stripped of whitespace.
        - Entries with empty URLs are filtered out during deduplication.
        - The function preserves the order of entries as they appear in the feed.

    Example:
        >>> entries = parse_feed("https://example.com/rss.xml")
        >>> for entry in entries:
        ...     print(f"{entry.title} - {entry.url}")
    """
    feed = feedparser.parse(url)
    entries: list[FeedEntry] = []
    for e in feed.entries or []:
        link = getattr(e, "link", None) or ""
        title = getattr(e, "title", None) or link
        author = getattr(e, "author", None) or ""
        published = getattr(e, "published", None) or getattr(e, "updated", None) or ""
        entries.append(
            FeedEntry(
                title=str(title).strip(),
                url=str(link).strip(),
                author=str(author).strip(),
                published=str(published).strip(),
            )
        )

    # Deduplicate by URL preserving order
    seen = set()
    out: list[FeedEntry] = []
    for it in entries:
        if it.url and it.url not in seen:
            out.append(it)
            seen.add(it.url)
    return out
