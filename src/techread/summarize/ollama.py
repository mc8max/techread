from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

Mode = Literal["short", "bullets", "takeaways"]


@dataclass(frozen=True)
class OllamaSettings:
    host: str
    model: str


def _prompt(mode: Mode, title: str, url: str, text: str) -> str:
    if mode == "short":
        instruction = "Write a TL;DR in 2-3 sentences. Be concrete and technical. No fluff."
    elif mode == "bullets":
        instruction = "Summarize into up to 5 bullet points. Each bullet must be one sentence. Be specific."
    else:
        instruction = (
            "Produce: (1) 3 key takeaways (bullets), (2) a 'Why it matters' paragraph (max 3 sentences), "
            "(3) 1 suggested experiment/action to try."
        )

    clipped = text[:12000]
    return (
        "You summarize technical writing for a busy senior engineer. Be precise.\n\n"
        f"Title: {title}\nURL: {url}\n\n"
        f"{instruction}\n\n"
        f"Article text:\n{clipped}\n"
    )


def summarize(settings: OllamaSettings, *, mode: Mode, title: str, url: str, text: str) -> str:
    payload = {"model": settings.model, "prompt": _prompt(mode, title, url, text), "stream": False}
    endpoint = f"{settings.host}/api/generate"
    with httpx.Client(timeout=60.0) as client:
        r = client.post(endpoint, json=payload)
        r.raise_for_status()
        data = r.json()
    return (data.get("response") or "").strip()
