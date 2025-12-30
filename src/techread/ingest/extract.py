from __future__ import annotations

from dataclasses import dataclass

import trafilatura

from ..utils.text import normalize_whitespace


@dataclass(frozen=True)
class Extracted:
    """Container for extracted text content and metadata.

    This frozen dataclass holds the results of HTML text extraction,
    including the cleaned text and word count.

    Attributes:
        text: The extracted and normalized plain text content.
        word_count: The number of words in the extracted text.
    """

    text: str
    word_count: int


def extract_text(html: str) -> Extracted:
    """Extract and clean plain text from HTML content.

    This function uses trafilatura to extract readable text from HTML,
    normalizes whitespace, and calculates word count.

    The extraction process includes tables but excludes comments to focus
    on the main content. The extracted text is then normalized to ensure
    consistent whitespace handling.

    Args:
        html: HTML string containing the content to extract.
              Can be from a web page, article, or any HTML document.

    Returns:
        Extracted: A dataclass containing:
            - text: The cleaned, normalized plain text
            - word_count: Number of words in the extracted text

    Examples:
        >>> html = "<html><body><p>Hello world</p></body></html>"
        >>> result = extract_text(html)
        >>> result.text
        'Hello world'
        >>> result.word_count
        2

    Note:
        If the HTML contains no extractable text, returns an Extracted
        object with empty string and word_count of 0.
    """
    text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    text = normalize_whitespace(text)
    wc = len(text.split()) if text else 0
    return Extracted(text=text, word_count=wc)
