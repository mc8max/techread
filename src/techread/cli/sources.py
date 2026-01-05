from __future__ import annotations

import typer

from techread.cli import common
from techread.cli.common import SOURCE_OPTION, _db, console
from techread.db import exec_, q1, qall, session
from techread.digest.render import print_sources
from techread.ingest.rss import parse_feed
from techread.sources.auto import autofill_source
from techread.utils.time import now_utc_iso


def sources_list():
    """List all RSS/Atom sources in the database.

    This command displays all configured sources with their details including:
    - Source ID
    - Name (or URL if not set)
    - URL
    - Type (currently always 'rss')
    - Weight (ranking priority)
    - Tags
    - Enabled status
    - Creation timestamp
    """
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
    """Add an RSS/Atom feed source to the database.

    This command adds a new RSS or Atom feed source to the database. It can:
    - Add a source with a custom name and tags
    - Automatically fill in missing name/tags using feed metadata and LLM
    - Set a weight for ranking sources
    - Enable the source immediately upon creation

    Parameters:
        url (str): The RSS/Atom feed URL to add
        name (str, optional): Display name for the source. If not provided,
                              the URL will be used as the name
        weight (float): Ranking priority for this source (default: 1.0)
        tags (str): Comma-separated list of tags for categorization

    Examples:
        # Add a source with default settings
        techread sources add https://example.com/rss

        # Add a source with custom name and tags
        techread sources add https://example.com/rss --name "Example Feed" --tags "tech,blog" --weight 2.0
    """
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
    """Remove a source from the database.

    This command removes a source from the database. It does not delete
    already-fetched posts associated with this source.

    Parameters:
        source_id (int): The ID of the source to remove

    Examples:
        # Remove a source by ID
        techread sources remove 123
    """
    db = _db()
    with session(db) as conn:
        cur = conn.execute("DELETE FROM sources WHERE id=?", (int(source_id),))
        if cur.rowcount == 0:
            console.print(f"[red]No such source[/red]: {source_id}")
            raise typer.Exit(code=1)
    console.print(f"Removed source {source_id}.")


def sources_enable(source_id: int = typer.Argument(..., help="Source id")):
    """Enable a source in the database.

    This command enables a source that was previously disabled. The source
    will be included in future feed fetching operations.

    Parameters:
        source_id (int): The ID of the source to enable

    Examples:
        # Enable a source by ID
        techread sources enable 123
    """
    db = _db()
    with session(db) as conn:
        cur = conn.execute("UPDATE sources SET enabled=1 WHERE id=?", (int(source_id),))
        if cur.rowcount == 0:
            console.print(f"[red]No such source[/red]: {source_id}")
            raise typer.Exit(code=1)
    console.print(f"Enabled source {source_id}.")


def sources_disable(source_id: int = typer.Argument(..., help="Source id")):
    """Disable a source in the database.

    This command disables a source, preventing it from being included in
    future feed fetching operations.

    Parameters:
        source_id (int): The ID of the source to disable

    Examples:
        # Disable a source by ID
        techread sources disable 123
    """
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
    """Remove posts that don't meet the minimum word count threshold.

    This command removes posts from the database that have fewer words
    than the configured minimum word count. It can be run in dry-run mode
    to first see how many posts would be removed.

    Parameters:
        source (list[int], optional): Limit purge to specific source IDs
        dry_run (bool): Show count of posts that would be purged without deleting them

    Examples:
        # Purge posts from all sources below minimum word count
        techread sources purge

        # Dry-run to see how many posts would be purged
        techread sources purge --dry-run

        # Purge posts from specific source(s)
        techread sources purge --source 123 --source 456
    """
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
    """Quick validation: parse feed and show the first 5 entries.

    This command quickly validates an RSS/Atom feed by parsing it and
    displaying the first 5 entries. It's useful for testing if a feed
    is accessible and properly formatted.

    Parameters:
        url (str): The RSS/Atom feed URL to test

    Examples:
        # Test a feed
        techread sources test https://example.com/rss

        # Test a feed with invalid URL (will show error)
        techread sources test https://invalid-feed.com/rss
    """
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
    """Auto-fill missing source names and tags using feed metadata and LLM tags.

    This command automatically fills in missing source names and tags by:
    - Extracting metadata from the RSS/Atom feed
    - Using LLM to generate relevant tags (if configured)
    - Updating sources in the database

    Parameters:
        source_id (int, optional): Only update this specific source ID.
                                   If not provided, updates all sources.
        force (bool): Overwrite existing name/tags with new values

    Examples:
        # Auto-fill all sources
        techread sources autofill

        # Auto-fill a specific source
        techread sources autofill --id 123

        # Force overwrite of existing values
        techread sources autofill --force
    """
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
