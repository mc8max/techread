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
    s = load_settings()
    db = DB(path=s.db_path)
    init_db(db)
    return db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_or_fallback(published: str) -> str:
    if not published:
        return now_utc_iso()
    try:
        dt = parse_datetime_iso(published)
        return iso_from_dt(dt)
    except Exception:
        return now_utc_iso()
