# Architecture

**techread** is a local-first CLI tool that **fetches technical writing**, **ranks it for a busy reader**, and can **summarize content locally** using **LM Studio**.  
This document describes the architecture as implemented in the generated repository.

---

## Goals

- **Local-first**: everything runs on your machine; content and metadata stored locally.
- **Busy-reader UX**: fast daily digest, explainable ranking, time-budget mode.
- **Incremental complexity**: start with RSS + keyword scoring; upgrade later to embeddings, advanced dedupe, UI.
- **Idempotent commands**: safe to re-run `fetch`, `rank`, and `digest`.

## Non-goals (for MVP)

- No complex crawling across the web (RSS/Atom is primary).
- No cloud services required.
- No collaborative features / multi-user permissions.
- No heavy semantic search (can be added later).

---

## System Overview

### High-level pipeline

1. **Ingest**: Read RSS/Atom feeds → discover post URLs + metadata.
2. **Fetch**: Download article HTML (cached locally).
3. **Extract**: Convert HTML to clean text (readability extraction).
4. **Persist**: Store metadata + extracted text in SQLite.
5. **Rank**: Compute a per-post score (explainable breakdown) and store it.
6. **Summarize (optional)**: Call LM Studio locally; cache summaries keyed by content hash.
7. **Present**: Render ranked list/digest in terminal with Rich.

---

## Component Diagram

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│     CLI       │────▶│  Service/Flow │────▶│     DB        │
│  (Typer)      │     │ (orchestrate) │     │  (SQLite)     │
└──────┬────────┘     └──────┬────────┘     └──────┬────────┘
       │                     │                     │
       │                     ▼                     │
       │             ┌───────────────┐            │
       │             │ Ingest/Fetch  │            │
       │             │ RSS + HTTP    │            │
       │             └──────┬────────┘            │
       │                    ▼                     │
       │             ┌───────────────┐            │
       │             │  Extraction   │            │
       │             │ (trafilatura) │            │
       │             └──────┬────────┘            │
       │                    ▼                     │
       │             ┌───────────────┐            │
       │             │    Ranker     │            │
       │             │ (scoring.py)  │            │
       │             └──────┬────────┘            │
       │                    ▼                     │
       │             ┌───────────────┐            │
       │             │ Summarizer    │            │
       │             │ (LM Studio)   │            │
       │             └───────────────┘            │
       ▼                                          ▼
┌───────────────┐                          ┌───────────────┐
│ Terminal UI   │                          │ Local Cache   │
│   (Rich)      │                          │ HTML files    │
└───────────────┘                          └───────────────┘
```

---

## Repository Structure

```
src/techread/
  cli/
    __init__.py           # Typer app wiring
    common.py             # shared CLI helpers/options
    filters.py            # shared query filters
    posts.py              # fetch/rank/digest/summarize/open/mark
    sources.py            # sources subcommands
  config.py               # config discovery + env overrides
  db.py                   # SQLite schema + helper functions
  ingest/
    rss.py                # feed parsing (feedparser)
    fetch.py              # http fetch + disk cache (httpx)
    extract.py            # HTML->text extraction (trafilatura)
  rank/
    scoring.py            # explainable scoring formula
  summarize/
    llm.py                # local LM Studio client + prompts
  digest/
    render.py             # Rich output renderers
  tags/
    llm.py                # tag generation + normalization
  sources/
    auto.py               # source name/tag autofill helpers
  utils/
    text.py               # hashing, normalization, keyword hits
    time.py               # iso times, date parsing
```

---

## Tech Stack

- **Python 3.11+**
- **Typer**: CLI commands
- **Rich**: terminal rendering
- **SQLite**: persistent local storage (WAL mode)
- **feedparser**: RSS/Atom parsing
- **httpx**: HTTP client with redirects and timeout
- **trafilatura**: content extraction to readable text
- **python-dateutil**: robust RSS datetime parsing
- **LM Studio** (optional): local LLM inference

---

## Configuration

### Where config is loaded from

- macOS/Linux: `~/.config/techread/config.toml`
- Windows: `%APPDATA%\techread\config.toml`

### Keys

- `db_path`: SQLite database path
- `cache_dir`: disk cache directory for fetched HTML
- `llm_model`: e.g. `mistral-small-3.2`
- `default_top_n`: default digest size
- `topics`: list of keywords used for simple relevance scoring
- `min_word_count`: minimum word count required to keep a post

### Environment overrides

- `TECHREAD_DB_PATH`
- `TECHREAD_CACHE_DIR`
- `TECHREAD_LLM_MODEL`
- `TECHREAD_DEFAULT_TOP_N`
- `TECHREAD_MIN_WORD_COUNT`

---

## Storage Model

techread stores all operational state locally in SQLite.

### Schema Summary

- `sources`: feed definitions and ranking weight
- `posts`: post metadata + extracted text
- `scores`: latest score and “why” breakdown per post
- `summaries`: cached summaries keyed by `(post, mode, model, content_hash)`

### Tables

**sources**
- `id` (PK)
- `name`
- `url` (UNIQUE)
- `type` (`rss` for MVP)
- `weight` (ranking prior)
- `tags` (comma-separated; for future use)
- `enabled` (0/1)
- `created_at`

**posts**
- `id` (PK)
- `source_id` (FK)
- `title`
- `url` (UNIQUE)
- `author`
- `published_at` (ISO string)
- `fetched_at` (ISO string)
- `content_text` (extracted)
- `content_hash` (SHA256 of `content_text`)
- `word_count`
- `read_state` (`unread|read|saved|skip`)

**scores**
- `post_id` (PK, FK → posts)
- `scored_at`
- `score` (float)
- `breakdown_json` (explainability payload)

**summaries**
- `post_id` (FK)
- `mode` (`short|bullets|takeaways|comprehensive`)
- `model` (LM Studio model name)
- `content_hash` (ties summary to specific content version)
- `summary_text`
- `created_at`
- PK: `(post_id, mode, model, content_hash)`

---

## Disk Cache

Fetched HTML is cached on disk under:

```
<cache_dir>/html/<sha256(url)>.html
```

This enables:
- fast re-runs (avoid refetch)
- offline inspection/troubleshooting
- resilience to transient network issues

---

## Command-Level Flows

### `techread sources add`
1. Insert into `sources` with `enabled=1`.
2. If `name` or `tags` are missing, parse feed metadata and auto-fill.
3. Tag generation uses LM Studio and normalizes to lowercase, hyphenated tags (max 5).

### `techread sources autofill`
1. Select sources (all or `--id`).
2. For each source, fill missing `name`/`tags` (or overwrite with `--force`).
3. Tag generation uses feed metadata + recent titles/snippets, normalized to lowercase,
   hyphenated tags (max 5).

### `techread sources purge`
1. Remove posts with `word_count < min_word_count`.
2. Optional `--dry-run` shows counts without deleting.

### `techread fetch`
For each enabled source:
1. Parse RSS/Atom feed entries.
2. For each entry:
   - Skip if `posts.url` already exists (dedupe).
   - Fetch HTML (disk-cached).
   - Extract `content_text` + `word_count`.
   - Compute `content_hash`.
   - If `word_count < min_word_count`, skip insert and log to `invalid_posts.log`.
   - Otherwise insert into `posts`.

**Failure behavior**
- Feed parse failures are logged and do not stop other sources.
- Fetch/extract failures still insert metadata, with empty content (so you can open URL).

### `techread rank`
1. Select posts in the time window (default: last 48 hours) and not read (unless `--include-read`).
2. Optional filtering by source ids (`-s/--source`) and source name/tags (`-t/--tag`).
2. Compute `score` + `breakdown_json` for each post.
3. Upsert into `scores`.
4. Print top N by score.

### `techread digest`
1. Ensure posts in window have scores (score if missing).
2. Optional filtering by source ids (`-s/--source`) and source name/tags (`-t/--tag`).
2. Pull a ranked candidate set (`top * 3`).
3. Optionally apply **time budget**:
   - Estimate minutes as `max(1, round(word_count / 220))`.
   - Choose items greedily by `score / minutes`.
4. Optionally generate missing `short` summaries (LM Studio) and cache them.
5. Render digest view.

### `techread summarize`
1. Load post by id.
2. Check cached summary by `(mode, model, content_hash)`.
3. If missing, call LM Studio and store summary.
4. `comprehensive` mode returns a structured report with sections for summary,
   key points, technical details, risks/limitations, and action items.
5. Mode aliases: `s=short`, `b=bullets`, `t=takeaways`, `c=comprehensive`.

### `techread mark`
Update `posts.read_state`.

---

## Ranking (Explainable Scoring)

MVP scoring is lightweight and tunable.

### Inputs

- `age_hours` (from `published_at`)
- `source_weight` (manual prior per source)
- `topic_hits` (simple keyword matches)
- `word_count` (length penalty)

### Formula (current implementation)

- Freshness: `exp(-age_hours / 36)`
- Topic score: `min(topic_hits * 0.15, 0.6)`
- Length penalty: `min(word_count / 2500, 1.0) * 0.30`

Final score:

```
score = 1.00 * freshness
      + 0.20 * source_weight
      + 0.70 * topic_score
      - 1.00 * length_penalty
```

### Explainability

`breakdown_json` stores freshness, topic hits, penalties, and final score.

---

## Summarization (LM Studio)

### Modes

- `short`: 2–3 sentence TL;DR
- `bullets`: up to 5 bullets
- `takeaways`: 3 takeaways + “why it matters” + one action

### Caching Strategy

Cache key:
- `(post_id, mode, model, content_hash)`

If extracted content changes, cached summaries naturally invalidate.

### Request Size Control

Article text is clipped to **12,000 characters** for summarization.

---

## Error Handling & Resilience

- Each source fetch is isolated; failures don’t stop the whole run.
- HTML caching reduces repeated network calls.
- Missing extraction results are tolerated (post still stored).
- Summarization failures produce a helpful message (commonly: LM Studio not running).

---

## Security & Privacy

- Local-first storage: content stays on your machine.
- Outbound requests: RSS + HTTP fetch.
- No inbound server is exposed.
- LM Studio inference is local.

---

## Extension Points (Roadmap-Friendly)

### Near-term
- Add **FTS5 search** over `posts.content_text`.
- Add **redundancy penalty** (avoid many similar posts in top N).
- Improve keyword matching (stemming, synonyms, weighted topics).

### Medium-term
- Add **embeddings** for semantic relevance and clustering.
- Add **backfill** (import older feed entries).
- Add **update detection** (re-fetch changed posts).

### Long-term
- TUI or web UI reusing the same service layer.
- Pluggable source types (GitHub releases, newsletter archives).

---

## Appendix: Suggested refactor (service layer)

As the project grows, move orchestration out of `cli.py` into `services/`:

- `services/ingestion.py`
- `services/ranking.py`
- `services/summarization.py`

This enables additional frontends (daemon/TUI/web) without duplicating logic.
