"""Unit tests for tag normalization."""

from techread.tags.llm import normalize_tags


def test_normalize_tags_basic():
    result = normalize_tags("AI, Machine Learning,   Cloud ")
    assert result == ["ai", "machine-learning", "cloud"]


def test_normalize_tags_dedup_and_limit():
    result = normalize_tags("DevOps, devops, observability, sre, platform, infra")
    assert result == ["devops", "observability", "sre", "platform", "infra"]


def test_normalize_tags_cleanup():
    result = normalize_tags("Data Science; k8s/containers; C++ ;  __ml__  ")
    assert result == ["data-science", "k8scontainers", "c", "ml"]
