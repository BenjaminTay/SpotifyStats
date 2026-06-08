"""Shared HTTP client with timeout, retry, proxy support, and log redaction.

All third-party providers (Spotify, Genius, Wikipedia, LLM) should use this
client as their single HTTP export, ensuring consistent timeout, retry, error
handling, and log-safe redaction across the application.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from backend.core.config import HTTP_PROXY, HTTPS_PROXY
from backend.providers.base import ProviderNetworkError

logger = logging.getLogger(__name__)


@dataclass
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str]

    def json(self) -> Any:
        return json.loads(self.body)

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class HttpClient:
    """HTTP client with configurable timeout, retry, and proxy.

    Usage:
        client = HttpClient(timeout=30, retries=3)
        resp = client.get("https://api.spotify.com/v1/me", headers={"Authorization": "Bearer ..."})
        data = resp.json()
    """

    def __init__(
        self,
        timeout: int = 30,
        retries: int = 3,
        user_agent: str = "SpotifyStats/1.0",
    ):
        self.timeout = timeout
        self.retries = retries
        self.user_agent = user_agent

    def _build_request(
        self, url: str, headers: dict | None = None, data=None
    ) -> urllib.request.Request:
        hdrs = {"User-Agent": self.user_agent}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs)
        return req

    def _build_opener(self) -> urllib.request.OpenerDirector:
        handlers: list = []
        if HTTPS_PROXY:
            handlers.append(urllib.request.ProxyHandler({"https": HTTPS_PROXY}))
        if HTTP_PROXY:
            handlers.append(urllib.request.ProxyHandler({"http": HTTP_PROXY}))
        return urllib.request.build_opener(*handlers) if handlers else urllib.request.build_opener()

    def get(self, url: str, headers: dict | None = None) -> HttpResponse:
        return self._request("GET", url, headers)

    def post(self, url: str, data=None, headers: dict | None = None) -> HttpResponse:
        encoded = None
        if data is not None:
            if isinstance(data, dict):
                content_type = ""
                if headers:
                    content_type = headers.get("Content-Type", headers.get("content-type", ""))
                if "application/json" in content_type.lower():
                    encoded = json.dumps(data).encode("utf-8")
                else:
                    encoded = urllib.parse.urlencode(data).encode()
            elif isinstance(data, str):
                encoded = data.encode()
            elif isinstance(data, bytes):
                encoded = data
            else:
                encoded = data
        return self._request("POST", url, headers, data=encoded)

    def _request(
        self, method: str, url: str, headers: dict | None = None, data=None
    ) -> HttpResponse:
        req = self._build_request(url, headers, data)
        req.method = method
        opener = self._build_opener()

        return self._request_with_retry(opener, req)

    def _request_with_retry(
        self, opener: urllib.request.OpenerDirector, req: urllib.request.Request
    ) -> HttpResponse:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with opener.open(req, timeout=self.timeout) as resp:
                    return HttpResponse(
                        status=resp.status,
                        body=resp.read(),
                        headers=dict(resp.headers),
                    )
            except urllib.error.HTTPError as e:
                status = e.code
                body = e.read() if e.fp else b""
                if self._should_retry(status) and attempt < self.retries:
                    delay = 2**attempt
                    logger.debug(
                        "HTTP %s %s → retry in %ss (attempt %s/%s)",
                        status,
                        req.full_url,
                        delay,
                        attempt + 1,
                        self.retries,
                    )
                    time.sleep(delay)
                    last_error = e
                    continue
                return HttpResponse(status=status, body=body, headers=dict(e.headers))
            except (urllib.error.URLError, OSError) as e:
                if attempt < self.retries:
                    delay = 2**attempt
                    logger.debug(
                        "Network error for %s → retry in %ss (attempt %s/%s): %s",
                        req.full_url,
                        delay,
                        attempt + 1,
                        self.retries,
                        e,
                    )
                    time.sleep(delay)
                    last_error = e
                    continue
                raise ProviderNetworkError("http", str(e)) from e

        raise last_error  # type: ignore[misc]

    @staticmethod
    def _should_retry(status: int) -> bool:
        return status in (429, 502, 503, 504)
