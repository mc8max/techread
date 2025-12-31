# techread

A local CLI tool that fetches daily technical blogs/writings, ranks them for a busy reader, and (optionally) summarizes
them using a local LM Studio model.

## Quickstart

### 1) Install (recommended via pipx)
```bash
pipx install -e .
```

Or using a venv:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2) Add sources
```bash
techread sources add https://www.allthingsdistributed.com/atom.xml --name "All Things Distributed" --weight 1.3 --tags "distributed,sre"
techread sources add https://netflixtechblog.com/feed --name "Netflix TechBlog" --weight 1.1 --tags "systems,platform"
```

### 3) Fetch and view a digest
```bash
techread fetch
techread digest --today --top 10
```

### 4) Summarize a post (requires LM Studio running locally)
Start LM Studio and make sure a supported model is available, then:
```bash
techread summarize 42 --mode takeaways
```

## Config

techread looks for a config file at:

- macOS/Linux: `~/.config/techread/config.toml`
- Windows: `%APPDATA%\techread\config.toml`

Example `config.toml`:
```toml
db_path = "~/.local/share/techread/techread.db"
cache_dir = "~/.local/share/techread/cache"
llm_model = "mistral-small-3.2"
default_top_n = 10
topics = ["distributed systems", "spark", "kafka", "data platform", "reliability", "llm"]
min_word_count = 500
```

## Commands (high level)

- `techread fetch`
- `techread rank --today`
- `techread digest --today`
- `techread summarize <id>`
- `techread open <id>`
- `techread mark <id> --read|--saved|--skip|--unread`
- `techread sources ...`

Source hygiene:
- `techread sources purge [--dry-run]` removes posts with `word_count < min_word_count`.

## Notes

- RSS/Atom is preferred. techread fetches linked articles, extracts readable text via `trafilatura`,
  and stores it locally in SQLite.
- Summaries are cached by content hash so repeated runs are fast.

MIT License.
