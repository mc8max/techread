from __future__ import annotations

import re

from techread.summarize.llm import LLMSettings, _strip_thinking, get_lmstudio_llm

_SPLIT_RE = re.compile(r"[,\n;]+")
_MULTI_HYPHEN_RE = re.compile(r"-{2,}")
_NON_TAG_RE = re.compile(r"[^a-z0-9-]+")


def _prompt(
    *,
    feed_title: str,
    feed_subtitle: str,
    entry_titles: list[str],
    entry_snippets: list[str],
) -> str:
    titles = "\n".join(f"- {t}" for t in entry_titles if t) or "- (none)"
    snippets = "\n".join(f"- {s}" for s in entry_snippets if s) or "- (none)"
    return (
        "You generate concise tags for a technical RSS feed.\n"
        "Return 3-5 tags, comma-separated.\n"
        "Rules: lowercase, use hyphens instead of spaces, no more than 5 tags.\n\n"
        f"Feed title: {feed_title}\n"
        f"Feed subtitle: {feed_subtitle}\n\n"
        "Recent entry titles:\n"
        f"{titles}\n\n"
        "Content snippets:\n"
        f"{snippets}\n"
    )


def normalize_tags(raw: str) -> list[str]:
    text = (raw or "").strip().lower()
    if not text:
        return []
    parts = _SPLIT_RE.split(text)
    out: list[str] = []
    seen = set()
    for part in parts:
        token = part.strip()
        if not token:
            continue
        token = token.replace("_", "-").replace(" ", "-")
        token = _NON_TAG_RE.sub("", token)
        token = _MULTI_HYPHEN_RE.sub("-", token).strip("-")
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= 5:
            break
    return out


def generate_tags(
    settings: LLMSettings,
    *,
    feed_title: str,
    feed_subtitle: str,
    entry_titles: list[str],
    entry_snippets: list[str],
) -> str:
    llm = get_lmstudio_llm(settings)
    response = llm.invoke(
        _prompt(
            feed_title=feed_title,
            feed_subtitle=feed_subtitle,
            entry_titles=entry_titles,
            entry_snippets=entry_snippets,
        )
    )
    cleaned = normalize_tags(_strip_thinking(response.content or ""))
    return ",".join(cleaned)
