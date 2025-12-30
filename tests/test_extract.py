"""Unit tests for the extract module."""

import pytest

from techread.ingest.extract import Extracted, extract_text


class TestExtracted:
    """Tests for the Extracted dataclass."""

    def test_extracted_attributes(self):
        """Test that Extracted has the expected attributes."""
        extracted = Extracted(text="hello world", word_count=2)
        assert extracted.text == "hello world"
        assert extracted.word_count == 2

    def test_extracted_immutable(self):
        """Test that Extracted is frozen/immutable."""
        extracted = Extracted(text="hello", word_count=1)
        with pytest.raises(AttributeError):
            extracted.text = "goodbye"


class TestExtractText:
    """Tests for the extract_text function."""

    def test_empty_html(self):
        """Test extraction from empty HTML."""
        result = extract_text("")
        assert result.text == ""
        assert result.word_count == 0

    def test_simple_html(self):
        """Test extraction from simple HTML with paragraph."""
        html = "<html><body><p>Hello world</p></body></html>"
        result = extract_text(html)
        assert "hello world" in result.text.lower()
        assert result.word_count >= 2

    def test_html_with_whitespace(self):
        """Test that whitespace is normalized properly."""
        html = "<html><body><p>  Hello   world  </p></body></html>"
        result = extract_text(html)
        assert "hello world" in result.text.lower()
        # After normalization, there should be single spaces
        assert "  hello" not in result.text
        assert "\thello" not in result.text

    def test_html_with_newlines(self):
        """Test extraction with newlines and various whitespace."""
        html = "<html><body><p>Line one\n\nLine two</p></body></html>"
        result = extract_text(html)
        # Newlines should be normalized to single spaces
        assert "line one line two" in result.text.lower()

    def test_html_with_tables(self):
        """Test that tables are included in extraction."""
        html = """
        <html>
            <body>
                <table>
                    <tr><td>Column 1</td><td>Column 2</td></tr>
                    <tr><td>Data A</td><td>Data B</td></tr>
                </table>
            </body>
        </html>
        """
        result = extract_text(html)
        assert "column" in result.text.lower() or "data" in result.text.lower()

    def test_html_with_comments(self):
        """Test that HTML comments are excluded."""
        html = "<html><body><!-- This is a comment --><p>Visible text</p></body></html>"
        result = extract_text(html)
        assert "visible text" in result.text.lower()
        # Comments should not appear
        assert "this is a comment" not in result.text

    def test_multiple_paragraphs(self):
        """Test extraction from multiple paragraphs."""
        html = """
        <html>
            <body>
                <p>First paragraph</p>
                <p>Second paragraph with more text</p>
            </body>
        </html>
        """
        result = extract_text(html)
        assert "first paragraph" in result.text.lower()
        assert "second paragraph" in result.text.lower()

    def test_word_count_calculation(self):
        """Test that word count is calculated correctly."""
        html = "<html><body><p>One two three four five</p></body></html>"
        result = extract_text(html)
        assert result.word_count == 5

    def test_empty_after_extraction(self):
        """Test when HTML has no extractable text."""
        html = "<html><body><script>var x = 1;</script></body></html>"
        result = extract_text(html)
        # Should return empty string and 0 word count
        assert result.text == ""
        assert result.word_count == 0

    def test_complex_html(self):
        """Test extraction from complex HTML with various elements."""
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Main Heading</h1>
                <p>Paragraph with <strong>bold text</strong> and <em>italic text</em></p>
                <ul>
                    <li>Item one</li>
                    <li>Item two</li>
                </ul>
            </body>
        </html>
        """
        result = extract_text(html)
        assert "main heading" in result.text.lower()
        assert "paragraph with" in result.text.lower()
        assert "item one" in result.text.lower()
        assert "item two" in result.text.lower()

    def test_unicode_content(self):
        """Test extraction of Unicode characters."""
        html = "<html><body><p>Hello 世界 🌍</p></body></html>"
        result = extract_text(html)
        assert "hello" in result.text.lower()
        # Unicode characters should be preserved
        assert "世界" in result.text or "🌍" in result.text

    def test_malformed_html(self):
        """Test extraction from malformed HTML."""
        html = "<html><body><p>Unclosed paragraph <div>Another element</div></p></body></html>"
        result = extract_text(html)
        # Should still extract what it can
        assert "unclosed paragraph" in result.text.lower()
