"""High-level search orchestrator for PFC SDK APIs.

This module coordinates multiple search strategies and provides
a unified search interface. It implements the Strategy pattern
to dynamically select the appropriate search approach.

Architecture:
    APISearcher orchestrates strategies in priority order:
    1. PathSearchStrategy (exact path matching)
    2. KeywordSearchStrategy (natural language)
    3. Future: SemanticSearchStrategy (embedding-based)
"""

from typing import List, Optional
from backend.infrastructure.pfc.python_api.models import SearchResult, SearchStrategy
from backend.infrastructure.pfc.python_api.search.path_search import PathSearchStrategy
from backend.infrastructure.pfc.python_api.search.keyword_search import KeywordSearchStrategy


class APISearcher:
    """Orchestrates multiple search strategies.

    This class implements the Strategy pattern, trying different search
    approaches in priority order until results are found.

    The orchestrator is designed for extensibility - new strategies can
    be added without modifying existing code.
    """

    def __init__(self):
        """Initialize with available search strategies.

        Strategies are tried in the order they appear in the list:
        1. PathSearchStrategy: For dot-separated paths
        2. KeywordSearchStrategy: For natural language
        """
        self.strategies = [
            PathSearchStrategy(),      # Try exact path first
            KeywordSearchStrategy(),   # Fall back to keywords
            # Future: SemanticSearchStrategy() for embedding-based search
        ]

    def search(self, query: str, top_n: int = 3) -> List[SearchResult]:
        """Smart API search with automatic strategy selection.

        Tries strategies in order until results are found:
        1. Module path matching (if query looks like module path)
        2. Path matching (if query contains '.')
        3. Keyword matching (always available)

        Args:
            query: Either an API path or natural language query
                   Examples:
                   - "itasca.ball" (module path)
                   - "itasca.ball.create" (function path)
                   - "BallBallContact.gap" (path with Contact type)
                   - "create ball" (natural language)
                   - "measure count" (natural language)
            top_n: Maximum number of results to return (default: 3)

        Returns:
            List of SearchResult objects sorted by score (highest first)
            Empty list if no matches found

        Example:
            >>> searcher = APISearcher()
            >>> results = searcher.search("itasca.ball.create")
            >>> results[0].api_name
            "itasca.ball.create"
            >>> results[0].score
            999
            >>> results[0].strategy
            SearchStrategy.PATH

            >>> results = searcher.search("itasca.ball")
            >>> results[0].api_name
            "itasca.ball"
            >>> results[0].metadata["type"]
            "module"
        """
        # Priority 0: Check if query is a module path
        # This check happens before strategies to avoid partial path matching
        if query.strip().startswith("itasca."):
            module_result = self._check_module_path(query.strip())
            if module_result:
                return [module_result]

        # Priority 1-N: Try each strategy in order
        for strategy in self.strategies:
            # Check if this strategy can handle the query
            if strategy.can_handle(query):
                results = strategy.search(query, top_n)
                # If we found results, return immediately
                if results:
                    return results

        # No strategy found any results
        return []

    def _check_module_path(self, query: str) -> Optional[SearchResult]:
        """Check if query matches a module path exactly.

        Args:
            query: Query string (must start with "itasca.")

        Returns:
            SearchResult for module if found, None otherwise

        Example:
            >>> self._check_module_path("itasca.ball")
            SearchResult(api_name="itasca.ball", score=999, ...)
        """
        from backend.infrastructure.pfc.python_api.loader import DocumentationLoader

        # Try to load as module
        doc = DocumentationLoader.load_api_doc(query)

        if doc and doc.get("type") == "module":
            return SearchResult(
                api_name=query,
                score=999,  # Exact match score
                strategy=SearchStrategy.PATH,
                metadata={"type": "module"}
            )

        return None

    def add_strategy(self, strategy):
        """Add a new search strategy to the orchestrator.

        This method allows dynamic extension of search capabilities
        without modifying the core class.

        Args:
            strategy: Instance of SearchStrategy subclass

        Example:
            >>> searcher = APISearcher()
            >>> semantic_strategy = SemanticSearchStrategy()
            >>> searcher.add_strategy(semantic_strategy)
        """
        self.strategies.append(strategy)
