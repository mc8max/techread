from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA_SQL = '''
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
'''


@dataclass(frozen=True)
class DB:
    path: str


def connect(db: DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db.path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db: DB) -> None:
    Path(db.path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


@contextmanager
def session(db: DB):
    conn = connect(db)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def q1(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    cur = conn.execute(sql, tuple(params))
    return cur.fetchone()


def qall(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()):
    cur = conn.execute(sql, tuple(params))
    return cur.fetchall()


def exec_(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> int:
    cur = conn.execute(sql, tuple(params))
    return int(cur.lastrowid)


def upsert_score(conn: sqlite3.Connection, post_id: int, scored_at: str, score: float, breakdown: dict) -> None:
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
    conn.execute(
        "INSERT OR REPLACE INTO summaries(post_id, mode, model, content_hash, summary_text, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (post_id, mode, model, content_hash, summary_text, created_at),
    )
