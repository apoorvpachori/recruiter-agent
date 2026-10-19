"""Brave LLM Context API implementation of the WebSearchProvider interface."""

import logging
from datetime import UTC, datetime

import httpx

from recruiter_agent.providers.search import SearchResult, WebSearchProvider, WebSearchResponse
from recruiter_agent.settings import Settings, get_settings

logger = logging.getLogger(__name__)
MAX_QUERY_LENGTH = 400
MAX_RESULTS = 5
MAX_SNIPPET_LENGTH = 1_500
TIMEOUT_SECONDS = 15.0


class BraveSearchProvider(WebSearchProvider):
    """Small sync client using Brave's standard web search endpoint."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def search(self, query: str, *, max_results: int = MAX_RESULTS) -> WebSearchResponse:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query must not be empty.")
        if len(normalized_query) > MAX_QUERY_LENGTH:
            raise ValueError(f"Search query must be at most {MAX_QUERY_LENGTH} characters.")
        if not 1 <= max_results <= MAX_RESULTS:
            raise ValueError(f"max_results must be between 1 and {MAX_RESULTS}.")

        api_key = self._settings.brave_search_api_key
        if api_key is None or not api_key.get_secret_value():
            raise RuntimeError("Set BRAVE_SEARCH_API_KEY in local .env to enable web search.")

        response = httpx.get(
            self._settings.brave_search_endpoint,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key.get_secret_value(),
            },
            params={
                "q": normalized_query,
                "count": max_results,
                "country": "us",
                "search_lang": "en",
                "maximum_number_of_urls": max_results,
                "maximum_number_of_tokens": 2048,
                "maximum_number_of_tokens_per_url": 1024,
                "context_threshold_mode": "strict",
                "enable_source_metadata": True,
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        grounding = payload.get("grounding", {})
        generic_results = grounding.get("generic", [])
        sources = payload.get("sources", {})
        results = []
        for item in generic_results[:max_results]:
            source_url = item.get("url")
            if not source_url:
                continue
            source_metadata = sources.get(source_url, {})
            age = source_metadata.get("age") or []
            published_at = next((value for value in age if isinstance(value, str)), None)
            snippets = item.get("snippets", [])
            results.append(
                SearchResult(
                    title=str(
                        item.get("title") or source_metadata.get("title") or "Untitled result"
                    )[:300],
                    url=source_url,
                    snippet="\n".join(str(snippet) for snippet in snippets)[:MAX_SNIPPET_LENGTH],
                    published_at=published_at,
                )
            )
        logger.info(
            "web_search_completed",
            extra={
                "event": "web_search_completed",
                "provider": "brave",
                "result_count": len(results),
            },
        )
        return WebSearchResponse(
            query=normalized_query,
            provider="brave",
            retrieved_at=datetime.now(UTC),
            results=results,
        )
