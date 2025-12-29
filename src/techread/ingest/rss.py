from __future__ import annotations

from dataclasses import dataclass
import feedparser


@dataclass(frozen=True)
class FeedEntry:
    title: str
    url: str
    author: str
    published: str


def parse_feed(url: str) -> list[FeedEntry]:
    feed = feedparser.parse(url)
    entries: list[FeedEntry] = []
    for e in feed.entries or []:
        link = getattr(e, "link", None) or ""
        title = getattr(e, "title", None) or link
        author = getattr(e, "author", None) or ""
        published = getattr(e, "published", None) or getattr(e, "updated", None) or ""
        entries.append(
            FeedEntry(
                title=str(title).strip(),
                url=str(link).strip(),
                author=str(author).strip(),
                published=str(published).strip(),
            )
        )

    # Deduplicate by URL preserving order
    seen = set()
    out: list[FeedEntry] = []
    for it in entries:
        if it.url and it.url not in seen:
            out.append(it)
            seen.add(it.url)
    return out
