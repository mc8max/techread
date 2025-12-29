from __future__ import annotations

from dataclasses import dataclass
import trafilatura

from ..utils.text import normalize_whitespace


@dataclass(frozen=True)
class Extracted:
    text: str
    word_count: int


def extract_text(html: str) -> Extracted:
    text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    text = normalize_whitespace(text)
    wc = len(text.split()) if text else 0
    return Extracted(text=text, word_count=wc)
