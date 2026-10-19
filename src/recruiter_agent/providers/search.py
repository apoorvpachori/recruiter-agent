"""Provider-neutral interface for public web search."""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class SearchResult(BaseModel):
    """One source returned by a web search provider."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: HttpUrl
    snippet: str
    published_at: str | None = None


class WebSearchResponse(BaseModel):
    """Bounded search response with retrieval timestamp and provider name."""

    model_config = ConfigDict(extra="forbid")

    query: str
    provider: str
    retrieved_at: datetime
    results: list[SearchResult]


class WebSearchProvider(ABC):
    """Interface allowing search vendors to be swapped independently."""

    @abstractmethod
    def search(self, query: str, *, max_results: int = 5) -> WebSearchResponse:
        """Search the public web and return bounded, cited results."""
