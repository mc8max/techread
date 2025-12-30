from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

"""Database module for TechRead application.

This module provides database functionality using SQLite to store and manage:
- Sources: RSS feeds and other content sources
- Posts: Individual articles and posts fetched from sources
- Scores: Scoring information for posts (relevance, quality, etc.)
- Summaries: Generated summaries of post content

The database schema includes:
1. sources table: Stores information about content sources (RSS feeds, etc.)
2. posts table: Stores individual articles/posts with metadata
3. scores table: Stores scoring information for posts
4. summaries table: Stores generated summaries of post content

Database operations are designed to be efficient and thread-safe using
context managers for connection handling.
"""

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  type TEXT NOT NULL DEFAULT 'rss',
  weight REAL NOT NULL DEFAULT 1.0,
  tags TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  author TEXT NOT NULL DEFAULT '',
  published_at TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  content_text TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  word_count INTEGER NOT NULL DEFAULT 0,
  read_state TEXT NOT NULL DEFAULT 'unread',
  FOREIGN KEY(source_id) REFERENCES sources(id)
);

CREATE INDEX IF NOT EXISTS idx_posts_published_at ON posts(published_at);
CREATE INDEX IF NOT EXISTS idx_posts_read_state ON posts(read_state);
CREATE INDEX IF NOT EXISTS idx_posts_source_id ON posts(source_id);

CREATE TABLE IF NOT EXISTS scores (
  post_id INTEGER PRIMARY KEY,
  scored_at TEXT NOT NULL,
  score REAL NOT NULL,
  breakdown_json TEXT NOT NULL,
  FOREIGN KEY(post_id) REFERENCES posts(id)
);

CREATE TABLE IF NOT EXISTS summaries (
  post_id INTEGER NOT NULL,
  mode TEXT NOT NULL,
  model TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  summary_text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (post_id, mode, model, content_hash),
  FOREIGN KEY(post_id) REFERENCES posts(id)
);
"""


@dataclass(frozen=True)
class DB:
    """Database configuration dataclass.

    Attributes:
        path: File system path to the SQLite database file.
    """
    path: str


def connect(db: DB) -> sqlite3.Connection:
    """Establish a connection to the SQLite database.

    Args:
        db: Database configuration containing the path to the database file.

    Returns:
        sqlite3.Connection: A connection object configured with Row factory
            for dictionary-like row access.

    Note:
        The connection is not automatically committed. Caller must commit
        or use the session context manager for automatic commit/rollback.
    """
    conn = sqlite3.connect(db.path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db: DB) -> None:
    """Initialize the database by creating all required tables and schema.

    Args:
        db: Database configuration containing the path to the database file.

    Returns:
        None

    Side Effects:
        - Creates parent directories if they don't exist
        - Executes the schema SQL to create all tables and indexes
        - Commits the transaction

    Note:
        This function is idempotent - can be safely called multiple times
        as the schema uses IF NOT EXISTS clauses.
    """
    Path(db.path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


@contextmanager
def session(db: DB):
    """Context manager for database sessions with automatic commit/rollback.

    Args:
        db: Database configuration containing the path to the database file.

    Yields:
        sqlite3.Connection: A database connection for use within the context.

    Example:
        >>> with session(db) as conn:
        ...     q1(conn, "INSERT INTO sources VALUES (?, ?, ?)", [1, "name", "url"])
        ...     # Transaction automatically committed on success
    """
    conn = connect(db)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def q1(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    """Execute a query and return the first row.

    Args:
        conn: Database connection object.
        sql: SQL query string to execute.
        params: Optional parameters for the SQL query.

    Returns:
        sqlite3.Row | None: A single row as a dictionary-like object, or None
            if no rows match the query.

    Example:
        >>> row = q1(conn, "SELECT * FROM sources WHERE id = ?", [1])
        >>> if row: print(row['name'])
    """
    cur = conn.execute(sql, tuple(params))
    return cur.fetchone()


def qall(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()):
    """Execute a query and return all matching rows.

    Args:
        conn: Database connection object.
        sql: SQL query string to execute.
        params: Optional parameters for the SQL query.

    Returns:
        list[sqlite3.Row]: List of rows as dictionary-like objects.

    Example:
        >>> rows = qall(conn, "SELECT * FROM sources WHERE enabled = ?", [1])
        >>> for row in rows: print(row['name'])
    """
    cur = conn.execute(sql, tuple(params))
    return cur.fetchall()


def exec_(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> int:
    """Execute an INSERT or UPDATE statement and return the row ID.

    Args:
        conn: Database connection object.
        sql: SQL statement to execute (typically INSERT or UPDATE).
        params: Optional parameters for the SQL statement.

    Returns:
        int: The row ID of the last inserted row, or 0 for UPDATE statements.

    Note:
        For INSERT statements with AUTOINCREMENT primary keys, returns the
        newly created row ID. For UPDATE statements or INSERT without
        AUTOINCREMENT, returns 0.

    Example:
        >>> post_id = exec_(conn, "INSERT INTO posts VALUES (?, ?, ?)", [1, "title", "url"])
    """
    cur = conn.execute(sql, tuple(params))
    return int(cur.lastrowid)


def upsert_score(
    conn: sqlite3.Connection, post_id: int, scored_at: str, score: float, breakdown: dict
) -> None:
    """Insert or update a post's scoring information.

    Args:
        conn: Database connection object.
        post_id: ID of the post being scored.
        scored_at: Timestamp when scoring occurred (ISO format).
        score: The calculated score value.
        breakdown: Dictionary containing detailed scoring breakdown.

    Returns:
        None

    Side Effects:
        - Inserts a new score record if one doesn't exist
        - Updates existing score record with new values

    Note:
        Uses ON CONFLICT to handle upserts efficiently.
    """
    conn.execute(
        "INSERT INTO scores(post_id, scored_at, score, breakdown_json) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(post_id) DO UPDATE SET scored_at=excluded.scored_at, score=excluded.score, breakdown_json=excluded.breakdown_json",
        (post_id, scored_at, float(score), json.dumps(breakdown, ensure_ascii=False)),
    )


def upsert_summary(
    conn: sqlite3.Connection,
    post_id: int,
    mode: str,
    model: str,
    content_hash: str,
    summary_text: str,
    created_at: str,
) -> None:
    """Insert or replace a post's summary information.

    Args:
        conn: Database connection object.
        post_id: ID of the post being summarized.
        mode: Summary mode (e.g., 'detailed', 'concise').
        model: Model used to generate the summary (e.g., 'gpt-4', 'local').
        content_hash: Hash of the post content used for summary generation.
        summary_text: The generated summary text.
        created_at: Timestamp when summary was created (ISO format).

    Returns:
        None

    Side Effects:
        - Inserts a new summary record
        - Replaces existing summary if one exists with same post_id, mode, model, and content_hash

    Note:
        The composite primary key (post_id, mode, model, content_hash) ensures
        that multiple summaries can be stored for the same post with different
        parameters.
    """
    conn.execute(
        "INSERT OR REPLACE INTO summaries(post_id, mode, model, content_hash, summary_text, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (post_id, mode, model, content_hash, summary_text, created_at),
    )
