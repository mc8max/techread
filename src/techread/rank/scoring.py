from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..utils.time import parse_datetime_iso
from ..utils.text import contains_any


@dataclass(frozen=True)
class ScoreResult:
    score: float
    breakdown: dict[str, Any]


def _freshness(age_hours: float) -> float:
    return float(math.exp(-age_hours / 36.0))


def score_post(
    *,
    now: datetime,
    published_at_iso: str,
    source_weight: float,
    title: str,
    content_text: str,
    word_count: int,
    topics: list[str],
) -> ScoreResult:
    try:
        published_dt = parse_datetime_iso(published_at_iso)
    except Exception:
        published_dt = now

    age_hours = max(0.0, (now - published_dt).total_seconds() / 3600.0)
    freshness = _freshness(age_hours)

    topic_hits = contains_any(title, topics) + contains_any(content_text[:2000], topics)
    topic_score = min(topic_hits * 0.15, 0.6)

    length_penalty = min((word_count / 2500.0), 1.0) * 0.30

    score = (
        1.00 * freshness
        + 0.20 * float(source_weight)
        + 0.70 * float(topic_score)
        - 1.00 * float(length_penalty)
    )

    breakdown = {
        "age_hours": round(age_hours, 2),
        "freshness": round(freshness, 4),
        "source_weight": round(float(source_weight), 3),
        "topic_hits": int(topic_hits),
        "topic_score": round(float(topic_score), 3),
        "word_count": int(word_count),
        "length_penalty": round(float(length_penalty), 3),
        "final": round(float(score), 4),
    }
    return ScoreResult(score=float(score), breakdown=breakdown)
