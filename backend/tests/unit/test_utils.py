"""Unit tests for core utilities — timezone conversion, platform classification."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestConvertToLocalTime:
    def test_basic_utc_to_beijing(self):
        from backend.core.utils import convert_to_local_time

        result = convert_to_local_time("2026-05-15T08:00:00Z", "CN")
        assert result["ts_year"] == 2026
        assert result["ts_month"] == 5
        assert result["ts_hour"] == 16  # UTC 8:00 + 8 = Beijing 16:00
        assert result["ts_date"] == "2026-05-15"

    def test_midnight_crossing(self):
        from backend.core.utils import convert_to_local_time

        result = convert_to_local_time("2026-05-15T20:00:00Z", "CN")
        # UTC 20:00 + 8 = Beijing 04:00 next day
        assert result["ts_hour"] == 4
        assert result["ts_date"] == "2026-05-16"

    def test_iso_week(self):
        from backend.core.utils import convert_to_local_time

        result = convert_to_local_time("2026-01-01T00:00:00Z", "CN")
        # Beijing Jan 1 2026 08:00 → ISO week 1
        assert result["ts_week"] == 1
        assert result["ts_year"] == 2026

    def test_dow_monday_zero(self):
        from backend.core.utils import convert_to_local_time

        # 2026-05-18 is a Monday (UTC)
        result = convert_to_local_time("2026-05-18T00:00:00Z", "CN")
        assert result["ts_dow"] == 0  # Monday -> 0

    def test_dow_sunday_six(self):
        from backend.core.utils import convert_to_local_time

        # 2026-05-17 16:00Z = Beijing May 18 00:00 (Monday)
        # 2026-05-24 is Sunday UTC → Beijing Sunday 08:00
        result = convert_to_local_time("2026-05-24T00:00:00Z", "CN")
        assert result["ts_dow"] == 6  # Sunday -> 6

    def test_country_ignored_always_beijing(self):
        from backend.core.utils import convert_to_local_time

        cn = convert_to_local_time("2026-05-15T00:00:00Z", "CN")
        us = convert_to_local_time("2026-05-15T00:00:00Z", "US")
        # Both should use UTC+8 (Beijing time), ignoring the country param
        assert cn["ts_hour"] == us["ts_hour"]

    def test_z_suffix_handled(self):
        from backend.core.utils import convert_to_local_time

        result = convert_to_local_time("2026-05-15T12:00:00Z", "JP")
        assert result["ts_hour"] == 20  # 12 + 8 = 20


class TestClassifyPlatform:
    def test_ios(self):
        from backend.core.utils import classify_platform

        assert classify_platform("iOS 15.5 (iPhone14,5)") == "ios"

    def test_android(self):
        from backend.core.utils import classify_platform

        assert classify_platform("Android 13 (SM-G998B)") == "android"

    def test_osx(self):
        from backend.core.utils import classify_platform

        assert classify_platform("OSX 14.5.0 (arm64)") == "osx"

    def test_mac(self):
        from backend.core.utils import classify_platform

        assert classify_platform("Mac OS X 10.15.7") == "osx"

    def test_windows(self):
        from backend.core.utils import classify_platform

        assert classify_platform("Windows 10 (Build 19045)") == "windows"

    def test_web(self):
        from backend.core.utils import classify_platform

        assert classify_platform("Web Player (Chrome 120)") == "web"

    def test_browser(self):
        from backend.core.utils import classify_platform

        assert classify_platform("browser Firefox") == "web"

    def test_unknown_empty(self):
        from backend.core.utils import classify_platform

        assert classify_platform("") == "unknown"
        assert classify_platform(None) == "unknown"

    def test_unknown_other(self):
        from backend.core.utils import classify_platform

        assert classify_platform("SmartTV") == "other"
        assert classify_platform("Car Thing") == "other"
