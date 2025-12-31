"""Unit tests for the config module."""

import dataclasses
import os
import platform
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from techread.config import (
    Settings,
    _default_cache_dir,
    _default_config_path,
    _default_db_path,
    _expand,
    load_settings,
)


class TestExpand:
    """Tests for the _expand function."""

    def test_expand_user_path(self):
        """Test that ~ is expanded to home directory."""
        result = _expand("~/test")
        assert result.startswith(os.path.expanduser("~"))
        assert result.endswith("/test")

    def test_expand_env_var(self):
        """Test that environment variables are expanded."""
        os.environ["TEST_VAR"] = "/tmp/test"
        result = _expand("$TEST_VAR/file")
        assert result == "/tmp/test/file"

    def test_expand_unknown_env_var(self):
        """Test that unknown environment variables are preserved."""
        result = _expand("$UNKNOWN_VAR/file")
        assert "$UNKNOWN_VAR" in result

    def test_expand_no_substitution(self):
        """Test that plain paths are returned unchanged."""
        result = _expand("/tmp/plain/path")
        assert result == "/tmp/plain/path"


class TestDefaultPaths:
    """Tests for default path functions."""

    def test_default_config_path_linux_mac(self):
        """Test default config path on Linux/macOS."""
        if not platform.system().lower().startswith("win"):
            home = str(Path.home())
            result = _default_config_path()
            assert str(result).startswith(f"{home}/.config/techread/config.toml")

    def test_default_config_path_windows(self):
        """Test default config path on Windows."""
        if platform.system().lower().startswith("win"):
            str(Path.home())
            result = _default_config_path()
            assert "AppData" in str(result)
            assert "config.toml" in str(result)

    def test_default_db_path_linux_mac(self):
        """Test default DB path on Linux/macOS."""
        if not platform.system().lower().startswith("win"):
            home = str(Path.home())
            result = _default_db_path()
            assert str(result).startswith(f"{home}/.local/share/techread/techread.db")

    def test_default_db_path_windows(self):
        """Test default DB path on Windows."""
        if platform.system().lower().startswith("win"):
            str(Path.home())
            result = _default_db_path()
            assert "AppData" in str(result)
            assert "techread.db" in str(result)

    def test_default_cache_dir_linux_mac(self):
        """Test default cache dir on Linux/macOS."""
        if not platform.system().lower().startswith("win"):
            home = str(Path.home())
            result = _default_cache_dir()
            assert str(result).startswith(f"{home}/.local/share/techread/cache")

    def test_default_cache_dir_windows(self):
        """Test default cache dir on Windows."""
        if platform.system().lower().startswith("win"):
            str(Path.home())
            result = _default_cache_dir()
            assert "AppData" in str(result)
            assert "cache" in str(result)


class TestSettings:
    """Tests for the Settings dataclass."""

    def test_settings_creation(self):
        """Test that Settings can be created with valid data."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=5,
            topics=["topic1", "topic2"],
        )
        assert settings.db_path == "/tmp/test.db"
        assert settings.cache_dir == "/tmp/cache"
        assert settings.llm_model == "test-model"
        assert settings.default_top_n == 5
        assert settings.topics == ["topic1", "topic2"]
        assert settings.min_word_count == 500

    def test_settings_immutable(self):
        """Test that Settings is immutable (frozen)."""
        settings = Settings(
            db_path="/tmp/test.db",
            cache_dir="/tmp/cache",
            llm_model="test-model",
            default_top_n=5,
            topics=["topic1"],
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.db_path = "/tmp/new.db"


class TestLoadSettings:
    """Tests for the load_settings function."""

    def test_load_settings_without_config_file(self, tmp_path):
        """Test loading settings when no config file exists."""
        with patch("techread.config._default_config_path") as mock_path:
            mock_path.return_value = tmp_path / "config.toml"
            settings = load_settings()

        assert isinstance(settings, Settings)
        assert settings.db_path.endswith("techread.db")
        assert settings.cache_dir.endswith("cache")
        assert settings.llm_model == "nemotron-3-nano"
        assert settings.default_top_n == 10
        assert settings.topics == []
        assert settings.min_word_count == 500

    def test_load_settings_with_config_file(self, tmp_path):
        """Test loading settings with a config file."""
        config_content = """
db_path = "/tmp/test.db"
cache_dir = "/tmp/cache"
llm_model = "custom-model"
default_top_n = 20
topics = ["python", "rust"]
min_word_count = 250
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        with patch("techread.config._default_config_path") as mock_path:
            mock_path.return_value = config_file
            settings = load_settings()

        assert settings.db_path == "/tmp/test.db"
        assert settings.cache_dir == "/tmp/cache"
        assert settings.llm_model == "custom-model"
        assert settings.default_top_n == 20
        assert settings.topics == ["python", "rust"]
        assert settings.min_word_count == 250

    def test_load_settings_with_env_overrides(self, tmp_path):
        """Test that environment variables override config file values."""
        config_content = """
db_path = "/tmp/test.db"
cache_dir = "/tmp/cache"
llm_model = "custom-model"
default_top_n = 20
topics = ["python", "rust"]
min_word_count = 250
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        # Save original env vars
        orig_db = os.environ.get("TECHREAD_DB_PATH")
        orig_cache = os.environ.get("TECHREAD_CACHE_DIR")
        orig_llm = os.environ.get("TECHREAD_LLM_MODEL")
        orig_top_n = os.environ.get("TECHREAD_DEFAULT_TOP_N")
        orig_min_wc = os.environ.get("TECHREAD_MIN_WORD_COUNT")

        try:
            os.environ["TECHREAD_DB_PATH"] = "/tmp/env/test.db"
            os.environ["TECHREAD_CACHE_DIR"] = "/tmp/env/cache"
            os.environ["TECHREAD_LLM_MODEL"] = "env-model"
            os.environ["TECHREAD_DEFAULT_TOP_N"] = "30"
            os.environ["TECHREAD_MIN_WORD_COUNT"] = "750"

            with patch("techread.config._default_config_path") as mock_path:
                mock_path.return_value = config_file
                settings = load_settings()

            assert settings.db_path == "/tmp/env/test.db"
            assert settings.cache_dir == "/tmp/env/cache"
            assert settings.llm_model == "env-model"
            assert settings.default_top_n == 30
            assert settings.topics == ["python", "rust"]
            assert settings.min_word_count == 750
        finally:
            # Restore original env vars
            if orig_db is not None:
                os.environ["TECHREAD_DB_PATH"] = orig_db
            elif "TECHREAD_DB_PATH" in os.environ:
                del os.environ["TECHREAD_DB_PATH"]

            if orig_cache is not None:
                os.environ["TECHREAD_CACHE_DIR"] = orig_cache
            elif "TECHREAD_CACHE_DIR" in os.environ:
                del os.environ["TECHREAD_CACHE_DIR"]

            if orig_llm is not None:
                os.environ["TECHREAD_LLM_MODEL"] = orig_llm
            elif "TECHREAD_LLM_MODEL" in os.environ:
                del os.environ["TECHREAD_LLM_MODEL"]

            if orig_top_n is not None:
                os.environ["TECHREAD_DEFAULT_TOP_N"] = orig_top_n
            elif "TECHREAD_DEFAULT_TOP_N" in os.environ:
                del os.environ["TECHREAD_DEFAULT_TOP_N"]

            if orig_min_wc is not None:
                os.environ["TECHREAD_MIN_WORD_COUNT"] = orig_min_wc
            elif "TECHREAD_MIN_WORD_COUNT" in os.environ:
                del os.environ["TECHREAD_MIN_WORD_COUNT"]

    def test_load_settings_with_empty_topics(self, tmp_path):
        """Test loading settings with empty topics list."""
        config_content = """
topics = []
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        with patch("techread.config._default_config_path") as mock_path:
            mock_path.return_value = config_file
            settings = load_settings()

        assert settings.topics == []

    def test_load_settings_with_whitespace_topics(self, tmp_path):
        """Test loading settings with topics containing whitespace."""
        config_content = """
topics = ["  python  ", "rust", "   ", "go"]
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        with patch("techread.config._default_config_path") as mock_path:
            mock_path.return_value = config_file
            settings = load_settings()

        assert settings.topics == ["python", "rust", "go"]

    def test_load_settings_creates_directories(self, tmp_path):
        """Test that load_settings creates required directories."""
        with TemporaryDirectory() as tmpdir:
            os.path.join(tmpdir, "new", "path", "test.db")
            os.path.join(tmpdir, "cache")

            config_content = """
db_path = "/tmp/nonexistent/test.db"
cache_dir = "/tmp/nonexistent/cache"
"""
            config_file = tmp_path / "config.toml"
            config_file.write_text(config_content)

            with patch("techread.config._default_config_path") as mock_path:
                mock_path.return_value = config_file

            settings = load_settings()

            assert os.path.exists(os.path.dirname(settings.db_path))
            assert os.path.exists(settings.cache_dir)

    def test_load_settings_invalid_default_top_n(self, tmp_path):
        """Test that invalid default_top_n is handled gracefully."""
        # Save original env var
        orig_top_n = os.environ.get("TECHREAD_DEFAULT_TOP_N")

        try:
            os.environ["TECHREAD_DEFAULT_TOP_N"] = "invalid"

            with patch("techread.config._default_config_path") as mock_path:
                mock_path.return_value = tmp_path / "config.toml"
                settings = load_settings()

            # Should fall back to default value
            assert settings.default_top_n == 10
        finally:
            # Restore original env var
            if orig_top_n is not None:
                os.environ["TECHREAD_DEFAULT_TOP_N"] = orig_top_n
            elif "TECHREAD_DEFAULT_TOP_N" in os.environ:
                del os.environ["TECHREAD_DEFAULT_TOP_N"]

    def test_load_settings_with_tilde_paths(self, tmp_path):
        """Test that tilde paths in config are expanded."""
        config_content = """
db_path = "~/test.db"
cache_dir = "~/.cache"
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        with patch("techread.config._default_config_path") as mock_path:
            mock_path.return_value = config_file
            settings = load_settings()

        assert "~" not in settings.db_path
        assert "~" not in settings.cache_dir

    def test_load_settings_with_env_vars_in_config(self, tmp_path):
        """Test that environment variables in config file are expanded."""
        # Save original env var
        orig_db = os.environ.get("MY_DB")

        try:
            os.environ["MY_DB"] = "/tmp/env_db"

            config_content = """
db_path = "$MY_DB/test.db"
"""
            config_file = tmp_path / "config.toml"
            config_file.write_text(config_content)

            with patch("techread.config._default_config_path") as mock_path:
                mock_path.return_value = config_file
                settings = load_settings()

            assert settings.db_path == "/tmp/env_db/test.db"
        finally:
            # Restore original env var
            if orig_db is not None:
                os.environ["MY_DB"] = orig_db
            elif "MY_DB" in os.environ:
                del os.environ["MY_DB"]
