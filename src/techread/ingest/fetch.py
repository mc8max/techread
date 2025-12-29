from __future__ import annotations

import time
from pathlib import Path

import httpx

from ..utils.text import stable_hash

DEFAULT_TIMEOUT = 20.0


def cache_path_for_url(cache_dir: str, url: str) -> Path:
    h = stable_hash(url)
    return Path(cache_dir) / "html" / f"{h}.html"


def fetch_html(url: str, cache_dir: str, user_agent: str = "techread/0.1") -> str:
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
