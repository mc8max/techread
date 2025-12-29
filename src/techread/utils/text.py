from __future__ import annotations

import hashlib
import re

_WS_RE = re.compile(r"\s+")


def stable_hash(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def normalize_whitespace(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip())


def contains_any(text: str, needles: list[str]) -> int:
    t = (text or "").lower()
    return sum(1 for n in needles if n and n.lower() in t)
