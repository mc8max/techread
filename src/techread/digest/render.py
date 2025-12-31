from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

from techread.utils.time import parse_datetime_iso

console = Console()


def print_sources(rows: list[dict[str, Any]]) -> None:
    """Print a formatted table of RSS sources with their configuration.

    Args:
        rows: List of dictionaries containing source information. Each dictionary should
              contain at least the following keys:
              - id: Unique identifier for the source
              - enabled: 1 if enabled, 0 if disabled
              - weight: Weighting factor for the source (float)
              - name: Display name of the source
              - url: URL of the RSS feed
              - tags: Optional tags associated with the source (string)

    Displays a Rich table showing each source's id, enabled status (✅/—),
    weight, name, URL, and tags. Enabled sources are marked with a checkmark.
    """
    t = Table(title="Sources")
    t.add_column("id", justify="right")
    t.add_column("enabled", justify="center")
    t.add_column("weight", justify="right")
    t.add_column("name")
    t.add_column("url")
    t.add_column("tags")
    for r in rows:
        t.add_row(
            str(r["id"]),
            "✅" if int(r["enabled"]) == 1 else "—",
            f'{float(r["weight"]):.2f}',
            str(r["name"]),
            str(r["url"]),
            str(r.get("tags", "")),
        )
    console.print(t)


def print_ranked(posts: list[dict[str, Any]], *, show_breakdown: bool = True) -> None:
    """Print a formatted table of ranked posts with scoring information.

    Args:
        posts: List of dictionaries containing post information. Each dictionary should
               contain at least the following keys:
               - id: Unique identifier for the post
               - title: Title of the post
               - word_count: Word count for reading time calculation
               - score: Scoring value (float)
               - read_state: Optional read state (e.g., "unread", "reading", "read")
               - breakdown_json: Optional JSON string containing scoring breakdown
                 with keys like 'freshness', 'topic_hits', and 'length_penalty'

        show_breakdown: If True, includes a column showing the scoring breakdown.
                        Defaults to True.

    Displays a Rich table showing each post's rank, id, read state, score,
    estimated reading time in minutes, title, and (optionally) the scoring
    breakdown explaining why the post was scored that way.
    """
    t = Table(title="Ranked posts")
    t.add_column("rank", justify="right")
    t.add_column("id", justify="right")
    t.add_column("state", justify="center")
    t.add_column("score", justify="right")
    t.add_column("mins", justify="right")
    t.add_column("title")
    if show_breakdown:
        t.add_column("why")

    for i, p in enumerate(posts, start=1):
        wc = int(p.get("word_count") or 0)
        mins = max(1, int(round(wc / 220.0))) if wc else 0
        state = str(p.get("read_state") or "unread")
        score = float(p.get("score") or 0.0)
        why = ""
        if show_breakdown:
            try:
                b = json.loads(p.get("breakdown_json") or "{}")
                why = f"fresh {b.get('freshness')} | topic {b.get('topic_hits')} | len -{b.get('length_penalty')}"
            except Exception:
                why = ""

        t.add_row(
            str(i), str(p["id"]), state[:1].upper(), f"{score:.3f}", str(mins), str(p["title"]), why
        )
    console.print(t)


def print_digest(posts: list[dict[str, Any]]) -> None:
    """Print a compact digest of posts for quick browsing.

    Args:
        posts: List of dictionaries containing post information. Each dictionary should
               contain at least the following keys:
               - id: Unique identifier for the post
               - title: Title of the post
               - url: URL to the full article
               - author: Author of the post (may be empty)
               - published_at: Published timestamp (ISO string)
               - word_count: Word count for reading time calculation
               - one_liner: Optional short summary/description

    Displays a concise list of posts with:
    - Rank number
    - Estimated reading time in minutes
    - Post title (bold)
    - Optional one-liner summary
    - Post URL, author, and published time

    This format is optimized for quick scanning of multiple posts.
    """
    console.print("[bold]Today's techread digest[/bold]")
    for i, p in enumerate(posts, start=1):
        wc = int(p.get("word_count") or 0)
        mins = max(1, int(round(wc / 220.0))) if wc else 1
        line = Text(f"#{i} [{mins}m] ", style="bold")
        line.append(str(p["title"]))
        console.print(line)
        author = str(p.get("author") or "").strip() or "-"
        published_raw = str(p.get("published_at") or "").strip()
        if published_raw:
            try:
                published = parse_datetime_iso(published_raw).strftime("%Y-%m-%d")
            except Exception:
                published = published_raw
        else:
            published = "-"
        console.print(f"  {p['url']}")
        console.print(f"  author={author}  published={published}")
        console.print(f"  id={p['id']}")
        if p.get("one_liner"):
            console.print("  ---")
            console.print(f"  • {p['one_liner']}")
        console.print()
