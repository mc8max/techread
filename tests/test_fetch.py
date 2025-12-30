"""Unit tests for the fetch module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from techread.ingest.fetch import cache_path_for_url, fetch_html


class TestCachePathForUrl:
    """Test cases for cache_path_for_url function."""

    def test_basic_url(self) -> None:
        """Test generating cache path for a basic URL."""
        result = cache_path_for_url("/tmp/cache", "https://example.com")
        assert isinstance(result, Path)
        assert str(result).endswith(".html")
        assert "html" in str(result)

    def test_url_with_path(self) -> None:
        """Test generating cache path for URL with path."""
        result = cache_path_for_url("/tmp/cache", "https://example.com/page")
        assert isinstance(result, Path)
        assert str(result).endswith(".html")

    def test_url_with_query_params(self) -> None:
        """Test generating cache path for URL with query parameters."""
        result = cache_path_for_url("/tmp/cache", "https://example.com?param=value")
        assert isinstance(result, Path)
        assert str(result).endswith(".html")

    def test_url_with_fragment(self) -> None:
        """Test generating cache path for URL with fragment."""
        result = cache_path_for_url("/tmp/cache", "https://example.com#section")
        assert isinstance(result, Path)
        assert str(result).endswith(".html")

    def test_different_urls_same_hash(self) -> None:
        """Test that different URLs with same hash produce same path."""
        url1 = "https://example.com"
        url2 = "https://example.com"  # Same URL
        path1 = cache_path_for_url("/tmp/cache", url1)
        path2 = cache_path_for_url("/tmp/cache", url2)
        assert path1 == path2

    def test_different_urls_different_hash(self) -> None:
        """Test that different URLs produce different paths."""
        url1 = "https://example.com"
        url2 = "https://different.com"
        path1 = cache_path_for_url("/tmp/cache", url1)
        path2 = cache_path_for_url("/tmp/cache", url2)
        assert path1 != path2

    def test_absolute_path(self) -> None:
        """Test with absolute cache directory path."""
        result = cache_path_for_url("/tmp/cache", "https://example.com")
        assert str(result).startswith("/tmp/cache")

    def test_relative_path(self) -> None:
        """Test with relative cache directory path."""
        result = cache_path_for_url("cache", "https://example.com")
        assert str(result).startswith("cache")

    def test_unicode_in_url(self) -> None:
        """Test URL with unicode characters."""
        result = cache_path_for_url("/tmp/cache", "https://example.com/日本語")
        assert isinstance(result, Path)
        assert str(result).endswith(".html")

    def test_special_characters_in_url(self) -> None:
        """Test URL with special characters."""
        result = cache_path_for_url("/tmp/cache", "https://example.com/?key=value&foo=bar")
        assert isinstance(result, Path)
        assert str(result).endswith(".html")


class TestFetchHtml:
    """Test cases for fetch_html function."""

    @patch("techread.ingest.fetch.httpx.Client")
    def test_fetch_from_cache(self, mock_client_class) -> None:
        """Test that cached content is returned without fetching."""
        with tempfile.TemporaryDirectory() as cache_dir:
            # Create a cached file
            url = "https://example.com"
            cached_html = "<html><body>Cached content</body></html>"
            cache_path = Path(cache_dir) / "html" / "abc123.html"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(cached_html)

            # Mock the stable_hash to return predictable value
            with patch("techread.ingest.fetch.stable_hash", return_value="abc123"):
                result = fetch_html(url, cache_dir)
                assert result == cached_html
                # Verify no actual HTTP request was made
                mock_client_class.assert_not_called()

    @patch("techread.ingest.fetch.httpx.Client")
    def test_fetch_new_content(self, mock_client_class) -> None:
        """Test fetching new content and caching it."""
        with tempfile.TemporaryDirectory() as cache_dir:
            url = "https://example.com"
            html_content = "<html><body>New content</body></html>"

            # Mock the HTTP client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Mock stable_hash to return predictable value
            with patch("techread.ingest.fetch.stable_hash", return_value="new123"):
                result = fetch_html(url, cache_dir)
                assert result == html_content

                # Verify HTTP request was made
                mock_client.get.assert_called_once_with(url)

                # Verify content was cached
                cache_file = Path(cache_dir) / "html" / "new123.html"
                assert cache_file.exists()
                assert cache_file.read_text() == html_content

    @patch("techread.ingest.fetch.httpx.Client")
    def test_http_error_raised(self, mock_client_class) -> None:
        """Test that HTTP errors are properly raised."""
        with tempfile.TemporaryDirectory() as cache_dir:
            url = "https://example.com"

            # Mock the HTTP client to raise an error
            mock_client = Mock()
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = Exception("HTTP Error")
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Mock stable_hash
            with patch("techread.ingest.fetch.stable_hash", return_value="error123"):
                with pytest.raises(Exception, match="HTTP Error"):
                    fetch_html(url, cache_dir)

    @patch("techread.ingest.fetch.httpx.Client")
    def test_network_error_raised(self, mock_client_class) -> None:
        """Test that network errors are properly raised."""
        with tempfile.TemporaryDirectory() as cache_dir:
            url = "https://example.com"

            # Mock the HTTP client to raise a network error
            mock_client = Mock()
            mock_client.get.side_effect = Exception("Network Error")
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Mock stable_hash
            with patch("techread.ingest.fetch.stable_hash", return_value="network123"):
                with pytest.raises(Exception, match="Network Error"):
                    fetch_html(url, cache_dir)

    @patch("techread.ingest.fetch.httpx.Client")
    def test_cache_directory_created(self, mock_client_class) -> None:
        """Test that cache directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "new_cache"
            url = "https://example.com"
            html_content = "<html><body>Content</body></html>"

            # Mock the HTTP client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Mock stable_hash
            with patch("techread.ingest.fetch.stable_hash", return_value="dirtest123"):
                result = fetch_html(url, str(cache_dir))
                assert result == html_content
                # Verify directory was created
                assert cache_dir.exists()
                assert (cache_dir / "html").exists()

    @patch("techread.ingest.fetch.httpx.Client")
    def test_user_agent_customization(self, mock_client_class) -> None:
        """Test that custom user agent is used."""
        with tempfile.TemporaryDirectory() as cache_dir:
            url = "https://example.com"
            html_content = "<html><body>Content</body></html>"
            custom_ua = "my-custom-agent/1.0"

            # Mock the HTTP client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response

            # Track Client initialization
            client_init_calls = []

            def track_client(*args, **kwargs):
                client_init_calls.append(kwargs)
                mock_obj = Mock()
                mock_obj.__enter__ = Mock(return_value=mock_client)
                mock_obj.__exit__ = Mock(return_value=None)
                return mock_obj

            mock_client_class.side_effect = track_client

            # Mock stable_hash
            with patch("techread.ingest.fetch.stable_hash", return_value="uatest123"):
                result = fetch_html(url, cache_dir, user_agent=custom_ua)
                assert result == html_content

                # Verify custom user agent was used in Client initialization
                assert len(client_init_calls) == 1
                assert "headers" in client_init_calls[0]
                assert client_init_calls[0]["headers"]["User-Agent"] == custom_ua

    @patch("techread.ingest.fetch.httpx.Client")
    def test_default_user_agent(self, mock_client_class) -> None:
        """Test that default user agent is used when not specified."""
        with tempfile.TemporaryDirectory() as cache_dir:
            url = "https://example.com"
            html_content = "<html><body>Content</body></html>"

            # Mock the HTTP client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response

            # Track Client initialization
            client_init_calls = []

            def track_client(*args, **kwargs):
                client_init_calls.append(kwargs)
                mock_obj = Mock()
                mock_obj.__enter__ = Mock(return_value=mock_client)
                mock_obj.__exit__ = Mock(return_value=None)
                return mock_obj

            mock_client_class.side_effect = track_client

            # Mock stable_hash
            with patch("techread.ingest.fetch.stable_hash", return_value="defaultua123"):
                result = fetch_html(url, cache_dir)
                assert result == html_content

                # Verify default user agent was used in Client initialization
                assert len(client_init_calls) == 1
                assert "headers" in client_init_calls[0]
                assert client_init_calls[0]["headers"]["User-Agent"] == "techread/0.1"

    @patch("techread.ingest.fetch.httpx.Client")
    def test_html_with_encoding(self, mock_client_class) -> None:
        """Test handling of HTML with special characters and encoding."""
        with tempfile.TemporaryDirectory() as cache_dir:
            url = "https://example.com"
            html_content = "<html><body>Hello 世界 🌍</body></html>"

            # Mock the HTTP client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Mock stable_hash
            with patch("techread.ingest.fetch.stable_hash", return_value="encoding123"):
                result = fetch_html(url, cache_dir)
                assert "世界" in result
                assert "🌍" in result

    @patch("techread.ingest.fetch.httpx.Client")
    def test_empty_html_content(self, mock_client_class) -> None:
        """Test handling of empty HTML content."""
        with tempfile.TemporaryDirectory() as cache_dir:
            url = "https://example.com"
            html_content = ""

            # Mock the HTTP client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Mock stable_hash
            with patch("techread.ingest.fetch.stable_hash", return_value="empty123"):
                result = fetch_html(url, cache_dir)
                assert result == ""
