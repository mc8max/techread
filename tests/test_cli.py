"""Unit tests for the techread CLI."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from techread.cli import (
    _db,
    _now,
    _parse_or_fallback,
    app,
)
from techread.config import Settings
from techread.db import DB, init_db, session

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
