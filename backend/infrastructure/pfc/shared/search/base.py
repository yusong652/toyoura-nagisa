"""Base search strategy interface.

This module defines the abstract base class for all search strategies,
ensuring a consistent interface across different search implementations.
"""

from abc import ABC, abstractmethod
from typing import List
from backend.infrastructure.pfc.shared.search.models import SearchResult


class SearchStrategy(ABC):
    """Abstract base class for search strategies.

    All search strategies must implement the search() and can_handle() methods.
    This allows the searcher orchestrator to dynamically select and compose
    strategies based on the query characteristics.
    """

    @abstractmethod
    def search(self, query: str, top_n: int = 3) -> List[SearchResult]:
        """Execute search with this strategy.

        Args:
            query: Search query string (path or natural language)
            top_n: Maximum number of results to return

        Returns:
            List of SearchResult objects sorted by score (highest first)

        Example:
            >>> strategy = PathSearchStrategy()
            >>> results = strategy.search("itasca.ball.create")
            >>> results[0].api_name
            "itasca.ball.create"
        """
        pass

    @abstractmethod
    def can_handle(self, query: str) -> bool:
        """Check if this strategy can handle the query.

        Args:
            query: Search query string

        Returns:
            True if this strategy is applicable to the query

        Example:
            >>> strategy = PathSearchStrategy()
            >>> strategy.can_handle("itasca.ball.create")
            True
            >>> strategy.can_handle("create a ball")
            False
        """
        pass
