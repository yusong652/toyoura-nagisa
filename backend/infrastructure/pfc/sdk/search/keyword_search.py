"""Keyword-based search strategy for natural language queries.

This strategy handles natural language queries by matching keywords
from the query against a pre-built keyword index.

Matching Algorithm:
- Flexible word matching: all keyword words must appear in query
- Score based on number of matching words
- Returns top-N results sorted by score
"""

from typing import List
from backend.infrastructure.pfc.sdk.models import SearchResult, SearchStrategy as StrategyEnum
from backend.infrastructure.pfc.sdk.search.base import SearchStrategy
from backend.infrastructure.pfc.sdk.loader import DocumentationLoader


class KeywordSearchStrategy(SearchStrategy):
    """Search by natural language keywords.

    This strategy uses a keyword index to find APIs based on natural
    language descriptions. It's the fallback strategy when path matching fails.

    Features:
    - Flexible word matching (all keyword words must be in query)
    - Score based on word overlap count
    - Returns top-N unique results
    """

    def can_handle(self, query: str) -> bool:
        """Keyword search can handle any query.

        This is the fallback strategy, so it always returns True.

        Args:
            query: Search query string

        Returns:
            True (always)

        Example:
            >>> strategy = KeywordSearchStrategy()
            >>> strategy.can_handle("create a ball")
            True
            >>> strategy.can_handle("anything")
            True
        """
        return True

    def search(self, query: str, top_n: int = 3) -> List[SearchResult]:
        """Execute keyword-based search with flexible word matching.

        Algorithm:
        1. Split query and keywords into word sets
        2. Calculate overlap between query words and keyword words
        3. Match if all keyword words are present in query
        4. Score = number of matching words
        5. Return top-N unique results sorted by score

        Args:
            query: Natural language query (e.g., "create a ball")
            top_n: Maximum number of results to return

        Returns:
            List of SearchResult objects sorted by score (highest first)

        Example:
            >>> strategy = KeywordSearchStrategy()
            >>> results = strategy.search("create a ball", top_n=3)
            >>> results[0].api_name
            "itasca.ball.create"
            >>> results[0].score
            2
        """
        keywords = DocumentationLoader.load_all_keywords()
        query_lower = query.lower()
        query_words = set(query_lower.split())

        matches = []  # List of (api_name, score) tuples

        # Match each keyword against query
        for keyword, apis in keywords.items():
            keyword_words = set(keyword.split())
            # Calculate how many keyword words match
            matching_words = keyword_words & query_words
            score = len(matching_words)

            # All keyword words must be in query for a valid match
            if matching_words == keyword_words and score > 0:
                # Add all APIs associated with this keyword
                for api_name in apis:
                    matches.append((api_name, score))

        # Sort by score (descending), then by API name (for stability)
        matches.sort(key=lambda x: (-x[1], x[0]))

        # Return top-N unique matches
        seen = set()
        results = []
        for api_name, score in matches:
            if api_name not in seen:
                seen.add(api_name)
                results.append(SearchResult(
                    api_name=api_name,
                    score=score,
                    strategy=StrategyEnum.KEYWORD,
                    metadata=None
                ))
                if len(results) >= top_n:
                    break

        return results
