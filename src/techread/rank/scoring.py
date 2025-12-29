from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..utils.time import parse_datetime_iso
from ..utils.text import contains_any


@dataclass(frozen=True)
class ScoreResult:
    """Container for scoring results with detailed breakdown.

    Attributes:
        score: The final computed score (0.0 to 1.0)
        breakdown: Dictionary containing detailed scoring components including
                   freshness, source weight, topic relevance, and length penalty.
    """
    score: float
    breakdown: dict[str, Any]


def _freshness(age_hours: float) -> float:
    """Calculate freshness score based on age in hours.

    Uses exponential decay with a half-life of approximately 25.6 hours
    (36 hours / ln(2)). Freshness ranges from 1.0 (brand new) to near 0
    for very old content.

    Args:
        age_hours: Age of content in hours (0 = brand new)

    Returns:
        Freshness score between 0.0 and 1.0
    """
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
    """Calculate a comprehensive score for a blog post or article.

    The scoring algorithm combines multiple factors:
    - Freshness (40%): Exponential decay based on publication time
    - Source weight (20%): Quality/reputation of the source
    - Topic relevance (70%): How well the content matches search topics
    - Length penalty (-30%): Penalty for very long articles

    Args:
        now: Current datetime for calculating age
        published_at_iso: ISO format publication datetime string
        source_weight: Source quality weight (0.0 to 1.0)
        title: Article title for topic matching
        content_text: Full article text (used first 2000 chars)
        word_count: Total word count of the article
        topics: List of search topics to match against

    Returns:
        ScoreResult containing the final score (0.0-1.0) and detailed breakdown

    Note:
        - Topic hits in title count more than in content
        - Maximum of 4 topic hits (capped at 0.6 score)
        - Length penalty applies to articles >2500 words
    """
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
