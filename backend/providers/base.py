"""Base provider interface.

All third-party service providers (Spotify, Genius, Wikipedia, LLM)
must implement this interface to ensure consistent behaviour for
timeout, retry, rate limiting, caching, and log redaction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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
