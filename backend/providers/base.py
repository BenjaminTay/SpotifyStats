"""Base provider interface.

All third-party service providers (Spotify, Genius, Wikipedia, LLM)
must implement this interface to ensure consistent behaviour for
timeout, retry, rate limiting, caching, and log redaction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


class ProviderError(RuntimeError):
    """Base error for third-party provider failures."""

    def __init__(self, provider: str, message: str, status: Optional[int] = None):  # noqa: UP045
        super().__init__(message)
        self.provider = provider
        self.status = status


class ProviderNetworkError(ProviderError):
    """Network or transport-level provider failure."""


class ProviderHTTPError(ProviderError):
    """HTTP provider failure with a status code."""


class ProviderAuthError(ProviderHTTPError):
    """Provider authentication or authorization failed."""


class ProviderRateLimitError(ProviderHTTPError):
    """Provider rate limit was reached."""


class ProviderServerError(ProviderHTTPError):
    """Provider server-side failure."""


class ProviderParseError(ProviderError):
    """Provider returned an unreadable or unexpected payload."""


def provider_error_from_status(provider: str, status: int, detail: str = "") -> ProviderHTTPError:
    """Map an HTTP status to the canonical provider error subtype."""
    message = detail or f"{provider} returned HTTP {status}"
    if status in (401, 403):
        return ProviderAuthError(provider, message, status)
    if status == 429:
        return ProviderRateLimitError(provider, message, status)
    if status >= 500:
        return ProviderServerError(provider, message, status)
    return ProviderHTTPError(provider, message, status)


@dataclass
class ProviderConfig:
    """Configuration for a third-party provider."""

    name: str
    base_url: str = ""
    timeout: int = 30
    retries: int = 3
    cache_policy: str = "db-first"  # "db-first" | "api-first" | "no-cache"

    # Rate limiting (requests per second)
    rate_limit_rps: float = 0.0  # 0 = no limit

    # Proxy
    http_proxy: str | None = field(default=None)
    https_proxy: str | None = field(default=None)


class BaseProvider(ABC):
    """Abstract base for all third-party API providers.

    Each provider must implement:
      - health_check() — verify the API is reachable and credentials are valid
      - redact()       — return a log-safe representation (mask tokens/keys)
    """

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    def health_check(self) -> bool: ...

    @abstractmethod
    def redact(self) -> dict: ...
