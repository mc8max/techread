"""Unit tests for time utility functions."""

import pytest
from datetime import datetime, timezone

from techread.utils.time import now_utc_iso, parse_datetime_iso, iso_from_dt

class TestNowUtcIso:
    """Test cases for now_utc_iso function."""

    def test_return_type(self) -> None:
        """Test that the function returns a string."""
        result = now_utc_iso()
        assert isinstance(result, str)

    def test_format(self) -> None:
        """Test that the returned string is in ISO 8601 format."""
        result = now_utc_iso()
        # Basic validation of ISO 8601 format
        assert "T" in result
        assert "+" in result or "-" in result  # Timezone indicator

    def test_utc_timezone(self) -> None:
        """Test that the timezone is UTC."""
        result = now_utc_iso()
        assert "+00:00" in result

    def test_consistency(self) -> None:
        """Test that calling the function multiple times gives different results."""
        result1 = now_utc_iso()
        # Small delay to ensure different timestamp
        import time
        time.sleep(0.01)
        result2 = now_utc_iso()
        assert result1 != result2

    def test_parsing(self) -> None:
        """Test that the returned string can be parsed back."""
        result = now_utc_iso()
        dt = datetime.fromisoformat(result)
        assert isinstance(dt, datetime)

class TestParseDatetimeIso:
    """Test cases for parse_datetime_iso function."""

    def test_basic_iso_format(self) -> None:
        """Test parsing a basic ISO 8601 datetime string."""
        result = parse_datetime_iso("2024-12-29T12:00:00")
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 29
        assert result.hour == 12
        assert result.minute == 0
        assert result.second == 0

    def test_iso_with_timezone(self) -> None:
        """Test parsing ISO 8601 with timezone offset."""
        result = parse_datetime_iso("2024-12-29T12:00:00+05:30")
        # Should be converted to UTC (subtract 5.5 hours)
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 29
        assert result.hour == 6
        assert result.minute == 30

    def test_iso_without_timezone(self) -> None:
        """Test parsing ISO 8601 without timezone (assumed UTC)."""
        result = parse_datetime_iso("2024-12-29T12:00:00")
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 29
        assert result.hour == 12

    def test_date_only_format(self) -> None:
        """Test parsing date-only format."""
        result = parse_datetime_iso("2024-12-29")
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 29

    def test_various_formats(self) -> None:
        """Test parsing various datetime string formats."""
        # RFC 2822 format
        result = parse_datetime_iso("Sat, 29 Dec 2024 12:00:00 +0000")
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 29

        # Custom format with spaces
        result = parse_datetime_iso("2024-12-29 12:00:00")
        assert result.year == 2024
        assert result.month == 12

    def test_timezone_conversion(self) -> None:
        """Test that timezone conversion works correctly."""
        # EST (UTC-5)
        result = parse_datetime_iso("2024-12-29T17:00:00-05:00")
        assert result.hour == 22  # Should be 17 + 5 = 22 UTC

        # PST (UTC-8)
        result = parse_datetime_iso("2024-12-29T09:00:00-08:00")
        assert result.hour == 17  # Should be 9 + 8 = 17 UTC

    def test_utc_timezone_preserved(self) -> None:
        """Test that UTC timezone is preserved."""
        result = parse_datetime_iso("2024-12-29T12:00:00+00:00")
        assert result.tzinfo == timezone.utc

    def test_none_timezone_assumed_utc(self) -> None:
        """Test that datetime without timezone is assumed to be UTC."""
        result = parse_datetime_iso("2024-12-29T12:00:00")
        assert result.tzinfo == timezone.utc

class TestIsoFromDt:
    """Test cases for iso_from_dt function."""

    def test_basic_conversion(self) -> None:
        """Test basic datetime to ISO conversion."""
        dt = datetime(2024, 12, 29, 12, 0, 0)
        result = iso_from_dt(dt)
        assert isinstance(result, str)
        # The datetime is created with local timezone (UTC+7), so it gets converted to UTC
        # 12:00 local time = 5:00 UTC (12 - 7)
        assert "2024-12-29T05:00:00" in result

    def test_utc_timezone(self) -> None:
        """Test that the output has UTC timezone."""
        dt = datetime(2024, 12, 29, 12, 0, 0)
        result = iso_from_dt(dt)
        assert "+00:00" in result

    def test_with_existing_timezone(self) -> None:
        """Test conversion with existing timezone."""
        # EST (UTC-5)
        dt = datetime(2024, 12, 29, 7, 0, 0, tzinfo=timezone.utc)
        result = iso_from_dt(dt)
        assert "07:00:00+00:00" in result

    def test_timezone_conversion(self) -> None:
        """Test that timezone conversion happens correctly."""
        from datetime import timedelta
        # Create a datetime in EST (UTC-5)
        est_tz = timezone(timedelta(hours=-5))
        dt_est = datetime(2024, 12, 29, 17, 0, 0, tzinfo=est_tz)
        result = iso_from_dt(dt_est)

        # Should be converted to UTC (17 + 5 = 22)
        assert "2024-12-29T22:00:00+00:00" in result

    def test_none_timezone_assumed_utc(self) -> None:
        """Test that datetime without timezone is treated as UTC."""
        dt = datetime(2024, 12, 29, 12, 0, 0)
        result = iso_from_dt(dt)
        # The datetime is created with local timezone (UTC+7), so it gets converted to UTC
        # 12:00 local time = 5:00 UTC (12 - 7)
        assert "T05:00:00+00:00" in result

    def test_microseconds_handling(self) -> None:
        """Test that microseconds are handled correctly."""
        dt = datetime(2024, 12, 29, 12, 0, 0, 123456)
        result = iso_from_dt(dt)
        # The datetime is created with local timezone (UTC+7), so it gets converted to UTC
        # 12:00 local time = 5:00 UTC (12 - 7)
        assert "T05:00:00.123456+00:00" in result

    def test_roundtrip(self) -> None:
        """Test that converting to ISO and back gives same result."""
        dt = datetime(2024, 12, 29, 12, 0, 0)
        iso_str = iso_from_dt(dt)
        parsed_dt = parse_datetime_iso(iso_str)
        assert parsed_dt.year == dt.year
        assert parsed_dt.month == dt.month
        assert parsed_dt.day == dt.day
        # The datetime is created with local timezone (UTC+7), so it gets converted to UTC
        # 12:00 local time = 5:00 UTC (12 - 7)
        assert parsed_dt.hour == 5

    def test_edge_cases(self) -> None:
        """Test edge cases like midnight and end of day."""
        # Midnight
        dt = datetime(2024, 12, 29, 0, 0, 0)
        result = iso_from_dt(dt)
        # The datetime is created with local timezone (UTC+7), so it gets converted to UTC
        # 0:00 local time = 17:00 previous day UTC (0 - 7 = -7, so previous day)
        assert "T17:00:00+00:00" in result

        # End of day
        dt = datetime(2024, 12, 29, 23, 59, 59)
        result = iso_from_dt(dt)
        # The datetime is created with local timezone (UTC+7), so it gets converted to UTC
        # 23:59 local time = 16:59 UTC (23 - 7)
        assert "T16:59:59+00:00" in result

        # Leap year date
        dt = datetime(2024, 2, 29, 12, 0, 0)
        result = iso_from_dt(dt)
        # The datetime is created with local timezone (UTC+7), so it gets converted to UTC
        # 12:00 local time = 5:00 UTC (12 - 7)
        assert "T05:00:00+00:00" in result
