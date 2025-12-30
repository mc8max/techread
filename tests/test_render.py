"""Unit tests for the techread.digest.render module."""

import json

from techread.digest.render import print_digest, print_ranked, print_sources


class TestPrintSources:
    """Test cases for the print_sources function."""

    def test_empty_list(self):
        """Test with an empty list of sources."""
        # Should not raise any exceptions
        print_sources([])

    def test_single_enabled_source(self):
        """Test with a single enabled source."""
        sources = [
            {
                "id": 1,
                "enabled": 1,
                "weight": 1.5,
                "name": "Tech News",
                "url": "https://example.com/feed.xml",
                "tags": "tech,news",
            }
        ]
        # Should not raise any exceptions
        print_sources(sources)

    def test_multiple_sources_with_different_states(self):
        """Test with multiple sources, some enabled and some disabled."""
        sources = [
            {
                "id": 1,
                "enabled": 1,
                "weight": 2.0,
                "name": "Python Blog",
                "url": "https://python.org/feed.xml",
                "tags": "python,programming",
            },
            {
                "id": 2,
                "enabled": 0,
                "weight": 1.0,
                "name": "Old News",
                "url": "https://oldnews.com/feed.xml",
                "tags": "",
            },
        ]
        # Should not raise any exceptions
        print_sources(sources)

    def test_source_without_tags(self):
        """Test source without tags field."""
        sources = [
            {
                "id": 3,
                "enabled": 1,
                "weight": 0.5,
                "name": "Minimal Source",
                "url": "https://minimal.com/feed.xml",
            }
        ]
        # Should not raise any exceptions
        print_sources(sources)


class TestPrintRanked:
    """Test cases for the print_ranked function."""

    def test_empty_list(self):
        """Test with an empty list of posts."""
        # Should not raise any exceptions
        print_ranked([])

    def test_single_post_with_breakdown(self):
        """Test with a single post showing breakdown."""
        posts = [
            {
                "id": 1,
                "title": "Python 3.12 Released",
                "word_count": 440,
                "score": 8.5,
                "read_state": "unread",
                "breakdown_json": json.dumps(
                    {
                        "freshness": 0.9,
                        "topic_hits": 3,
                        "length_penalty": -0.2,
                    }
                ),
            }
        ]
        # Should not raise any exceptions
        print_ranked(posts)

    def test_multiple_posts_without_breakdown(self):
        """Test with multiple posts without showing breakdown."""
        posts = [
            {
                "id": 1,
                "title": "Post One",
                "word_count": 220,
                "score": 5.0,
                "read_state": "unread",
            },
            {
                "id": 2,
                "title": "Post Two",
                "word_count": 660,
                "score": 7.5,
                "read_state": "reading",
            },
        ]
        # Should not raise any exceptions
        print_ranked(posts, show_breakdown=False)

    def test_post_with_zero_word_count(self):
        """Test post with zero word count."""
        posts = [
            {
                "id": 1,
                "title": "Short Post",
                "word_count": 0,
                "score": 1.0,
            }
        ]
        # Should not raise any exceptions
        print_ranked(posts)

    def test_invalid_breakdown_json(self):
        """Test with invalid JSON in breakdown field."""
        posts = [
            {
                "id": 1,
                "title": "Post with Bad JSON",
                "word_count": 220,
                "score": 5.0,
                "breakdown_json": "not valid json",
            }
        ]
        # Should not crash with invalid JSON
        print_ranked(posts)

    def test_missing_optional_fields(self):
        """Test with missing optional fields."""
        posts = [
            {
                "id": 1,
                "title": "Minimal Post",
                "word_count": 220,
            }
        ]
        # Should not raise any exceptions
        print_ranked(posts)


class TestPrintDigest:
    """Test cases for the print_digest function."""

    def test_empty_list(self):
        """Test with an empty list of posts."""
        # Should not raise any exceptions
        print_digest([])

    def test_single_post_with_one_liner(self):
        """Test with a single post including one-liner."""
        posts = [
            {
                "id": 1,
                "title": "Python 3.12 Features",
                "url": "https://example.com/python-features",
                "word_count": 440,
                "one_liner": "New features in Python 3.12",
            }
        ]
        # Should not raise any exceptions
        print_digest(posts)

    def test_multiple_posts_without_one_liner(self):
        """Test with multiple posts without one-liners."""
        posts = [
            {
                "id": 1,
                "title": "Post One",
                "url": "https://example.com/post1",
                "word_count": 220,
            },
            {
                "id": 2,
                "title": "Post Two",
                "url": "https://example.com/post2",
                "word_count": 660,
            },
        ]
        # Should not raise any exceptions
        print_digest(posts)

    def test_post_with_zero_word_count(self):
        """Test post with zero word count."""
        posts = [
            {
                "id": 1,
                "title": "Short Post",
                "url": "https://example.com/short",
                "word_count": 0,
            }
        ]
        # Should not raise any exceptions
        print_digest(posts)

    def test_missing_optional_fields(self):
        """Test with missing optional fields."""
        posts = [
            {
                "id": 1,
                "title": "Minimal Post",
                "url": "https://example.com/minimal",
            }
        ]
        # Should not raise any exceptions
        print_digest(posts)

    def test_post_with_very_long_title(self):
        """Test post with a very long title."""
        long_title = "A" * 100
        posts = [
            {
                "id": 1,
                "title": long_title,
                "url": "https://example.com/long",
                "word_count": 220,
            }
        ]
        # Should not raise any exceptions
        print_digest(posts)
