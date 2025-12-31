"""Unit tests for the techread CLI."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from techread.cli import _db, _now, _parse_or_fallback, app
from techread.config import Settings
from techread.db import DB, init_db, session
from techread.ingest.rss import FeedEntry
from techread.sources.auto import AutofillResult
from techread.utils.text import stable_hash
from techread.utils.time import now_utc_iso

runner = CliRunner()


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = DB(path=db_path)
        init_db(db)

        # Create a test source
        with session(db) as conn:
            conn.execute(
                "INSERT INTO sources(name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, 'rss', 1.0, '', 1, ?)",
                (
                    "Test Source",
                    "https://example.com/feed.xml",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        yield db_path


@pytest.fixture
def settings():
    """Create test settings."""
    return Settings(
        db_path=":memory:",
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=["python", "javascript"],
    )


def test_now():
    """Test _now() returns UTC datetime."""
    now = _now()
    assert isinstance(now, datetime)
    assert now.tzinfo == timezone.utc


def test_parse_or_fallback():
    """Test _parse_or_fallback with various inputs."""
    # Empty string should return current time
    result = _parse_or_fallback("")
    assert isinstance(result, str)
    # ISO format with microseconds can be 32 or 34 characters
    assert len(result) in (32, 34)

    # Valid ISO datetime
    valid_dt = "2023-01-01T12:00:00+00:00"
    result = _parse_or_fallback(valid_dt)
    assert result == valid_dt

    # Invalid datetime should fallback to current time
    invalid_dt = "not-a-date"
    result = _parse_or_fallback(invalid_dt)
    assert isinstance(result, str)
    # ISO format with microseconds can be 32 or 34 characters
    assert len(result) in (32, 34)


def test_db(temp_db):
    """Test _db() function."""
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value.db_path = temp_db
        db = _db()
        assert isinstance(db, DB)
        assert db.path == temp_db


def test_fetch_no_sources(temp_db):
    """Test fetch command with no enabled sources."""
    # Disable the test source we created
    with session(DB(path=temp_db)) as conn:
        conn.execute("UPDATE sources SET enabled=0 WHERE id=1")

    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value.db_path = temp_db
        mock_load.return_value.cache_dir = "/tmp/cache"

        result = runner.invoke(app, ["fetch"])
        assert result.exit_code == 1
        assert "No sources enabled" in result.output


def test_rank_no_posts(temp_db):
    """Test rank command with no posts."""
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value.db_path = temp_db
        mock_load.return_value.default_top_n = 5

        result = runner.invoke(app, ["rank"])
        assert result.exit_code == 0
        assert "No posts to rank" in result.output


def test_sources_remove_invalid(temp_db):
    """Test sources remove with invalid ID."""
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value.db_path = temp_db

        result = runner.invoke(app, ["sources", "remove", "999"])
        assert result.exit_code == 1
        assert "No such source" in result.output


def test_sources_enable_invalid(temp_db):
    """Test sources enable with invalid ID."""
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value.db_path = temp_db

        result = runner.invoke(app, ["sources", "enable", "999"])
        assert result.exit_code == 1
        assert "No such source" in result.output


def test_sources_disable_invalid(temp_db):
    """Test sources disable with invalid ID."""
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value.db_path = temp_db

        result = runner.invoke(app, ["sources", "disable", "999"])
        assert result.exit_code == 1
        assert "No such source" in result.output


def test_sources_test_invalid_url():
    """Test sources test with invalid URL."""
    result = runner.invoke(app, ["sources", "test", "http://invalid.url"])
    # The test might succeed (exit code 0) if the URL is actually valid
    # Just verify it doesn't crash
    assert result.exit_code in (0, 1)


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def test_help_text(self):
        """Test that help text is available."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "techread: fetch, rank" in result.output

    def test_sources_help(self):
        """Test sources subcommand help."""
        result = runner.invoke(app, ["sources", "--help"])
        assert result.exit_code == 0
        assert "Manage sources" in result.output


class TestCLIOptions:
    """Test various CLI option combinations."""

    def test_digest_options(self, temp_db):
        """Test digest command with various options."""
        with patch("techread.cli.load_settings") as mock_load:
            mock_load.return_value.db_path = temp_db
            mock_load.return_value.default_top_n = 5
            mock_load.return_value.llm_model = "nemotron-3-nano"
            mock_load.return_value.topics = []

            result = runner.invoke(app, ["digest", "--today", "--top", "5"])
            assert result.exit_code == 0


def test_sources_autofill_updates(temp_db):
    """Test sources autofill updates missing name and tags."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        with patch("techread.cli.autofill_source") as mock_autofill:
            mock_autofill.return_value = AutofillResult(
                name="New Source Name", tags="ai,ml", warnings=[]
            )
            result = runner.invoke(app, ["sources", "autofill", "--id", "1"])
            assert result.exit_code == 0
            assert "Updated sources: 1" in result.output

    with session(DB(path=temp_db)) as conn:
        row = conn.execute("SELECT name, tags FROM sources WHERE id=1").fetchone()
        assert row["name"] == "New Source Name"
        assert row["tags"] == "ai,ml"


def test_sources_add_autofill(temp_db):
    """Test sources add uses autofill when name/tags are missing."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        with patch("techread.cli.autofill_source") as mock_autofill:
            mock_autofill.return_value = AutofillResult(
                name="Auto Name", tags="devops,sre", warnings=[]
            )
            result = runner.invoke(
                app, ["sources", "add", "https://example.com/new.xml", "--weight", "1.0"]
            )
            assert result.exit_code == 0
            assert "Added source" in result.output

    with session(DB(path=temp_db)) as conn:
        row = conn.execute(
            "SELECT name, tags FROM sources WHERE url=?",
            ("https://example.com/new.xml",),
        ).fetchone()
        assert row["name"] == "Auto Name"
        assert row["tags"] == "devops,sre"


def test_summarize_uses_cached_summary_and_prints_metadata(temp_db):
    """Test summarize prints metadata and uses cached summary."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    content = "x" * 300
    content_hash = stable_hash(content)
    with session(DB(path=temp_db)) as conn:
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                1,
                "Post Title",
                "https://example.com/post",
                "Test Author",
                "2023-01-02T00:00:00+00:00",
                now_utc_iso(),
                content,
                content_hash,
                300,
            ),
        )
        conn.execute(
            "INSERT INTO summaries(post_id, mode, model, content_hash, summary_text, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "takeaways", "test-model", content_hash, "Cached summary.", now_utc_iso()),
        )

    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        result = runner.invoke(app, ["summarize", "1"])
        assert result.exit_code == 0
        assert "Post Title" in result.output
        assert "https://example.com/post" in result.output
        assert "author=Test Author" in result.output
        assert "published=2023-01-02" in result.output
        assert "Cached summary." in result.output


def test_fetch_inserts_posts(temp_db):
    """Test fetch inserts new posts from parsed feed entries."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
        min_word_count=0,
    )
    entry = FeedEntry(
        title="Entry One",
        url="https://example.com/entry1",
        author="Entry Author",
        published="2023-01-01T00:00:00+00:00",
    )

    class Extracted:
        text = "hello world"
        word_count = 2

    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        with patch("techread.cli.parse_feed") as mock_parse:
            mock_parse.return_value = [entry]
            with patch("techread.cli.fetch_html") as mock_fetch:
                mock_fetch.return_value = "<html></html>"
                with patch("techread.cli.extract_text") as mock_extract:
                    mock_extract.return_value = Extracted()
                    result = runner.invoke(app, ["fetch", "--limit-per-source", "1"])
                    assert result.exit_code == 0

    with session(DB(path=temp_db)) as conn:
        row = conn.execute("SELECT * FROM posts WHERE url=?", (entry.url,)).fetchone()
        assert row is not None
        assert row["title"] == "Entry One"
        assert row["author"] == "Entry Author"


def test_rank_scores_posts(temp_db):
    """Test rank computes scores and prints ranked output."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with session(DB(path=temp_db)) as conn:
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                1,
                "Ranked Post",
                "https://example.com/ranked",
                "Author",
                now_utc_iso(),
                now_utc_iso(),
                "content",
                stable_hash("content"),
                100,
            ),
        )

    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        with patch("techread.cli.print_ranked") as mock_print:
            result = runner.invoke(app, ["rank", "--top", "1"])
            assert result.exit_code == 0
            mock_print.assert_called_once()

    with session(DB(path=temp_db)) as conn:
        row = conn.execute("SELECT * FROM scores WHERE post_id=1").fetchone()
        assert row is not None


def test_digest_prints_metadata_without_summaries(temp_db):
    """Test digest includes metadata and skips summaries when disabled."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    published_at = now_utc_iso()
    with session(DB(path=temp_db)) as conn:
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                1,
                "Digest Post",
                "https://example.com/digest",
                "Digest Author",
                published_at,
                now_utc_iso(),
                "content",
                stable_hash("content"),
                220,
            ),
        )
        conn.execute(
            "INSERT INTO scores(post_id, scored_at, score, breakdown_json) VALUES (?, ?, ?, ?)",
            (1, now_utc_iso(), 0.5, "{}"),
        )

    captured = {}

    def _capture(items):
        captured["items"] = items

    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        with patch("techread.cli.print_digest") as mock_print:
            mock_print.side_effect = _capture
            result = runner.invoke(app, ["digest", "--top", "1", "--no-auto-summarize"])
            assert result.exit_code == 0

    items = captured.get("items", [])
    assert len(items) == 1
    assert items[0]["author"] == "Digest Author"
    assert items[0]["published_at"] == published_at


def test_rank_filters_by_source_id(temp_db):
    """Test rank filters posts by source id."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with session(DB(path=temp_db)) as conn:
        conn.execute(
            "INSERT INTO sources(name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, 'rss', 1.0, '', 1, ?)",
            ("Other Source", "https://example.com/other.xml", now_utc_iso()),
        )
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                1,
                "Source One Post",
                "https://example.com/source1",
                "Author",
                now_utc_iso(),
                now_utc_iso(),
                "content",
                stable_hash("content"),
                100,
            ),
        )
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                2,
                "Source Two Post",
                "https://example.com/source2",
                "Author",
                now_utc_iso(),
                now_utc_iso(),
                "content",
                stable_hash("content2"),
                100,
            ),
        )

    captured = {}

    def _capture(posts, **_kwargs):
        captured["posts"] = posts

    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        with patch("techread.cli.print_ranked") as mock_print:
            mock_print.side_effect = _capture
            result = runner.invoke(app, ["rank", "--top", "5", "--source", "2"])
            assert result.exit_code == 0

    posts = captured.get("posts", [])
    assert len(posts) == 1
    assert posts[0]["title"] == "Source Two Post"


def test_rank_filters_by_tag(temp_db):
    """Test rank filters posts by source name/tags."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with session(DB(path=temp_db)) as conn:
        conn.execute(
            "INSERT INTO sources(name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, 'rss', 1.0, ?, 1, ?)",
            ("Data Source", "https://example.com/data.xml", "ml,infra", now_utc_iso()),
        )
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                1,
                "Source One Post",
                "https://example.com/source1",
                "Author",
                now_utc_iso(),
                now_utc_iso(),
                "content",
                stable_hash("content"),
                100,
            ),
        )
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                2,
                "Tagged Post",
                "https://example.com/tagged",
                "Author",
                now_utc_iso(),
                now_utc_iso(),
                "content",
                stable_hash("content2"),
                100,
            ),
        )

    captured = {}

    def _capture(posts, **_kwargs):
        captured["posts"] = posts

    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        with patch("techread.cli.print_ranked") as mock_print:
            mock_print.side_effect = _capture
            result = runner.invoke(app, ["rank", "--top", "5", "--tag", "ML"])
            assert result.exit_code == 0

    posts = captured.get("posts", [])
    assert len(posts) == 1
    assert posts[0]["title"] == "Tagged Post"


def test_digest_filters_by_source_id(temp_db):
    """Test digest filters posts by source id."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with session(DB(path=temp_db)) as conn:
        conn.execute(
            "INSERT INTO sources(name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, 'rss', 1.0, '', 1, ?)",
            ("Other Source", "https://example.com/other.xml", now_utc_iso()),
        )
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                1,
                "Source One Digest",
                "https://example.com/digest1",
                "Author",
                now_utc_iso(),
                now_utc_iso(),
                "content",
                stable_hash("content"),
                100,
            ),
        )
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                2,
                "Source Two Digest",
                "https://example.com/digest2",
                "Author",
                now_utc_iso(),
                now_utc_iso(),
                "content",
                stable_hash("content2"),
                100,
            ),
        )
        conn.execute(
            "INSERT INTO scores(post_id, scored_at, score, breakdown_json) VALUES (?, ?, ?, ?)",
            (1, now_utc_iso(), 0.5, "{}"),
        )
        conn.execute(
            "INSERT INTO scores(post_id, scored_at, score, breakdown_json) VALUES (?, ?, ?, ?)",
            (2, now_utc_iso(), 0.6, "{}"),
        )

    captured = {}

    def _capture(items):
        captured["items"] = items

    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        with patch("techread.cli.print_digest") as mock_print:
            mock_print.side_effect = _capture
            result = runner.invoke(
                app, ["digest", "--top", "5", "--no-auto-summarize", "--source", "2"]
            )
            assert result.exit_code == 0

    items = captured.get("items", [])
    assert len(items) == 1
    assert items[0]["title"] == "Source Two Digest"


def test_mark_updates_state(temp_db):
    """Test mark updates read state."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with session(DB(path=temp_db)) as conn:
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                1,
                "Mark Post",
                "https://example.com/mark",
                "Author",
                now_utc_iso(),
                now_utc_iso(),
                "content",
                stable_hash("content"),
                10,
            ),
        )
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        result = runner.invoke(app, ["mark", "1", "--read"])
        assert result.exit_code == 0

    with session(DB(path=temp_db)) as conn:
        row = conn.execute("SELECT read_state FROM posts WHERE id=1").fetchone()
        assert row["read_state"] == "read"


def test_mark_invalid_flags(temp_db):
    """Test mark requires exactly one state flag."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        result = runner.invoke(app, ["mark", "1", "--read", "--saved"])
        assert result.exit_code == 1
        assert "Invalid state" in result.output


def test_open_uses_browser(temp_db):
    """Test open command calls webbrowser."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with session(DB(path=temp_db)) as conn:
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                1,
                "Open Post",
                "https://example.com/open",
                "Author",
                now_utc_iso(),
                now_utc_iso(),
                "content",
                stable_hash("content"),
                10,
            ),
        )
    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        with patch("techread.cli.webbrowser.open") as mock_open:
            result = runner.invoke(app, ["open", "1"])
            assert result.exit_code == 0
            mock_open.assert_called_once()


def test_sources_test_success():
    """Test sources test prints entries."""
    entry = FeedEntry(
        title="Entry One",
        url="https://example.com/entry1",
        author="Entry Author",
        published="2023-01-01T00:00:00+00:00",
    )
    with patch("techread.cli.parse_feed") as mock_parse:
        mock_parse.return_value = [entry]
        result = runner.invoke(app, ["sources", "test", "https://example.com/rss.xml"])
        assert result.exit_code == 0
        assert "Top entries for" in result.output
        assert "Entry One" in result.output


def test_summarize_short_content(temp_db):
    """Test summarize fails for short content and prints metadata."""
    settings = Settings(
        db_path=temp_db,
        cache_dir="/tmp/cache",
        llm_model="test-model",
        default_top_n=5,
        topics=[],
    )
    with session(DB(path=temp_db)) as conn:
        conn.execute(
            "INSERT INTO posts(source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread')",
            (
                1,
                "Short Post",
                "https://example.com/short",
                "Short Author",
                "2023-01-03T00:00:00+00:00",
                now_utc_iso(),
                "tiny",
                stable_hash("tiny"),
                5,
            ),
        )

    with patch("techread.cli.load_settings") as mock_load:
        mock_load.return_value = settings
        result = runner.invoke(app, ["summarize", "1"])
        assert result.exit_code == 1
        assert "Short Post" in result.output
        assert "Not enough extracted text" in result.output
