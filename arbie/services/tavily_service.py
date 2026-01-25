"""Tavily API service for web research.

Provides web search capabilities for the Research Agent to find
regulatory and compliance information for short-term rentals.
"""

import os
import time
from dataclasses import dataclass, field

from tavily import TavilyClient


@dataclass
class SearchResult:
    """A single search result from Tavily."""

    title: str
    url: str
    content: str
    score: float
    raw_content: str | None = None


@dataclass
class SearchResponse:
    """Response from a Tavily search."""

    query: str
    answer: str | None
    results: list[SearchResult] = field(default_factory=list)
    response_time: float = 0.0


class TavilyService:
    """Tavily API wrapper with retry support.

    Provides web search for compliance research with exponential
    backoff retry logic.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize the Tavily service.

        Args:
            api_key: Tavily API key. If not provided, reads from
                     TAVILY_API_KEY environment variable.
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Tavily API key required. Set TAVILY_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self._client: TavilyClient | None = None

    @property
    def client(self) -> TavilyClient:
        """Get or create the Tavily client."""
        if self._client is None:
            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def search(
        self,
        query: str,
        search_depth: str = "advanced",
        max_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        include_answer: bool = True,
    ) -> SearchResponse:
        """Search the web using Tavily.

        Args:
            query: Search query string
            search_depth: "basic" or "advanced" (more thorough)
            max_results: Number of results (1-10)
            include_domains: Limit search to these domains
            exclude_domains: Exclude these domains from search
            include_answer: Whether to include AI-generated answer

        Returns:
            SearchResponse with results and optional answer
        """
        start_time = time.time()

        # Build search parameters
        kwargs = {
            "query": query,
            "search_depth": search_depth,
            "max_results": min(max(1, max_results), 10),
            "include_answer": include_answer,
        }

        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains

        # Execute search
        response = self.client.search(**kwargs)

        # Parse results
        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                raw_content=r.get("raw_content"),
            )
            for r in response.get("results", [])
        ]

        return SearchResponse(
            query=query,
            answer=response.get("answer"),
            results=results,
            response_time=time.time() - start_time,
        )

    def search_with_retry(
        self,
        query: str,
        max_retries: int = 2,
        base_delay: float = 1.0,
        **kwargs,
    ) -> SearchResponse:
        """Search with exponential backoff retry.

        Args:
            query: Search query string
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds (doubles each retry)
            **kwargs: Additional arguments passed to search()

        Returns:
            SearchResponse with results

        Raises:
            Exception: If all retries fail
        """
        last_error = None
        delay = base_delay

        for attempt in range(max_retries + 1):
            try:
                return self.search(query, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff

        raise last_error


# Singleton instance
_tavily_service: TavilyService | None = None


def get_tavily_service() -> TavilyService:
    """Get the singleton Tavily service instance."""
    global _tavily_service
    if _tavily_service is None:
        _tavily_service = TavilyService()
    return _tavily_service
