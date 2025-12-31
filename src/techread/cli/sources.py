from __future__ import annotations

import typer

from techread.db import exec_, q1, qall, session
from techread.digest.render import print_sources
from techread.ingest.rss import parse_feed
from techread.sources.auto import autofill_source
from techread.utils.time import now_utc_iso

from . import common
from .common import SOURCE_OPTION, _db, console


def sources_list():
    """List sources."""
    db = _db()
    with session(db) as conn:
        rows = [dict(r) for r in qall(conn, "SELECT * FROM sources ORDER BY id")]
    print_sources(rows)


def sources_add(
    url: str = typer.Argument(..., help="RSS/Atom feed URL"),
    name: str | None = typer.Option(None, help="Display name"),
    weight: float = typer.Option(1.0, help="Source weight (ranking prior)"),
    tags: str = typer.Option("", help="Comma-separated tags"),
):
    """Add an RSS/Atom source."""
    db = _db()
    settings = common.load_settings()
    with session(db) as conn:
        nm = name or url
        tags_out = tags
        if not name or not tags:
            res = autofill_source(
                conn,
                settings,
                source_id=None,
                url=url,
                name=nm,
                tags=tags_out,
                force=False,
            )
            if res.name:
                nm = res.name
            if res.tags:
                tags_out = res.tags
            for warning in res.warnings:
                console.print(f"[yellow]Warn[/yellow] {warning}")
        try:
            exec_(
                conn,
                "INSERT INTO sources(name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, 'rss', ?, ?, 1, ?)",
                (nm, url, float(weight), tags_out, now_utc_iso()),
            )
        except Exception as e:
            console.print(f"[red]Could not add source[/red]: {e}")
            raise typer.Exit(code=1) from e
    console.print(f"Added source: [bold]{nm}[/bold]")


def sources_remove(source_id: int = typer.Argument(..., help="Source id")):
    """Remove a source (does not delete already-fetched posts)."""
    db = _db()
    with session(db) as conn:
        cur = conn.execute("DELETE FROM sources WHERE id=?", (int(source_id),))
        if cur.rowcount == 0:
            console.print(f"[red]No such source[/red]: {source_id}")
            raise typer.Exit(code=1)
    console.print(f"Removed source {source_id}.")


def sources_enable(source_id: int = typer.Argument(..., help="Source id")):
    db = _db()
    with session(db) as conn:
        cur = conn.execute("UPDATE sources SET enabled=1 WHERE id=?", (int(source_id),))
        if cur.rowcount == 0:
            console.print(f"[red]No such source[/red]: {source_id}")
            raise typer.Exit(code=1)
    console.print(f"Enabled source {source_id}.")


def sources_disable(source_id: int = typer.Argument(..., help="Source id")):
    db = _db()
    with session(db) as conn:
        cur = conn.execute("UPDATE sources SET enabled=0 WHERE id=?", (int(source_id),))
        if cur.rowcount == 0:
            console.print(f"[red]No such source[/red]: {source_id}")
            raise typer.Exit(code=1)
    console.print(f"Disabled source {source_id}.")


def sources_purge(
    source: list[int] = SOURCE_OPTION,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show count without deleting."),
):
    """Remove invalid posts below the minimum word count."""
    settings = common.load_settings()
    db = _db()
    with session(db) as conn:
        params: list = [int(settings.min_word_count)]
        where = "word_count < ?"
        if source:
            placeholders = ",".join("?" for _ in source)
            where += f" AND source_id IN ({placeholders})"
            params.extend(source)
        if dry_run:
            row = q1(conn, f"SELECT COUNT(*) AS cnt FROM posts WHERE {where}", params)
            count = int(row["cnt"] if row else 0)
            console.print(f"Invalid posts found: [bold]{count}[/bold]")
            raise typer.Exit(code=0)
        cur = conn.execute(f"DELETE FROM posts WHERE {where}", tuple(params))
        console.print(f"Purged posts: [bold]{cur.rowcount}[/bold]")


def sources_test(url: str = typer.Argument(..., help="RSS/Atom feed URL")):
    """Quick validation: parse feed and show the first 5 entries."""
    try:
        entries = parse_feed(url)[:5]
    except Exception as e:
        console.print(f"[red]Failed[/red]: {e}")
        raise typer.Exit(code=1) from e

    if not entries:
        console.print("[yellow]No entries found.[/yellow]")
        raise typer.Exit(code=0)

    console.print(f"[bold]Top entries for[/bold] {url}")
    for i, e in enumerate(entries, start=1):
        console.print(f"{i}. {e.title}")
        console.print(f"   {e.url}")
        if e.published:
            console.print(f"   published: {e.published}")
        console.print()


def sources_autofill(
    source_id: int | None = typer.Option(None, "--id", help="Only update this source id"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing name/tags."),
):
    """Auto-fill missing source names and tags using feed metadata and LLM tags."""
    settings = common.load_settings()
    db = _db()
    with session(db) as conn:
        if source_id is None:
            rows = qall(conn, "SELECT * FROM sources ORDER BY id")
        else:
            rows = qall(conn, "SELECT * FROM sources WHERE id=?", (int(source_id),))
        if not rows:
            console.print("[yellow]No sources found.[/yellow]")
            raise typer.Exit(code=0)

        updated = 0
        for row in rows:
            res = autofill_source(
                conn,
                settings,
                source_id=int(row["id"]),
                url=str(row["url"]),
                name=str(row["name"] or ""),
                tags=str(row["tags"] or ""),
                force=force,
            )
            for warning in res.warnings:
                console.print(f"[yellow]Warn[/yellow] {warning}")
            if res.name is None and res.tags is None:
                continue
            conn.execute(
                "UPDATE sources SET name=COALESCE(?, name), tags=COALESCE(?, tags) WHERE id=?",
                (res.name, res.tags, int(row["id"])),
            )
            updated += 1
    console.print(f"Updated sources: [bold]{updated}[/bold]")
