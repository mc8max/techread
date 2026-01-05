from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from langchain_openai import ChatOpenAI

Mode = Literal["short", "bullets", "takeaways", "comprehensive", "s", "b", "t", "c"]

_MODE_ALIASES = {
    "s": "short",
    "b": "bullets",
    "t": "takeaways",
    "c": "comprehensive",
}


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
    """Configuration settings for Large Language Model (LLM) usage.

    This dataclass holds the essential parameters needed to configure
    LLM interactions, including model selection and temperature settings.

    Attributes:
        model (str): The name of the LLM model to use for generation.
        temperature (float): Controls randomness in generation (0.0 = deterministic, 1.0 = maximum randomness).
    """

    model: str
    temperature: float


def canonical_mode(mode: Mode) -> str:
    """Convert abbreviated mode names to their full forms.

    This function handles alias expansion for summary modes, converting
    short forms like "s" to their full equivalents like "short".

    Args:
        mode: The summary mode, either in full form ("short", "bullets", etc.)
            or abbreviated form ("s", "b", etc.).

    Returns:
        The canonical (full) form of the mode name.

    Example:
        >>> canonical_mode("s")
        'short'
        >>> canonical_mode("bullets")
        'bullets'
    """
    return _MODE_ALIASES.get(mode, mode)


def _prompt(mode: Mode, title: str, url: str, text: str) -> str:
    """Generate a prompt for the LLM based on the summary mode.

    This function creates a structured prompt that instructs the LLM on
    how to format its response based on the desired summary mode.

    Args:
        mode: The summary mode ("short", "bullets", or "takeaways").
        title: The title of the article to summarize.
        url: The URL of the article.
        text: The full text content of the article.

    Returns:
        A formatted prompt string containing instructions and the article text.

    Example:
        >>> _prompt("short", "Test Title", "http://example.com", "Test content")
        'You summarize technical writing for a busy senior engineer. Be precise....'
    """
    mode = canonical_mode(mode)
    if mode == "short":
        instruction = "Write a TL;DR in 2-3 sentences. Be concrete and technical. No fluff."
    elif mode == "bullets":
        instruction = (
            "Summarize into up to 5 bullet points. Each bullet must be one sentence. Be specific."
        )
    elif mode == "takeaways":
        instruction = (
            "Produce: (1) 3 key takeaways (bullets), (2) a 'Why it matters' paragraph (max 3 sentences), "
            "(3) 1 suggested experiment/action to try."
        )
    else:
        instruction = (
            "Produce a comprehensive technical summary with this structure:\n"
            "1) Summary: 3-5 sentences.\n"
            "2) Key Points: 5 bullets, one sentence each.\n"
            "3) Technical Details: 3-5 bullets focused on methods, data, or systems.\n"
            "4) Risks/Limitations: 2-4 bullets.\n"
            "5) Action Items: 2-3 bullets for practical next steps."
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
    """Remove model reasoning blocks if present.

    This utility function removes special XML-style tags that some LLMs
    may include in their responses to show internal reasoning or thinking.

    Args:
        text: The raw text output from an LLM that may contain reasoning blocks.

    Returns:
        The cleaned text with any thinking blocks removed.

    Example:
        >>> _strip_thinking("Some content <think>internal reasoning</think> more content")
        'Some content  more content'
    """
    without_blocks = _THINKING_BLOCK_RE.sub("", text)
    without_trailer = _THINKING_TRAILER_RE.sub("", without_blocks, count=1)
    return without_trailer.strip()


def get_lmstudio_llm(settings: LLMSettings) -> ChatOpenAI:
    """Return a ChatOpenAI instance for LM Studio models.

    This function creates and configures a ChatOpenAI instance that can
    communicate with LM Studio models running locally or on a specified API endpoint.

    Args:
        settings: LLM Settings to retrieve Large Language Model.

    Returns:
        A ChatOpenAI instance configured with the specified model and temperature.

    Raises:
        ValueError: If the specified model is not found in the LM Studio configuration.

    Example:
        >>> settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        >>> llm = get_lmstudio_llm(settings)
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

    This function orchestrates the complete process of generating a summary:
    it prepares the prompt, calls the LLM with appropriate settings, and processes
    the response to remove any internal reasoning blocks.

    Args:
        settings: The LLM configuration settings including model and temperature.
        mode: The summary mode ("short", "bullets", or "takeaways").
        title: The title of the article to summarize.
        url: The URL of the article.
        text: The full text content of the article.

    Returns:
        The generated summary as a string, with any internal reasoning blocks removed.

    Example:
        >>> settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        >>> summary = summarize(settings, mode="short", title="Test", url="http://example.com", text="Test content")

    Note:
        The function limits input text to 12000 characters for performance reasons.
    """
    llm = get_lmstudio_llm(settings)
    response = llm.invoke(_prompt(mode, title, url, text))
    return _strip_thinking(response.content or "")
