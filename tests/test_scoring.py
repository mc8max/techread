"""Unit tests for the scoring module."""

from datetime import datetime, timezone

import pytest

from techread.rank.scoring import ScoreResult, _freshness, score_post


class TestFreshness:
    """Test the _freshness function."""

    def test_freshness_new_content(self):
        """Freshness should be 1.0 for brand new content."""
        assert _freshness(0.0) == pytest.approx(1.0, rel=1e-6)

    def test_freshness_very_old_content(self):
        """Freshness should approach 0 for very old content."""
        assert _freshness(100.0) < 0.07
        assert _freshness(200.0) < 0.1


class TestScorePost:
    """Test the score_post function."""

    def test_basic_scoring(self):
        """Test basic scoring with all factors."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.8,
            title="Python Programming Guide",
            content_text="This is a comprehensive guide to Python programming.",
            word_count=1500,
            topics=["python", "programming"],
        )

        assert isinstance(result, ScoreResult)
        assert result.score >= 0.0

        # Check breakdown contains all expected keys
        expected_keys = {
            "age_hours",
            "freshness",
            "source_weight",
            "topic_hits",
            "topic_score",
            "word_count",
            "length_penalty",
            "final",
        }
        assert set(result.breakdown.keys()) == expected_keys

    def test_fresh_content(self):
        """Test scoring for very fresh content."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 11, 59, 0, tzinfo=timezone.utc)  # 1 minute old

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=1.0,
            title="Python 3.11 Features",
            content_text="New features in Python 3.11 include performance improvements and type system enhancements.",
            word_count=2000,
            topics=["python", "3.11"],
        )

        # Fresh content should have high freshness score
        assert result.breakdown["age_hours"] < 0.1
        assert result.breakdown["freshness"] > 0.9

    def test_old_content(self):
        """Test scoring for old content."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2022, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # 1 year old

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.5,
            title="Python 2.7 Migration",
            content_text="Guide to migrating from Python 2.7 to Python 3.",
            word_count=1000,
            topics=["python", "migration"],
        )

        # Old content should have low freshness score
        assert result.breakdown["age_hours"] > 8700
        assert result.breakdown["freshness"] < 0.1

    def test_high_source_weight(self):
        """Test scoring with high source weight."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=1.0,  # High quality source
            title="Python Official Documentation",
            content_text="Official Python documentation provides comprehensive information.",
            word_count=5000,
            topics=["python", "documentation"],
        )

        assert result.breakdown["source_weight"] == 1.0

    def test_low_source_weight(self):
        """Test scoring with low source weight."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.2,  # Low quality source
            title="Random Blog Post",
            content_text="This is just a random blog post about Python.",
            word_count=800,
            topics=["python"],
        )

        assert result.breakdown["source_weight"] == 0.2

    def test_topic_matching_in_title(self):
        """Test that topic matches in title are detected."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.5,
            title="Python Programming Best Practices",
            content_text="Some unrelated content about programming.",
            word_count=1000,
            topics=["python", "programming"],
        )

        # Should have 3 topic hits (both in title and one in content)
        assert result.breakdown["topic_hits"] == 3
        assert result.breakdown["topic_score"] > 0

    def test_topic_matching_in_content(self):
        """Test that topic matches in content are detected."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.5,
            title="A Random Article",
            content_text="Python programming is very powerful. It's used for web development, data science, and more.",
            word_count=1000,
            topics=["python", "programming"],
        )

        # Should have 2 topic hits (both in content)
        assert result.breakdown["topic_hits"] == 2
        assert result.breakdown["topic_score"] > 0

    def test_no_topic_matches(self):
        """Test scoring when no topics match."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.5,
            title="A Random Article",
            content_text="This article is about completely unrelated topics.",
            word_count=1000,
            topics=["python", "programming"],
        )

        # Should have 0 topic hits
        assert result.breakdown["topic_hits"] == 0
        assert result.breakdown["topic_score"] == 0.0

    def test_length_penalty_short(self):
        """Test no length penalty for short articles."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.5,
            title="Short Article",
            content_text="This is a very short article.",
            word_count=500,  # Well under 2500
            topics=["article"],
        )

        # Length penalty should be minimal for short articles
        assert result.breakdown["length_penalty"] < 0.1

    def test_length_penalty_long(self):
        """Test length penalty for long articles."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.5,
            title="Very Long Article",
            content_text="A" * 10000,  # Very long content
            word_count=5000,  # Well over 2500
            topics=["article"],
        )

        # Length penalty should be significant for long articles
        assert result.breakdown["length_penalty"] > 0.2

    def test_invalid_datetime(self):
        """Test handling of invalid datetime string."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso="invalid-date",
            source_weight=0.5,
            title="Article Title",
            content_text="Some article content.",
            word_count=1000,
            topics=["article"],
        )

        # Should use current time as fallback
        assert result.breakdown["age_hours"] < 0.1

    def test_max_topic_score(self):
        """Test that topic score is capped at maximum."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Create content with many topic matches
        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.5,
            title="Python Programming Python Programming Python",
            content_text="python python python programming programming programming",
            word_count=1000,
            topics=["python", "programming"],
        )

        # Topic score should be capped at 0.6
        assert result.breakdown["topic_score"] <= 0.6

    def test_negative_word_count_handling(self):
        """Test handling of edge cases with word count."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.5,
            title="Empty Article",
            content_text="",
            word_count=0,  # Edge case
            topics=["article"],
        )

        # Should handle zero word count gracefully
        assert result.breakdown["word_count"] == 0
        assert result.score >= 0.0

    def test_empty_topics_list(self):
        """Test scoring with empty topics list."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.5,
            title="Article Title",
            content_text="Some article content.",
            word_count=1000,
            topics=[],  # Empty list
        )

        # Should handle empty topics gracefully
        assert result.breakdown["topic_hits"] == 0
        assert result.breakdown["topic_score"] == 0.0

    def test_perfect_score(self):
        """Test conditions that would give near-perfect score."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2023, 1, 1, 11, 59, 0, tzinfo=timezone.utc)  # Very fresh

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=1.0,  # Best source
            title="Python Programming Guide",
            content_text="Comprehensive guide to Python programming with examples.",
            word_count=1500,  # Good length
            topics=["python", "programming"],
        )

        # Should have high score due to all positive factors
        assert result.score > 0.8

    def test_worst_score(self):
        """Test conditions that would give poor score."""
        now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_at = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # Very old

        result = score_post(
            now=now,
            published_at_iso=published_at.isoformat(),
            source_weight=0.1,  # Poor source
            title="Random Article",
            content_text="Unrelated content.",
            word_count=1000,
            topics=["python"],  # No matches
        )

        # Should have low score due to all negative factors
        assert result.score < 0.3
