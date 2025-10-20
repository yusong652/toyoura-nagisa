"""Path-based search strategy for exact API path matching.

This strategy handles queries that look like API paths (contain dots)
and attempts to match them exactly against the index.

Supports:
- Full paths: "itasca.ball.create"
- Partial paths: "Ball.vel"
- Contact types: "BallBallContact.gap" (with intelligent aliasing)
- Case-insensitive matching
"""

from typing import List
from backend.infrastructure.pfc.sdk.models import SearchResult, SearchStrategy as StrategyEnum
from backend.infrastructure.pfc.sdk.search.base import SearchStrategy
from backend.infrastructure.pfc.sdk.loader import DocumentationLoader
from backend.infrastructure.pfc.sdk.types.contact import ContactTypeResolver


class PathSearchStrategy(SearchStrategy):
    """Search by exact API path matching.

    This strategy is used when the query contains a dot character,
    indicating it's likely an API path (e.g., "itasca.ball.create").

    Features:
    - Exact path matching with case-insensitive fallback
    - Special handling for Contact types (maps aliases to shared interface)
    - High score (999) for exact matches
    """

    def can_handle(self, query: str) -> bool:
        """Path queries must contain a dot.

        Args:
            query: Search query string

        Returns:
            True if query contains '.' (path-like)

        Example:
            >>> strategy = PathSearchStrategy()
            >>> strategy.can_handle("itasca.ball.create")
            True
            >>> strategy.can_handle("create ball")
            False
        """
        return '.' in query.strip()

    def search(self, query: str, top_n: int = 3) -> List[SearchResult]:
        """Execute path-based search.

        Search priority:
        1. Check if query is a Contact type (special handling)
        2. Try exact path match (case-sensitive)
        3. Try case-insensitive match (user convenience)

        Args:
            query: API path string (e.g., "itasca.ball.create")
            top_n: Maximum number of results (ignored, path search returns 0 or 1)

        Returns:
            List with single SearchResult if found, empty list otherwise

        Example:
            >>> strategy = PathSearchStrategy()
            >>> results = strategy.search("BallBallContact.gap")
            >>> results[0].api_name
            "Contact.gap"
            >>> results[0].metadata["contact_type"]
            "BallBallContact"
        """
        query_stripped = query.strip()
        index = DocumentationLoader.load_index()
        quick_ref = index.get("quick_ref", {})

        # Strategy 1: Check Contact types first
        # Contact types need special handling to map official names to internal docs
        if ContactTypeResolver.is_contact_query(query_stripped):
            contact_result = ContactTypeResolver.resolve(query_stripped, quick_ref)
            if contact_result:
                return [SearchResult(
                    api_name=contact_result.internal_path,
                    score=999,  # Exact match score
                    strategy=StrategyEnum.PATH,
                    metadata={
                        "contact_type": contact_result.contact_type,
                        "original_query": contact_result.original_query,
                        "all_contact_types": contact_result.all_types
                    }
                )]

        # Strategy 2: Regular path lookup (exact match)
        if query_stripped in quick_ref:
            return [SearchResult(
                api_name=query_stripped,
                score=999,
                strategy=StrategyEnum.PATH,
                metadata=None
            )]

        # Strategy 3: Case-insensitive fallback
        # Helps users who don't remember exact casing
        query_lower = query_stripped.lower()
        for api_name in quick_ref.keys():
            if api_name.lower() == query_lower:
                return [SearchResult(
                    api_name=api_name,  # Return correctly-cased version
                    score=999,
                    strategy=StrategyEnum.PATH,
                    metadata=None
                )]

        return []
