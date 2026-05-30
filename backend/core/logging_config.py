"""Centralized logging configuration with sensitive-data redaction.

Automatically masks API keys, tokens, and other secrets from log output.
"""

import logging
import re
import sys

_SENSITIVE_PATTERNS = [
    (re.compile(r'(llm_api_key["\s:=]+)([^\s"\',}]+)', re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r'(api_key["\s:=]+)([^\s"\',}]+)', re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(Bearer\s+)([A-Za-z0-9._\-]+)"), r"\1[REDACTED]"),
    (re.compile(r'(access_token["\s:=]+)([^\s"\',}]+)', re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r'(refresh_token["\s:=]+)([^\s"\',}]+)', re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r'(client_secret["\s:=]+)([^\s"\',}]+)', re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(sk-[A-Za-z0-9]{20,})"), r"[REDACTED_API_KEY]"),
    (re.compile(r"(deepseek-[A-Za-z0-9]{20,})"), r"[REDACTED_API_KEY]"),
    (re.compile(r'(Authorization["\s:=]+)([^\s"\',}]+)', re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r'(x-api-key["\s:=]+)([^\s"\',}]+)', re.IGNORECASE), r"\1[REDACTED]"),
]


class SensitiveDataFilter(logging.Filter):
    """Logging filter that redacts secrets from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern, replacement in _SENSITIVE_PATTERNS:
            message = pattern.sub(replacement, message)
        record.msg = message
        record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with redaction filter and structured format."""
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(SensitiveDataFilter())
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
