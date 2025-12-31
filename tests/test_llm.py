"""Unit tests for the LLM summarization module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from techread.summarize.llm import (
    LLMSettings,
    _prompt,
    canonical_mode,
    get_lmstudio_llm,
    summarize,
)


class TestPromptGeneration:
    """Test cases for the _prompt function."""

    def test_short_mode_prompt(self) -> None:
        """Test prompt generation for short summary mode."""
        title = "Test Article"
        url = "https://example.com/test"
        text = "This is a test article with some content."

        result = _prompt("short", title, url, text)

        assert "Test Article" in result
        assert "https://example.com/test" in result
        assert "This is a test article with some content." in result
        assert "TL;DR" in result

    def test_bullets_mode_prompt(self) -> None:
        """Test prompt generation for bullets summary mode."""
        title = "Another Article"
        url = "https://example.com/another"
        text = "Content for bullet points."

        result = _prompt("bullets", title, url, text)

        assert "Another Article" in result
        assert "https://example.com/another" in result
        assert "Content for bullet points." in result
        assert "bullet points" in result

    def test_takeaways_mode_prompt(self) -> None:
        """Test prompt generation for takeaways summary mode."""
        title = "Takeaways Article"
        url = "https://example.com/takeaways"
        text = "Content for takeaways."

        result = _prompt("takeaways", title, url, text)

        assert "Takeaways Article" in result
        assert "https://example.com/takeaways" in result
        assert "Content for takeaways." in result
        assert "key takeaways" in result

    def test_comprehensive_mode_prompt(self) -> None:
        """Test prompt generation for comprehensive summary mode."""
        title = "Comprehensive Article"
        url = "https://example.com/comprehensive"
        text = "Content for comprehensive summary."

        result = _prompt("comprehensive", title, url, text)

        assert "Comprehensive Article" in result
        assert "https://example.com/comprehensive" in result
        assert "Content for comprehensive summary." in result
        assert "comprehensive technical summary" in result

    def test_mode_aliases(self) -> None:
        """Test canonical mode aliases."""
        assert canonical_mode("s") == "short"
        assert canonical_mode("b") == "bullets"
        assert canonical_mode("t") == "takeaways"
        assert canonical_mode("c") == "comprehensive"

    def test_text_clipping(self) -> None:
        """Test that text is clipped to 12000 characters."""
        title = "Long Article"
        url = "https://example.com/long"
        text = "x" * 15000

        result = _prompt("short", title, url, text)

        # Extract just the article text portion (after "Article text:\n")
        lines = result.split("\n")
        article_text = "\n".join(lines[lines.index("Article text:") + 1 :])
        # Should be exactly 12000 x's plus a newline
        assert len(article_text) == 12001
        assert article_text.count("x") == 12000

    def test_empty_text(self) -> None:
        """Test prompt generation with empty text."""
        title = "Empty Article"
        url = "https://example.com/empty"
        text = ""

        result = _prompt("short", title, url, text)

        assert "Empty Article" in result
        assert "https://example.com/empty" in result
        assert "Article text:\n\n" in result


class TestGetLMStudioLLM:
    """Test cases for the get_lmstudio_llm function."""

    def test_valid_model(self) -> None:
        """Test with a valid model from LM_STUDIO_MODELS."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)

        with patch("techread.summarize.llm.ChatOpenAI") as mock_chat:
            result = get_lmstudio_llm(settings)

            assert result == mock_chat.return_value
            mock_chat.assert_called_once_with(
                model="mistralai/mistral-small-3.2",
                temperature=0.7,
                api_key="lmstudio-not-needed",
                base_url="http://localhost:1234/v1",
            )

    def test_invalid_model(self) -> None:
        """Test with an invalid model that doesn't exist in LM_STUDIO_MODELS."""
        settings = LLMSettings(model="invalid-model", temperature=0.7)

        with pytest.raises(ValueError) as excinfo:
            get_lmstudio_llm(settings)

        assert "invalid-model is not found in current LM Studio tool" in str(excinfo.value)

    def test_custom_api_key(self) -> None:
        """Test with custom API key from environment."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "custom-key"}):
            with patch("techread.summarize.llm.ChatOpenAI") as mock_chat:
                result = get_lmstudio_llm(settings)

                assert result == mock_chat.return_value
                mock_chat.assert_called_once_with(
                    model="mistralai/mistral-small-3.2",
                    temperature=0.7,
                    api_key="custom-key",
                    base_url="http://localhost:1234/v1",
                )

    def test_custom_base_url(self) -> None:
        """Test with custom base URL from environment."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)

        with patch.dict(os.environ, {"OPENAI_BASE_URL": "http://custom:8080/v1"}):
            with patch("techread.summarize.llm.ChatOpenAI") as mock_chat:
                result = get_lmstudio_llm(settings)

                assert result == mock_chat.return_value
                mock_chat.assert_called_once_with(
                    model="mistralai/mistral-small-3.2",
                    temperature=0.7,
                    api_key="lmstudio-not-needed",
                    base_url="http://custom:8080/v1",
                )


class TestSummarize:
    """Test cases for the summarize function."""

    def test_summarize_short_mode(self) -> None:
        """Test summary generation in short mode."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        title = "Test Article"
        url = "https://example.com/test"
        text = "This is a test article with some content."

        mock_response = MagicMock()
        mock_response.content = "This is a summary of the article."

        with patch("techread.summarize.llm.get_lmstudio_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            result = summarize(settings, mode="short", title=title, url=url, text=text)

            assert result == "This is a summary of the article."
            mock_llm.invoke.assert_called_once()

    def test_summarize_bullets_mode(self) -> None:
        """Test summary generation in bullets mode."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        title = "Bullet Article"
        url = "https://example.com/bullets"
        text = "Content for bullet points."

        mock_response = MagicMock()
        mock_response.content = "- Point 1\n- Point 2\n- Point 3"

        with patch("techread.summarize.llm.get_lmstudio_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            result = summarize(settings, mode="bullets", title=title, url=url, text=text)

            assert result == "- Point 1\n- Point 2\n- Point 3"

    def test_summarize_takeaways_mode(self) -> None:
        """Test summary generation in takeaways mode."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        title = "Takeaways Article"
        url = "https://example.com/takeaways"
        text = "Content for takeaways."

        mock_response = MagicMock()
        mock_response.content = "Takeaway 1\nTakeaway 2\nTakeaway 3"

        with patch("techread.summarize.llm.get_lmstudio_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            result = summarize(settings, mode="takeaways", title=title, url=url, text=text)

            assert result == "Takeaway 1\nTakeaway 2\nTakeaway 3"

    def test_summarize_empty_response(self) -> None:
        """Test summary generation with empty response content."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        title = "Empty Article"
        url = "https://example.com/empty"
        text = "Some content."

        mock_response = MagicMock()
        mock_response.content = ""

        with patch("techread.summarize.llm.get_lmstudio_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            result = summarize(settings, mode="short", title=title, url=url, text=text)

            assert result == ""

    def test_summarize_none_response(self) -> None:
        """Test summary generation with None response content."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        title = "None Article"
        url = "https://example.com/none"
        text = "Some content."

        mock_response = MagicMock()
        mock_response.content = None

        with patch("techread.summarize.llm.get_lmstudio_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            result = summarize(settings, mode="short", title=title, url=url, text=text)

            assert result == ""

    def test_summarize_with_whitespace(self) -> None:
        """Test summary generation with whitespace in response."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        title = "Whitespace Article"
        url = "https://example.com/whitespace"
        text = "Some content."

        mock_response = MagicMock()
        mock_response.content = "  Summary with spaces  \n\n"

        with patch("techread.summarize.llm.get_lmstudio_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            result = summarize(settings, mode="short", title=title, url=url, text=text)

            assert result == "Summary with spaces"

    def test_summarize_strips_thinking_block(self) -> None:
        """Test summary generation strips model thinking blocks."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        title = "Thinking Article"
        url = "https://example.com/thinking"
        text = "Some content."

        mock_response = MagicMock()
        mock_response.content = "<think>Reasoning here.</think>\nFinal answer."

        with patch("techread.summarize.llm.get_lmstudio_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            result = summarize(settings, mode="short", title=title, url=url, text=text)

            assert result == "Final answer."

    def test_summarize_strips_thinking_trailer(self) -> None:
        """Test summary generation strips reasoning text before a closing tag."""
        settings = LLMSettings(model="mistral-small-3.2", temperature=0.7)
        title = "Thinking Trailer"
        url = "https://example.com/thinking-trailer"
        text = "Some content."

        mock_response = MagicMock()
        mock_response.content = "Reasoning...\n</think>\nFinal answer."

        with patch("techread.summarize.llm.get_lmstudio_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            result = summarize(settings, mode="short", title=title, url=url, text=text)

            assert result == "Final answer."
