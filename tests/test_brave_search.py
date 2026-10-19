import httpx
import pytest

from recruiter_agent.agent.tools import search_company_web
from recruiter_agent.providers.brave_search import BraveSearchProvider
from recruiter_agent.settings import Settings


def test_brave_search_returns_bounded_cited_results(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_get(url: str, *, headers: dict, params: dict, timeout: float) -> httpx.Response:
        captured.update(url=url, headers=headers, params=params, timeout=timeout)
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "grounding": {
                    "generic": [
                        {
                            "title": "Company funding",
                            "url": "https://example.com/funding",
                            "snippets": ["Company raised a Series B."],
                        }
                    ]
                },
                "sources": {
                    "https://example.com/funding": {
                        "title": "Company funding",
                        "hostname": "example.com",
                        "age": ["Monday, January 1, 2026", "2026-01-01", "recent"],
                    }
                },
            },
        )

    monkeypatch.setattr("recruiter_agent.providers.brave_search.httpx.get", fake_get)
    provider = BraveSearchProvider(
        Settings(brave_search_api_key="test-key", brave_search_endpoint="https://search.test/web")
    )

    result = provider.search("Example company funding", max_results=3)

    assert result.provider == "brave"
    assert str(result.results[0].url) == "https://example.com/funding"
    assert result.results[0].published_at == "Monday, January 1, 2026"
    assert captured["headers"]["X-Subscription-Token"] == "test-key"
    assert captured["params"]["count"] == 3
    assert captured["params"]["q"] == "Example company funding"
    assert captured["url"] == "https://search.test/web"
    assert captured["params"]["maximum_number_of_tokens"] == 2048


def test_brave_search_requires_key() -> None:
    provider = BraveSearchProvider(Settings(brave_search_api_key=None))

    with pytest.raises(RuntimeError, match="BRAVE_SEARCH_API_KEY"):
        provider.search("Example company funding")


@pytest.mark.parametrize("query", ["", "  ", "x" * 401])
def test_brave_search_validates_query(query: str) -> None:
    provider = BraveSearchProvider(Settings(brave_search_api_key="test-key"))

    with pytest.raises(ValueError):
        provider.search(query)


def test_search_tool_returns_safe_error_on_provider_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_search(query: str, *, max_results: int = 5):
        request = httpx.Request("POST", "https://api.search.brave.com/test")
        response = httpx.Response(422, request=request)
        raise httpx.HTTPStatusError("provider rejected query", request=request, response=response)

    monkeypatch.setattr("recruiter_agent.agent.tools._web_search_provider.search", fail_search)

    result = search_company_web.invoke({"query": "company defense contract research"})

    assert result["ok"] is False
    assert result["provider"] == "brave"
    assert result["results"] == []
    assert "HTTPStatusError" in result["error"]
