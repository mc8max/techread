from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()


def print_sources(rows: list[dict[str, Any]]) -> None:
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

        t.add_row(str(i), str(p["id"]), state[:1].upper(), f"{score:.3f}", str(mins), str(p["title"]), why)
    console.print(t)


def print_digest(posts: list[dict[str, Any]]) -> None:
    console.print("[bold]Today's techread digest[/bold]")
    for i, p in enumerate(posts, start=1):
        wc = int(p.get("word_count") or 0)
        mins = max(1, int(round(wc / 220.0))) if wc else 1
        line = Text(f"#{i} [{mins}m] ", style="bold")
        line.append(str(p["title"]))
        console.print(line)
        if p.get("one_liner"):
            console.print(f"  • {p['one_liner']}")
        console.print(f"  id={p['id']}  {p['url']}")
        console.print()
