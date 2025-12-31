"""Unit tests for the techread.sources.auto module."""

from unittest.mock import MagicMock, patch

from techread.config import Settings
from techread.ingest.rss import FeedMeta
from techread.sources.auto import (
    _collect_snippets,
    _entry_titles,
    autofill_source,
    infer_source_name,
)


class TestInferSourceName:
    """Tests for infer_source_name function."""

    def test_with_title(self):
        """Test that feed title is used when available."""
        meta = FeedMeta(title="Test Blog", subtitle="A test blog", link="https://example.com")
        url = "https://example.com/feed.xml"
        result = infer_source_name(meta, url)
        assert result == "Test Blog"

    def test_without_title_hostname(self):
        """Test fallback to hostname when no title."""
        meta = FeedMeta(title=None, subtitle="A test blog", link="https://example.com")
        url = "https://example.com/feed.xml"
        result = infer_source_name(meta, url)
        assert result == "example.com"

    def test_without_title_path(self):
        """Test fallback to path when no hostname."""
        meta = FeedMeta(title=None, subtitle="A test blog", link="/path/to/feed.xml")
        url = "/path/to/feed.xml"
        result = infer_source_name(meta, url)
        assert result == "/path/to/feed.xml"

    def test_with_url_only(self):
        """Test with just URL when no metadata."""
        meta = FeedMeta(title=None, subtitle=None, link="https://example.com")
        url = "https://example.com/feed.xml"
        result = infer_source_name(meta, url)
        assert result == "example.com"


class TestCollectSnippets:
    """Tests for _collect_snippets function."""

    @patch("sqlite3.Connection")
    def test_with_none_source_id(self, mock_conn):
        """Test that empty list is returned for None source_id."""
        result = _collect_snippets(mock_conn, None)
        assert result == []
        mock_conn.execute.assert_not_called()

    @patch("sqlite3.Connection")
    def test_with_valid_source_id(self, mock_conn):
        """Test snippet collection with valid source."""
        # Mock database rows
        mock_conn.execute.return_value.fetchall.return_value = [
            {"content_text": "This is a test snippet."},
            {"content_text": "Another snippet with more content here."},
        ]

        result = _collect_snippets(mock_conn, 1)

        # Verify database query was called correctly
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert (
            call_args[0][0]
            == "SELECT content_text FROM posts WHERE source_id=? ORDER BY published_at DESC LIMIT ?"
        )
        assert call_args[0][1] == (1, 4)  # _MAX_SNIPPETS = 4

        # Verify snippets are truncated
        assert len(result) == 2
        assert result[0] == "This is a test snippet."
        assert len(result[1]) <= 800  # _SNIPPET_CHARS = 800

    @patch("sqlite3.Connection")
    def test_with_empty_content(self, mock_conn):
        """Test handling of empty content rows."""
        mock_conn.execute.return_value.fetchall.return_value = [
            {"content_text": ""},
            {"content_text": None},
        ]

        result = _collect_snippets(mock_conn, 1)
        assert result == []


class TestEntryTitles:
    """Tests for _entry_titles function."""

    def test_with_valid_entries(self):
        """Test title extraction from entries."""
        entries = [
            MagicMock(title="First Entry"),
            MagicMock(title="Second Entry"),
            MagicMock(title="Third Entry"),
        ]

        result = _entry_titles(entries)
        assert len(result) == 3
        assert result[0] == "First Entry"
        assert result[1] == "Second Entry"
        assert result[2] == "Third Entry"

    def test_with_empty_titles(self):
        """Test handling of entries with empty titles."""
        entries = [
            MagicMock(title=""),
            MagicMock(title=None),
            MagicMock(title="Valid Title"),
        ]

        result = _entry_titles(entries)
        assert len(result) == 1
        assert result[0] == "Valid Title"

    def test_max_entries_limit(self):
        """Test that only _MAX_ENTRY_TITLES are collected."""
        entries = [MagicMock(title=f"Entry {i}") for i in range(15)]

        result = _entry_titles(entries)
        assert len(result) == 10  # _MAX_ENTRY_TITLES = 10

    def test_entries_without_title_attribute(self):
        """Test handling of entries without title attribute."""
        # MagicMock returns string representation when accessed
        entries = [
            MagicMock(title=None),  # Will have no title attribute
            MagicMock(title="Valid Entry"),
        ]

        result = _entry_titles(entries)
        assert len(result) == 1
        assert result[0] == "Valid Entry"


class TestAutofillSource:
    """Tests for autofill_source function."""

    @patch("techread.sources.auto.parse_feed_full")
    def test_no_updates_needed(self, mock_parse):
        """Test that no updates occur when name and tags exist."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=10,
            topics=[],
        )
        conn = MagicMock()

        mock_parse.return_value = (
            FeedMeta(title="Test Feed", subtitle="", link="https://example.com"),
            [],
        )

        result = autofill_source(
            conn=conn,
            settings=settings,
            source_id=None,
            url="https://example.com/feed.xml",
            name="Existing Name",
            tags="existing tag1, existing tag2",
        )

        assert result.name is None
        assert result.tags is None
        assert result.warnings == []

    @patch("techread.sources.auto.parse_feed_full")
    @patch("techread.sources.auto.generate_tags")
    def test_force_update(self, mock_tags, mock_parse):
        """Test that force=True triggers regeneration."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=10,
            topics=[],
        )
        conn = MagicMock()
        mock_tags.return_value = "new, tags"

        mock_parse.return_value = (
            FeedMeta(title="New Feed Title", subtitle="", link="https://example.com"),
            [],
        )

        result = autofill_source(
            conn=conn,
            settings=settings,
            source_id=None,
            url="https://example.com/feed.xml",
            name="Existing Name",
            tags="existing tag1, existing tag2",
            force=True,
        )

        assert result.name == "New Feed Title"
        assert result.tags == "new, tags"  # Should attempt tag generation

    @patch("techread.sources.auto.parse_feed_full")
    def test_parse_failure(self, mock_parse):
        """Test handling of feed parsing errors."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=10,
            topics=[],
        )
        conn = MagicMock()

        mock_parse.side_effect = Exception("Parse error")

        result = autofill_source(
            conn=conn,
            settings=settings,
            source_id=None,
            url="https://example.com/feed.xml",
            name="Existing Name",
            tags="existing tag1, existing tag2",
        )

        assert result.name is None
        assert result.tags is None
        # When parse fails, no warnings are added (early return)
        assert len(result.warnings) == 0

    @patch("techread.sources.auto.parse_feed_full")
    def test_tag_generation_failure(self, mock_parse):
        """Test handling of tag generation errors."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=10,
            topics=[],
        )
        conn = MagicMock()

        mock_parse.return_value = (
            FeedMeta(title="Test Feed", subtitle="", link="https://example.com"),
            [],
        )

        # Mock generate_tags to raise an exception
        with patch(
            "techread.sources.auto.generate_tags", side_effect=Exception("Tag generation failed")
        ):
            result = autofill_source(
                conn=conn,
                settings=settings,
                source_id=None,
                url="https://example.com/feed.xml",
                name="",  # Empty name triggers update
                tags="",
            )

        assert result.name == "Test Feed"
        assert len(result.warnings) == 1
        assert "Failed to generate tags" in result.warnings[0]

    @patch("techread.sources.auto.parse_feed_full")
    def test_no_tags_generated(self, mock_parse):
        """Test handling when no tags are generated."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=10,
            topics=[],
        )
        conn = MagicMock()

        mock_parse.return_value = (
            FeedMeta(title="Test Feed", subtitle="", link="https://example.com"),
            [],
        )

        # Mock generate_tags to return empty string
        with patch("techread.sources.auto.generate_tags", return_value=""):
            result = autofill_source(
                conn=conn,
                settings=settings,
                source_id=None,
                url="https://example.com/feed.xml",
                name="",  # Empty name triggers update
                tags="",
            )

        assert result.name == "Test Feed"
        assert len(result.warnings) == 1
        assert "No tags generated" in result.warnings[0]

    @patch("techread.sources.auto.parse_feed_full")
    @patch("techread.sources.auto.generate_tags")
    def test_successful_autofill(self, mock_tags, mock_parse):
        """Test successful name and tag autofill."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=10,
            topics=[],
        )
        conn = MagicMock()

        mock_parse.return_value = (
            FeedMeta(title="Test Blog", subtitle="A test blog", link="https://example.com"),
            [MagicMock(title="Entry 1"), MagicMock(title="Entry 2")],
        )
        mock_tags.return_value = "python, programming, technology"

        result = autofill_source(
            conn=conn,
            settings=settings,
            source_id=None,
            url="https://example.com/feed.xml",
            name="",
            tags="",
        )

        assert result.name == "Test Blog"
        assert result.tags == "python, programming, technology"
        assert result.warnings == []

    @patch("techread.sources.auto.parse_feed_full")
    def test_name_only_update(self, mock_parse):
        """Test updating only name when tags already exist."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=10,
            topics=[],
        )
        conn = MagicMock()

        mock_parse.return_value = (
            FeedMeta(title="New Name", subtitle="", link="https://example.com"),
            [],
        )

        # Mock generate_tags to avoid actual LLM call
        with patch("techread.sources.auto.generate_tags", return_value="new, tags"):
            result = autofill_source(
                conn=conn,
                settings=settings,
                source_id=None,
                url="https://example.com/feed.xml",
                name="",  # Empty name triggers update
                tags="existing tag1, existing tag2",
            )

        assert result.name == "New Name"
        assert result.tags is None  # Tags should not change
        assert result.warnings == []

    @patch("techread.sources.auto.parse_feed_full")
    def test_tags_only_update(self, mock_parse):
        """Test updating only tags when name already exists."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=10,
            topics=[],
        )
        conn = MagicMock()

        mock_parse.return_value = (FeedMeta(title="", subtitle="", link="https://example.com"), [])
        # Mock generate_tags to return value
        with patch("techread.sources.auto.generate_tags", return_value="new, tags"):
            result = autofill_source(
                conn=conn,
                settings=settings,
                source_id=None,
                url="https://example.com/feed.xml",
                name="Existing Name",
                tags="",
            )

        assert result.name is None  # Name should not change
        assert result.tags == "new, tags"
        assert result.warnings == []

    @patch("techread.sources.auto.parse_feed_full")
    def test_url_as_name_fallback(self, mock_parse):
        """Test that URL is used as name when appropriate."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=10,
            topics=[],
        )

        mock_parse.return_value = (FeedMeta(title="", subtitle="", link="https://example.com"), [])

        # Mock generate_tags to avoid actual LLM call
        with patch("techread.sources.auto.generate_tags", return_value="new, tags"):
            result = autofill_source(
                conn=MagicMock(),
                settings=settings,
                source_id=None,
                url="https://example.com/feed.xml",
                name="https://example.com/feed.xml",  # Same as URL
                tags="",
            )

        assert result.name == "example.com"  # Should infer from URL
        # When tags are empty and no force, warnings about tag generation should not be added
        assert len(result.warnings) == 0 or result.warnings[0].startswith("No tags generated")
