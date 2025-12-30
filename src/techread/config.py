from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
import tomllib


def _expand(p: str) -> str:
    return os.path.expanduser(os.path.expandvars(p))


def _default_config_path() -> Path:
    # Linux/macOS: ~/.config/techread/config.toml
    # Windows: %APPDATA%/techread/config.toml
    if platform.system().lower().startswith("win"):
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / "techread" / "config.toml"
    return Path.home() / ".config" / "techread" / "config.toml"


def _default_db_path() -> str:
    if platform.system().lower().startswith("win"):
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return str(Path(base) / "techread" / "techread.db")
    return str(Path.home() / ".local" / "share" / "techread" / "techread.db")


def _default_cache_dir() -> str:
    if platform.system().lower().startswith("win"):
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return str(Path(base) / "techread" / "cache")
    return str(Path.home() / ".local" / "share" / "techread" / "cache")


@dataclass(frozen=True)
class Settings:
    db_path: str
    cache_dir: str
    ollama_host: str
    ollama_model: str
    default_top_n: int
    topics: list[str]


def load_settings() -> Settings:
    cfg_path = _default_config_path()
    data: dict = {}
    if cfg_path.exists():
        with cfg_path.open("rb") as f:
            data = tomllib.load(f) or {}

    db_path = _expand(str(data.get("db_path", _default_db_path())))
    cache_dir = _expand(str(data.get("cache_dir", _default_cache_dir())))
    ollama_host = str(data.get("ollama_host", "http://localhost:11434")).rstrip("/")
    ollama_model = str(data.get("ollama_model", "mistral-small-3.2"))
    default_top_n = int(data.get("default_top_n", 10))
    topics = data.get("topics", []) or []
    topics = [str(t).strip() for t in topics if str(t).strip()]

    # Environment overrides (useful for testing)
    db_path = _expand(os.environ.get("TECHREAD_DB_PATH", db_path))
    cache_dir = _expand(os.environ.get("TECHREAD_CACHE_DIR", cache_dir))
    ollama_host = os.environ.get("TECHREAD_OLLAMA_HOST", ollama_host).rstrip("/")
    ollama_model = os.environ.get("TECHREAD_OLLAMA_MODEL", ollama_model)
    try:
        default_top_n = int(os.environ.get("TECHREAD_DEFAULT_TOP_N", str(default_top_n)))
    except ValueError:
        pass

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    return Settings(
        db_path=db_path,
        cache_dir=cache_dir,
        ollama_host=ollama_host,
        ollama_model=ollama_model,
        default_top_n=default_top_n,
        topics=topics,
    )
