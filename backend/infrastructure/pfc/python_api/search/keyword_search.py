"""Keyword-based search strategy for natural language queries.

This strategy handles natural language queries by matching keywords
from the query against a pre-built keyword index using unified search algorithms.

Matching Algorithm (shared with command search):
- BM25-inspired multi-factor scoring
- Partial matching support (abbreviations like "pos" → "position")
- Score based on keyword coverage + query precision + match count
- Returns top-N results sorted by score
"""

from typing import List, Dict, Set, Optional
from backend.infrastructure.pfc.shared.search.models import SearchResult, DocumentType, SearchStrategy as SearchStrategyEnum
from backend.infrastructure.pfc.shared.search.base import SearchStrategy
from backend.infrastructure.pfc.shared.search.keyword_matcher import (
    calculate_relevance_score,
    find_partial_matches,
    word_match_quality
)
from backend.infrastructure.pfc.python_api.loader import DocumentationLoader
from backend.infrastructure.pfc.python_api.types.contact import CONTACT_TYPES

# Backward compatibility alias
StrategyEnum = SearchStrategyEnum


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
        """Execute keyword-based search with partial matching and smart scoring.

        Algorithm (inspired by BM25 principles):
        1. Split query and keywords into word sets
        2. Calculate word overlap between query and keywords
        3. Match if any words overlap (partial matching)
        4. Score based on:
           - Keyword coverage (primary): How much of the keyword is covered
           - Query precision (secondary): How focused is the match
           - Match count (tie-breaker): Absolute number of matching words
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
            >>> results[0].score >= 1000  # Complete match gets high score
            True
        """
        keywords = DocumentationLoader.load_all_keywords()
        query_lower = query.lower()
        query_words = set(query_lower.split())

        matches = []  # List of (api_name, score) tuples

        # Match each keyword against query
        for keyword, apis in keywords.items():
            keyword_words = set(keyword.split())
            matching_words = keyword_words & query_words

            # Calculate potential partial matches first
            # This allows queries like "pos" to match keywords like "ball position"
            unmatched_query = query_words - matching_words
            unmatched_keyword = keyword_words - matching_words
            partial_matches, _ = find_partial_matches(unmatched_query, unmatched_keyword)

            # Match if there's either exact or partial overlap
            if len(matching_words) > 0 or len(partial_matches) > 0:
                # Calculate multi-factor score using shared algorithm
                score = calculate_relevance_score(
                    keyword_words,
                    query_words,
                    matching_words
                )

                # Add all APIs associated with this keyword
                # (keywords now use complete paths from keywords.json)
                for api_name in apis:
                    matches.append((api_name, score))

        # Sort by score (descending), then by API name (for stability)
        matches.sort(key=lambda x: (-x[1], x[0]))

        # Deduplicate with Contact type grouping
        results = self._deduplicate_with_contact_grouping(matches, top_n)

        return results

    def _deduplicate_with_contact_grouping(
        self,
        matches: List[tuple],
        top_n: int
    ) -> List[SearchResult]:
        """Deduplicate results with intelligent Contact type grouping.

        For Contact APIs (BallBallContact, BallFacetContact, etc.), group all
        Contact types that share the same method into a single SearchResult.

        Args:
            matches: List of (api_name, score) tuples
            top_n: Maximum number of results to return

        Returns:
            List of SearchResult objects with Contact types properly grouped

        Example:
            Input matches:
                [("itasca.BallBallContact.force_global", 1070),
                 ("itasca.BallFacetContact.force_global", 1070),
                 ("itasca.ball.create", 1000)]

            Output results:
                [SearchResult(
                    api_name="itasca.BallBallContact.force_global",
                    score=1070,
                    metadata={
                        "all_contact_types": ["BallBallContact", "BallFacetContact", ...],
                        "contact_method": "force_global"
                    }
                ),
                SearchResult(
                    api_name="itasca.ball.create",
                    score=1000,
                    metadata=None
                )]
        """
        seen_apis = set()  # Track non-Contact APIs
        contact_methods: Dict[str, Dict] = {}  # Track Contact methods: {method_name: {...}}
        results = []

        for api_name, score in matches:
            # Check if this is a Contact API
            contact_info = self._extract_contact_info(api_name)

            if contact_info:
                # This is a Contact API
                method_name = contact_info["method"]

                if method_name not in contact_methods:
                    # First time seeing this Contact method
                    contact_methods[method_name] = {
                        "api_name": api_name,  # Use first Contact type's path
                        "score": score,
                        "contact_types": set([contact_info["contact_type"]])  # Use set to avoid duplicates
                    }
                else:
                    # Add this Contact type to the existing group (set handles deduplication)
                    contact_methods[method_name]["contact_types"].add(
                        contact_info["contact_type"]
                    )
            else:
                # Regular API (non-Contact)
                if api_name not in seen_apis:
                    seen_apis.add(api_name)
                    results.append(SearchResult(
                        name=api_name,
                        score=score,
                        doc_type=DocumentType.API,
                        category=self._extract_category(api_name),
                        strategy=StrategyEnum.KEYWORD,
                        metadata=None
                    ))

        # Add Contact methods to results
        for method_name, info in contact_methods.items():
            results.append(SearchResult(
                name=info["api_name"],
                score=info["score"],
                doc_type=DocumentType.API,
                category=self._extract_category(info["api_name"]),
                strategy=StrategyEnum.KEYWORD,
                metadata={
                    "all_contact_types": sorted(list(info["contact_types"])),  # Convert set to sorted list
                    "contact_method": method_name
                }
            ))

        # Sort by score (descending) to maintain score-based ordering
        results.sort(key=lambda r: -r.score)

        # Return top-N
        return results[:top_n]

    def _extract_contact_info(self, api_name: str) -> Optional[Dict[str, str]]:
        """Extract Contact type and method name from API path.

        Args:
            api_name: Full API path (e.g., "itasca.BallBallContact.force_global")

        Returns:
            Dict with "contact_type" and "method" if this is a Contact API,
            None otherwise

        Example:
            >>> self._extract_contact_info("itasca.BallBallContact.force_global")
            {"contact_type": "BallBallContact", "method": "force_global"}
            >>> self._extract_contact_info("itasca.ball.create")
            None
        """
        parts = api_name.split('.')

        # Check each part for Contact type match
        for i, part in enumerate(parts):
            if part in CONTACT_TYPES:
                # Found a Contact type
                # Method name should be the next part
                if i + 1 < len(parts):
                    return {
                        "contact_type": part,
                        "method": parts[i + 1]
                    }

        return None

    def _extract_category(self, api_name: str) -> str:
        """Extract category from API name.

        Args:
            api_name: Full API path (e.g., "itasca.ball.create", "itasca.BallBallContact.force_global")

        Returns:
            Category name (e.g., "ball", "contact")

        Example:
            >>> self._extract_category("itasca.ball.create")
            "ball"
            >>> self._extract_category("itasca.BallBallContact.force_global")
            "contact"
        """
        parts = api_name.split('.')

        # Check if any part is a Contact type
        for part in parts:
            if part in CONTACT_TYPES:
                return "contact"

        # Otherwise use the module name (second part if starts with "itasca.")
        if len(parts) >= 2 and parts[0] == "itasca":
            return parts[1].lower()

        # Fallback
        return "unknown"
