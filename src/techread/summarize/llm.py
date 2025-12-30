from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from langchain_openai import ChatOpenAI

Mode = Literal["short", "bullets", "takeaways"]


LM_STUDIO_MODELS = {
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

@dataclass(frozen=True)
class LLMSettings:
    model: str
    temperature: float

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
    return ChatOpenAI(model=actual_model, temperature=settings.temperature)


def summarize(settings: LLMSettings, *, mode: Mode, title: str, url: str, text: str) -> str:
    llm = get_lmstudio_llm(settings)
    response = llm.invoke(_prompt(mode, title, url, text))
    return (response.content or "").strip()
