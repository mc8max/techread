"""Unit tests for the db module."""

import json
import os
import sqlite3
import tempfile
from datetime import datetime

import pytest

from techread.db import (
    DB,
    connect,
    exec_,
    init_db,
    q1,
    qall,
    session,
    upsert_score,
    upsert_summary,
)


class TestDBClass:
    """Tests for the DB dataclass."""

    def test_db_creation(self):
        """Test that DB can be created with a path."""
        db = DB(path="/tmp/test.db")
        assert db.path == "/tmp/test.db"

    def test_db_immutable(self):
        """Test that DB is immutable (frozen)."""
        db = DB(path="/tmp/test.db")
        with pytest.raises(Exception):
            db.path = "/tmp/new.db"


class TestConnect:
    """Tests for the connect function."""

    def test_connect_creates_database(self, tmp_path):
        """Test that connect creates a database file."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        conn = connect(db)
        assert os.path.exists(db_file)

        conn.close()

    def test_connect_returns_connection(self, tmp_path):
        """Test that connect returns a valid connection."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        conn = connect(db)
        assert hasattr(conn, "execute")
        assert hasattr(conn, "commit")

        conn.close()

    def test_connect_row_factory(self, tmp_path):
        """Test that connect sets row factory to Row."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        conn = connect(db)
        assert conn.row_factory == sqlite3.Row

        conn.close()


class TestInitDB:
    """Tests for the init_db function."""

    def test_init_db_creates_tables(self, tmp_path):
        """Test that init_db creates all required tables."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        conn = connect(db)
        tables = qall(conn, "SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [row[0] for row in tables]

        assert "sources" in table_names
        assert "posts" in table_names
        assert "scores" in table_names
        assert "summaries" in table_names

        conn.close()

    def test_init_db_creates_indexes(self, tmp_path):
        """Test that init_db creates all required indexes."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        conn = connect(db)
        indexes = qall(conn, "SELECT name FROM sqlite_master WHERE type='index'")
        index_names = [row[0] for row in indexes]

        assert any("idx_posts_published_at" in name for name in index_names)
        assert any("idx_posts_read_state" in name for name in index_names)
        assert any("idx_posts_source_id" in name for name in index_names)

        conn.close()

    def test_init_db_is_idempotent(self, tmp_path):
        """Test that init_db can be called multiple times safely."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)
        init_db(db)  # Should not raise an error
        init_db(db)  # Should not raise an error

        conn = connect(db)
        tables = qall(conn, "SELECT name FROM sqlite_master WHERE type='table'")
        # Should have 4 tables plus sqlite_sequence
        assert len(tables) >= 4

        conn.close()

    def test_init_db_creates_parent_dirs(self, tmp_path):
        """Test that init_db creates parent directories if needed."""
        db_dir = tmp_path / "new" / "db" / "path"
        db_file = db_dir / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        assert os.path.exists(db_dir)
        assert os.path.exists(db_file)


class TestSession:
    """Tests for the session context manager."""

    def test_session_commits_on_success(self, tmp_path):
        """Test that session commits on successful execution."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        # Verify the data was committed
        with session(db) as conn:
            row = q1(conn, "SELECT name FROM sources WHERE url = ?", ["http://test.com/rss"])
            assert row is not None
            assert row["name"] == "Test Source"

    def test_session_rolls_back_on_error(self, tmp_path):
        """Test that session rolls back on error."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        try:
            with session(db) as conn:
                exec_(
                    conn,
                    "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        "Test Source",
                        "http://test.com/rss",
                        "rss",
                        1.0,
                        "",
                        1,
                        datetime.now().isoformat(),
                    ],
                )
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify the data was rolled back
        with session(db) as conn:
            row = q1(conn, "SELECT name FROM sources WHERE url = ?", ["http://test.com/rss"])
            assert row is None

    def test_session_closes_connection(self, tmp_path):
        """Test that session closes the connection."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            pass

        # Connection should be closed
        with pytest.raises(Exception):
            conn.execute("SELECT 1")


class TestQ1:
    """Tests for the q1 function."""

    def test_q1_returns_single_row(self, tmp_path):
        """Test that q1 returns a single row."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        with session(db) as conn:
            row = q1(conn, "SELECT name FROM sources WHERE url = ?", ["http://test.com/rss"])
            assert row is not None
            assert row["name"] == "Test Source"

    def test_q1_returns_none_for_no_match(self, tmp_path):
        """Test that q1 returns None when no rows match."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            row = q1(conn, "SELECT name FROM sources WHERE url = ?", ["http://nonexistent.com/rss"])
            assert row is None

    def test_q1_without_params(self, tmp_path):
        """Test that q1 works without parameters."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        with session(db) as conn:
            row = q1(conn, "SELECT name FROM sources LIMIT 1")
            assert row is not None
            assert row["name"] == "Test Source"

    def test_q1_row_is_dict_like(self, tmp_path):
        """Test that q1 returns rows that are dict-like."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        with session(db) as conn:
            row = q1(conn, "SELECT name, url FROM sources WHERE url = ?", ["http://test.com/rss"])
            assert row["name"] == "Test Source"
            assert row["url"] == "http://test.com/rss"


class TestQAll:
    """Tests for the qall function."""

    def test_qall_returns_multiple_rows(self, tmp_path):
        """Test that qall returns multiple rows."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source 1",
                    "http://test1.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source 2",
                    "http://test2.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        with session(db) as conn:
            rows = qall(conn, "SELECT name FROM sources ORDER BY name")
            assert len(rows) == 2
            assert rows[0]["name"] == "Test Source 1"
            assert rows[1]["name"] == "Test Source 2"

    def test_qall_returns_empty_list_for_no_match(self, tmp_path):
        """Test that qall returns empty list when no rows match."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            rows = qall(
                conn, "SELECT name FROM sources WHERE url = ?", ["http://nonexistent.com/rss"]
            )
            assert rows == []

    def test_qall_without_params(self, tmp_path):
        """Test that qall works without parameters."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        with session(db) as conn:
            rows = qall(conn, "SELECT name FROM sources")
            assert len(rows) == 1
            assert rows[0]["name"] == "Test Source"

    def test_qall_rows_are_dict_like(self, tmp_path):
        """Test that qall returns rows that are dict-like."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        with session(db) as conn:
            rows = qall(conn, "SELECT name, url FROM sources")
            assert len(rows) == 1
            assert rows[0]["name"] == "Test Source"
            assert rows[0]["url"] == "http://test.com/rss"


class TestExec:
    """Tests for the exec_ function."""

    def test_exec_inserts_row(self, tmp_path):
        """Test that exec_ inserts a row and returns the ID."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            row_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            assert row_id > 0

        with session(db) as conn:
            row = q1(conn, "SELECT name FROM sources WHERE id = ?", [row_id])
            assert row is not None
            assert row["name"] == "Test Source"

    def test_exec_returns_zero_for_update(self, tmp_path):
        """Test that exec_ returns 0 for UPDATE statements."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        with session(db) as conn:
            row_id = exec_(
                conn,
                "UPDATE sources SET name = ? WHERE url = ?",
                ["Updated Name", "http://test.com/rss"],
            )
            assert row_id == 0

    def test_exec_without_params(self, tmp_path):
        """Test that exec_ works without parameters."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            row_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES ('Test', 'http://test.com', 'rss', 1.0, '', 1, datetime('now'))",
            )
            assert row_id > 0

    def test_exec_updates_row(self, tmp_path):
        """Test that exec_ can update rows."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        with session(db) as conn:
            exec_(
                conn,
                "UPDATE sources SET name = ? WHERE url = ?",
                ["Updated Name", "http://test.com/rss"],
            )

        with session(db) as conn:
            row = q1(conn, "SELECT name FROM sources WHERE url = ?", ["http://test.com/rss"])
            assert row["name"] == "Updated Name"


class TestUpsertScore:
    """Tests for the upsert_score function."""

    def test_upsert_score_inserts_new_record(self, tmp_path):
        """Test that upsert_score inserts a new score record."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            source_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            post_id = exec_(
                conn,
                "INSERT INTO posts (source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    source_id,
                    "Test Post",
                    "http://test.com/post",
                    "Author",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "Content",
                    "hash123",
                    100,
                    "unread",
                ],
            )

            upsert_score(
                conn, post_id, datetime.now().isoformat(), 0.95, {"relevance": 0.8, "quality": 1.0}
            )

        with session(db) as conn:
            row = q1(conn, "SELECT score FROM scores WHERE post_id = ?", [post_id])
            assert row is not None
            assert row["score"] == 0.95

    def test_upsert_score_updates_existing_record(self, tmp_path):
        """Test that upsert_score updates an existing score record."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            source_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            post_id = exec_(
                conn,
                "INSERT INTO posts (source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    source_id,
                    "Test Post",
                    "http://test.com/post",
                    "Author",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "Content",
                    "hash123",
                    100,
                    "unread",
                ],
            )

            upsert_score(
                conn, post_id, datetime.now().isoformat(), 0.95, {"relevance": 0.8, "quality": 1.0}
            )
            upsert_score(
                conn, post_id, datetime.now().isoformat(), 0.98, {"relevance": 0.95, "quality": 1.0}
            )

        with session(db) as conn:
            row = q1(conn, "SELECT score FROM scores WHERE post_id = ?", [post_id])
            assert row is not None
            assert row["score"] == 0.98

    def test_upsert_score_stores_breakdown_json(self, tmp_path):
        """Test that upsert_score stores the breakdown as JSON."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            source_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            post_id = exec_(
                conn,
                "INSERT INTO posts (source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    source_id,
                    "Test Post",
                    "http://test.com/post",
                    "Author",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "Content",
                    "hash123",
                    100,
                    "unread",
                ],
            )

            breakdown = {"relevance": 0.8, "quality": 1.0, "recency": 0.9}
            upsert_score(conn, post_id, datetime.now().isoformat(), 0.95, breakdown)

        with session(db) as conn:
            row = q1(conn, "SELECT breakdown_json FROM scores WHERE post_id = ?", [post_id])
            assert row is not None
            stored_breakdown = json.loads(row["breakdown_json"])
            assert stored_breakdown == breakdown

    def test_upsert_score_only_one_record_per_post(self, tmp_path):
        """Test that upsert_score maintains only one record per post."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            source_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            post_id = exec_(
                conn,
                "INSERT INTO posts (source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    source_id,
                    "Test Post",
                    "http://test.com/post",
                    "Author",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "Content",
                    "hash123",
                    100,
                    "unread",
                ],
            )

            upsert_score(conn, post_id, datetime.now().isoformat(), 0.95, {"relevance": 0.8})
            upsert_score(conn, post_id, datetime.now().isoformat(), 0.98, {"relevance": 0.95})

        with session(db) as conn:
            rows = qall(conn, "SELECT score FROM scores WHERE post_id = ?", [post_id])
            assert len(rows) == 1
            assert rows[0]["score"] == 0.98


class TestUpsertSummary:
    """Tests for the upsert_summary function."""

    def test_upsert_summary_inserts_new_record(self, tmp_path):
        """Test that upsert_summary inserts a new summary record."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            source_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            post_id = exec_(
                conn,
                "INSERT INTO posts (source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    source_id,
                    "Test Post",
                    "http://test.com/post",
                    "Author",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "Content",
                    "hash123",
                    100,
                    "unread",
                ],
            )

            upsert_summary(
                conn,
                post_id,
                "detailed",
                "gpt-4",
                "hash123",
                "This is a summary.",
                datetime.now().isoformat(),
            )

        with session(db) as conn:
            row = q1(
                conn,
                "SELECT summary_text FROM summaries WHERE post_id = ? AND mode = ? AND model = ?",
                [post_id, "detailed", "gpt-4"],
            )
            assert row is not None
            assert row["summary_text"] == "This is a summary."

    def test_upsert_summary_replaces_existing_record(self, tmp_path):
        """Test that upsert_summary replaces an existing summary record."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            source_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            post_id = exec_(
                conn,
                "INSERT INTO posts (source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    source_id,
                    "Test Post",
                    "http://test.com/post",
                    "Author",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "Content",
                    "hash123",
                    100,
                    "unread",
                ],
            )

            upsert_summary(
                conn,
                post_id,
                "detailed",
                "gpt-4",
                "hash123",
                "First summary.",
                datetime.now().isoformat(),
            )
            upsert_summary(
                conn,
                post_id,
                "detailed",
                "gpt-4",
                "hash123",
                "Updated summary.",
                datetime.now().isoformat(),
            )

        with session(db) as conn:
            row = q1(
                conn,
                "SELECT summary_text FROM summaries WHERE post_id = ? AND mode = ? AND model = ?",
                [post_id, "detailed", "gpt-4"],
            )
            assert row is not None
            assert row["summary_text"] == "Updated summary."

    def test_upsert_summary_multiple_summaries_for_same_post(self, tmp_path):
        """Test that multiple summaries can exist for the same post with different parameters."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            source_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            post_id = exec_(
                conn,
                "INSERT INTO posts (source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    source_id,
                    "Test Post",
                    "http://test.com/post",
                    "Author",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "Content",
                    "hash123",
                    100,
                    "unread",
                ],
            )

            upsert_summary(
                conn,
                post_id,
                "detailed",
                "gpt-4",
                "hash123",
                "Detailed summary.",
                datetime.now().isoformat(),
            )
            upsert_summary(
                conn,
                post_id,
                "concise",
                "gpt-4",
                "hash123",
                "Concise summary.",
                datetime.now().isoformat(),
            )
            upsert_summary(
                conn,
                post_id,
                "detailed",
                "local",
                "hash123",
                "Local detailed summary.",
                datetime.now().isoformat(),
            )

        with session(db) as conn:
            rows = qall(
                conn,
                "SELECT mode, model, summary_text FROM summaries WHERE post_id = ? ORDER BY mode",
                [post_id],
            )
            assert len(rows) == 3
            assert rows[0]["summary_text"] == "Concise summary."
            assert rows[1]["summary_text"] == "Detailed summary."
            assert rows[2]["summary_text"] == "Local detailed summary."

    def test_upsert_summary_with_different_content_hashes(self, tmp_path):
        """Test that summaries with different content hashes are stored separately."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        with session(db) as conn:
            source_id = exec_(
                conn,
                "INSERT INTO sources (name, url, type, weight, tags, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    "Test Source",
                    "http://test.com/rss",
                    "rss",
                    1.0,
                    "",
                    1,
                    datetime.now().isoformat(),
                ],
            )
            post_id = exec_(
                conn,
                "INSERT INTO posts (source_id, title, url, author, published_at, fetched_at, content_text, content_hash, word_count, read_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    source_id,
                    "Test Post",
                    "http://test.com/post",
                    "Author",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "Content",
                    "hash123",
                    100,
                    "unread",
                ],
            )

            upsert_summary(
                conn,
                post_id,
                "detailed",
                "gpt-4",
                "hash123",
                "Summary for hash123.",
                datetime.now().isoformat(),
            )
            upsert_summary(
                conn,
                post_id,
                "detailed",
                "gpt-4",
                "hash456",
                "Summary for hash456.",
                datetime.now().isoformat(),
            )

        with session(db) as conn:
            rows = qall(
                conn,
                "SELECT content_hash, summary_text FROM summaries WHERE post_id = ? ORDER BY content_hash",
                [post_id],
            )
            assert len(rows) == 2
            assert rows[0]["summary_text"] == "Summary for hash123."
            assert rows[1]["summary_text"] == "Summary for hash456."


class TestIntegration:
    """Integration tests for multiple database operations."""

    def test_complete_workflow(self, tmp_path):
        """Test a complete workflow of database operations."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        # Create a source
        with session(db) as conn:
            source_id = exec_(
                conn,
                """
                INSERT INTO sources (name, url, type, weight, tags, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    "Tech News",
                    "http://technews.com/rss",
                    "rss",
                    1.5,
                    "technology",
                    1,
                    datetime.now().isoformat(),
                ],
            )

        # Create a post
        with session(db) as conn:
            post_id = exec_(
                conn,
                """
                INSERT INTO posts (source_id, title, url, author, published_at, fetched_at,
                                 content_text, content_hash, word_count, read_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    source_id,
                    "New Python Features",
                    "http://technews.com/python",
                    "Jane Doe",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "Python 3.12 introduces new features...",
                    "abc123",
                    500,
                    "unread",
                ],
            )

        # Add a score
        with session(db) as conn:
            upsert_score(
                conn,
                post_id,
                datetime.now().isoformat(),
                0.92,
                {"relevance": 0.85, "quality": 1.0, "recency": 0.9},
            )

        # Add a summary
        with session(db) as conn:
            upsert_summary(
                conn,
                post_id,
                "detailed",
                "gpt-4",
                "abc123",
                "Python 3.12 introduces async improvements and better type hints.",
                datetime.now().isoformat(),
            )

        # Verify all data
        with session(db) as conn:
            # Check source
            source = q1(conn, "SELECT name FROM sources WHERE id = ?", [source_id])
            assert source["name"] == "Tech News"

            # Check post
            post = q1(conn, "SELECT title FROM posts WHERE id = ?", [post_id])
            assert post["title"] == "New Python Features"

            # Check score
            score = q1(conn, "SELECT score FROM scores WHERE post_id = ?", [post_id])
            assert abs(score["score"] - 0.92) < 0.01

            # Check summary
            summary = q1(conn, "SELECT summary_text FROM summaries WHERE post_id = ?", [post_id])
            assert "Python 3.12" in summary["summary_text"]

        # Update the post
        with session(db) as conn:
            exec_(conn, "UPDATE posts SET read_state = ? WHERE id = ?", ["reading", post_id])

        # Verify update
        with session(db) as conn:
            post = q1(conn, "SELECT read_state FROM posts WHERE id = ?", [post_id])
            assert post["read_state"] == "reading"

    def test_transaction_rollback(self, tmp_path):
        """Test that transactions roll back on error."""
        db_file = tmp_path / "test.db"
        db = DB(path=str(db_file))

        init_db(db)

        try:
            with session(db) as conn:
                source_id = exec_(
                    conn,
                    """
                    INSERT INTO sources (name, url, type, weight, tags, enabled, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        "Test Source",
                        "http://test.com/rss",
                        "rss",
                        1.0,
                        "",
                        1,
                        datetime.now().isoformat(),
                    ],
                )

                # This will fail due to missing required field
                exec_(
                    conn,
                    """
                    INSERT INTO posts (source_id, title)
                    VALUES (?, ?)
                """,
                    [source_id, "Incomplete Post"],
                )

        except Exception:
            pass

        # Verify nothing was committed
        with session(db) as conn:
            sources = qall(conn, "SELECT name FROM sources")
            assert len(sources) == 0

            posts = qall(conn, "SELECT title FROM posts")
            assert len(posts) == 0
