from __future__ import annotations

import os

import httpx
from pydantic import BaseModel, Field

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class WebResearchError(RuntimeError):
    pass


class WebResearchConfig(BaseModel):
    """API key comes from the environment, never a request payload or a
    default -- same discipline as the caption writer and vision analyzer."""

    api_key: str | None = Field(default_factory=lambda: os.getenv("TAVILY_API_KEY"))
    timeout_seconds: float = 20.0
    max_results: int = 5
    search_depth: str = "advanced"  # "basic" or "advanced" -- advanced costs more credits but reads full pages


class WebResearchResult(BaseModel):
    title: str
    url: str
    content: str
    published_date: str | None = None


class WebResearchResponse(BaseModel):
    query: str
    results: list[WebResearchResult]
    answer: str | None = None  # Tavily's own short synthesized answer, when available


class TavilyWebResearcher:
    """The one component allowed to search the live web on AURON's own
    behalf -- a real, bounded HTTPS call to Tavily's API (built for AI
    agents: pre-filtered, deduplicated, full-page-read results rather than
    raw search-engine snippets). Fails closed: no API key, a transport
    error, or an API error status all raise rather than returning
    fabricated results.
    """

    def __init__(self, config: WebResearchConfig | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or WebResearchConfig()
        self._client = client

    def search(self, query: str, *, max_results: int | None = None) -> WebResearchResponse:
        if not self.config.api_key:
            raise WebResearchError(
                "TAVILY_API_KEY is not set -- AURON cannot search the web without it. Set it in the backend's environment."
            )

        client, should_close = (self._client, False) if self._client else (httpx.Client(), True)
        try:
            response = client.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": self.config.api_key,
                    "query": query,
                    "search_depth": self.config.search_depth,
                    "max_results": max_results or self.config.max_results,
                    "include_answer": True,
                },
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise WebResearchError(f"Tavily API returned {response.status_code}: {response.text[:500]}")
            data = response.json()
            results = [
                WebResearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    published_date=item.get("published_date"),
                )
                for item in data.get("results", [])
            ]
            return WebResearchResponse(query=query, results=results, answer=data.get("answer"))
        except httpx.HTTPError as exc:
            raise WebResearchError(f"Could not reach the Tavily API: {exc}") from exc
        finally:
            if should_close:
                client.close()
