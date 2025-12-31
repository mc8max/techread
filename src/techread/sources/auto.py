"""Automatic source name and tag generation for RSS feeds.

This module provides functionality to automatically infer source names from
RSS feed metadata and generate relevant tags based on feed content. It's used
to populate missing or incomplete source information when adding new feeds.

The main functionality includes:
- Inferring source names from feed titles or URLs
- Collecting recent entry titles and content snippets
- Generating descriptive tags using LLM-based tag generation
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from techread.config import Settings
from techread.ingest.rss import FeedMeta, parse_feed_full
from techread.summarize.llm import LLMSettings
from techread.tags.llm import generate_tags

_MAX_ENTRY_TITLES = 10
_MAX_SNIPPETS = 4
_SNIPPET_CHARS = 800


@dataclass(frozen=True)
class AutofillResult:
    """Result of automatic source name and tag generation.

    Attributes:
        name: The inferred source name, or None if no change is needed.
        tags: The generated tags string, or None if no change is needed.
        warnings: List of warning messages encountered during processing.
    """

    name: str | None
    tags: str | None
    warnings: list[str]


def infer_source_name(meta: FeedMeta, url: str) -> str:
    """Infer a source name from feed metadata or URL.

    Attempts to extract the most descriptive name possible:
    1. Uses the feed's title if available
    2. Falls back to the hostname from the URL
    3. Uses the URL path if no hostname is available

    Args:
        meta: The feed metadata containing title and subtitle information.
        url: The URL of the RSS feed.

    Returns:
        A descriptive name for the source.
    """
    if meta.title:
        return meta.title
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    return host or url


def _collect_snippets(conn: sqlite3.Connection, source_id: int | None) -> list[str]:
    """Collect recent content snippets from a source's posts.

    Retrieves up to _MAX_SNIPPETS recent posts and extracts
    content text snippets (up to _SNIPPET_CHARS per snippet).

    Args:
        conn: SQLite database connection.
        source_id: The ID of the source to collect snippets from.

    Returns:
        List of content text snippets, truncated to _SNIPPET_CHARS each.
    """
    if source_id is None:
        return []
    rows = conn.execute(
        "SELECT content_text FROM posts WHERE source_id=? ORDER BY published_at DESC LIMIT ?",
        (int(source_id), _MAX_SNIPPETS),
    ).fetchall()
    snippets = []
    for row in rows:
        text = str(row["content_text"] or "").strip()
        if not text:
            continue
        snippets.append(text[:_SNIPPET_CHARS])
    return snippets


def _entry_titles(entries: Iterable) -> list[str]:
    """Extract titles from feed entries.

    Collects up to _MAX_ENTRY_TITLES non-empty titles from
    the provided iterable of feed entries.

    Args:
        entries: Iterable of feed entry objects with 'title' attributes.

    Returns:
        List of up to _MAX_ENTRY_TITLES entry titles.
    """
    titles: list[str] = []
    for e in entries:
        title = str(getattr(e, "title", "") or "").strip()
        if title:
            titles.append(title)
        if len(titles) >= _MAX_ENTRY_TITLES:
            break
    return titles


def autofill_source(
    conn: sqlite3.Connection,
    settings: Settings,
    *,
    source_id: int | None,
    url: str,
    name: str,
    tags: str,
    force: bool = False,
) -> AutofillResult:
    """Automatically fill in missing source name and tags.

    Analyzes an RSS feed to infer a descriptive source name and generate
    relevant tags. Only updates fields that are missing or when force=True.

    Args:
        conn: SQLite database connection for accessing existing posts.
        settings: Application settings containing LLM configuration.
        source_id: ID of the source to collect existing content from (optional).
        url: URL of the RSS feed to analyze.
        name: Current source name (may be empty or placeholder).
        tags: Current tags string (may be empty).
        force: If True, regenerate even if name and tags already exist.

    Returns:
        AutofillResult containing updated name, tags, and any warnings.
    """
    warnings: list[str] = []
    want_name = force or not name or name == url
    want_tags = force or not tags.strip()
    if not want_name and not want_tags:
        return AutofillResult(None, None, warnings)

    try:
        meta, entries = parse_feed_full(url)
    except Exception as exc:
        warnings.append(f"Failed to parse feed {url}: {exc}")
        return AutofillResult(None, None, warnings)

    new_name = name
    new_tags = tags

    if want_name:
        new_name = infer_source_name(meta, url)

    if want_tags:
        entry_titles = _entry_titles(entries)
        entry_snippets = _collect_snippets(conn, source_id)
        tag_error = None
        try:
            tag_out = generate_tags(
                settings=LLMSettings(model=settings.llm_model, temperature=0.3),
                feed_title=meta.title,
                feed_subtitle=meta.subtitle,
                entry_titles=entry_titles,
                entry_snippets=entry_snippets,
            )
        except Exception as exc:
            tag_error = exc
            tag_out = ""
            warnings.append(f"Failed to generate tags for {url}: {exc}")
        if tag_out:
            new_tags = tag_out
        elif tag_error is None:
            warnings.append(f"No tags generated for {url}")

    update_name = new_name if want_name and new_name != name else None
    update_tags = new_tags if want_tags and new_tags != tags else None
    return AutofillResult(update_name, update_tags, warnings)
