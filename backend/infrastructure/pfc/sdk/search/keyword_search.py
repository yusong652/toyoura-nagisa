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
        index = DocumentationLoader.load_index()
        quick_ref = index.get("quick_ref", {})

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
            partial_matches, _ = self._find_partial_matches(unmatched_query, unmatched_keyword)

            # Match if there's either exact or partial overlap
            if len(matching_words) > 0 or len(partial_matches) > 0:
                # Calculate multi-factor score (includes partial matching)
                score = self._calculate_relevance_score(
                    keyword_words,
                    query_words,
                    matching_words
                )

                # Add all APIs associated with this keyword
                # Resolve short paths (Ball.pos) to full paths (itasca.ball.Ball.pos)
                for api_name in apis:
                    resolved_path = self._resolve_api_path(api_name, quick_ref)
                    matches.append((resolved_path, score))

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

    def _calculate_relevance_score(
        self,
        keyword_words: set,
        query_words: set,
        matching_words: set
    ) -> int:
        """Calculate relevance score using multi-factor ranking with partial matching.

        Scoring factors (inspired by BM25):
        1. Keyword coverage: How much of the keyword is covered by the query
           - Includes both exact matches and partial matches (abbreviations)
        2. Query precision: How focused is the match (fewer extra words = better)
        3. Match count: Absolute number of matching words (tie-breaker)

        Args:
            keyword_words: Set of words in the keyword
            query_words: Set of words in the query
            matching_words: Set of overlapping words (exact matches)

        Returns:
            Integer score (higher = more relevant)

        Example:
            >>> # Query: "pos" (1 word)
            >>> # Keyword: "ball position" (2 words)
            >>> # Exact matching: {} (0 words)
            >>> # Partial matching: "pos" → "position" (prefix, quality=0.8)
            >>> # Coverage: 0.8 / 2 = 40%
            >>> # Score: 400 + precision + matches ≈ 450-500
        """
        # Calculate exact and partial matches
        exact_matches = matching_words
        partial_matches, partial_quality = self._find_partial_matches(
            query_words - exact_matches,
            keyword_words - exact_matches
        )

        # Calculate effective coverage including partial matches
        # Partial matches contribute based on their quality (0.6-0.8 weight)
        exact_match_contribution = len(exact_matches)
        partial_match_contribution = len(partial_matches) * partial_quality

        total_match_value = exact_match_contribution + partial_match_contribution

        # Factor 1: Keyword coverage (primary factor, 0-1000 points)
        # How much of the keyword is covered by the query (exact + partial)
        keyword_coverage = total_match_value / len(keyword_words)

        # Factor 2: Query precision (secondary factor, 0-100 points)
        # Penalize queries with many irrelevant words
        # Partial matches count as 0.5 for precision (less precise than exact)
        effective_query_matches = len(exact_matches) + len(partial_matches) * 0.5
        query_precision = effective_query_matches / len(query_words)

        # Factor 3: Match count (tie-breaker, 1-10 points)
        # Exact matches worth more than partial matches
        match_count = len(exact_matches) * 2 + len(partial_matches)

        # Combined score (weighted sum)
        score = int(
            keyword_coverage * 1000 +  # Primary: complete matches rank highest
            query_precision * 100 +     # Secondary: focused queries rank higher
            match_count                 # Tie-breaker: exact matches > partial
        )

        return score

    def _find_partial_matches(
        self,
        unmatched_query_words: set,
        unmatched_keyword_words: set
    ) -> tuple:
        """Find partial matches between unmatched query and keyword words.

        Uses the same logic as PathSearchStrategy for consistency:
        - Prefix matching (minimum 3 chars): quality 0.8
        - Substring matching: quality 0.6

        Args:
            unmatched_query_words: Query words that didn't exact-match
            unmatched_keyword_words: Keyword words that didn't exact-match

        Returns:
            (partial_matches, avg_quality) where:
            - partial_matches: set of (query_word, keyword_word) pairs
            - avg_quality: average match quality (0.0-1.0)

        Example:
            >>> unmatched_query = {"pos", "vel"}
            >>> unmatched_keyword = {"position", "velocity"}
            >>> matches, quality = self._find_partial_matches(
            ...     unmatched_query, unmatched_keyword
            ... )
            >>> matches
            {('pos', 'position'), ('vel', 'velocity')}
            >>> quality
            0.8  # Both are prefix matches
        """
        partial_matches = set()
        quality_scores = []

        for q_word in unmatched_query_words:
            best_match = None
            best_quality = 0

            for k_word in unmatched_keyword_words:
                quality = self._word_match_quality(q_word, k_word)

                if quality > best_quality:
                    best_quality = quality
                    best_match = k_word

            # Only accept matches with quality >= 0.6 (substring match minimum)
            if best_match and best_quality >= 0.6:
                partial_matches.add((q_word, best_match))
                quality_scores.append(best_quality)

        # Calculate average quality
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

        return partial_matches, avg_quality

    def _word_match_quality(self, query_word: str, keyword_word: str) -> float:
        """Calculate match quality between two words.

        Uses the same scoring logic as PathSearchStrategy._calculate_attr_match_score
        for consistency across the search system.

        Scoring rules:
        - Exact match: 1.0 (shouldn't happen, handled by exact matching)
        - Prefix match (3+ chars): 0.8
        - Substring match: 0.6
        - No match: 0.0

        Args:
            query_word: Word from query (lowercase)
            keyword_word: Word from keyword (lowercase)

        Returns:
            Match quality score (0.0-1.0)

        Example:
            >>> self._word_match_quality("pos", "position")
            0.8  # "pos" is prefix of "position"
            >>> self._word_match_quality("vel", "velocity")
            0.8  # "vel" is prefix of "velocity"
            >>> self._word_match_quality("norm", "normal")
            0.8  # "norm" is prefix of "normal"
            >>> self._word_match_quality("xyz", "position")
            0.0  # No match
        """
        if query_word == keyword_word:
            return 1.0  # Exact match (shouldn't happen)

        # Prefix matching (minimum 3 chars to avoid false positives like "a", "an")
        min_prefix_len = 3
        if len(query_word) >= min_prefix_len and len(keyword_word) >= min_prefix_len:
            # Check if one is prefix of the other
            if keyword_word.startswith(query_word) or query_word.startswith(keyword_word):
                return 0.8

        # Substring matching (one is contained in the other)
        if query_word in keyword_word or keyword_word in query_word:
            return 0.6

        return 0.0

    def _resolve_api_path(self, api_name: str, quick_ref: dict) -> str:
        """Resolve short API paths to full paths using the index.

        Keywords may contain short paths (e.g., "Ball.pos", "Contact.gap")
        that need to be resolved to full official paths found in the index.

        Resolution strategy:
        1. If api_name exists in quick_ref, return as-is (already full path)
        2. If not, search quick_ref for matching full path:
           - For object methods: "Ball.pos" → "itasca.ball.Ball.pos"
           - For Contact types: "Contact.gap" → "itasca.BallBallContact.gap" (any variant)
           - For module functions: usually already full, return as-is

        Args:
            api_name: API name from keywords (may be short or full path)
            quick_ref: Index of available API paths

        Returns:
            Full API path if found in index, otherwise original api_name

        Example:
            >>> self._resolve_api_path("Ball.pos", quick_ref)
            "itasca.ball.Ball.pos"
            >>> self._resolve_api_path("Contact.gap", quick_ref)
            "itasca.BallBallContact.gap"
            >>> self._resolve_api_path("itasca.ball.create", quick_ref)
            "itasca.ball.create"  # Already full path
        """
        # Case 1: Already a full path in index
        if api_name in quick_ref:
            return api_name

        # Case 2: Short path - need to find full path in index
        # Parse into parts for matching
        if '.' not in api_name:
            # Single word, not a path - return as-is
            return api_name

        parts = api_name.split('.')
        if len(parts) < 2:
            return api_name

        # Try to find matching full path in quick_ref
        # Match pattern: index key ends with the short path
        # Example: "Ball.pos" matches "itasca.ball.Ball.pos"
        #          "Contact.gap" matches "itasca.BallBallContact.gap"

        # Strategy 1: Exact suffix match (case-insensitive)
        api_name_lower = api_name.lower()
        for full_path in quick_ref.keys():
            full_path_lower = full_path.lower()

            # Check if full_path ends with api_name pattern
            # "itasca.ball.Ball.pos" should match "Ball.pos"
            full_parts = full_path_lower.split('.')

            # Match last N parts where N = len(parts)
            if len(full_parts) >= len(parts):
                # Compare last N parts
                if '.'.join(full_parts[-len(parts):]) == api_name_lower:
                    return full_path

        # Strategy 2: Contact type special handling
        # "Contact.gap" should match any "itasca.*Contact.gap"
        if parts[0].lower() == 'contact':
            method_name = parts[-1]
            for full_path in quick_ref.keys():
                if full_path.lower().endswith(f"contact.{method_name.lower()}"):
                    # Return first matching Contact type variant
                    return full_path

        # Not found - return original (may cause downstream error, but preserves debugging info)
        return api_name
