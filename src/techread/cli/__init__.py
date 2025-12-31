from __future__ import annotations

import typer

from .common import _db, _now, _parse_or_fallback, console, load_settings  # noqa: F401
from .posts import digest, fetch, mark, open, rank, summarize
from .sources import (
    sources_add,
    sources_autofill,
    sources_disable,
    sources_enable,
    sources_list,
    sources_purge,
    sources_remove,
    sources_test,
)

app = typer.Typer(
    add_completion=False, help="techread: fetch, rank, and summarize technical blogs locally."
)
sources_app = typer.Typer(help="Manage sources (RSS/Atom).")
app.add_typer(sources_app, name="sources")

app.command()(fetch)
app.command()(rank)
app.command()(digest)
app.command()(summarize)
app.command()(open)
app.command()(mark)

sources_app.command("list")(sources_list)
sources_app.command("add")(sources_add)
sources_app.command("remove")(sources_remove)
sources_app.command("enable")(sources_enable)
sources_app.command("disable")(sources_disable)
sources_app.command("purge")(sources_purge)
sources_app.command("test")(sources_test)
sources_app.command("autofill")(sources_autofill)

__all__ = ["app", "_db", "_now", "_parse_or_fallback", "console", "load_settings"]
