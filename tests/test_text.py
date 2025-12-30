"""Unit tests for text utility functions."""

from techread.utils.text import contains_any, normalize_whitespace, stable_hash


class TestStableHash:
    """Test cases for stable_hash function."""

    def test_basic_string(self) -> None:
        """Test hashing a basic string."""
        result = stable_hash("hello world")
        assert isinstance(result, str)
        assert len(result) == 64
        # Expected hash for "hello world"
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_empty_string(self) -> None:
        """Test hashing an empty string."""
        result = stable_hash("")
        assert isinstance(result, str)
        assert len(result) == 64
        # Hash of empty string
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_unicode_string(self) -> None:
        """Test hashing a unicode string."""
        result = stable_hash("こんにちは世界")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_special_characters(self) -> None:
        """Test hashing strings with special characters."""
        result = stable_hash("!@#$%^&*()\n\t")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_consistency(self) -> None:
        """Test that the same input always produces the same hash."""
        hash1 = stable_hash("test string")
        hash2 = stable_hash("test string")
        assert hash1 == hash2

    def test_different_inputs(self) -> None:
        """Test that different inputs produce different hashes."""
        hash1 = stable_hash("abc")
        hash2 = stable_hash("abcd")
        assert hash1 != hash2

    def test_none_handling(self) -> None:
        """Test that the function handles edge cases gracefully."""
        # The function should work with any string input
        result = stable_hash("   \t\n")
        assert isinstance(result, str)
        assert len(result) == 64


class TestNormalizeWhitespace:
    """Test cases for normalize_whitespace function."""

    def test_basic_normalization(self) -> None:
        """Test basic whitespace normalization."""
        result = normalize_whitespace("  hello   world  \n")
        assert result == "hello world"

    def test_tabs_and_newlines(self) -> None:
        """Test normalization with tabs and newlines."""
        result = normalize_whitespace("\t\tfoo\tbar\n")
        assert result == "foo bar"

    def test_empty_string(self) -> None:
        """Test normalization of empty string."""
        result = normalize_whitespace("")
        assert result == ""

    def test_none_input(self) -> None:
        """Test normalization with None input."""
        result = normalize_whitespace(None)
        assert result == ""

    def test_single_spaces(self) -> None:
        """Test that single spaces are preserved."""
        result = normalize_whitespace("a b c")
        assert result == "a b c"

    def test_multiple_spaces(self) -> None:
        """Test that multiple spaces are collapsed."""
        result = normalize_whitespace("a    b    c")
        assert result == "a b c"

    def test_leading_trailing_spaces(self) -> None:
        """Test that leading and trailing spaces are stripped."""
        result = normalize_whitespace("  hello world  ")
        assert result == "hello world"

    def test_mixed_whitespace(self) -> None:
        """Test normalization with mixed whitespace types."""
        result = normalize_whitespace(" \t hello \n world \r ")
        assert result == "hello world"

    def test_no_whitespace(self) -> None:
        """Test string with no whitespace."""
        result = normalize_whitespace("helloworld")
        assert result == "helloworld"

    def test_unicode_with_whitespace(self) -> None:
        """Test normalization with unicode characters."""
        result = normalize_whitespace("  こんにちは   世界  ")
        assert result == "こんにちは 世界"


class TestContainsAny:
    """Test cases for contains_any function."""

    def test_basic_match(self) -> None:
        """Test basic string matching."""
        result = contains_any("Hello World", ["hello"])
        assert result == 1

    def test_no_match(self) -> None:
        """Test when no needles match."""
        result = contains_any("Hello World", ["foo", "bar"])
        assert result == 0

    def test_multiple_matches(self) -> None:
        """Test when multiple needles match."""
        result = contains_any("Hello World Python", ["hello", "python"])
        assert result == 2

    def test_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        result = contains_any("Hello World", ["HELLO", "WORLD"])
        assert result == 2

    def test_partial_matches(self) -> None:
        """Test partial string matching."""
        result = contains_any("Hello World", ["llo", "orl"])
        assert result == 2

    def test_empty_text(self) -> None:
        """Test with empty text."""
        result = contains_any("", ["hello", "world"])
        assert result == 0

    def test_none_text(self) -> None:
        """Test with None text."""
        result = contains_any(None, ["hello", "world"])
        assert result == 0

    def test_empty_needles(self) -> None:
        """Test with empty needles list."""
        result = contains_any("Hello World", [])
        assert result == 0

    def test_empty_string_needles(self) -> None:
        """Test with empty string needles (should be ignored)."""
        result = contains_any("Hello World", ["", "hello"])
        assert result == 1

    def test_mixed_case_needles(self) -> None:
        """Test with mixed case needles."""
        result = contains_any("Python is Great", ["PYTHON", "is", "great"])
        assert result == 3

    def test_special_characters(self) -> None:
        """Test with special characters in text and needles."""
        result = contains_any("Hello@World!", ["hello", "@world"])
        assert result == 2

    def test_unicode_text(self) -> None:
        """Test with unicode text."""
        result = contains_any("こんにちは世界", ["こんにちは"])
        assert result == 1

    def test_substring_matching(self) -> None:
        """Test that substrings are matched correctly."""
        result = contains_any("Hello World", ["llo W"])
        assert result == 1

    def test_overlapping_needles(self) -> None:
        """Test with overlapping needle patterns."""
        result = contains_any("abcabc", ["ab", "bc", "ca"])
        assert result == 3
