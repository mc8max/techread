from __future__ import annotations

import os
import platform
import tomllib
from dataclasses import dataclass
from pathlib import Path


def _expand(p: str) -> str:
    """Expand environment variables and user paths in a string.

    Args:
        p: Path string containing environment variables or ~ notation

    Returns:
        Expanded path with environment variables and user paths resolved
    """
    return os.path.expanduser(os.path.expandvars(p))


def _default_config_path() -> Path:
    """Get the default path for the configuration file.

    Returns:
        Path object pointing to the config.toml file location.
        - Linux/macOS: ~/.config/techread/config.toml
        - Windows: %APPDATA%/techread/config.toml

    The function checks the platform and returns the appropriate default path
    based on operating system conventions.
    """
    # Linux/macOS: ~/.config/techread/config.toml
    # Windows: %APPDATA%/techread/config.toml
    if platform.system().lower().startswith("win"):
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / "techread" / "config.toml"
    return Path.home() / ".config" / "techread" / "config.toml"


def _default_db_path() -> str:
    """Get the default path for the SQLite database file.

    Returns:
        String path to the techread.db file location.
        - Linux/macOS: ~/.local/share/techread/techread.db
        - Windows: %LOCALAPPDATA%/techread/techread.db

    The function checks the platform and returns the appropriate default path
    based on operating system conventions.
    """
    if platform.system().lower().startswith("win"):
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return str(Path(base) / "techread" / "techread.db")
    return str(Path.home() / ".local" / "share" / "techread" / "techread.db")


def _default_cache_dir() -> str:
    """Get the default path for the cache directory.

    Returns:
        String path to the cache directory location.
        - Linux/macOS: ~/.local/share/techread/cache
        - Windows: %LOCALAPPDATA%/techread/cache

    The function checks the platform and returns the appropriate default path
    based on operating system conventions.
    """
    if platform.system().lower().startswith("win"):
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return str(Path(base) / "techread" / "cache")
    return str(Path.home() / ".local" / "share" / "techread" / "cache")


@dataclass(frozen=True)
class Settings:
    """Configuration settings for the TechRead application.

    This dataclass holds all the application configuration parameters
    that control behavior and resource locations.

    Attributes:
        db_path: Path to the SQLite database file
        cache_dir: Directory path for caching downloaded content
        llm_model: LLM model identifier/name to use for summarization
        default_top_n: Default number of items to return in queries
        topics: List of topic keywords/phrases for filtering content
    """

    db_path: str
    cache_dir: str
    llm_model: str
    default_top_n: int
    topics: list[str]


def load_settings() -> Settings:
    """Load application settings from configuration file and environment.

    This function loads settings from the following sources in order of precedence:
    1. Environment variables (highest priority)
    2. Configuration file
    3. Default values (lowest priority)

    Environment variables supported:
        - TECHREAD_DB_PATH: Override database path
        - TECHREAD_CACHE_DIR: Override cache directory
        - TECHREAD_LLM_MODEL: Override LLM model
        - TECHREAD_DEFAULT_TOP_N: Override default top N value

    Returns:
        Settings object containing all configuration parameters.

    The function ensures that required directories exist by creating them
    if necessary. It also processes the configuration file (TOML format) and
    validates all settings before returning them.
    """
    cfg_path = _default_config_path()
    data: dict = {}
    if cfg_path.exists():
        with cfg_path.open("rb") as f:
            data = tomllib.load(f) or {}

    db_path = _expand(str(data.get("db_path", _default_db_path())))
    cache_dir = _expand(str(data.get("cache_dir", _default_cache_dir())))
    llm_model = str(data.get("llm_model", data.get("llm_model", "nemotron-3-nano")))
    default_top_n = int(data.get("default_top_n", 10))
    topics = data.get("topics", []) or []
    topics = [str(t).strip() for t in topics if str(t).strip()]

    # Environment overrides (useful for testing); ignore empty values.
    env_db_path = os.environ.get("TECHREAD_DB_PATH")
    env_cache_dir = os.environ.get("TECHREAD_CACHE_DIR")
    env_llm_model = os.environ.get("TECHREAD_LLM_MODEL")

    if env_db_path:
        db_path = _expand(env_db_path)
    if env_cache_dir:
        cache_dir = _expand(env_cache_dir)
    if env_llm_model:
        llm_model = env_llm_model
    try:
        default_top_n = int(os.environ.get("TECHREAD_DEFAULT_TOP_N", str(default_top_n)))
    except ValueError:
        pass

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    return Settings(
        db_path=db_path,
        cache_dir=cache_dir,
        llm_model=llm_model,
        default_top_n=default_top_n,
        topics=topics,
    )
