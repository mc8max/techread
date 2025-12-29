from __future__ import annotations

from datetime import datetime, timezone
from dateutil import parser


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_datetime_iso(dt_str: str) -> datetime:
    dt = parser.parse(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_from_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()
