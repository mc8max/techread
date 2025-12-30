from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from langchain_openai import ChatOpenAI

Mode = Literal["short", "bullets", "takeaways"]


LM_STUDIO_MODELS = {
    "nemotron-3-nano": "nvidia/nemotron-3-nano",
    "mistral-small-3.2": "mistralai/mistral-small-3.2",
    "magistral-small-2509": "mistralai/magistral-small-2509",
    "gpt-oss:20b": "openai/gpt-oss-20b",
    "gemma-3:12b": "google/gemma-3-12b",
    "llama-3:8b": "meta-llama-3-8b-instruct",
    "deepseek-r1:8b": "deepseek/deepseek-r1-0528-qwen3-8b",
    "qwen3-thinking:4b": "qwen/qwen3-4b-thinking-2507",
    "qwen3:8b": "qwen/qwen3-8b",
    "qwen3:14b": "qwen/qwen3-14b",
    "qwen3-vl:8b": "qwen/qwen3-vl-8b",
    "qwen3-vl:30b": "qwen/qwen3-vl-30b",
}

DEFAULT_LMSTUDIO_API_KEY = "lmstudio-not-needed"
DEFAULT_LMSTUDIO_BASE_URL = "http://localhost:1234/v1"


@dataclass(frozen=True)
class LLMSettings:
    model: str
    temperature: float


def _prompt(mode: Mode, title: str, url: str, text: str) -> str:
    """Generate a prompt for the LLM based on the summary mode.

    Args:
        mode: The summary mode ("short", "bullets", or "takeaways").
        title: The title of the article to summarize.
        url: The URL of the article.
        text: The full text content of the article.

    Returns:
        A formatted prompt string containing instructions and the article text.
    """
    if mode == "short":
        instruction = "Write a TL;DR in 2-3 sentences. Be concrete and technical. No fluff."
    elif mode == "bullets":
        instruction = (
            "Summarize into up to 5 bullet points. Each bullet must be one sentence. Be specific."
        )
    else:
        instruction = (
            "Produce: (1) 3 key takeaways (bullets), (2) a 'Why it matters' paragraph (max 3 sentences), "
            "(3) 1 suggested experiment/action to try."
        )

    clipped = text[:12000]
    return (
        "You summarize technical writing for a busy senior engineer. Be precise.\n"
        "Do not include chain-of-thought or hidden reasoning in the response.\n\n"
        f"Title: {title}\nURL: {url}\n\n"
        f"{instruction}\n\n"
        f"Article text:\n{clipped}\n"
    )


_THINKING_BLOCK_RE = re.compile(r"<(think|analysis)>\s*.*?\s*</\1>\s*", re.DOTALL | re.IGNORECASE)
_THINKING_TRAILER_RE = re.compile(r".*?</(think|analysis)>\s*", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Remove model reasoning blocks if present."""
    without_blocks = _THINKING_BLOCK_RE.sub("", text)
    without_trailer = _THINKING_TRAILER_RE.sub("", without_blocks, count=1)
    return without_trailer.strip()


def get_lmstudio_llm(settings: LLMSettings) -> ChatOpenAI:
    """Return a ChatOpenAI instance for LM Studio models.

    Args:
        settings: LLM Settings to retrieve Large Language Model.

    Returns:
        A ChatOpenAI instance configured with the specified model and temperature.

    Raises:
        ValueError: If the specified model is not found in the LM Studio configuration.
    """
    actual_model = LM_STUDIO_MODELS.get(settings.model)
    if actual_model is None:
        raise ValueError(f"{settings.model} is not found in current LM Studio tool.")
    api_key = os.environ.get("OPENAI_API_KEY", DEFAULT_LMSTUDIO_API_KEY)
    base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_LMSTUDIO_BASE_URL)
    return ChatOpenAI(
        model=actual_model, temperature=settings.temperature, api_key=api_key, base_url=base_url
    )


def summarize(settings: LLMSettings, *, mode: Mode, title: str, url: str, text: str) -> str:
    """Generate a summary of the given text using an LLM.

    Args:
        settings: The LLM configuration settings.
        mode: The summary mode ("short", "bullets", or "takeaways").
        title: The title of the article to summarize.
        url: The URL of the article.
        text: The full text content of the article.

    Returns:
        The generated summary as a string.
    """
    llm = get_lmstudio_llm(settings)
    response = llm.invoke(_prompt(mode, title, url, text))
    return _strip_thinking(response.content or "")
