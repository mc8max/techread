"""Unit tests for the RSS feed parsing module."""

from dataclasses import FrozenInstanceError
from unittest.mock import Mock, patch

import pytest

from techread.ingest.rss import FeedEntry, parse_feed


class TestFeedEntry:
    """Test cases for the FeedEntry dataclass."""

    def test_feed_entry_creation(self) -> None:
        """Test creating a FeedEntry with all fields."""
        entry = FeedEntry(
            title="Test Article",
            url="https://example.com/article",
            author="John Doe",
            published="2023-01-01T00:00:00Z",
        )
        assert entry.title == "Test Article"
        assert entry.url == "https://example.com/article"
        assert entry.author == "John Doe"
        assert entry.published == "2023-01-01T00:00:00Z"

    def test_feed_entry_frozen(self) -> None:
        """Test that FeedEntry is immutable."""
        entry = FeedEntry(
            title="Test", url="https://example.com", author="Author", published="2023-01-01"
        )
        with pytest.raises(FrozenInstanceError):
            entry.title = "New Title"

    def test_feed_entry_str_representation(self) -> None:
        """Test string representation of FeedEntry."""
        entry = FeedEntry(
            title="Article", url="https://example.com", author="Author", published="2023-01-01"
        )
        # FeedEntry should have a string representation
        assert (
            str(entry)
            == "FeedEntry(title='Article', url='https://example.com', author='Author', published='2023-01-01')"
        )


class TestParseFeed:
    """Test cases for the parse_feed function."""

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_valid_feed(self, mock_parse) -> None:
        """Test parsing a valid RSS feed with multiple entries."""
        # Mock feed data
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                link="https://example.com/article1",
                title="Article One",
                author="Author One",
                published="2023-01-01T10:00:00Z",
            ),
            Mock(
                link="https://example.com/article2",
                title="Article Two",
                author="Author Two",
                published="2023-01-02T10:00:00Z",
            ),
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 2
        assert result[0].title == "Article One"
        assert result[0].url == "https://example.com/article1"
        assert result[0].author == "Author One"
        assert result[0].published == "2023-01-01T10:00:00Z"
        assert result[1].title == "Article Two"
        assert result[1].url == "https://example.com/article2"

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_feed_with_missing_fields(self, mock_parse) -> None:
        """Test parsing feed with missing optional fields."""
        # Mock feed data with missing fields
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                link="https://example.com/article1",
                title=None,  # Missing title
                author=None,  # Missing author
                published=None,  # Missing published
                updated=None,  # Missing updated (fallback)
            )
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 1
        # Title should fall back to link when missing
        assert result[0].title == "https://example.com/article1"
        assert result[0].url == "https://example.com/article1"
        assert result[0].author == ""  # Empty string for missing author
        assert result[0].published == ""  # Empty string when both published and updated are missing

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_feed_with_updated_fallback(self, mock_parse) -> None:
        """Test that 'updated' field is used as fallback for 'published'."""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                link="https://example.com/article1",
                title="Article One",
                author="Author One",
                published=None,  # Missing published
                updated="2023-01-01T10:00:00Z",  # Has updated
            )
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 1
        assert result[0].published == "2023-01-01T10:00:00Z"

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_empty_feed(self, mock_parse) -> None:
        """Test parsing an empty feed (no entries)."""
        mock_feed = Mock()
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 0

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_feed_with_none_entries(self, mock_parse) -> None:
        """Test parsing when feed.entries is None."""
        mock_feed = Mock()
        mock_feed.entries = None
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 0

    @patch("techread.ingest.rss.feedparser.parse")
    def test_deduplicate_entries_by_url(self, mock_parse) -> None:
        """Test that duplicate entries by URL are removed while preserving order."""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                link="https://example.com/article1",
                title="Article One",
                author="Author One",
                published="2023-01-01T10:00:00Z",
            ),
            Mock(
                link="https://example.com/article1",  # Duplicate URL
                title="Article One Duplicate",
                author="Author Two",
                published="2023-01-02T10:00:00Z",
            ),
            Mock(
                link="https://example.com/article2",
                title="Article Two",
                author="Author Three",
                published="2023-01-03T10:00:00Z",
            ),
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 2
        assert result[0].title == "Article One"  # First occurrence kept
        assert result[1].title == "Article Two"
        assert result[0].url == "https://example.com/article1"

    @patch("techread.ingest.rss.feedparser.parse")
    def test_filter_entries_with_empty_url(self, mock_parse) -> None:
        """Test that entries with empty URLs are filtered out."""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                link="https://example.com/article1",
                title="Article One",
                author="Author One",
                published="2023-01-01T10:00:00Z",
            ),
            Mock(
                link="",  # Empty URL
                title="Article With No URL",
                author="Author Two",
                published="2023-01-02T10:00:00Z",
            ),
            Mock(
                link=None,  # None URL
                title="Article With None URL",
                author="Author Three",
                published="2023-01-03T10:00:00Z",
            ),
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 1
        assert result[0].title == "Article One"

    @patch("techread.ingest.rss.feedparser.parse")
    def test_whitespace_stripping(self, mock_parse) -> None:
        """Test that whitespace is properly stripped from all fields."""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                link="  https://example.com/article1  ",
                title="  Article One  ",
                author="  Author One  ",
                published="  2023-01-01T10:00:00Z  ",
            )
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 1
        assert result[0].title == "Article One"
        assert result[0].url == "https://example.com/article1"
        assert result[0].author == "Author One"
        assert result[0].published == "2023-01-01T10:00:00Z"

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_feed_error_handling(self, mock_parse) -> None:
        """Test that parsing errors are properly propagated."""
        mock_parse.side_effect = RuntimeError("Network error")

        with pytest.raises(RuntimeError, match="Network error"):
            parse_feed("https://invalid-url.com/rss.xml")

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_feed_with_special_characters(self, mock_parse) -> None:
        """Test parsing feed entries with special characters and unicode."""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                link="https://example.com/article-日本語",
                title="Article with 世界 🌍",
                author="Author with émojis 😀",
                published="2023-01-01T10:00:00Z",
            )
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 1
        assert "世界" in result[0].title
        assert "🌍" in result[0].title
        assert "émojis" in result[0].author
        assert "😀" in result[0].author

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_feed_preserves_order(self, mock_parse) -> None:
        """Test that the order of entries is preserved after deduplication."""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(link="https://example.com/article1", title="First Article"),
            Mock(link="https://example.com/article2", title="Second Article"),
            Mock(link="https://example.com/article3", title="Third Article"),
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 3
        assert result[0].title == "First Article"
        assert result[1].title == "Second Article"
        assert result[2].title == "Third Article"

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_feed_with_mixed_valid_invalid(self, mock_parse) -> None:
        """Test parsing feed with mix of valid and invalid entries."""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(link="https://example.com/article1", title="Valid Article 1"),
            Mock(link="", title="Invalid Article"),  # Invalid - empty URL
            Mock(link="https://example.com/article2", title="Valid Article 2"),
            Mock(link=None, title="Another Invalid"),  # Invalid - None URL
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 2
        assert result[0].title == "Valid Article 1"
        assert result[1].title == "Valid Article 2"

    @patch("techread.ingest.rss.feedparser.parse")
    def test_parse_feed_with_numeric_urls(self, mock_parse) -> None:
        """Test parsing feed with numeric URLs."""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(link="12345", title="Article with numeric URL"),
            Mock(link="https://example.com/67890", title="Article with mixed URL"),
        ]
        mock_parse.return_value = mock_feed

        result = parse_feed("https://example.com/rss.xml")

        assert len(result) == 2
        # Both should be included as they have non-empty URLs
        assert result[0].url in ["12345", "https://example.com/67890"]
        assert result[1].url in ["12345", "https://example.com/67890"]
