"""Unit tests for logging_config — SensitiveDataFilter redaction (no DB)."""

from __future__ import annotations

import logging

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def filt():
    from backend.core.logging_config import SensitiveDataFilter

    return SensitiveDataFilter()


class TestSensitiveDataFilter:
    def test_filters_llm_api_key(self, filt):
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "API call with llm_api_key=sk-abc123xyz", None, None, None
        )
        assert filt.filter(record) is True
        assert "sk-abc123xyz" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_filters_bearer_token(self, filt):
        record = logging.LogRecord(
            "test",
            logging.INFO,
            "",
            0,
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abcdefg",
            None,
            None,
            None,
        )
        assert filt.filter(record) is True
        assert "eyJhbGciOiJIUzI1NiJ9.abcdefg" not in record.msg

    def test_filters_access_token(self, filt):
        record = logging.LogRecord(
            "test",
            logging.INFO,
            "",
            0,
            "access_token=BQD-token-value-here&expires",
            None,
            None,
            None,
        )
        assert filt.filter(record) is True
        assert "BQD-token-value-here" not in record.msg

    def test_filters_refresh_token(self, filt):
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "refresh_token=AQD-refresh-secret-value", None, None, None
        )
        assert filt.filter(record) is True
        assert "AQD-refresh-secret-value" not in record.msg

    def test_filters_sk_key(self, filt):
        # sk- pattern requires 20+ alphanumeric chars (no hyphens)
        record = logging.LogRecord(
            "test",
            logging.INFO,
            "",
            0,
            "key=sk-projabcde1234567890abcdefxyz",  # pragma: allowlist secret
            None,
            None,
            None,
        )
        assert filt.filter(record) is True
        assert "sk-projabcde1234567890abcdefxyz" not in record.msg  # pragma: allowlist secret

    def test_filters_client_secret(self, filt):
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "client_secret=abc123secret456def", None, None, None
        )
        assert filt.filter(record) is True
        assert "abc123secret456def" not in record.msg

    def test_does_not_filter_benign_content(self, filt):
        msg = "GET /api/dashboard returned 200 — 52000 records"
        record = logging.LogRecord("test", logging.INFO, "", 0, msg, None, None, None)
        assert filt.filter(record) is True
        assert record.msg == msg

    def test_filters_multiple_tokens(self, filt):
        record = logging.LogRecord(
            "test",
            logging.INFO,
            "",
            0,
            "Headers: x-api-key=sk-aaa, Authorization=Bearer tok123",
            None,
            None,
            None,
        )
        assert filt.filter(record) is True
        assert "sk-aaa" not in record.msg
        assert "tok123" not in record.msg
