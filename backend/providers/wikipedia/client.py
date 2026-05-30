"""Wikipedia provider — unified interface for Wikipedia API.

Uses the shared HttpClient for HTTP transport.
"""

from __future__ import annotations

from urllib.parse import quote

from backend.infrastructure.http.client import HttpClient
from backend.providers.base import BaseProvider, ProviderConfig


class WikipediaProvider(BaseProvider):
    """Provider for Wikipedia REST API (page summaries, extracts, search)."""

    BASE_URL = "https://en.wikipedia.org/api/rest_v1"
    BASE_URL_ACTION = "https://en.wikipedia.org/w/api.php"

    def __init__(self, config: ProviderConfig | None = None):
        if config is None:
            config = ProviderConfig(
                name="wikipedia",
                base_url=self.BASE_URL,
                timeout=20,
                retries=2,
                rate_limit_rps=5.0,
            )
        super().__init__(config)
        self._http = HttpClient(timeout=config.timeout, retries=config.retries)

    def health_check(self) -> bool:
        try:
            resp = self._http.get(f"{self.BASE_URL}/page/summary/Music")
            return resp.status == 200
        except Exception:
            return False

    def redact(self) -> dict:
        return {"provider": "wikipedia", "base_url": self.BASE_URL}

    def get_page_summary(self, title: str, language: str = "en") -> dict | None:
        url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
        resp = self._http.get(url)
        if resp.status == 200:
            return resp.json()
        return None

    def get_page_extract(self, title: str, language: str = "en") -> str | None:
        """Get plain text extract of a Wikipedia page."""
        url = (
            f"https://{language}.wikipedia.org/w/api.php"
            f"?action=query&titles={quote(title)}&prop=extracts"
            f"&exintro=1&explaintext=1&format=json"
        )
        resp = self._http.get(url)
        if resp.status == 200:
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                return page.get("extract")
        return None

    def search(self, query: str, language: str = "en", limit: int = 5) -> list[dict]:
        url = (
            f"https://{language}.wikipedia.org/w/api.php"
            f"?action=opensearch&search={quote(query)}&limit={limit}&format=json"
        )
        resp = self._http.get(url)
        if resp.status == 200:
            data = resp.json()
            results = []
            if len(data) >= 4:
                titles = data[1]
                descriptions = data[2]
                urls = data[3]
                for i in range(len(titles)):
                    results.append(
                        {
                            "title": titles[i],
                            "description": descriptions[i],
                            "url": urls[i],
                        }
                    )
            return results
        return []
