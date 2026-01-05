from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from techread.config import load_settings
from techread.db import DB, init_db
from techread.utils.time import iso_from_dt, now_utc_iso, parse_datetime_iso

console = Console()

SOURCE_OPTION = typer.Option(None, "-s", "--source", help="Filter by source id (repeatable).")
TAG_OPTION = typer.Option(
    None, "-t", "--tag", help="Filter by source name/tags containing tag (repeatable)."
)


def _log_invalid_post(
    settings,
    *,
    source_id: int,
    source_name: str,
    url: str,
    title: str,
    word_count: int,
    reason: str,
) -> None:
    """Log invalid posts to a file with detailed information.

    This function logs details about posts that failed validation checks to
    a dedicated log file. It records metadata such as source information,
    URL, title, word count, and the reason for invalidation.

    Args:
        settings: Configuration settings object containing cache directory path
        source_id: The ID of the source where the post originated
        source_name: The name of the source where the post originated
        url: The URL of the invalid post
        title: The title of the invalid post
        word_count: The word count of the post content
        reason: The reason why the post was considered invalid

    Returns:
        None: This function writes to a log file but doesn't return a value

    Example:
        This function is typically called internally by the fetch command
        when posts fail validation checks. It logs to:
        {cache_dir}/invalid_posts.log
    """
    log_path = Path(settings.cache_dir) / "invalid_posts.log"
    safe_title = title.replace("\n", " ").strip()
    line = (
        f"{now_utc_iso()}\t"
        f"source_id={source_id}\t"
        f"source={source_name}\t"
        f"url={url}\t"
        f"title={safe_title}\t"
        f"word_count={word_count}\t"
        f"reason={reason}\n"
    )
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass


def _db() -> DB:
    """Initialize and return a database connection.

    This function loads the application settings, creates a database connection
    using the configured database path, and initializes the database schema.

    Returns:
        DB: A database connection object ready for use

    Example:
        db = _db()
        # Use db for database operations
    """
    s = load_settings()
    db = DB(path=s.db_path)
    init_db(db)
    return db


def _now() -> datetime:
    """Get the current UTC datetime.

    This function returns the current date and time in UTC timezone,
    which is used as a reference point for various timestamp operations.

    Returns:
        datetime: Current UTC datetime object

    Example:
        current_time = _now()
        # Returns current UTC time
    """
    return datetime.now(timezone.utc)


def _parse_or_fallback(published: str) -> str:
    """Parse a datetime string or return current time as fallback.

    This function attempts to parse a datetime string into ISO format.
    If parsing fails, it returns the current UTC time as a fallback.

    Args:
        published: A datetime string to parse

    Returns:
        str: ISO formatted datetime string (either parsed or current time)

    Example:
        parsed_time = _parse_or_fallback("2023-01-01T12:00:00Z")
        # Returns parsed ISO datetime

        fallback_time = _parse_or_fallback("")
        # Returns current UTC time as ISO string
    """
    if not published:
        return now_utc_iso()
    try:
        dt = parse_datetime_iso(published)
        return iso_from_dt(dt)
    except Exception:
        return now_utc_iso()
