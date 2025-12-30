from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser


def now_utc_iso() -> str:
    """Return current UTC time as ISO 8601 formatted string.

    Returns:
        str: Current UTC datetime in ISO 8601 format (e.g., '2024-01-01T12:00:00+00:00').

    Example:
        >>> now_utc_iso()
        '2024-12-29T02:31:41+00:00'
    """
    return datetime.now(timezone.utc).isoformat()


def parse_datetime_iso(dt_str: str) -> datetime:
    """Parse ISO 8601 datetime string and convert to UTC.

    Args:
        dt_str: Datetime string in ISO 8601 format (e.g., '2024-01-01T12:00:00').
                Can also handle various other datetime string formats.

    Returns:
        datetime: Datetime object in UTC timezone. If input has no timezone,
                  it's assumed to be UTC.

    Example:
        >>> parse_datetime_iso('2024-12-29T12:00:00')
        datetime(2024, 12, 29, 12, 0, 0, tzinfo=datetime.timezone.utc)
        >>> parse_datetime_iso('2024-12-29T12:00:00+05:30')
        datetime(2024, 12, 29, 6, 30, 0, tzinfo=datetime.timezone.utc)
    """
    dt = parser.parse(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_from_dt(dt: datetime) -> str:
    """Convert datetime to UTC and return as ISO 8601 formatted string.

    Args:
        dt: Datetime object (with or without timezone information).

    Returns:
        str: UTC datetime in ISO 8601 format (e.g., '2024-01-01T12:00:00+00:00').

    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2024, 12, 29, 12, 0, 0)
        >>> iso_from_dt(dt)
        '2024-12-29T12:00:00+00:00'
        >>> dt_est = datetime(2024, 12, 29, 7, 0, 0, tzinfo=timezone.utc)
        >>> iso_from_dt(dt_est)
        '2024-12-29T07:00:00+00:00'
    """
    return dt.astimezone(timezone.utc).isoformat()
