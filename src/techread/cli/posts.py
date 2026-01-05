from __future__ import annotations

import webbrowser
from datetime import timedelta
from typing import Annotated

import typer

from techread.cli import common
from techread.cli.common import (
    SOURCE_OPTION,
    TAG_OPTION,
    _db,
    _log_invalid_post,
    _now,
    _parse_or_fallback,
    console,
)
from techread.cli.filters import _build_source_filters
from techread.db import exec_, q1, qall, session, upsert_score, upsert_summary
from techread.digest.render import print_digest, print_ranked
from techread.ingest.extract import extract_text
from techread.ingest.fetch import fetch_html
from techread.ingest.rss import parse_feed
from techread.rank.scoring import score_post
from techread.summarize.llm import LLMSettings, Mode, canonical_mode
from techread.summarize.llm import summarize as llm_summarize
from techread.utils.text import stable_hash
from techread.utils.time import iso_from_dt, now_utc_iso, parse_datetime_iso


def fetch(
    limit_per_source: int = typer.Option(50, help="Max entries to consider per source per run.")
):
    """Fetch new posts from enabled sources, extract readable text, and store locally."""
    settings = common.load_settings()
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

                extract_error = None
                try:
                    html = fetch_html(e.url, settings.cache_dir)
                    ext = extract_text(html)
                    content_text = ext.text
                    word_count = ext.word_count
                    content_hash = stable_hash(content_text) if content_text else ""
                except Exception as ex:
                    extract_error = ex
                    console.print(f"[yellow]Warn[/yellow] could not fetch/extract: {e.url} ({ex})")

                if int(word_count or 0) < int(settings.min_word_count):
                    reason = (
                        f"below_min_word_count({settings.min_word_count})"
                        if extract_error is None
                        else f"extract_failed({extract_error})"
                    )
                    _log_invalid_post(
                        settings,
                        source_id=int(s["id"]),
                        source_name=name,
                        url=e.url,
                        title=e.title or e.url,
                        word_count=int(word_count or 0),
                        reason=reason,
                    )
                    continue

                exec_(
                    conn,
                    "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
                    (
                        int(s["id"]),
                        e.title or e.url,
                        e.url,
                        author,
                        published_iso,
                        fetched_at,
                        content_text,
                        content_hash,
                        int(word_count),
                    ),
                )
                new_posts += 1

        console.print(f"Done. New posts added: [bold]{new_posts}[/bold]")


def rank(
    today: bool = typer.Option(True, "--today/--all", help="Rank only recent posts (default)."),
    top: int | None = typer.Option(None, help="Show top N ranked posts."),
    include_read: bool = typer.Option(False, help="Include already read posts."),
    hours: int = typer.Option(48, help="Recent window for --today ranking."),
    source: list[int] = SOURCE_OPTION,
    tag: list[str] = TAG_OPTION,
):
    """Compute ranking scores for posts and print a ranked list with explanations."""
    settings = common.load_settings()
    db = _db()
    now = _now()
    since = now - timedelta(hours=max(1, int(hours)))

    with session(db) as conn:
        where_sql, params = _build_source_filters(
            source=source,
            tag=tag,
            today=today,
            include_read=include_read,
            since_iso=iso_from_dt(since),
        )

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
            "JOIN sources s ON p.source_id=s.id "
            f"{where_sql} "
            "ORDER BY sc.score DESC "
            "LIMIT ?",
            (*params, top),
        )
        posts = [dict(x) for x in ranked]
        print_ranked(posts, show_breakdown=True)


def digest(
    today: bool = typer.Option(True, "--today/--all", help="Use recent posts (default)."),
    top: int | None = typer.Option(None, help="Top N items."),
    minutes: int = typer.Option(0, help="Time budget in minutes (0 = no budget)."),
    auto_summarize: bool = typer.Option(
        True, help="Generate missing 1-line summaries for the digest (uses LM Studio)."
    ),
    source: list[int] = SOURCE_OPTION,
    tag: list[str] = TAG_OPTION,
):
    """Print a busy-reader digest: ranked titles + optional 1-line takeaways."""
    settings = common.load_settings()
    db = _db()

    now = _now()
    since = now - timedelta(hours=48)

    with session(db) as conn:
        # Score missing posts in the window
        where_sql, params = _build_source_filters(
            source=source,
            tag=tag,
            today=today,
            include_read=False,
            since_iso=iso_from_dt(since),
        )

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
            "SELECT p.id, p.title, p.url, p.author, p.published_at, p.word_count, "
            "p.read_state, p.content_text, p.content_hash, sc.score "
            "FROM posts p JOIN scores sc ON p.id=sc.post_id "
            "JOIN sources s ON p.source_id=s.id "
            f"{where_sql} "
            "ORDER BY sc.score DESC "
            "LIMIT ?",
            (*params, top * 3),
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
            llm_settings = LLMSettings(model=settings.llm_model, temperature=0.5)
            for it in items:
                if not it.get("content_text"):
                    it["one_liner"] = ""
                    continue
                ch = it.get("content_hash") or stable_hash(it["content_text"])
                it["content_hash"] = ch
                existing = q1(
                    conn,
                    "SELECT summary_text FROM summaries WHERE post_id=? AND mode=? AND model=? AND content_hash=?",
                    (int(it["id"]), "short", settings.llm_model, ch),
                )
                if existing:
                    one = str(existing["summary_text"]).strip()
                else:
                    try:
                        one = llm_summarize(
                            llm_settings,
                            mode="short",
                            title=it["title"],
                            url=it["url"],
                            text=it["content_text"],
                        )
                        upsert_summary(
                            conn, int(it["id"]), "short", settings.llm_model, ch, one, now_utc_iso()
                        )
                    except Exception:
                        one = ""
                it["one_liner"] = one.splitlines()[0].strip() if one else ""
        else:
            for it in items:
                it["one_liner"] = ""

        print_digest(items)


def summarize(
    post_id: int = typer.Argument(..., help="Post id"),
    mode: Annotated[
        Mode,
        typer.Option(help="Summary mode: short|bullets|takeaways|comprehensive (aliases: s|b|t|c)"),
    ] = "takeaways",
):
    """Summarize a stored post using the configured LLM. Cached by content hash."""
    settings = common.load_settings()
    db = _db()
    with session(db) as conn:
        r = q1(conn, "SELECT * FROM posts WHERE id=?", (int(post_id),))
        if not r:
            console.print(f"[red]No such post[/red]: {post_id}")
            raise typer.Exit(code=1)

        title = str(r["title"])
        url = str(r["url"])
        author = str(r["author"] or "").strip() or "-"
        published_raw = str(r["published_at"] or "").strip()
        if published_raw:
            try:
                published = parse_datetime_iso(published_raw).strftime("%Y-%m-%d")
            except Exception:
                published = published_raw
        else:
            published = "-"

        console.print(f"[bold]{title}[/bold]")
        console.print(f"  {url}")
        console.print(f"  author={author}  published={published}")
        console.print(f"  id={post_id}")
        console.print("  ---")

        content = str(r["content_text"] or "")
        if len(content) < 200:
            console.print(
                "[yellow]Not enough extracted text to summarize.[/yellow] Try `techread open <id>`."
            )
            raise typer.Exit(code=1)

        mode = canonical_mode(mode)
        ch = str(r["content_hash"] or "") or stable_hash(content)
        model = settings.llm_model
        existing = q1(
            conn,
            "SELECT summary_text FROM summaries WHERE post_id=? AND mode=? AND model=? AND content_hash=?",
            (int(post_id), mode, model, ch),
        )
        if existing:
            console.print(str(existing["summary_text"]))
            raise typer.Exit(code=0)

        llm_settings = LLMSettings(model=settings.llm_model, temperature=0.5)
        try:
            out = llm_summarize(
                llm_settings, mode=mode, title=str(r["title"]), url=str(r["url"]), text=content
            )
        except Exception as e:
            console.print(f"[red]Summarization failed[/red]. Is LM Studio running? ({e})")
            raise typer.Exit(code=1) from e

        upsert_summary(conn, int(post_id), mode, model, ch, out, now_utc_iso())
        console.print(out)


def open(post_id: int = typer.Argument(..., help="Post id")):
    """Open a post in your default browser."""
    db = _db()
    with session(db) as conn:
        r = q1(conn, "SELECT url FROM posts WHERE id=?", (int(post_id),))
        if not r:
            console.print(f"[red]No such post[/red]: {post_id}")
            raise typer.Exit(code=1)
        webbrowser.open(str(r["url"]))


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
        console.print(
            "[red]Invalid state[/red]: choose exactly one of --read/--saved/--skip/--unread."
        )
        raise typer.Exit(code=1)
    state = selected[0]

    db = _db()
    with session(db) as conn:
        cur = conn.execute("UPDATE posts SET read_state=? WHERE id=?", (state, int(post_id)))
        if cur.rowcount == 0:
            console.print(f"[red]No such post[/red]: {post_id}")
            raise typer.Exit(code=1)
        console.print(f"Marked {post_id} as [bold]{state}[/bold].")
