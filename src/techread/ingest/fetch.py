from __future__ import annotations

import time
from pathlib import Path

import httpx

from ..utils.text import stable_hash

DEFAULT_TIMEOUT = 20.0

def cache_path_for_url(cache_dir: str, url: str) -> Path:
    """Generate a cache file path for a given URL.

    Creates a stable, deterministic path based on the URL's hash.
    The path includes a subdirectory for HTML files.

    Args:
        cache_dir: The base directory where cached content is stored.
        url: The URL to generate a cache path for.

    Returns:
        Path: A Path object pointing to the cached HTML file location.
              The path will be in the format: {cache_dir}/html/{hash}.html

    Examples:
        >>> cache_path_for_url("/tmp/cache", "https://example.com")
        PosixPath('/tmp/cache/html/abc123.html')
    """
    h = stable_hash(url)
    return Path(cache_dir) / "html" / f"{h}.html"

def fetch_html(url: str, cache_dir: str, user_agent: str = "techread/0.1") -> str:
    """Fetch HTML content from a URL with caching support.

    This function attempts to retrieve HTML content from the specified URL.
    It first checks if the content is already cached, and if so, returns
    the cached version. Otherwise, it fetches the content from the web,
    caches it for future use, and returns it.

    The function includes a politeness delay after fetching to avoid
    overwhelming servers.

    Args:
        url: The URL to fetch HTML content from.
        cache_dir: Directory where cached HTML files are stored.
        user_agent: User-Agent string to identify the client (default: "techread/0.1").

    Returns:
        str: The HTML content as a string.

    Raises:
        httpx.HTTPStatusError: If the HTTP request returns an error status.
        httpx.RequestError: If there's a network-related issue.

    Examples:
        >>> html = fetch_html("https://example.com", "/tmp/cache")
        >>> len(html) > 0
        True

    Note:
        - The cache directory structure is automatically created if it doesn't exist.
        - Cached files are named using a stable hash of the URL.
        - A 0.2 second delay is added after fetching to be polite to servers.
    """
    p = cache_path_for_url(cache_dir, url)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")

    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(follow_redirects=True, timeout=DEFAULT_TIMEOUT, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        html = r.text

    p.write_text(html, encoding="utf-8")
    # Politeness delay
    time.sleep(0.2)
    return html
