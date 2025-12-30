from __future__ import annotations

import webbrowser
from datetime import datetime, timezone, timedelta

import typer
from rich.console import Console

from .config import load_settings
from .db import DB, init_db, session, q1, qall, exec_, upsert_score, upsert_summary
from .utils.time import now_utc_iso, parse_datetime_iso, iso_from_dt
from .utils.text import stable_hash
from .ingest.rss import parse_feed
from .ingest.fetch import fetch_html
from .ingest.extract import extract_text
from .rank.scoring import score_post
from .summarize.ollama import OllamaSettings, summarize as ollama_summarize, Mode
from .digest.render import print_sources, print_ranked, print_digest

app = typer.Typer(add_completion=False, help="techread: fetch, rank, and summarize technical blogs locally.")
sources_app = typer.Typer(help="Manage sources (RSS/Atom).")
app.add_typer(sources_app, name="sources")

console = Console()


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


@app.command()
def fetch(limit_per_source: int = typer.Option(50, help="Max entries to consider per source per run.")):
    """Fetch new posts from enabled sources, extract readable text, and store locally."""
    settings = load_settings()
    db = _db()
    with session(db) as conn:
        sources = qall(conn, "SELECT * FROM sources WHERE enabled=1 ORDER BY id")
        if not sources:
            console.print("No sources enabled. Add one with: techread sources add <rss_url>")
            raise typer.Exit(code=1)

        new_posts = 0
        for s in sources:
            url = str(s["url"])
            name = str(s["name"])
            console.print(f"[bold]Fetching[/bold] {name}: {url}")
            try:
                entries = parse_feed(url)[: max(1, int(limit_per_source))]
            except Exception as e:
                console.print(f"[red]Failed to parse feed[/red]: {e}")
                continue

            for e in entries:
                if not e.url:
                    continue
                if q1(conn, "SELECT id FROM posts WHERE url=?", (e.url,)):
                    continue

                published_iso = _parse_or_fallback(e.published)
                fetched_at = now_utc_iso()
                author = e.author or ""

                content_text = ""
                word_count = 0
                content_hash = ""

                try:
                    html = fetch_html(e.url, settings.cache_dir)
                    ext = extract_text(html)
                    content_text = ext.text
                    word_count = ext.word_count
                    content_hash = stable_hash(content_text) if content_text else ""
                except Exception as ex:
                    console.print(f"[yellow]Warn[/yellow] could not fetch/extract: {e.url} ({ex})")

                exec_(
                    conn,
                    "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
                    (int(s["id"]), e.title or e.url, e.url, author, published_iso, fetched_at, content_text, content_hash, int(word_count)),
                )
                new_posts += 1

        console.print(f"Done. New posts added: [bold]{new_posts}[/bold]")


@app.command()
def rank(
    today: bool = typer.Option(True, "--today/--all", help="Rank only recent posts (default)."),
    top: int | None = typer.Option(None, help="Show top N ranked posts."),
    include_read: bool = typer.Option(False, help="Include already read posts."),
    hours: int = typer.Option(48, help="Recent window for --today ranking."),
):
    """Compute ranking scores for posts and print a ranked list with explanations."""
    settings = load_settings()
    db = _db()
    now = _now()
    since = now - timedelta(hours=max(1, int(hours)))

    with session(db) as conn:
        where = []
        params: list = []
        if today:
            where.append("published_at >= ?")
            params.append(iso_from_dt(since))
        if not include_read:
            where.append("read_state != 'read'")
        where_sql = " AND ".join(where)
        if where_sql:
            where_sql = "WHERE " + where_sql

        rows = qall(
            conn,
            f"SELECT p.*, s.weight AS source_weight FROM posts p JOIN sources s ON p.source_id=s.id {where_sql} ORDER BY p.published_at DESC",
            params,
        )
        if not rows:
            console.print("No posts to rank (try `techread fetch` first).")
            raise typer.Exit(code=0)

        scored_at = now_utc_iso()
        for r in rows:
            res = score_post(
                now=now,
                published_at_iso=str(r["published_at"]),
                source_weight=float(r["source_weight"]),
                title=str(r["title"]),
                content_text=str(r["content_text"] or ""),
                word_count=int(r["word_count"] or 0),
                topics=settings.topics,
            )
            upsert_score(conn, int(r["id"]), scored_at, res.score, res.breakdown)

        if top is None:
            top = settings.default_top_n
        top = max(1, int(top))

        ranked = qall(
            conn,
            "SELECT p.id, p.title, p.url, p.word_count, p.read_state, sc.score, sc.breakdown_json "
            "FROM posts p JOIN scores sc ON p.id=sc.post_id "
            "ORDER BY sc.score DESC "
            "LIMIT ?",
            (top,),
        )
        posts = [dict(x) for x in ranked]
        print_ranked(posts, show_breakdown=True)


@app.command()
def digest(
    today: bool = typer.Option(True, "--today/--all", help="Use recent posts (default)."),
    top: int | None = typer.Option(None, help="Top N items."),
    minutes: int = typer.Option(0, help="Time budget in minutes (0 = no budget)."),
    auto_summarize: bool = typer.Option(True, help="Generate missing 1-line summaries for the digest (uses Ollama)."),
):
    """Print a busy-reader digest: ranked titles + optional 1-line takeaways."""
    settings = load_settings()
    db = _db()

    now = _now()
    since = now - timedelta(hours=48)

    with session(db) as conn:
        # Score missing posts in the window
        where = []
        params: list = []
        if today:
            where.append("published_at >= ?")
            params.append(iso_from_dt(since))
        where.append("read_state != 'read'")
        where_sql = " AND ".join(where)
        if where_sql:
            where_sql = "WHERE " + where_sql

        rows = qall(
            conn,
            f"SELECT p.*, s.weight AS source_weight FROM posts p JOIN sources s ON p.source_id=s.id {where_sql}",
            params,
        )
        scored_at = now_utc_iso()
        for r in rows:
            if q1(conn, "SELECT score FROM scores WHERE post_id=?", (int(r["id"]),)):
                continue
            res = score_post(
                now=now,
                published_at_iso=str(r["published_at"]),
                source_weight=float(r["source_weight"]),
                title=str(r["title"]),
                content_text=str(r["content_text"] or ""),
                word_count=int(r["word_count"] or 0),
                topics=settings.topics,
            )
            upsert_score(conn, int(r["id"]), scored_at, res.score, res.breakdown)

        if top is None:
            top = settings.default_top_n
        top = max(1, int(top))

        ranked = qall(
            conn,
            "SELECT p.id, p.title, p.url, p.word_count, p.read_state, p.content_text, p.content_hash, sc.score "
            "FROM posts p JOIN scores sc ON p.id=sc.post_id "
            "WHERE p.read_state != 'read' "
            "ORDER BY sc.score DESC "
            "LIMIT ?",
            (top * 3,),
        )
        items = [dict(x) for x in ranked]

        # Time budget (greedy by score/minutes)
        if minutes and int(minutes) > 0:
            budget = int(minutes)
            for it in items:
                wc = int(it.get("word_count") or 0)
                it["_mins"] = max(1, int(round(wc / 220.0))) if wc else 1
                it["_ratio"] = float(it["score"]) / float(it["_mins"])
            items.sort(key=lambda x: x["_ratio"], reverse=True)

            chosen = []
            remaining = budget
            for it in items:
                if it["_mins"] <= remaining:
                    chosen.append(it)
                    remaining -= it["_mins"]
                if remaining <= 0 or len(chosen) >= top:
                    break
            items = chosen
        else:
            items = items[:top]

        # 1-line summaries (mode=short)
        if auto_summarize:
            oll = OllamaSettings(host=settings.ollama_host, model=settings.ollama_model)
            for it in items:
                if not it.get("content_text"):
                    it["one_liner"] = ""
                    continue
                ch = it.get("content_hash") or stable_hash(it["content_text"])
                it["content_hash"] = ch
                existing = q1(
                    conn,
                    "SELECT summary_text FROM summaries WHERE post_id=? AND mode=? AND model=? AND content_hash=?",
                    (int(it["id"]), "short", settings.ollama_model, ch),
                )
                if existing:
                    one = str(existing["summary_text"]).strip()
                else:
                    try:
                        one = ollama_summarize(
                            oll, mode="short", title=it["title"], url=it["url"], text=it["content_text"]
                        )
                        upsert_summary(conn, int(it["id"]), "short", settings.ollama_model, ch, one, now_utc_iso())
                    except Exception:
                        one = ""
                it["one_liner"] = one.splitlines()[0].strip() if one else ""
        else:
            for it in items:
                it["one_liner"] = ""

        print_digest(items)


@app.command()
def summarize(
    post_id: int = typer.Argument(..., help="Post id"),
    mode: Mode = typer.Option("takeaways", help="Summary mode: short|bullets|takeaways"),
):
    """Summarize a stored post using Ollama. Cached by content hash."""
    settings = load_settings()
    db = _db()
    with session(db) as conn:
        r = q1(conn, "SELECT * FROM posts WHERE id=?", (int(post_id),))
        if not r:
            console.print(f"[red]No such post[/red]: {post_id}")
            raise typer.Exit(code=1)

        content = str(r["content_text"] or "")
        if len(content) < 200:
            console.print("[yellow]Not enough extracted text to summarize.[/yellow] Try `techread open <id>`.")
            raise typer.Exit(code=1)

        ch = str(r["content_hash"] or "") or stable_hash(content)
        model = settings.ollama_model
        existing = q1(
            conn,
            "SELECT summary_text FROM summaries WHERE post_id=? AND mode=? AND model=? AND content_hash=?",
            (int(post_id), mode, model, ch),
        )
        if existing:
            console.print(str(existing["summary_text"]))
            raise typer.Exit(code=0)

        oll = OllamaSettings(host=settings.ollama_host, model=model)
        try:
            out = ollama_summarize(oll, mode=mode, title=str(r["title"]), url=str(r["url"]), text=content)
        except Exception as e:
            console.print(f"[red]Summarization failed[/red]. Is Ollama running at {settings.ollama_host}? ({e})")
            raise typer.Exit(code=1)

        upsert_summary(conn, int(post_id), mode, model, ch, out, now_utc_iso())
        console.print(out)


@app.command()
def open(post_id: int = typer.Argument(..., help="Post id")):
    """Open a post in your default browser."""
    db = _db()
    with session(db) as conn:
        r = q1(conn, "SELECT url FROM posts WHERE id=?", (int(post_id),))
        if not r:
            console.print(f"[red]No such post[/red]: {post_id}")
            raise typer.Exit(code=1)
        webbrowser.open(str(r["url"]))


@app.command()
def mark(
    post_id: int = typer.Argument(..., help="Post id"),
    read: bool = typer.Option(False, "--read", help="Mark as read."),
    saved: bool = typer.Option(False, "--saved", help="Mark as saved."),
    skip: bool = typer.Option(False, "--skip", help="Mark as skipped."),
    unread: bool = typer.Option(False, "--unread", help="Mark as unread."),
):
    """Update read state for a post."""
    choices = [("read", read), ("saved", saved), ("skip", skip), ("unread", unread)]
    selected = [name for name, enabled in choices if enabled]
    if len(selected) != 1:
        console.print("[red]Invalid state[/red]: choose exactly one of --read/--saved/--skip/--unread.")
        raise typer.Exit(code=1)
    state = selected[0]

    db = _db()
    with session(db) as conn:
        cur = conn.execute("UPDATE posts SET read_state=? WHERE id=?", (state, int(post_id)))
        if cur.rowcount == 0:
            console.print(f"[red]No such post[/red]: {post_id}")
            raise typer.Exit(code=1)
        console.print(f"Marked {post_id} as [bold]{state}[/bold].")


@sources_app.command("list")
def sources_list():
    """List sources."""
    db = _db()
    with session(db) as conn:
        rows = [dict(r) for r in qall(conn, "SELECT * FROM sources ORDER BY id")]
    print_sources(rows)


@sources_app.command("add")
def sources_add(
    url: str = typer.Argument(..., help="RSS/Atom feed URL"),
    name: str | None = typer.Option(None, help="Display name"),
    weight: float = typer.Option(1.0, help="Source weight (ranking prior)"),
    tags: str = typer.Option("", help="Comma-separated tags"),
):
    """Add an RSS/Atom source."""
    db = _db()
    with session(db) as conn:
        nm = name or url
        try:
            exec_(
                conn,
                "INSERT INTO sources(name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, 'rss', ?, ?, 1, ?)",
                (nm, url, float(weight), tags, now_utc_iso()),
            )
        except Exception as e:
            console.print(f"[red]Could not add source[/red]: {e}")
            raise typer.Exit(code=1)
    console.print(f"Added source: [bold]{nm}[/bold]")


@sources_app.command("remove")
def sources_remove(source_id: int = typer.Argument(..., help="Source id")):
    """Remove a source (does not delete already-fetched posts)."""
    db = _db()
    with session(db) as conn:
        cur = conn.execute("DELETE FROM sources WHERE id=?", (int(source_id),))
        if cur.rowcount == 0:
            console.print(f"[red]No such source[/red]: {source_id}")
            raise typer.Exit(code=1)
    console.print(f"Removed source {source_id}.")


@sources_app.command("enable")
def sources_enable(source_id: int = typer.Argument(..., help="Source id")):
    db = _db()
    with session(db) as conn:
        cur = conn.execute("UPDATE sources SET enabled=1 WHERE id=?", (int(source_id),))
        if cur.rowcount == 0:
            console.print(f"[red]No such source[/red]: {source_id}")
            raise typer.Exit(code=1)
    console.print(f"Enabled source {source_id}.")


@sources_app.command("disable")
def sources_disable(source_id: int = typer.Argument(..., help="Source id")):
    db = _db()
    with session(db) as conn:
        cur = conn.execute("UPDATE sources SET enabled=0 WHERE id=?", (int(source_id),))
        if cur.rowcount == 0:
            console.print(f"[red]No such source[/red]: {source_id}")
            raise typer.Exit(code=1)
    console.print(f"Disabled source {source_id}.")


@sources_app.command("test")
def sources_test(url: str = typer.Argument(..., help="RSS/Atom feed URL")):
    """Quick validation: parse feed and show the first 5 entries."""
    try:
        entries = parse_feed(url)[:5]
    except Exception as e:
        console.print(f"[red]Failed[/red]: {e}")
        raise typer.Exit(code=1)

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


if __name__ == "__main__":
    app()
